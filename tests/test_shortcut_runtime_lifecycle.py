"""Shortcut command ownership and listener lifecycle without native keyboard hooks."""

import asyncio
import importlib
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.bootstrap.container import ServiceContainer
from src.bootstrap.plugin_wiring import register_cleanup_resources
from src.constants.constants import ListeningMode
from src.core.event_bus import Events
from src.plugins.shortcuts import ShortcutBackend, ShortcutConfig, ShortcutsPlugin
from src.plugins.ui_session import SessionActions
from src.utils.config_manager import ConfigManager


class MemoryBackend(ShortcutBackend):
    def __init__(self, loop):
        super().__init__(loop)
        self.starts = 0
        self.stops = 0

    async def start(self):
        self.starts += 1
        self._running = True
        return True

    async def stop(self):
        self.stops += 1
        self._running = False

    def register(self, name, config, callback):
        self._shortcuts[name] = config
        self._callbacks[name] = callback
        return True

    def unregister(self, name):
        self._shortcuts.pop(name, None)
        self._callbacks.pop(name, None)
        return True


class MemoryTransport:
    def __init__(self):
        self.opened = False
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.block_connect = False
        self.cancelled = False
        self.starts = []
        self.aborts = []

    def is_audio_channel_opened(self):
        return self.opened

    async def connect(self):
        self.entered.set()
        if self.block_connect:
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        self.opened = True
        return True

    async def send_start_listening(self, mode):
        self.starts.append(mode)
        return True

    async def send_stop_listening(self):
        return True

    async def send_abort_speaking(self, reason):
        self.aborts.append(reason)
        return True

    async def shutdown(self):
        self.opened = False


async def make_runtime(monkeypatch, *, enabled=True):
    config = ConfigManager.from_dict(
        {"SHORTCUTS": {"ENABLED": enabled}, "AEC_OPTIONS": {"ENABLED": True}}
    )
    core = ServiceContainer(config)
    core.tasks.initialize()
    transport = MemoryTransport()
    core.protocol = transport
    core.session.protocol = transport
    backend = MemoryBackend(asyncio.get_running_loop())
    monkeypatch.setattr("src.plugins.shortcuts.create_backend", lambda loop: backend)
    plugin = ShortcutsPlugin()
    core.plugins.register(plugin)
    await core.plugins.setup_all(
        core.create_plugin_context(), core.create_plugin_commands()
    )
    register_cleanup_resources(core)
    await core.plugins.start_all()
    return core, plugin, backend, transport


async def drain(core):
    """Let queued callables and their managed descendants finish."""
    for _ in range(12):
        await asyncio.sleep(0)
    tasks = list(core.tasks._tasks)
    if tasks:
        await asyncio.wait_for(asyncio.gather(*tasks), 1)


def test_backend_without_scheduler_keeps_sync_fallback_and_rejects_async():
    backend = MemoryBackend(None)
    backend._running = True
    sync = Mock()
    async_callback = AsyncMock()
    backend.register("sync", ShortcutConfig("ctrl", "a"), sync)
    backend.register("async", ShortcutConfig("ctrl", "b"), async_callback)

    backend._run_callback("sync")
    backend._run_callback("async")

    sync.assert_called_once_with()
    async_callback.assert_not_called()


@pytest.mark.asyncio
async def test_backend_without_scheduler_hops_sync_and_rejects_async():
    loop = asyncio.get_running_loop()
    backend = MemoryBackend(loop)
    backend._running = True
    sync, async_callback = Mock(), AsyncMock()
    backend.register("sync", ShortcutConfig("ctrl", "a"), sync)
    backend.register("async", ShortcutConfig("ctrl", "b"), async_callback)

    backend._run_callback("sync")
    backend._run_callback("async")
    sync.assert_not_called()
    await asyncio.sleep(0)
    sync.assert_called_once_with()
    async_callback.assert_not_called()


