"""应用插件退出、依赖约束和延迟资源创建的回归测试（不访问音频设备）."""

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bootstrap.container import ServiceContainer
from src.bootstrap.health import check_critical_plugins
from src.core.event_bus import EventBus
from src.core.resource_pool import ResourcePool
from src.plugins.base import Plugin
from src.plugins.manager import PluginManager
from src.plugins.wake_word import WakeWordPlugin


class RecordingPlugin(Plugin):
    def __init__(self, name, events, *, requires=(), fail=None):
        super().__init__()
        self.name = name
        self.requires = list(requires)
        self.events = events
        self.fail = fail

    async def setup(self, ctx, cmd):
        await super().setup(ctx, cmd)
        self.events.append((self.name, "setup"))
        if self.fail == "setup":
            raise RuntimeError("setup failed")

    async def start(self):
        await super().start()
        self.events.append((self.name, "start"))
        if self.fail == "start":
            raise RuntimeError("start failed")

    async def stop(self):
        self.events.append((self.name, "stop"))
        await super().stop()
        if self.fail == "stop":
            raise RuntimeError("stop failed")


def make_container(plugins, pool):
    # 只测试退出编排，不构造配置、协议或音频服务。
    container = ServiceContainer.__new__(ServiceContainer)
    container.plugins = plugins
    container.resource_pool = pool
    container._shutting_down = False
    container._mode = "cli"
    return container


def test_duplicate_names_are_rejected_without_partial_registration():
    manager = PluginManager()
    original = RecordingPlugin("audio", [])
    manager.register(original)
    manager.register(original)  # 同一实例保持幂等。
    with pytest.raises(ValueError, match="名称重复"):
        manager.register(RecordingPlugin("new", []), RecordingPlugin("audio", []))
    assert manager.get_plugin("audio") is original
    assert manager.get_plugin("new") is None
    assert manager._plugins == [original]


@pytest.mark.asyncio
async def test_cycles_abort_before_setup_and_cannot_start_afterwards():
    events = []
    manager = PluginManager()
    manager.register(
        RecordingPlugin("audio", events, requires=["ui"]),
        RecordingPlugin("ui", events, requires=["audio"]),
        RecordingPlugin("independent", events),
    )
    with pytest.raises(ValueError, match="循环依赖"):
        await manager.setup_all(None, None)
    await manager.start_all()
    assert events == []
    assert set(manager.failed_plugins()) == {"audio", "ui", "independent"}
    assert "ui" in check_critical_plugins(manager)


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["setup", "start"])
async def test_failed_lifecycle_is_visible_to_health_and_skips_dependents(
    phase, monkeypatch
):
    monkeypatch.delenv("XIAOZHI_DISABLE_AUDIO", raising=False)
    monkeypatch.delenv("XIAOZHI_DEGRADED_AUDIO", raising=False)
    events = []
    audio = RecordingPlugin("audio", events, fail=phase)
    ui = RecordingPlugin("ui", events, requires=["audio"])
    manager = PluginManager()
    manager.register(ui, audio)
    await manager.setup_all(None, None)
    await manager.start_all()
    assert audio.failed and ui.failed
    assert not audio._started
    assert ("ui", "start") not in events
    assert "audio" in check_critical_plugins(manager)
    assert "ui" in check_critical_plugins(manager)


@pytest.mark.asyncio
async def test_container_stops_plugins_in_reverse_order_before_pool_even_if_one_fails():
    events = []
    manager = PluginManager()
    manager.register(
        RecordingPlugin("audio", events),
        RecordingPlugin("ui", events, requires=["audio"], fail="stop"),
    )
    await manager.setup_all(None, None)
    await manager.start_all()
    events.clear()
    pool = ResourcePool()
    pool.register("resources", lambda: events.append(("pool", "shutdown")))
    container = make_container(manager, pool)
    await container.shutdown()
    await container.shutdown()
    assert events == [("ui", "stop"), ("audio", "stop"), ("pool", "shutdown")]


@pytest.mark.asyncio
async def test_container_pool_cleanup_runs_when_stop_all_itself_raises():
    plugins = SimpleNamespace(stop_all=AsyncMock(side_effect=RuntimeError("stop failed")))
    pool = SimpleNamespace(shutdown=AsyncMock())
    container = make_container(plugins, pool)
    await container.shutdown()
    plugins.stop_all.assert_awaited_once()
    pool.shutdown.assert_awaited_once()


