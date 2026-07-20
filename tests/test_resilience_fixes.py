"""验证风险修复：插件失败隔离、TaskManager 堆栈、协议有界音频队列."""

import asyncio
import logging
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolTransport, _INCOMING_AUDIO_QUEUE_SIZE
from src.core.task_manager import TaskManager
from src.plugins.base import Plugin
from src.plugins.manager import PluginManager


class _OkPlugin(Plugin):
    name = "ok"
    priority = 10

    def __init__(self):
        super().__init__()
        self.setup_calls = 0
        self.start_calls = 0
        self.notify_calls = 0

    async def setup(self, ctx, cmd):
        await super().setup(ctx, cmd)
        self.setup_calls += 1

    async def start(self):
        await super().start()
        self.start_calls += 1

    async def on_incoming_json(self, message):
        self.notify_calls += 1


class _BoomPlugin(Plugin):
    name = "boom"
    priority = 5

    async def setup(self, ctx, cmd):
        await super().setup(ctx, cmd)
        raise RuntimeError("boom setup failed")


class _DepPlugin(Plugin):
    name = "dep_user"
    priority = 20
    requires = ["boom"]

    def __init__(self):
        super().__init__()
        self.setup_calls = 0
        self.start_calls = 0

    async def setup(self, ctx, cmd):
        await super().setup(ctx, cmd)
        self.setup_calls += 1

    async def start(self):
        await super().start()
        self.start_calls += 1


@pytest.mark.asyncio
async def test_plugin_manager_marks_failed_and_skips_dependents():
    mgr = PluginManager()
    boom = _BoomPlugin()
    dep = _DepPlugin()
    ok = _OkPlugin()
    mgr.register(boom, dep, ok)

    await mgr.setup_all(ctx=None, cmd=None)
    await mgr.start_all()
    await mgr.notify_incoming_json({"type": "test"})

    assert boom.failed is True
    assert dep.failed is True
    assert dep.setup_calls == 0
    assert dep.start_calls == 0
    assert ok.failed is False
    assert ok.setup_calls == 1
    assert ok.start_calls == 1
    assert ok.notify_calls == 1
    assert "boom" in mgr.failed_plugins()
    assert mgr.is_failed("boom")
    assert not mgr.is_failed("ok")


@pytest.mark.asyncio
async def test_event_bus_isolates_handler_errors(caplog):
    bus = EventBus()
    seen = []

    async def bad(_=None):
        raise ValueError("handler boom")

    async def good(_=None):
        seen.append("ok")

    bus.on(Events.NETWORK_ERROR, bad)
    bus.on(Events.NETWORK_ERROR, good)

    with caplog.at_level(logging.ERROR):
        await bus.emit(Events.NETWORK_ERROR, "net")

    assert seen == ["ok"]
    assert any("handler boom" in r.getMessage() for r in caplog.records)
    # 应带异常信息（exc_info 填充）
    assert any(r.exc_info is not None for r in caplog.records)


@pytest.mark.asyncio
async def test_task_manager_logs_exception_with_traceback(caplog):
    tm = TaskManager()
    tm.initialize()

    async def boom():
        raise RuntimeError("task failed for real")

    with caplog.at_level(logging.ERROR):
        task = tm.spawn(boom(), "unit:boom")
        assert task is not None
        with pytest.raises(RuntimeError):
            await task
        # done callback 异步触发，让出一点
        await asyncio.sleep(0)

    assert any("unit:boom" in r.getMessage() for r in caplog.records)
    # 关键：exc_info 必须绑定到任务异常，而非空 context
    logged = [r for r in caplog.records if "unit:boom" in r.getMessage()]
    assert logged
    assert logged[0].exc_info is not None
    assert logged[0].exc_info[0] is RuntimeError


@pytest.mark.asyncio
async def test_protocol_audio_queue_uses_single_consumer_not_per_frame_tasks():
    bus = EventBus()
    transport = ProtocolTransport(bus)
    received = []

    async def handler(data: bytes):
        received.append(data)
        await asyncio.sleep(0)  # 让出，模拟慢消费

    transport.set_audio_handler(handler)
    # 注入大量帧：不得创建与帧数等量的 pending tasks
    n = _INCOMING_AUDIO_QUEUE_SIZE + 20
    for i in range(n):
        transport._on_incoming_audio(bytes([i % 256]))

    # 等待 consumer 排空（有界队列会丢旧帧，最终 received 有上限）
    for _ in range(50):
        if transport._audio_queue.empty() and len(received) > 0:
            # 再等一轮处理
            await asyncio.sleep(0.01)
            if transport._audio_queue.empty():
                break
        await asyncio.sleep(0.01)

    assert len(received) > 0
    # 队列容量限制：处理数量应不超过 n，且远小于「若 per-frame create_task 会同时挂起 n 个」
    assert len(received) <= n
    # consumer 仅一条
    assert transport._audio_consumer_task is not None

    await transport.disconnect()