@pytest.mark.parametrize("change", ["replace", "unregister", "stop"])
def test_backend_rechecks_running_and_callback_identity_before_invoking(change):
    backend = MemoryBackend(None)
    backend._running = True
    schedule = Mock()
    backend.bind_commands(SimpleNamespace(schedule_command_nowait=schedule))
    callback, replacement = Mock(), Mock()
    config = ShortcutConfig("ctrl", "a")
    backend.register("manual", config, callback)
    backend._run_callback("manual")
    invoke = schedule.call_args.args[0]
    if change == "replace":
        backend.register("manual", config, replacement)
    elif change == "unregister":
        backend.unregister("manual")
    else:
        backend._running = False

    assert invoke() is None
    callback.assert_not_called()
    replacement.assert_not_called()


@pytest.mark.asyncio
async def test_initially_disabled_config_starts_and_restarts_actual_listener(monkeypatch):
    core, plugin, backend, _ = await make_runtime(monkeypatch, enabled=False)
    try:
        assert not backend.is_running and backend.starts == 0
        assert not backend._shortcuts
        for enabled, starts in ((True, 1), (False, 1), (True, 2)):
            core.config.update_config("SHORTCUTS.ENABLED", enabled, save=False)
            await core.event_bus.emit(Events.CONFIG_CHANGED)
            assert backend.is_running is enabled
            assert backend.starts == starts
            assert len(backend._shortcuts) == (5 if enabled else 0)
        # Reloading mappings while enabled must not duplicate the listener.
        core.config.update_config("SHORTCUTS.MANUAL_PRESS.key", "z", save=False)
        await core.event_bus.emit(Events.CONFIG_CHANGED)
        assert backend._shortcuts[plugin.MANUAL_PRESS].key == "z"
        assert backend.starts == 2
    finally:
        await core.shutdown()


@pytest.mark.asyncio
async def test_sync_reload_reconciles_listener_and_stop_revokes_pending_reload(monkeypatch):
    core, plugin, backend, _ = await make_runtime(monkeypatch, enabled=False)
    loop = asyncio.get_running_loop()
    thread_hop = Mock(wraps=loop.call_soon_threadsafe)
    monkeypatch.setattr(loop, "call_soon_threadsafe", thread_hop)
    try:
        core.config.update_config("SHORTCUTS.ENABLED", True, save=False)
        plugin.reload_from_config()
        await drain(core)
        assert backend.is_running and backend.starts == 1
        core.config.update_config("SHORTCUTS.ENABLED", False, save=False)
        plugin.reload_from_config()
        await drain(core)
        assert not backend.is_running and not backend._shortcuts
        core.config.update_config("SHORTCUTS.ENABLED", True, save=False)
        plugin.reload_from_config()
        await plugin.stop()
        await drain(core)
        assert not backend.is_running and backend.starts == 1
        assert thread_hop.call_count == 3
    finally:
        await core.shutdown()


@pytest.mark.asyncio
async def test_stop_wins_over_inflight_config_listener_start(monkeypatch):
    core, plugin, backend, _ = await make_runtime(monkeypatch, enabled=False)
    entered, release = asyncio.Event(), asyncio.Event()
    original_start = backend.start

    async def delayed_start():
        entered.set()
        await release.wait()
        return await original_start()

    monkeypatch.setattr(backend, "start", delayed_start)
    reload_task = stop_task = None
    try:
        core.config.update_config("SHORTCUTS.ENABLED", True, save=False)
        reload_task = asyncio.create_task(core.event_bus.emit(Events.CONFIG_CHANGED))
        await asyncio.wait_for(entered.wait(), 1)
        stop_task = asyncio.create_task(plugin.stop())
        await asyncio.sleep(0)
        assert core.event_bus.handler_count(Events.CONFIG_CHANGED) == 0
        release.set()
        await asyncio.wait_for(asyncio.gather(reload_task, stop_task), 1)
        assert not backend.is_running and not backend._shortcuts
    finally:
        release.set()
        await asyncio.gather(
            *(task for task in (reload_task, stop_task) if task), return_exceptions=True
        )
        await core.shutdown()


