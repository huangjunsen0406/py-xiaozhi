"""TaskManager 协程所有权、任务追踪及调度拒绝的回归测试。"""

import asyncio
import gc
import inspect
import logging
from unittest.mock import Mock

import pytest

from src.core.event_bus import EventBus
from src.core.protocol_manager import ProtocolManager
from src.core.task_manager import TaskManager


async def _noop():
    return 42


def _assert_no_unawaited_warning(recwarn):
    gc.collect()
    assert not [
        warning
        for warning in recwarn
        if issubclass(warning.category, RuntimeWarning)
        and "was never awaited" in str(warning.message)
    ]


def test_spawn_before_initialize_closes_native_coroutine(recwarn):
    manager = TaskManager()
    coro = _noop()

    assert manager.spawn(coro, "rejected") is None
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert manager.task_count() == 0

    del coro
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
@pytest.mark.parametrize("shutdown", ["requested", "completed"])
async def test_spawn_after_shutdown_closes_native_coroutine(shutdown, recwarn):
    manager = TaskManager()
    manager.initialize()
    if shutdown == "requested":
        manager.request_shutdown()
    else:
        await manager.cancel_all()
    coro = _noop()

    assert manager.spawn(coro, "rejected") is None
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert manager.task_count() == 0

    del coro
    _assert_no_unawaited_warning(recwarn)


def test_spawn_without_running_loop_closes_coroutine_and_reraises(recwarn):
    manager = TaskManager()
    loop = asyncio.new_event_loop()
    manager.initialize(loop)
    coro = _noop()
    try:
        with pytest.raises(RuntimeError, match="no running event loop"):
            manager.spawn(coro, "no-loop")
        assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
        assert manager.task_count() == 0
    finally:
        coro.close()
        loop.close()

    del coro
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_create_task_failure_closes_coroutine_and_preserves_error(
    error_type, monkeypatch, recwarn
):
    manager = TaskManager()
    manager.initialize()
    coro = _noop()
    error = error_type("task creation failed")
    create_task = Mock(side_effect=error)
    with monkeypatch.context() as patch:
        patch.setattr(asyncio, "create_task", create_task)
        with pytest.raises(error_type) as raised:
            manager.spawn(coro, "creation-failed")

    assert raised.value is error
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert manager.task_count() == 0
    create_task.assert_called_once_with(coro, name="creation-failed")

    del coro
    del create_task
    del raised
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
async def test_task_factory_failure_releases_coroutine_and_manager_remains_usable(
    recwarn,
):
    manager = TaskManager()
    manager.initialize()
    loop = asyncio.get_running_loop()
    original_factory = loop.get_task_factory()
    coro = _noop()

    def failing_factory(loop, coro, **kwargs):
        raise RuntimeError("factory failed")

    try:
        loop.set_task_factory(failing_factory)
        with pytest.raises(RuntimeError, match="factory failed"):
            manager.spawn(coro, "factory-failed")
    finally:
        loop.set_task_factory(original_factory)

    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    assert manager.task_count() == 0
    task = manager.spawn(_noop(), "accepted")
    assert task is not None
    assert manager.task_count() == 1
    assert task.get_name() == "accepted"
    assert manager.get_task_names() == ["accepted"]
    assert await task == 42
    await asyncio.sleep(0)
    assert manager.task_count() == 0

    del coro
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
async def test_accepted_task_exception_is_logged_with_original_traceback(caplog):
    manager = TaskManager()
    manager.initialize()
    error = ValueError("accepted task failed")

    async def failing():
        raise error

    with caplog.at_level(logging.ERROR):
        task = manager.spawn(failing(), "owned:error")
        assert task is not None
        assert manager.task_count() == 1
        with pytest.raises(ValueError) as raised:
            await task
        await asyncio.sleep(0)

    assert raised.value is error
    assert task.exception() is error
    assert manager.task_count() == 0
    logged = [record for record in caplog.records if "owned:error" in record.message]
    assert len(logged) == 1
    assert logged[0].exc_info[1] is error
    assert logged[0].exc_info[2] is not None


@pytest.mark.asyncio
async def test_cancel_all_cancels_and_waits_for_tracked_tasks(caplog):
    manager = TaskManager()
    manager.initialize()
    started = [asyncio.Event(), asyncio.Event()]
    finalized = []

    async def waiting(index):
        started[index].set()
        try:
            await asyncio.Event().wait()
        finally:
            finalized.append(index)

    tasks = [manager.spawn(waiting(index), f"waiting:{index}") for index in range(2)]
    await asyncio.gather(*(event.wait() for event in started))
    assert manager.task_count() == 2
    assert set(manager.get_task_names()) == {"waiting:0", "waiting:1"}

    with caplog.at_level(logging.ERROR):
        await manager.cancel_all()
        await manager.cancel_all()

    assert all(task.cancelled() for task in tasks)
    assert sorted(finalized) == [0, 1]
    assert manager.task_count() == 0
    assert manager.get_task_names() == []
    assert not manager.running
    assert manager.shutdown_event.is_set()
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