@pytest.mark.asyncio
async def test_protocol_json_spawns_via_task_manager():
    bus = EventBus()
    tm = TaskManager()
    tm.initialize()
    transport = ProtocolTransport(bus, task_manager=tm)

    got = []

    async def on_json(data):
        got.append(data)

    bus.on(Events.INCOMING_JSON, on_json)
    transport._on_incoming_json({"type": "hello"})

    # 等待 spawn 的任务
    for _ in range(30):
        if got:
            break
        await asyncio.sleep(0.01)

    assert got == [{"type": "hello"}]
    await tm.cancel_all()


@pytest.mark.asyncio
async def test_plugin_mark_failed_skips_notify_only_for_failed():
    mgr = PluginManager()
    ok = _OkPlugin()
    ok.mark_failed()
    mgr.register(ok)
    await mgr.notify_incoming_json({"x": 1})
    assert ok.notify_calls == 0


def test_constants_import_has_no_config_manager_side_effect(monkeypatch):
    """import constants 不应在模块级拉起 ConfigManager IO."""
    import importlib
    import sys

    # 清掉已加载模块，强制重新 import
    for name in list(sys.modules):
        if name == "src.constants.constants" or name.startswith("src.constants.constants."):
            del sys.modules[name]

    calls = {"n": 0}

    class FakeCM:
        @classmethod
        def get_instance(cls):
            calls["n"] += 1
            raise AssertionError("import 时不应调用 ConfigManager.get_instance")

    monkeypatch.setattr(
        "src.utils.config_manager.ConfigManager", FakeCM, raising=False
    )
    # 重新加载
    import src.constants.constants as constants

    importlib.reload(constants)

    assert calls["n"] == 0
    assert constants.AudioConfig.OUTPUT_SAMPLE_RATE == 24000
    assert constants.DeviceState.IDLE == "idle"


def test_music_player_detach_and_reset():
    from src.mcp.tools.music import music_player as mp_mod

    mp_mod.reset_music_player_instance()
    player = mp_mod.get_music_player_instance()
    player._audio_codec = object()  # type: ignore
    player._event_bus = object()  # type: ignore
    player.detach()
    assert player._audio_codec is None
    assert player._event_bus is None

    mp_mod.reset_music_player_instance()
    assert mp_mod._music_player_instance is None
    # 再取会新建
    p2 = mp_mod.get_music_player_instance()
    assert p2 is not None
    mp_mod.reset_music_player_instance()


def test_music_player_container_bind_lifecycle():
    from src.mcp.tools.music import music_player as mp_mod
    from src.mcp.tools.music.music_player import MusicPlayer

    mp_mod.reset_music_player_instance()
    owned = MusicPlayer()
    mp_mod.bind_music_player(owned)
    assert mp_mod.is_music_player_bound()
    assert mp_mod.get_music_player_instance() is owned

    # 工具侧拿到的就是容器实例
    from src.mcp.tools.music._tools import _player

    assert _player() is owned

    mp_mod.unbind_music_player()
    assert not mp_mod.is_music_player_bound()
    assert mp_mod._music_player_instance is None


def test_mcp_server_detach_and_reset():
    from src.mcp.mcp_server import McpServer

    McpServer.reset_instance()
    server = McpServer.get_instance()
    server.set_send_callback(lambda m: None)
    assert server._send_callback is not None
    server.detach()
    assert server._send_callback is None

    McpServer.reset_instance()
    assert McpServer._instance is None
    # 重建
    s2 = McpServer.get_instance()
    assert s2 is not None
    McpServer.reset_instance()


def test_mcp_server_container_bind_lifecycle():
    from src.mcp.mcp_server import McpServer

    McpServer.reset_instance()
    owned = McpServer()
    McpServer.bind_instance(owned)
    assert McpServer.is_bound()
    assert McpServer.get_instance() is owned

    McpServer.unbind_instance()
    assert not McpServer.is_bound()
    assert McpServer._instance is None


def test_ui_plugin_uses_view_facade_not_main_model():
    """UIPlugin 源码不应再直连 main_model / _emotion_service 私有路径."""
    import inspect

    from src.plugins import ui as ui_mod

    source = inspect.getsource(ui_mod.UIPlugin)
    assert "main_model" not in source
    assert "_emotion_service" not in source
    assert "set_tts_text" in source or "_view_set_tts_text" in source


def test_config_manager_reset_instance():
    from src.utils.config_manager import ConfigManager

    a = ConfigManager.get_instance()
    ConfigManager.reset_instance()
    b = ConfigManager.get_instance()
    assert a is not b
    # 再 reset 避免污染其它测试
    ConfigManager.reset_instance()