@pytest.mark.asyncio
async def test_stop_revokes_callback_permission_before_waiting_for_lifecycle_lock(
    monkeypatch,
):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    pending = None
    await plugin._lifecycle_lock.acquire()
    try:
        pending = core.tasks.spawn(plugin.stop(), "test:shortcuts.stop")
        await asyncio.sleep(0)
        assert not pending.done()
        assert backend.is_running
        backend._run_callback(plugin.AUTO_TOGGLE)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not transport.entered.is_set()
    finally:
        plugin._lifecycle_lock.release()
        if pending:
            await asyncio.wait_for(pending, 1)
        await core.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [False, True], ids=["queued", "managed"])
async def test_stop_revokes_queued_callbacks_and_late_config_events(monkeypatch, managed):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    try:
        # Simulate a keyboard thread which queues callbacks without running the loop.
        thread = threading.Thread(
            target=lambda: [backend._run_callback(name) for name in backend._callbacks]
        )
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        if managed:
            # Hand coroutines to TaskManager, then stop before their bodies run.
            await asyncio.sleep(0)
            assert core.tasks.task_count() == len(backend._callbacks)
        await plugin.stop()
        assert core.event_bus.handler_count(Events.CONFIG_CHANGED) == 0
        await core.event_bus.emit(Events.CONFIG_CHANGED)
        # Include an already-captured EventBus handler snapshot.
        await plugin._on_config_changed()
        plugin.reload_from_config()
        await drain(core)
        assert backend.starts == 1 and not backend.is_running
        assert not backend._shortcuts
        assert not transport.entered.is_set()
        # A later explicit lifecycle start subscribes once and uses fresh config.
        await plugin.start()
        assert backend.starts == 2
        assert core.event_bus.handler_count(Events.CONFIG_CHANGED) == 1
    finally:
        await core.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("managed", [False, True], ids=["queued", "managed"])
@pytest.mark.parametrize("change", ["remap", "disable", "sync_reload"])
async def test_config_change_revokes_old_callbacks(monkeypatch, managed, change):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    emitted = []
    for event in (Events.UI_MANUAL_TOGGLE, Events.UI_AUTO_TOGGLE, Events.UI_TOGGLE_WINDOW):
        async def record(event=event):
            emitted.append(event)

        core.event_bus.on(event, record)
    try:
        for name in backend._callbacks:
            backend._run_callback(name)
        if managed:
            # The hop has run and handed callbacks to TaskManager, but their bodies
            # have not run. Backend callback identity alone cannot revoke them now.
            await asyncio.sleep(0)
            assert core.tasks.task_count() == 5
        if change == "disable":
            core.config.update_config("SHORTCUTS.ENABLED", False, save=False)
            await plugin._on_config_changed()
        else:
            core.config.update_config("SHORTCUTS.MANUAL_PRESS.key", "z", save=False)
            if change == "sync_reload":
                plugin.reload_from_config()
            else:
                await plugin._on_config_changed()
        await drain(core)
        assert emitted == []
        assert not transport.entered.is_set()
        assert transport.aborts == []
        assert backend.is_running is (change != "disable")
        if change != "disable":
            assert backend._shortcuts[plugin.MANUAL_PRESS].key == "z"
            backend._run_callback(plugin.AUTO_TOGGLE)
            await drain(core)
            assert transport.entered.is_set()
    finally:
        await core.shutdown()


