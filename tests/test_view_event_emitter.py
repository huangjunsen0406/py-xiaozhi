"""Non-Qt view event submission preserves task ownership and thread safety."""

import asyncio
import inspect
import logging
import threading
from concurrent.futures import Future
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.ui.cli.manager import CliViewManager
from src.ui.gpio.manager import GpioViewManager
from src.ui.shared import event_emitter
from src.ui.tui.manager import TuiViewManager


@pytest.fixture(params=[CliViewManager, TuiViewManager, GpioViewManager])
def view_factory(request, monkeypatch):
    # Constructors must not intercept pytest logging or probe physical GPIO.
    monkeypatch.setattr(
        "src.ui.cli.manager.CLIDisplay.intercept_logging", lambda _: None
    )
    monkeypatch.setattr("src.ui.gpio.manager.GPIOInput", Mock())
    return request.param


def call_from_worker(callback):
    errors = []

    def run():
        try:
            callback()
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    # Keep the loop occupied: submitting must not wait for the loop to advance.
    thread.join(timeout=1)
    assert not thread.is_alive(), "event submission blocked the worker thread"
    assert not errors


@pytest.mark.asyncio
@pytest.mark.parametrize("worker", [False, True])
@pytest.mark.parametrize("payload", [None, {"text": "hello"}])
async def test_managers_schedule_lazy_emit_on_owner_loop(view_factory, worker, payload):
    bus = EventBus()
    tasks = TaskManager()
    tasks.initialize()
    tasks.schedule_nowait = Mock(wraps=tasks.schedule_nowait)
    bus.emit = Mock(wraps=bus.emit)
    view = view_factory(bus, tasks)
    delivered = asyncio.Event()
    owner_thread = threading.get_ident()
    seen = []

    async def handler(data=None):
        seen.append((data, threading.get_ident()))
        delivered.set()

    bus.on(Events.UI_SEND_TEXT, handler)
    try:

        def submit():
            view._safe_emit(Events.UI_SEND_TEXT, payload)

        if worker:
            call_from_worker(submit)
        else:
            submit()
        tasks.schedule_nowait.assert_called_once()
        factory = tasks.schedule_nowait.call_args.args[0]
        assert callable(factory) and not inspect.iscoroutine(factory)
        bus.emit.assert_not_called()
        await asyncio.wait_for(delivered.wait(), timeout=1)
        assert seen == [(payload, owner_thread)]
        expected = (
            (Events.UI_SEND_TEXT,)
            if payload is None
            else (Events.UI_SEND_TEXT, payload)
        )
        bus.emit.assert_called_once_with(*expected)
    finally:
        await tasks.cancel_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["uninitialized", "shutdown", "cancelled"])
async def test_task_manager_rejection_never_uses_loop_fallback(
    view_factory, state, monkeypatch
):
    tasks = TaskManager()
    if state != "uninitialized":
        tasks.initialize()
        if state == "shutdown":
            tasks.request_shutdown()
        else:
            await tasks.cancel_all()
    bus = SimpleNamespace(emit=Mock())
    view = view_factory(bus, tasks)
    view._loop = asyncio.get_running_loop()
    fallback = Mock()
    monkeypatch.setattr(event_emitter.asyncio, "run_coroutine_threadsafe", fallback)
    call_from_worker(lambda: view._safe_emit(Events.UI_QUIT_REQUEST))
    await asyncio.sleep(0)
    fallback.assert_not_called()
    bus.emit.assert_not_called()
    await tasks.cancel_all()


@pytest.mark.parametrize("state", ["absent", "stopped", "closed"])
def test_no_running_loop_does_not_create_coroutine(view_factory, state):
    bus = SimpleNamespace(emit=Mock())
    view = view_factory(bus)
    loop = None if state == "absent" else asyncio.new_event_loop()
    if state == "closed":
        loop.close()
    view._loop = loop
    try:
        view._safe_emit(Events.UI_SEND_TEXT, {"text": "ignored"})
        bus.emit.assert_not_called()
    finally:
        if loop is not None:
            loop.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("worker", [False, True])
@pytest.mark.parametrize("broken_tasks", [False, True])
async def test_managers_fallback_delivers_on_view_loop(
    view_factory, worker, broken_tasks, caplog
):
    bus = EventBus()
    tasks = (
        SimpleNamespace(schedule_nowait=Mock(side_effect=RuntimeError("submit failed")))
        if broken_tasks
        else None
    )
    view = view_factory(bus, tasks)
    view._loop = asyncio.get_running_loop()
    delivered = asyncio.Event()
    seen = []
    owner_thread = threading.get_ident()

    async def handler(data):
        seen.append((data, threading.get_ident()))
        delivered.set()

    bus.on(Events.UI_SEND_TEXT, handler)
    with caplog.at_level(logging.ERROR):

        def submit():
            view._safe_emit(Events.UI_SEND_TEXT, {"text": "fallback"})

        if worker:
            call_from_worker(submit)
        else:
            submit()
        await asyncio.wait_for(delivered.wait(), timeout=1)
    assert seen == [({"text": "fallback"}, owner_thread)]
    if broken_tasks:
        record = next(r for r in caplog.records if "submit failed" in r.getMessage())
        assert record.exc_info[0] is RuntimeError


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [False, True])
async def test_emit_failures_are_observed_with_traceback(managed, monkeypatch, caplog):
    tasks = TaskManager() if managed else None
    if tasks is not None:
        tasks.initialize()
    completed = asyncio.Event()
    real_error = RuntimeError("event emission failed")

    async def fail(event):
        completed.set()
        raise real_error

    futures = []
    submit = asyncio.run_coroutine_threadsafe

    def capture(coro, loop):
        future = submit(coro, loop)
        futures.append(future)
        return future

    monkeypatch.setattr(event_emitter.asyncio, "run_coroutine_threadsafe", capture)
    try:
        with caplog.at_level(logging.ERROR):
            event_emitter.safe_emit(
                SimpleNamespace(emit=fail),
                Events.UI_ABORT_REQUEST,
                task_manager=tasks,
                loop=asyncio.get_running_loop(),
                source="TestView",
            )
            await asyncio.wait_for(completed.wait(), timeout=1)
            if futures:
                with pytest.raises(RuntimeError, match="event emission failed"):
                    await asyncio.wrap_future(futures[0])
            await asyncio.sleep(0)
        record = next(
            r for r in caplog.records if "event emission failed" in r.getMessage()
        )
        assert record.exc_info[1] is real_error
        assert record.exc_info[2] is not None
    finally:
        if tasks is not None:
            await tasks.cancel_all()


