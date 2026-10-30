"""Activation owners unwind on window close, caller cancellation and SIGINT."""

import asyncio
import signal
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src import cli


@pytest.mark.parametrize("mode", ["cli", "tui"])
def test_first_sigint_cancels_startup_and_restores_handler(monkeypatch, mode):
    original = signal.getsignal(signal.SIGINT)
    cleaned = []

    async def pending(*args, **kwargs):
        try:
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            await asyncio.sleep(0)
            pytest.fail("startup continued after SIGINT")
        finally:
            cleaned.append(True)

    monkeypatch.setattr(cli, "_container", None)
    monkeypatch.setattr(cli, "start_app", pending)
    monkeypatch.setitem(sys.modules, "textual", SimpleNamespace())
    assert cli._run(cli.parse_args(["--mode", mode])) == 0
    assert cleaned == [True]
    assert signal.getsignal(signal.SIGINT) is original


class Service:
    def __init__(self, result=None):
        self.result = result
        self.started = asyncio.Event()
        self.finished = asyncio.Event()
        self.cancel_activation = Mock()

    def get_activation_data(self):
        return {"code": "123456", "challenge": "fake"}

    async def activate(self, data):
        self.started.set()
        try:
            if self.result is None:
                await asyncio.Future()
            if isinstance(self.result, Exception):
                raise self.result
            return self.result
        finally:
            # A real child can need asynchronous HTTP/session cleanup.
            await asyncio.sleep(0)
            self.finished.set()

    def get_serial_number(self):
        return "fake"

    def get_mac_address(self):
        return "fake"

    def get_activation_status(self):
        return {}


class Engine:
    def __init__(self):
        self.deleteLater = Mock()


@pytest.fixture
def controller(monkeypatch):
    pytest.importorskip("PySide6")
    from src.ui.gui import activation

    timers = []
    monkeypatch.setattr(
        activation,
        "QTimer",
        SimpleNamespace(singleShot=lambda delay, callback: timers.append(callback)),
    )

    def create(result=None, *, setup_error=False):
        service = Service(result)
        ui = activation.GuiActivation(service, {"need_activation_ui": True})
        engine = Engine()

        def setup():
            ui._engine = engine
            if setup_error:
                raise RuntimeError("QML load failure")

        monkeypatch.setattr(ui, "_setup_ui", setup)
        monkeypatch.setattr(ui, "_show_window", lambda: None)
        return ui, service, engine, timers

    return create


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["titlebar", "cancel_slot", "caller"])
async def test_gui_activation_cancellation_joins_child_and_disposes_engine(
    controller, action
):
    ui, service, engine, timers = controller()
    task = asyncio.create_task(ui.run())
    await asyncio.sleep(0)
    timers.pop(0)()
    await service.started.wait()
    child = ui._activation_task
    if action == "caller":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        if action == "titlebar":
            ui._on_window_closing()
        else:
            ui.cancelActivation()
        assert await task is False
    assert child.done() and service.finished.is_set()
    service.cancel_activation.assert_called_once()
    engine.deleteLater.assert_called_once()
    assert ui._engine is None
    assert ui._completion_future is None or ui._completion_future.done()
    ui._start_activation()
    await asyncio.sleep(0)
    assert ui._activation_task is None or ui._activation_task.done()


@pytest.mark.asyncio
async def test_close_before_start_timer_cannot_schedule_disposed_controller(controller):
    ui, service, engine, timers = controller()
    task = asyncio.create_task(ui.run())
    await asyncio.sleep(0)
    delayed = timers.pop(0)
    ui._on_window_closing()
    assert await task is False
    delayed()
    await asyncio.sleep(0)
    assert not service.started.is_set()
    assert ui._activation_task is None
    engine.deleteLater.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [True, False, RuntimeError("activation failed")])
async def test_activation_completion_cleans_engine_and_owned_task(controller, result):
    ui, service, engine, timers = controller(result)
    task = asyncio.create_task(ui.run())
    await asyncio.sleep(0)
    timers.pop(0)()
    await service.finished.wait()
    await asyncio.sleep(0)
    if result is True:
        timers.pop(0)()
    assert await asyncio.wait_for(task, timeout=0.2) is (result is True)
    assert ui._activation_task is None or ui._activation_task.done()
    engine.deleteLater.assert_called_once()


@pytest.mark.asyncio
async def test_partial_qml_setup_failure_cleans_engine(controller):
    ui, service, engine, _ = controller(setup_error=True)
    with pytest.raises(RuntimeError, match="QML load failure"):
        await ui.run()
    engine.deleteLater.assert_called_once()
    assert ui._completion_future is None or ui._completion_future.done()
    assert not service.started.is_set()