@pytest.mark.asyncio
async def test_auto_connect_is_managed_and_cancelled_before_container_exit(monkeypatch):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    transport.block_connect = True
    loop = asyncio.get_running_loop()
    thread_hop = Mock(wraps=loop.call_soon_threadsafe)
    monkeypatch.setattr(loop, "call_soon_threadsafe", thread_hop)
    try:
        thread = threading.Thread(target=lambda: backend._run_callback(plugin.AUTO_TOGGLE))
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        await asyncio.wait_for(transport.entered.wait(), 1)
        assert thread_hop.call_count == 1
        assert core.tasks.task_count() == 1
        await core.shutdown()
        assert transport.cancelled
        assert core.tasks.task_count() == 0
        transport.release.set()
        await asyncio.sleep(0)
        assert not transport.opened
        assert not transport.starts
    finally:
        await core.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,command",
    [
        (ShortcutsPlugin.AUTO_TOGGLE, "start_auto_conversation"),
        (ShortcutsPlugin.ABORT, "abort_speaking"),
    ],
)
async def test_command_errors_remain_owned_by_managed_task(monkeypatch, name, command):
    core, _, backend, _ = await make_runtime(monkeypatch)
    error = RuntimeError("shortcut command failed")
    callback = AsyncMock(side_effect=error)
    monkeypatch.setattr(core.create_plugin_commands(), command, callback)
    try:
        backend._run_callback(name)
        await asyncio.sleep(0)
        task, = core.tasks._tasks
        with pytest.raises(RuntimeError) as raised:
            await task
        assert raised.value is error
        callback.assert_awaited_once()
        await asyncio.sleep(0)
        assert core.tasks.task_count() == 0
    finally:
        await core.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,event",
    [
        (ShortcutsPlugin.MANUAL_PRESS, Events.UI_MANUAL_TOGGLE),
        (ShortcutsPlugin.MODE_TOGGLE, Events.UI_AUTO_TOGGLE),
        (ShortcutsPlugin.WINDOW_TOGGLE, Events.UI_TOGGLE_WINDOW),
        (ShortcutsPlugin.ABORT, None),
    ],
)
async def test_each_callback_path_has_managed_cancellation(monkeypatch, name, event):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def block(*args):
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    if event:
        core.event_bus.on(event, block)
    else:
        transport.send_abort_speaking = block
        transport.opened = True
    try:
        backend._run_callback(name)
        await asyncio.wait_for(entered.wait(), 1)
        assert core.tasks.task_count() == 1
        await core.shutdown()
        assert cancelled.is_set()
        assert core.tasks.task_count() == 0
    finally:
        release.set()
        await core.shutdown()


@pytest.mark.asyncio
async def test_shortcut_ui_modes_and_auto_intent_remain_unchanged(monkeypatch):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    presenter = Mock()
    actions = SessionActions(
        core.create_plugin_context(), core.create_plugin_commands(), presenter
    )
    actions.subscribe(core.event_bus)
    try:
        backend._run_callback(plugin.MANUAL_PRESS)
        await drain(core)
        assert actions.manual_recording
        assert transport.starts == [ListeningMode.MANUAL]
        backend._run_callback(plugin.MANUAL_PRESS)
        await drain(core)
        assert not actions.manual_recording
        backend._run_callback(plugin.MODE_TOGGLE)
        await drain(core)
        assert actions.auto_mode
        presenter.set_auto_mode.assert_called_once_with(True)
        backend._run_callback(plugin.AUTO_TOGGLE)
        await drain(core)
        # Actual AEC availability, rather than the shortcut, selects the mode.
        assert transport.starts[-1] == ListeningMode.AUTO_STOP
        assert core.state.keep_listening
    finally:
        await core.shutdown()