@pytest.mark.asyncio
async def test_failed_loop_submission_closes_created_coroutine(monkeypatch, caplog):
    coroutines = []

    async def emit(event):
        raise AssertionError("must never run")

    def create(event):
        coro = emit(event)
        coroutines.append(coro)
        return coro

    monkeypatch.setattr(
        event_emitter.asyncio,
        "run_coroutine_threadsafe",
        Mock(side_effect=RuntimeError("loop closed during submission")),
    )
    with caplog.at_level(logging.ERROR):
        event_emitter.safe_emit(
            SimpleNamespace(emit=create),
            Events.UI_ABORT_REQUEST,
            loop=asyncio.get_running_loop(),
        )
    assert len(coroutines) == 1
    assert inspect.getcoroutinestate(coroutines[0]) == inspect.CORO_CLOSED
    assert any(
        "loop closed during submission" in r.getMessage() for r in caplog.records
    )


@pytest.mark.asyncio
async def test_fallback_coroutine_factory_error_is_logged(caplog):
    with caplog.at_level(logging.ERROR):
        event_emitter.safe_emit(
            SimpleNamespace(emit=Mock(side_effect=ValueError("factory failed"))),
            Events.UI_ABORT_REQUEST,
            loop=asyncio.get_running_loop(),
        )
    record = next(r for r in caplog.records if "factory failed" in r.getMessage())
    assert record.exc_info[0] is ValueError


@pytest.mark.asyncio
async def test_cancelled_fallback_future_is_normal_shutdown(monkeypatch, caplog):
    def cancel(coro, loop):
        coro.close()
        future = Future()
        future.cancel()
        return future

    monkeypatch.setattr(event_emitter.asyncio, "run_coroutine_threadsafe", cancel)
    with caplog.at_level(logging.ERROR):
        event_emitter.safe_emit(
            EventBus(), Events.UI_ABORT_REQUEST, loop=asyncio.get_running_loop()
        )
    assert not caplog.records


def test_cli_retains_display_state_and_gpio_key1_retains_mode(monkeypatch):
    monkeypatch.setattr(
        "src.ui.cli.manager.CLIDisplay.intercept_logging", lambda _: None
    )
    monkeypatch.setattr("src.ui.gpio.manager.GPIOInput", Mock())
    cli = CliViewManager(EventBus())
    cli.set_status("ready", False)
    cli.set_chat_text("first")
    cli.set_music_line("lyrics")
    cli.set_chat_text("second")
    cli.set_auto_mode(True)
    assert cli._display._dash_status == "ready"
    assert cli._display._dash_connected is False
    assert cli._display._dash_text == "second"
    assert cli._display._dash_music == "lyrics"
    assert cli._display._dash_auto_mode is True

    gpio = GpioViewManager(EventBus())
    gpio._safe_emit = Mock()
    gpio.set_auto_mode(True)
    gpio._on_key1()
    gpio._safe_emit.assert_called_once_with(Events.UI_AUTO_START)
    gpio._safe_emit.reset_mock()
    gpio.set_auto_mode(False)
    gpio._on_key1()
    gpio._safe_emit.assert_called_once_with(Events.UI_MANUAL_TOGGLE)


@pytest.mark.asyncio
async def test_tui_replays_updates_received_before_start(monkeypatch):
    import sys

    app = SimpleNamespace(run_async=Mock(), uninstall_log_handler=Mock())
    seen = []

    async def run():
        seen.append(
            (
                app.status_text,
                app.connected,
                app.chat_text,
                app.music_line,
                app.emotion,
                app.auto_mode,
            )
        )

    app.run_async = run
    monkeypatch.setitem(
        sys.modules,
        "src.ui.tui.app",
        SimpleNamespace(XiaozhiTuiApp=lambda **kwargs: app),
    )
    view = TuiViewManager(EventBus())
    view.set_status("listening", True)
    view.set_chat_text("hello")
    view.set_music_line("lyrics")
    view.set_emotion("happy")
    view.set_auto_mode(True)
    await view.start()
    assert seen == [("listening", True, "hello", "lyrics", "happy", True)]
    app.uninstall_log_handler.assert_called_once()
