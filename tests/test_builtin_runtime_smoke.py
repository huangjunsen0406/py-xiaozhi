"""Real built-in assembly stays healthy with only device and transport boundaries fake."""

import asyncio
import json
import logging
import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.bootstrap.container import ServiceContainer
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import Events
from src.plugins.shortcuts import ShortcutBackend, ShortcutsPlugin
from src.protocols.protocol import Protocol
from src.utils.config_manager import ConfigManager


class MemoryCodec:
    def __init__(self, *, config, audio_config):
        self.config = config
        self.audio_config = audio_config
        self.aec_active = config.get_config("AEC_OPTIONS.ENABLED")
        self.initialized = 0
        self.closed = 0
        self.reloads = []
        self.encoded_callback = None
        self.incoming_audio = []
        self.audio_received = asyncio.Event()

    async def initialize(self):
        self.initialized += 1

    def set_encoded_callback(self, callback):
        self.encoded_callback = callback

    async def reload_devices(self, *, reenumerate):
        self.reloads.append(reenumerate)
        return True

    async def write_audio(self, data):
        self.incoming_audio.append(data)
        self.audio_received.set()

    async def clear_audio_queue(self):
        pass

    async def close(self):
        self.closed += 1
        self.encoded_callback = None


class MemoryKeyboard(ShortcutBackend):
    def __init__(self, loop):
        super().__init__(loop)
        self.starts = 0
        self.stops = 0

    async def start(self):
        if not self._running:
            self.starts += 1
        self._running = True
        return True

    async def stop(self):
        if self._running:
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


class MemoryViewport:
    def __init__(self):
        self.started = asyncio.Event()
        self.mode_changed = asyncio.Event()
        self.closed = 0
        self.statuses = []
        self.chat = []
        self.music = []
        self.buttons = []
        self.emotions = []
        self.auto_mode = False

    async def start(self, mode):
        self.started.set()
        await asyncio.Event().wait()

    async def close(self):
        self.closed += 1

    def set_status(self, status, connected=True):
        self.statuses.append((status, connected))

    def set_chat_text(self, text):
        self.chat.append(text)

    def set_music_line(self, text):
        self.music.append(text)

    def set_button_text(self, text):
        self.buttons.append(text)

    def set_emotion(self, emotion):
        self.emotions.append(emotion)

    def set_auto_mode(self, auto_mode):
        self.auto_mode = auto_mode
        self.mode_changed.set()


class MemoryTransport(Protocol):
    def __init__(self):
        super().__init__()
        self.ready = asyncio.Event()
        self.opened = False
        self.closed = 0
        self.sent = []

    async def start(self):
        self.ready.set()
        return True

    def is_audio_channel_opened(self):
        return self.opened

    async def open_audio_channel(self):
        self.opened = True
        await self._on_audio_channel_opened()
        return True

    async def close_audio_channel(self):
        if self.opened:
            self.opened = False
            self.closed += 1
            await self._on_audio_channel_closed()

    async def send_text(self, message):
        self.sent.append(json.loads(message))
        return True


@pytest.fixture
def boundaries(monkeypatch, tmp_path):
    for name in (
        "DATA", "CACHE", "LOG", "MUSIC_CACHE", "KEYWORDS"
    ):
        monkeypatch.setenv(f"XIAOZHI_{name}_DIR", str(tmp_path / name.lower()))
    monkeypatch.delenv("XIAOZHI_DISABLE_AUDIO", raising=False)
    from src.utils.resource_finder import clear_path_caches

    clear_path_caches()
    # Cover both the existing top-level alias and the pending lazy native import.
    previous_audio = sys.modules.get("src.plugins.audio")
    native = ModuleType("src.audio_codecs.audio_codec")
    native.AudioCodec = MemoryCodec
    monkeypatch.setitem(sys.modules, native.__name__, native)
    if previous_audio is not None:
        monkeypatch.setattr(previous_audio, "AudioCodec", MemoryCodec, raising=False)

    viewport = MemoryViewport()
    keyboard = MemoryKeyboard(None)
    transport = MemoryTransport()
    monkeypatch.setattr("src.plugins.shortcuts.create_backend", lambda loop: keyboard)
    monkeypatch.setattr("src.plugins.ui.create_viewport", lambda *a, **kw: viewport)
    wire = ModuleType("src.protocols.websocket_protocol")
    wire.WebsocketProtocol = lambda **kwargs: transport
    monkeypatch.setitem(sys.modules, wire.__name__, wire)
    # Real volume tool registration must never probe the host's native mixer.
    from src.mcp.tools.volume.volume_controller import VolumeController

    monkeypatch.setattr(VolumeController, "check_dependencies", lambda: True)
    monkeypatch.setattr(
        VolumeController,
        "_create_backend",
        lambda self: SimpleNamespace(get_volume=lambda: 50, set_volume=lambda value: None),
    )
    try:
        yield SimpleNamespace(viewport=viewport, keyboard=keyboard, transport=transport)
    finally:
        clear_path_caches()
        if previous_audio is None:
            # Do not leave a module containing the fake old-style codec alias behind.
            sys.modules.pop("src.plugins.audio", None)
            import src.plugins

            if hasattr(src.plugins, "audio"):
                del src.plugins.audio


