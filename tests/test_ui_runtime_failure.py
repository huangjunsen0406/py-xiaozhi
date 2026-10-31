"""Critical viewport tasks must determine the runtime's exit status."""

import asyncio
import subprocess
import sys
from types import ModuleType
from unittest.mock import AsyncMock

import pytest

from src.bootstrap.container import ServiceContainer
from src.bootstrap.plugin_wiring import register_cleanup_resources
from src.plugins.ui import UIPlugin


@pytest.fixture
def runtime(monkeypatch):
    import src.bootstrap.container as module

    container = ServiceContainer()
    monkeypatch.setenv("XIAOZHI_DISABLE_AUDIO", "1")
    plugins = []

    async def setup(owner, mode, ctx, cmd):
        plugin = UIPlugin(mode=mode, task_manager=owner.tasks)
        plugins.append(plugin)
        owner.plugins.register(plugin)
        await owner.plugins.setup_all(ctx, cmd)
        register_cleanup_resources(owner)

    monkeypatch.setattr(module, "setup_plugins", setup)
    return container, plugins


@pytest.mark.asyncio
async def test_real_tui_missing_dependency_exits_one(runtime, monkeypatch):
    monkeypatch.setitem(sys.modules, "src.ui.tui.app", None)
    container, plugins = runtime
    assert await asyncio.wait_for(container.run(mode="tui"), 0.5) == 1
    assert plugins[0].failed
    assert container.tasks.task_count() == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [True, False])
@pytest.mark.parametrize("blocked_start", [False, True])
async def test_real_tui_later_failure_or_normal_exit_reaches_container(
    runtime, monkeypatch, failure, blocked_start
):
    entered = asyncio.Event()
    release = asyncio.Event()

    class App:
        def __init__(self, **kwargs):
            pass

        async def run_async(self):
            entered.set()
            await release.wait()
            if failure:
                raise RuntimeError("injected TUI runtime failure")

        def exit(self):
            release.set()

        def uninstall_log_handler(self):
            pass

    module = ModuleType("src.ui.tui.app")
    module.XiaozhiTuiApp = App
    monkeypatch.setitem(sys.modules, module.__name__, module)
    container, plugins = runtime
    protocol_entered = asyncio.Event()
    protocol_cancelled = asyncio.Event()

    async def blocked_protocol_start():
        protocol_entered.set()
        try:
            await asyncio.Future()
        finally:
            protocol_cancelled.set()

    if blocked_start:
        monkeypatch.setattr(container.protocol, "start", blocked_protocol_start)
    run = asyncio.create_task(container.run(mode="tui"))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        if blocked_start:
            await asyncio.wait_for(protocol_entered.wait(), 0.5)
        await asyncio.sleep(0)
        release.set()
        assert await asyncio.wait_for(run, 0.5) == int(failure)
        if blocked_start:
            assert protocol_cancelled.is_set()
        assert plugins[0].failed is failure
        assert container.tasks.task_count() == 0
        assert not plugins[0].viewport.is_running
    finally:
        container.tasks.request_shutdown()
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)


@pytest.mark.asyncio
async def test_stop_cancellation_is_not_a_viewport_failure(runtime, monkeypatch):
    entered = asyncio.Event()

    class App:
        def __init__(self, **kwargs):
            pass

        async def run_async(self):
            entered.set()
            await asyncio.Future()

        def exit(self):
            pass

        def uninstall_log_handler(self):
            pass

    module = ModuleType("src.ui.tui.app")
    module.XiaozhiTuiApp = App
    monkeypatch.setitem(sys.modules, module.__name__, module)
    container, plugins = runtime
    run = asyncio.create_task(container.run(mode="tui"))
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        container.tasks.request_shutdown()
        assert await asyncio.wait_for(run, 0.5) == 0
        assert not plugins[0].failed
        assert not plugins[0].viewport.is_running
        assert container.tasks.task_count() == 0
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)


@pytest.mark.asyncio
async def test_real_gui_qml_start_failure_is_critical(runtime, monkeypatch):
    from src.ui.gui.qml_host import QmlAppHost

    def fail(*args):
        raise RuntimeError("injected QML startup failure")

    monkeypatch.setattr(QmlAppHost, "create_engine", fail)
    container, plugins = runtime
    assert await asyncio.wait_for(container.run(mode="gui"), 0.5) == 1
    assert plugins[0].failed
    assert not plugins[0].viewport.is_running
    assert container.tasks.task_count() == 0


