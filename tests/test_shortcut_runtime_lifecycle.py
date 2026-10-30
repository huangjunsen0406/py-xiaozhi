"""Shortcut command ownership and listener lifecycle without native keyboard hooks."""

import asyncio
import importlib
import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

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
async def test_stop_revokes_queued_callbacks_and_late_config_events(monkeypatch):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    try:
        # Simulate a keyboard thread which queues callbacks without running the loop.
        thread = threading.Thread(
            target=lambda: [backend._run_callback(name) for name in backend._callbacks]
        )
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        # Also queue a handler directly: stop must revoke both scheduling layers.
        plugin._handle_auto_toggle()
        plugin.reload_from_config()
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
async def test_auto_connect_is_managed_and_cancelled_before_container_exit(monkeypatch):
    core, plugin, backend, transport = await make_runtime(monkeypatch)
    transport.block_connect = True
    try:
        thread = threading.Thread(target=lambda: backend._run_callback(plugin.AUTO_TOGGLE))
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        await asyncio.wait_for(transport.entered.wait(), 1)
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
    "method,event",
    [
        ("_handle_manual_press", Events.UI_MANUAL_TOGGLE),
        ("_handle_mode_toggle", Events.UI_AUTO_TOGGLE),
        ("_handle_window_toggle", Events.UI_TOGGLE_WINDOW),
        ("_handle_abort", None),
    ],
)
async def test_each_callback_path_has_managed_cancellation(monkeypatch, method, event):
    core, plugin, _, transport = await make_runtime(monkeypatch)
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
        getattr(plugin, method)()
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
    core, plugin, _, transport = await make_runtime(monkeypatch)
    presenter = Mock()
    actions = SessionActions(
        core.create_plugin_context(), core.create_plugin_commands(), presenter
    )
    actions.subscribe(core.event_bus)
    try:
        plugin._handle_manual_press()
        await drain(core)
        assert actions.manual_recording
        assert transport.starts == [ListeningMode.MANUAL]
        plugin._handle_manual_press()
        await drain(core)
        assert not actions.manual_recording
        plugin._handle_mode_toggle()
        await drain(core)
        assert actions.auto_mode
        presenter.set_auto_mode.assert_called_once_with(True)
        plugin._handle_auto_toggle()
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