@pytest.mark.asyncio
@pytest.mark.parametrize("aec_active", [False, True], ids=["half_duplex", "aec"])
async def test_builtin_assembly_normal_lifecycle_has_no_error_logs(
    boundaries, tmp_path, caplog, aec_active
):
    caplog.set_level(logging.INFO)
    config = ConfigManager.from_dict(
        {
            "WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False},
            "MCP_PLUGINS": {"ENABLED": False, "DIR": str(tmp_path / "plugins")},
            "AEC_OPTIONS": {"ENABLED": aec_active},
            "AUDIO_DEVICES": {"frame_duration": 20},
        }
    )
    core = ServiceContainer(config)
    before = asyncio.all_tasks()
    runtime = asyncio.create_task(core.run(mode="cli"))
    viewport, keyboard, transport = (
        boundaries.viewport, boundaries.keyboard, boundaries.transport
    )
    try:
        await asyncio.wait_for(transport.ready.wait(), 2)
        await asyncio.wait_for(viewport.started.wait(), 1)
        assert [plugin.name for plugin in core.plugins.plugins] == [
            "audio", "mcp", "wake_word", "ui", "shortcuts"
        ]
        assert core.plugins.failed_plugins() == []
        audio = core.plugins.get_plugin("audio")
        codec = audio.codec
        music, notifications, server = (
            core.music_player, core.notification_player, core.mcp_server
        )
        assert type(codec) is MemoryCodec and codec.initialized == 1
        assert core.session.audio is codec
        assert music._engine.audio_codec is codec
        assert notifications._codec is codec
        assert len(keyboard._shortcuts) == 5 and keyboard.starts == 1
        tool_names = {tool.name for tool in server.tools}
        assert {
            "take_photo", "music_player.get_status", "self.audio_speaker.get_volume"
        } <= tool_names

        codecs = []

        async def observe_codec(value=None):
            codecs.append(value)

        core.event_bus.on(Events.AUDIO_CODEC_CHANGED, observe_codec)
        await core.event_bus.emit(Events.CONFIG_CHANGED)
        assert codecs == [None, codec]
        assert codec.reloads == [True]
        assert core.session.audio is codec
        assert music._engine.audio_codec is codec
        assert notifications._codec is codec
        assert keyboard.starts == 1

        delivered = asyncio.Queue()

        async def observed_message(message):
            delivered.put_nowait(message)

        core.event_bus.on(Events.SESSION_MESSAGE, observed_message)

        async def deliver(message):
            transport._on_incoming_json(message)
            assert await asyncio.wait_for(delivered.get(), 1) is message

        # Exercise the actual UI actions, unified session intent and protocol framing.
        await core.event_bus.emit(Events.UI_BUTTON_PRESS)
        assert core.state.listening_mode == ListeningMode.MANUAL
        assert core.state.device_state == DeviceState.LISTENING
        await core.event_bus.emit(Events.UI_BUTTON_RELEASE)
        assert core.state.device_state == DeviceState.IDLE
        keyboard._run_callback(ShortcutsPlugin.MODE_TOGGLE)
        await asyncio.wait_for(viewport.mode_changed.wait(), 1)
        assert viewport.auto_mode
        await core.event_bus.emit(Events.UI_AUTO_START)
        mode = ListeningMode.REALTIME if aec_active else ListeningMode.AUTO_STOP
        assert core.state.listening_mode == mode and core.state.keep_listening

        await deliver({"type": "stt", "text": "烟测输入"})
        await deliver({"type": "tts", "state": "start"})
        assert core.session.is_speaking()
        assert core.state.device_state == (
            DeviceState.LISTENING if aec_active else DeviceState.SPEAKING
        )
        transport._on_incoming_audio(b"encoded speech")
        await asyncio.wait_for(codec.audio_received.wait(), 1)
        await deliver({"type": "tts", "state": "sentence_start", "text": "烟测回答"})
        await deliver({"type": "tts", "state": "stop"})
        assert core.state.device_state == DeviceState.LISTENING
        assert not core.session.is_speaking()
        assert viewport.chat == ["烟测输入", "烟测回答"]
        assert codec.incoming_audio == [b"encoded speech"]
        assert ("聆听中...", True) in viewport.statuses

        await deliver({
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "music_player.get_status", "arguments": {}},
            },
        })
        responses = [item["payload"] for item in transport.sent if item["type"] == "mcp"]
        assert len(responses) == 1 and responses[0]["id"] == 7
        assert "error" not in responses[0]
        assert not responses[0]["result"].get("isError", False)
        await music.emit_state_change("stopped", "测试歌曲")
        await core.event_bus.emit(Events.NOTIFICATION_SUBTITLE, "通知字幕")
        assert viewport.music[-1] == "已停止: 测试歌曲"
        assert viewport.chat[-1] == "通知字幕"
        await core.event_bus.emit(Events.UI_QUIT_REQUEST)
        assert await asyncio.wait_for(runtime, 2) == 0

        assert codec.closed == 1 and codec.encoded_callback is None
        assert viewport.closed == 1
        assert keyboard.stops == 1 and not keyboard.is_running
        assert transport.closed == 1 and not transport.opened
        assert core.tasks.task_count() == 0 and not core.tasks.running
        assert core.protocol._audio_consumer_task is None
        assert not core.resource_pool._resources
        assert core.session.audio is None
        assert core.session._notification_player is None
        assert music._engine.audio_codec is None and music._bus.event_bus is None
        assert notifications._codec is None and notifications._event_bus is None
        assert server._send_callback is None and server.get_camera() is None
        assert core.mcp_server is core.music_player is core.notification_player is None
        assert all(not handlers for handlers in core.event_bus._handlers.values())
        await asyncio.sleep(0)
        assert not [task for task in asyncio.all_tasks() - before if not task.done()]
        records = caplog.get_records("setup") + caplog.get_records("call")
        assert not [
            record for record in records if record.levelno >= logging.ERROR
        ], caplog.text
    finally:
        core.tasks.request_shutdown()
        await asyncio.wait_for(runtime, 2)
