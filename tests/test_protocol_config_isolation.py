"""Per-client protocol configuration and consolidated lifecycle regressions."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus
from src.core.protocol_manager import ProtocolManager
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager


def _config(name, frame_duration):
    return ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {
                "DEVICE_ID": f"device-{name}",
                "CLIENT_ID": f"client-{name}",
                "NETWORK": {
                    "WEBSOCKET_URL": f"wss://{name}.example.test",
                    "WEBSOCKET_ACCESS_TOKEN": f"token-{name}",
                },
            },
            "AUDIO_DEVICES": {"frame_duration": frame_duration},
        }
    )


def test_protocol_construction_needs_no_process_configuration(monkeypatch):
    from src.utils import config_manager

    def forbidden():
        raise AssertionError("protocol must not read process configuration")

    monkeypatch.setattr(config_manager, "get_config", forbidden)
    a = ProtocolManager(EventBus())
    b = ProtocolManager(EventBus())
    w = WebsocketProtocol()
    assert a.config is not b.config
    assert a.audio_config is not b.audio_config
    assert w.config is not a.config
    a.config.update_config("SYSTEM_OPTIONS.DEVICE_ID", "only-a", save=False)
    assert b.config.get_config("SYSTEM_OPTIONS.DEVICE_ID") != "only-a"


@pytest.mark.asyncio
async def test_manager_passes_original_configuration_to_each_protocol():
    source = _config("one", 40)
    audio = AudioConfig.from_config(source)
    manager = ProtocolManager(EventBus(), config=source, audio_config=audio)
    try:
        for protocol_type in ("websocket", "mqtt"):
            manager.set_protocol(protocol_type)
            assert manager.protocol.config is source
            assert manager.protocol.audio_config is audio
            await manager.shutdown()
    finally:
        await manager.shutdown()


class _WebSocket:
    close_code = None

    def __init__(self, protocol):
        self.protocol = protocol
        self.sent = []
        self._closed = asyncio.Event()

    async def send(self, payload):
        self.sent.append(json.loads(payload))
        self.protocol.hello_received.set()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._closed.wait()
        raise StopAsyncIteration

    async def close(self):
        self.close_code = 1000
        self._closed.set()


@pytest.mark.asyncio
async def test_websocket_instances_keep_url_token_and_audio_frames_separate(
    monkeypatch,
):
    from src.protocols import websocket_protocol as module

    first_source = _config("first", 20)
    second_source = _config("second", 60)
    first = WebsocketProtocol(config=first_source)
    second = WebsocketProtocol(config=second_source)
    calls = []
    sockets = []
    current = None

    async def connect(**kwargs):
        calls.append(kwargs)
        socket = _WebSocket(current)
        sockets.append(socket)
        return socket

    monkeypatch.setattr(module.websockets, "connect", connect)
    for protocol in (first, second):
        monkeypatch.setattr(protocol, "_start_connection_monitor", lambda: None)
    try:
        current = first
        assert await first.connect()
        current = second
        assert await second.connect()
        assert [call["uri"] for call in calls] == [
            "wss://first.example.test",
            "wss://second.example.test",
        ]
        assert [call["additional_headers"]["Authorization"] for call in calls] == [
            "Bearer token-first",
            "Bearer token-second",
        ]
        assert [
            socket.sent[0]["audio_params"]["frame_duration"] for socket in sockets
        ] == [20, 60]

        await first.close_audio_channel()
        first_source.update_config(
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "wss://updated.test", save=False
        )
        first_source.update_config(
            "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "updated", save=False
        )
        first.audio_config.FRAME_DURATION = 40
        current = first
        assert await first.connect()
        assert calls[-1]["uri"] == "wss://updated.test"
        assert calls[-1]["additional_headers"]["Authorization"] == "Bearer updated"
        assert sockets[-1].sent[0]["audio_params"]["frame_duration"] == 40
        assert second.audio_config.FRAME_DURATION == 60
        assert second.HEADERS["Authorization"] == "Bearer token-second"
    finally:
        await first.shutdown()
        await second.shutdown()


@pytest.mark.asyncio
async def test_mqtt_default_and_injected_audio_parameters_are_independent(monkeypatch):
    from src.utils import config_manager

    monkeypatch.setattr(
        config_manager, "get_config", lambda: pytest.fail("global config read")
    )
    first = MqttProtocol(asyncio.get_running_loop(), config=_config("first", 20))
    second = MqttProtocol(asyncio.get_running_loop(), config=_config("second", 60))
    default = MqttProtocol(asyncio.get_running_loop())
    sent = []
    for protocol in (first, second, default):

        async def send(payload, owner=protocol):
            sent.append(json.loads(payload))
            owner.server_hello_event.set()
            return True

        monkeypatch.setattr(protocol, "send_text", send)
        monkeypatch.setattr(protocol._udp, "start", lambda: None)
        monkeypatch.setattr(protocol, "_start_connection_monitor", lambda: None)
        assert await protocol._open_udp_audio_session()
    assert [item["audio_params"]["frame_duration"] for item in sent[:2]] == [20, 60]
    assert default.config is not first.config
    assert default.audio_config is not first.audio_config
    for protocol in (first, second, default):
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_manager_serializes_connect_and_honors_timeout():
    manager = ProtocolManager(EventBus())
    opened = False
    calls = 0

    async def open_channel():
        nonlocal opened, calls
        calls += 1
        await asyncio.sleep(0)
        opened = True
        return True

    class Probe:
        open_audio_channel = staticmethod(open_channel)

        def is_audio_channel_opened(self):
            return opened

    manager._protocol = Probe()
    assert await asyncio.gather(manager.connect(), manager.connect()) == [True, True]
    assert calls == 1

    opened = False
    blocked = asyncio.Event()
    manager._protocol.open_audio_channel = blocked.wait
    assert await manager.connect(timeout=0.001) is False
    assert manager._connect_lock.locked() is False


@pytest.mark.asyncio
async def test_manager_preserves_session_control_lifetimes_and_send_gates():
    manager = ProtocolManager(EventBus())

    class Probe:
        opened = False
        close_audio_channel = AsyncMock()
        shutdown = AsyncMock()
        send_audio = AsyncMock()
        send_mcp_message = AsyncMock(return_value=True)

        def is_audio_channel_opened(self):
            return self.opened

    probe = Probe()
    manager._protocol = probe
    await manager.send_audio(b"closed")
    probe.send_audio.assert_not_awaited()
    assert await manager.send_mcp_message("control-before-audio") is True
    probe.opened = True
    await manager.send_audio(b"open")
    probe.send_audio.assert_awaited_once_with(b"open")
    await manager.disconnect()
    probe.close_audio_channel.assert_awaited_once()
    probe.shutdown.assert_not_awaited()
    await manager.shutdown()
    probe.shutdown.assert_awaited_once()