class _CloseableFuture(asyncio.Future):
    def __init__(self):
        super().__init__()
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["uninitialized", "running", "shutdown"])
@pytest.mark.parametrize("kind", ["future", "task"])
async def test_spawn_rejects_foreign_future_or_task_without_taking_ownership(
    state, kind
):
    manager = TaskManager()
    if state != "uninitialized":
        manager.initialize()
    if state == "shutdown":
        manager.request_shutdown()

    external = (
        _CloseableFuture()
        if kind == "future"
        else asyncio.create_task(asyncio.Event().wait(), name="external")
    )
    try:
        with pytest.raises(TypeError, match="native coroutine"):
            manager.spawn(external, "invalid")
        assert not external.done()
        assert not external.cancelled()
        assert manager.task_count() == 0
        await manager.cancel_all()
        assert not external.done()
        if kind == "future":
            assert external.close_calls == 0
            external.set_result("still usable")
            assert await external == "still usable"
    finally:
        if not external.done():
            external.cancel()
        await asyncio.gather(external, return_exceptions=True)


@pytest.mark.asyncio
async def test_spawn_rejects_custom_awaitable_without_closing_or_awaiting_it():
    class Awaitable:
        def __init__(self):
            self.close = Mock()
            self.cancel = Mock()

        def __await__(self):
            raise AssertionError("must not await external awaitable")

    manager = TaskManager()
    manager.initialize()
    external = Awaitable()
    with pytest.raises(TypeError, match="native coroutine"):
        manager.spawn(external, "invalid")
    external.close.assert_not_called()
    external.cancel.assert_not_called()
    assert manager.task_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("shutdown", ["requested", "completed"])
async def test_queued_schedule_closes_coroutine_when_shutdown_precedes_runner(
    shutdown, recwarn
):
    manager = TaskManager()
    manager.initialize()
    produced = []

    def callback():
        coro = _noop()
        produced.append(coro)
        return coro

    manager.schedule_nowait(callback)
    if shutdown == "requested":
        manager.request_shutdown()
    else:
        await manager.cancel_all()
    await asyncio.sleep(0)

    assert len(produced) == 1
    assert inspect.getcoroutinestate(produced[0]) == inspect.CORO_CLOSED
    assert manager.task_count() == 0
    produced.clear()
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
async def test_schedule_nowait_from_worker_thread_tracks_and_cancels_task():
    manager = TaskManager()
    manager.initialize()
    started = asyncio.Event()
    finalized = asyncio.Event()

    async def callback():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            finalized.set()

    await asyncio.to_thread(manager.schedule_nowait, callback)
    await asyncio.wait_for(started.wait(), timeout=1)
    assert manager.task_count() == 1
    assert manager.get_task_names() == ["scheduled:callback"]
    await manager.cancel_all()
    assert finalized.is_set()
    assert manager.task_count() == 0


@pytest.mark.asyncio
async def test_scheduled_create_task_failure_releases_coroutine(monkeypatch, recwarn):
    manager = TaskManager()
    manager.initialize()
    produced = []

    def callback():
        coro = _noop()
        produced.append(coro)
        return coro

    with monkeypatch.context() as patch:
        patch.setattr(asyncio, "create_task", Mock(side_effect=RuntimeError("failed")))
        manager.schedule_nowait(callback)
        await asyncio.sleep(0)

    assert len(produced) == 1
    assert inspect.getcoroutinestate(produced[0]) == inspect.CORO_CLOSED
    assert manager.task_count() == 0
    produced.clear()
    _assert_no_unawaited_warning(recwarn)


@pytest.mark.asyncio
async def test_scheduled_foreign_future_is_left_untouched():
    manager = TaskManager()
    manager.initialize()
    external = _CloseableFuture()
    manager.schedule_nowait(lambda: external)
    await asyncio.sleep(0)
    await manager.cancel_all()

    assert not external.done()
    assert external.close_calls == 0
    external.set_result(42)
    assert await external == 42


@pytest.mark.asyncio
async def test_schedule_rejected_before_enqueue_does_not_invoke_callable():
    manager = TaskManager()
    callback = Mock()
    manager.schedule_nowait(callback)
    manager.initialize()
    await manager.cancel_all()
    manager.schedule_nowait(callback)
    await asyncio.sleep(0)
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_protocol_spawn_delegates_rejected_coroutine_cleanup(recwarn):
    manager = TaskManager()
    transport = ProtocolManager(EventBus(), task_manager=manager)
    coro = _noop()

    transport._spawn(coro, "protocol:rejected")
    assert inspect.getcoroutinestate(coro) == inspect.CORO_CLOSED
    transport.set_audio_handler(None)
    assert not transport._audio_consumer_running
    assert transport._audio_consumer_task is None
    assert manager.task_count() == 0

    del coro
    _assert_no_unawaited_warning(recwarn)