@pytest.mark.asyncio
async def test_cli_view_manager_uses_task_manager_for_emit():
    from src.core.event_bus import EventBus, Events
    from src.core.task_manager import TaskManager
    from src.ui.cli.manager import CLIViewManager

    bus = EventBus()
    tm = TaskManager()
    tm.initialize()
    got = []

    async def on_abort(_=None):
        got.append("abort")

    bus.on(Events.UI_ABORT_REQUEST, on_abort)
    vm = CLIViewManager(event_bus=bus, task_manager=tm)
    vm._loop = asyncio.get_running_loop()
    vm._safe_emit(Events.UI_ABORT_REQUEST)

    for _ in range(30):
        if got:
            break
        await asyncio.sleep(0.01)

    assert got == ["abort"]
    await tm.cancel_all()


@pytest.mark.asyncio
async def test_music_player_tick_lyrics_in_playback_path():
    """歌词由主循环 _tick_lyrics 驱动，无独立 lyrics task."""
    from src.mcp.tools.music.music_player import MusicPlayer

    player = MusicPlayer()
    assert not hasattr(player, "_lyrics_task") or player.__dict__.get("_lyrics_task") is None

    emitted = []

    async def fake_emit(text, time_sec=0):
        emitted.append(text)

    player.lyrics = [(0.0, "hello"), (5.0, "world")]
    player.start_play_time = __import__("time").time() - 0.1
    player.total_duration = 100
    player.current_lyric_index = -1
    player._last_lyric_tick = 0.0
    player._emit_lyrics_update = fake_emit  # type: ignore

    await player._tick_lyrics()
    assert player.current_lyric_index == 0
    assert emitted and "hello" in emitted[0]

    # 节流：立即再 tick 不应重复
    n = len(emitted)
    await player._tick_lyrics()
    assert len(emitted) == n


def test_lyric_at_pure_function():
    from src.mcp.tools.music.lyrics import format_lyric_display, lyric_at

    lyrics = [(0.0, "a"), (5.0, "b"), (10.0, "c")]
    assert lyric_at(lyrics, 0.0)[1] == "a"
    # 算法 lead=0.5：在 5.6 时进入 b 句
    assert lyric_at(lyrics, 5.6)[1] == "b"
    assert lyric_at(lyrics, 99.0)[1] == "c"
    assert lyric_at([], 1.0) is None
    assert "[00:01/03:00]" in format_lyric_display("x", 1.0, 180.0)


def test_music_cache_paths(tmp_path):
    from src.mcp.tools.music.cache import MusicCache

    c = MusicCache(root=tmp_path / "music")
    c.prepare()
    p = c.path_for_song("123")
    assert p.parent == c.root
    assert not c.has("123")
    p.write_bytes(b"x")
    assert c.has("123")
    assert c.find_song_file("123") == p


def test_gui_activation_no_ensure_future_or_get_event_loop():
    import inspect
    from src.ui.gui import activation as act_mod

    src = inspect.getsource(act_mod.GUIActivation)
    assert "ensure_future" not in src
    assert "get_event_loop" not in src
    assert "get_running_loop" in src or "create_task" in src


def test_config_manager_batch_update_single_save(tmp_path, monkeypatch):
    """批量 update_configs 只落盘一次."""
    from src.utils.config_manager import ConfigManager

    ConfigManager.reset_instance()
    cm = ConfigManager.get_instance()
    # 指向临时文件，避免污染用户配置
    cm.config_dir = tmp_path
    cm.config_file = tmp_path / "config.json"
    cm._config = {
        "SYSTEM_OPTIONS": {
            "NETWORK": {
                "MQTT_INFO": None,
                "WEBSOCKET_URL": None,
                "WEBSOCKET_ACCESS_TOKEN": None,
            }
        }
    }

    saves = {"n": 0}
    orig = cm._save_config

    def counting_save(cfg):
        saves["n"] += 1
        return orig(cfg)

    monkeypatch.setattr(cm, "_save_config", counting_save)

    ok = cm.update_configs(
        {
            "SYSTEM_OPTIONS.NETWORK.MQTT_INFO": {"host": "x"},
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL": "wss://example",
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN": "tok",
        }
    )
    assert ok is True
    assert saves["n"] == 1
    assert cm.get_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL") == "wss://example"

    # 单次 update 仍会 save
    cm.update_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "tok2")
    assert saves["n"] == 2

    ConfigManager.reset_instance()


def test_music_player_init_is_lazy():
    """MusicPlayer 构造不应立刻扫缓存目录或读满配置副作用路径."""
    from src.mcp.tools.music.music_player import MusicPlayer

    p = MusicPlayer()
    assert p._config is None
    assert p._cache._ready is False
    assert p._cache._temp_cleaned is False
    cfg = p.config
    assert isinstance(cfg, dict)
    assert "SEARCH_URL" in cfg