@pytest.mark.parametrize("phase", ["initialize", "activate"])
def test_real_startup_activation_unwinds_on_first_sigint(monkeypatch, phase):
    from src import activation

    events = []

    class ActivationService:
        @classmethod
        async def create(cls, config=None):
            return cls()

        async def initialize(self):
            if phase == "initialize":
                try:
                    signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
                    await asyncio.sleep(0)
                finally:
                    events.append("initialize-cleaned")
            return {"success": True, "need_activation_ui": True}

        async def activate(self):
            try:
                signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                # Production ActivationService turns cancellation into False.
                return False
            finally:
                events.append("activate-cleaned")

    monkeypatch.setattr(activation, "ActivationService", ActivationService)
    monkeypatch.setattr(
        activation,
        "create_activation_ui",
        lambda mode, service, result: SimpleNamespace(run=service.activate),
    )
    monkeypatch.setitem(
        sys.modules,
        "src.bootstrap.container",
        SimpleNamespace(
            ServiceContainer=lambda **kwargs: pytest.fail(
                "runtime started after interrupt"
            )
        ),
    )
    monkeypatch.setattr(cli, "_container", None)
    assert cli._run(cli.parse_args(["--mode", "cli"])) == 0
    assert events == [phase + "-cleaned"]


def test_gui_sigint_cancels_startup_with_fake_qasync_loop(monkeypatch):
    class Loop(asyncio.SelectorEventLoop):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    app = SimpleNamespace(setQuitOnLastWindowClosed=Mock(), quit=Mock())
    monkeypatch.setitem(
        sys.modules, "qasync", SimpleNamespace(QEventLoop=lambda _app: Loop())
    )
    monkeypatch.setitem(
        sys.modules,
        "PySide6.QtWidgets",
        SimpleNamespace(QApplication=SimpleNamespace(instance=lambda: app)),
    )
    monkeypatch.setattr(cli, "_container", None)
    finished = []

    async def pending(*args, **kwargs):
        try:
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            await asyncio.sleep(0)
            pytest.fail("GUI startup continued after SIGINT")
        finally:
            finished.append(True)

    monkeypatch.setattr(cli, "start_app", pending)
    try:
        assert cli._run(cli.parse_args(["--mode", "gui"])) == 0
    finally:
        asyncio.set_event_loop(None)
    assert finished == [True]
    app.quit.assert_not_called()


def test_runtime_sigint_preserves_graceful_shutdown_request(monkeypatch):
    shutdown = Mock()
    monkeypatch.setattr(
        cli,
        "_container",
        SimpleNamespace(tasks=SimpleNamespace(request_shutdown=shutdown)),
    )

    async def running(*args, **kwargs):
        signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
        await asyncio.sleep(0)
        shutdown.assert_called_once()
        return 0

    monkeypatch.setattr(cli, "start_app", running)
    assert cli._run(cli.parse_args(["--mode", "cli"])) == 0


@pytest.mark.asyncio
async def test_late_success_timer_and_duplicate_start_are_inert_after_close(controller):
    ui, service, engine, timers = controller(True)
    signals = []
    ui.activationCompleted.connect(signals.append)
    task = asyncio.create_task(ui.run())
    await asyncio.sleep(0)
    timers.pop(0)()
    child = ui._activation_task
    ui._start_activation()
    assert ui._activation_task is child
    await service.finished.wait()
    await asyncio.sleep(0)
    delayed_success = timers.pop(0)
    ui.cancelActivation()
    assert await task is False
    delayed_success()
    ui._on_window_closing()
    assert signals == [False]
    engine.deleteLater.assert_called_once()


@pytest.mark.asyncio
async def test_real_setup_connects_window_close_to_owned_cancellation(monkeypatch):
    pytest.importorskip("PySide6")
    from src.ui.gui import activation

    class Closing:
        def connect(self, callback):
            self.callback = callback

        def emit(self, event):
            self.callback(event)

    service = Service()
    window = SimpleNamespace(
        closing=Closing(), show=Mock(), raise_=Mock(), requestActivate=Mock()
    )
    engine = SimpleNamespace(
        rootContext=lambda: SimpleNamespace(setContextProperty=Mock()),
        addImportPath=Mock(),
        load=Mock(),
        rootObjects=lambda: [window],
        deleteLater=Mock(),
    )
    monkeypatch.setattr(activation, "QQmlApplicationEngine", lambda: engine)
    monkeypatch.setattr(
        activation,
        "QTimer",
        SimpleNamespace(
            singleShot=lambda delay, callback: asyncio.get_running_loop().call_soon(
                callback
            )
        ),
    )
    ui = activation.GuiActivation(service, {"need_activation_ui": True})
    task = asyncio.create_task(ui.run())
    await service.started.wait()
    child = ui._activation_task
    window.closing.emit(object())
    assert await task is False
    assert child.done() and service.finished.is_set()
    engine.load.assert_called_once()
    engine.deleteLater.assert_called_once()