def native_backend(monkeypatch, kind, core):
    """Load the real platform implementation against memory-only native APIs."""
    import src.plugins.shortcuts as shortcuts

    listeners = []

    def listener(**kwargs):
        result = SimpleNamespace(
            start=Mock(), stop=Mock(), is_alive=Mock(return_value=True), **kwargs
        )
        listeners.append(result)
        return result

    quartz = SimpleNamespace(
        kCGEventFlagMaskCommand=1,
        kCGEventFlagMaskControl=2,
        kCGEventFlagMaskAlternate=4,
        kCGEventFlagMaskShift=8,
        kCGEventKeyDown=10,
        kCGEventFlagsChanged=12,
        kCGSessionEventTap=0,
        kCGHeadInsertEventTap=0,
        kCGEventTapOptionListenOnly=0,
        kCFRunLoopCommonModes=0,
        kCGKeyboardEventKeycode=0,
        CGEventMaskBit=lambda kind: 1 << kind,
        CGEventTapCreate=Mock(return_value=object()),
        CFMachPortCreateRunLoopSource=Mock(return_value=object()),
        CFRunLoopGetCurrent=Mock(return_value=object()),
        CFRunLoopAddSource=Mock(),
        CFRunLoopRemoveSource=Mock(),
        CGEventTapEnable=Mock(),
        CGEventTapIsEnabled=Mock(return_value=True),
        CGEventGetFlags=lambda event: event.flags,
        CGEventGetIntegerValueField=lambda event, field: event.keycode,
    )
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "darwin")
        patch.setitem(sys.modules, "Quartz", quartz)
        patch.setitem(sys.modules, "pynput", SimpleNamespace(
            keyboard=SimpleNamespace(Listener=listener)
        ))
        spec = importlib.util.spec_from_file_location(
            f"src.plugins.shortcuts._test_{kind}",
            Path(shortcuts.__file__).with_name(f"{kind}_backend.py"),
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    cls = module.MacOSShortcutBackend if kind == "macos" else module.PynputShortcutBackend
    backend = cls(asyncio.get_running_loop())
    backend.bind_commands(core.create_plugin_commands())
    return backend, quartz, listeners


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["macos", "pynput"])
async def test_native_press_release_and_health_tasks_are_owned(monkeypatch, kind):
    core = ServiceContainer()
    core.tasks.initialize()
    backend, quartz, listeners = native_backend(monkeypatch, kind, core)
    entered, release, cancelled = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def callback():
        calls.append("press")
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    backend.register("manual", ShortcutConfig("ctrl", "a"), callback)
    try:
        assert await backend.start()
        assert core.tasks.task_count() == 1  # native health supervisor
        if kind == "pynput":
            backend._on_key_press(SimpleNamespace(name="ctrl_l"))
            backend._on_key_press(SimpleNamespace(char="\x01"))
            backend._on_key_release(SimpleNamespace(char="\x01"))
            backend._on_key_release(SimpleNamespace(name="ctrl_l"))
            assert not backend._pressed_keys
            assert len(listeners) == 1
        else:
            event = SimpleNamespace(keycode=0, flags=2)
            assert backend._event_callback(None, quartz.kCGEventKeyDown, event, None) is event
            # Flags changes update modifier state; they do not trigger the shortcut.
            backend._event_callback(None, quartz.kCGEventFlagsChanged, event, None)
            assert backend._pressed_modifiers == 2
        await asyncio.wait_for(entered.wait(), 1)
        assert calls == ["press"]
        assert core.tasks.task_count() == 2
        await backend.stop()
        assert backend._health_check_task is None
        await core.tasks.cancel_all()
        assert cancelled.is_set()
        assert core.tasks.task_count() == 0
        # A late native event or a queued callback after stop is inert.
        backend._run_callback("manual")
        await asyncio.sleep(0)
        assert calls == ["press"]
    finally:
        release.set()
        await backend.stop()
        await core.tasks.cancel_all()


@pytest.mark.asyncio
async def test_pynput_delayed_restart_cannot_recreate_listener_after_stop(monkeypatch):
    core = ServiceContainer()
    core.tasks.initialize()
    backend, _, listeners = native_backend(monkeypatch, "pynput", core)
    entered, release = asyncio.Event(), asyncio.Event()
    real_sleep = asyncio.sleep

    async def pause(delay):
        if delay == 0.5:
            entered.set()
            await release.wait()
        else:
            await real_sleep(delay)

    # Patch only the loaded backend boundary, not the process-wide asyncio module.
    restart_globals = backend._restart_listener.__func__.__globals__
    monkeypatch.setitem(
        restart_globals, "asyncio", SimpleNamespace(sleep=pause, gather=asyncio.gather)
    )
    pending = None
    try:
        assert await backend.start()
        pending = asyncio.create_task(backend._restart_listener())
        await asyncio.wait_for(entered.wait(), 1)
        await backend.stop()
        release.set()
        await asyncio.wait_for(pending, 1)
        assert len(listeners) == 1
        assert backend._listener is None
        assert not backend.is_running
    finally:
        release.set()
        if pending:
            await asyncio.gather(pending, return_exceptions=True)
        await backend.stop()
        await core.tasks.cancel_all()