class FakeDetector:
    def __init__(self, events, *, fail=None):
        self.events = events
        self.fail = fail

    async def initialize(self):
        self.events.append("initialize")
        return self.fail != "initialize"

    def on_detected(self, callback):
        self.callback = callback

    async def start(self, codec):
        self.events.append("start")
        if self.fail == "exception":
            raise RuntimeError("detector start failed")
        return self.fail != "start"

    async def stop(self):
        self.events.append("stop")

    async def shutdown(self):
        self.events.append("shutdown")
        await self.stop()


async def make_wake_plugin(monkeypatch, events, *, enabled=True, fail=None):
    detector = FakeDetector(events, fail=fail)
    monkeypatch.setitem(
        sys.modules,
        "src.audio_processing.wake_word_detect",
        SimpleNamespace(WakeWordDetector=lambda: detector),
    )
    config = SimpleNamespace(get_config=lambda key, default=None: enabled)
    ctx = SimpleNamespace(event_bus=EventBus(), get_config=lambda: config)
    audio = RecordingPlugin("audio", [])
    audio.codec = object()
    wake = WakeWordPlugin()
    manager = PluginManager()
    manager.register(wake, audio)
    await manager.setup_all(ctx, None)
    pool = ResourcePool()
    # 与真实装配相同：登记资源发生在 start 创建检测器之前。
    wake.register_resources(pool)
    return wake, detector, manager, pool


@pytest.mark.asyncio
async def test_late_created_wake_detector_is_stopped_and_fully_shutdown(monkeypatch):
    events = []
    wake, detector, manager, pool = await make_wake_plugin(monkeypatch, events)
    assert wake.detector is None
    await manager.start_all()
    assert wake.detector is detector
    await make_container(manager, pool).shutdown()
    assert events == ["initialize", "start", "stop", "shutdown", "stop"]
    assert wake.detector is None
    assert not wake.failed
    assert not wake._started


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["initialize", "start", "exception"])
async def test_wake_start_failure_marks_failed_and_releases_partial_detector(
    monkeypatch, failure
):
    events = []
    wake, _, manager, pool = await make_wake_plugin(monkeypatch, events, fail=failure)
    await manager.start_all()
    assert manager.is_failed("wake_word")
    assert wake.detector is None
    assert not wake._started
    assert events[-2:] == ["shutdown", "stop"]
    await pool.shutdown()
    assert events.count("shutdown") == 1


@pytest.mark.asyncio
async def test_disabled_wake_word_is_not_a_start_failure(monkeypatch):
    events = []
    wake, _, manager, pool = await make_wake_plugin(monkeypatch, events, enabled=False)
    await manager.start_all()
    await make_container(manager, pool).shutdown()
    assert events == []
    assert not wake.failed
    assert wake.detector is None


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["registration", "event_bus"])
async def test_mcp_setup_failure_is_visible_and_detaches_server(monkeypatch, phase):
    from src.mcp.mcp_server import McpServer
    from src.plugins.mcp import McpPlugin

    def register(*args):
        if phase == "registration":
            raise RuntimeError("tool registration failed")

    def bind_bus(*args):
        if phase == "event_bus":
            raise RuntimeError("event bus injection failed")

    monkeypatch.setitem(sys.modules, "src.mcp.tools.camera", SimpleNamespace(
        create_camera=lambda: object(), register_camera_tools=register,
    ))
    monkeypatch.setitem(sys.modules, "src.mcp.tools.screenshot", SimpleNamespace(
        register_screenshot_tools=lambda *args: None,
    ))
    server = McpServer()
    monkeypatch.setattr(server, "add_common_tools", lambda **kwargs: None)
    plugin = McpPlugin(server, SimpleNamespace(set_event_bus=bind_bus))
    manager = PluginManager()
    manager.register(plugin)
    await manager.setup_all(SimpleNamespace(event_bus=EventBus()), SimpleNamespace())
    await manager.start_all()
    assert manager.is_failed("mcp")
    assert not plugin._started
    assert server._send_callback is None