def test_core_ui_import_does_not_require_qt():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import src.bootstrap.container; import src.plugins.ui; import sys; assert 'PySide6' not in sys.modules; assert 'qasync' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_real_gui_short_start_keeps_runtime_alive(runtime, monkeypatch):
    from src.ui.gui.manager import GuiViewManager
    from src.ui.gui.qml_host import QmlAppHost
    from src.ui.gui.settings_controller import SettingsController

    for method in ("create_engine", "inject_context", "load_main", "show_root"):
        monkeypatch.setattr(QmlAppHost, method, lambda *args, **kwargs: None)
    monkeypatch.setattr(SettingsController, "ensure_model", lambda self: None)
    monkeypatch.setattr(GuiViewManager, "_setup_tray", lambda self: None)
    container, plugins = runtime
    run = asyncio.create_task(container.run(mode="gui"))
    try:
        for _ in range(30):
            if (
                plugins
                and plugins[0]._viewport_task is not None
                and plugins[0]._viewport_task.done()
            ):
                break
            await asyncio.sleep(0)
        assert plugins[0]._viewport_task.done()
        assert not plugins[0].failed
        assert plugins[0].viewport.is_running
        assert not container.tasks.shutdown_event.is_set()
        assert not run.done()
        container.tasks.request_shutdown()
        assert await asyncio.wait_for(run, 0.5) == 0
        assert not plugins[0].viewport.is_running
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)


@pytest.mark.asyncio
async def test_stop_detaches_closed_viewport_and_pending_ui_gestures(monkeypatch):
    import src.plugins.ui as ui_module
    from src.bootstrap.plugin_wiring import subscribe_builtin_events
    from src.constants.constants import DeviceState
    from src.core.event_bus import Events

    container = ServiceContainer()
    container.tasks.initialize()
    writes_after_close = []
    entered = asyncio.Event()
    release = asyncio.Event()

    class Viewport:
        closed = False
        close_calls = 0

        async def start(self, mode):
            pass

        async def close(self):
            self.close_calls += 1
            self.closed = True
            await container.event_bus.emit(Events.NETWORK_ERROR, "during close")

        def __getattr__(self, name):
            if name.startswith("set_"):

                def setter(*args, **kwargs):
                    if self.closed:
                        writes_after_close.append(name)
                        raise RuntimeError("viewport already destroyed")

                return setter
            raise AttributeError(name)

    async def blocked(data):
        entered.set()
        await release.wait()

    viewport = Viewport()
    monkeypatch.setattr(ui_module, "create_viewport", lambda *args, **kwargs: viewport)
    commands = container.create_plugin_commands()
    monkeypatch.setattr(commands, "send_user_text", AsyncMock())
    container.event_bus.on(Events.UI_SEND_TEXT, blocked)
    plugin = UIPlugin(mode="gui", task_manager=container.tasks)
    container.plugins.register(plugin)
    await container.plugins.setup_all(container.create_plugin_context(), commands)
    subscribe_builtin_events(container)
    plugin.register_resources(container.resource_pool)
    await plugin.start()
    plugin.is_first = False
    pending = asyncio.create_task(
        container.event_bus.emit_sequential(
            Events.UI_SEND_TEXT, {"text": "already selected"}
        )
    )
    try:
        await asyncio.wait_for(entered.wait(), 0.5)
        await plugin.stop()
        await container.event_bus.emit(Events.SYSTEM_NOTICE, "late notice")
        await container.event_bus.emit(Events.NETWORK_ERROR, "late error")
        await container.event_bus.emit(
            Events.DEVICE_STATE_CHANGED,
            {"old_state": DeviceState.SPEAKING, "new_state": DeviceState.IDLE},
        )
        await container.event_bus.emit(
            Events.SESSION_MESSAGE,
            {"type": "tts", "state": "sentence_start", "text": "late text"},
        )
        release.set()
        await asyncio.wait_for(pending, 0.5)
        await container.event_bus.emit(Events.UI_SEND_TEXT, {"text": "after stop"})
        await container.resource_pool.shutdown()
        assert writes_after_close == []
        commands.send_user_text.assert_not_awaited()
        assert container.event_bus.handler_count(Events.NETWORK_ERROR) == 0
        assert container.event_bus.handler_count(Events.UI_SEND_TEXT) == 1
        assert viewport.close_calls == 1
        assert plugin._presenter.viewport is None
    finally:
        release.set()
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await plugin.stop()
        await container.tasks.cancel_all()
