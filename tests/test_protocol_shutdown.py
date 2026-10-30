import pytest

from src.protocols.protocol import Protocol


class _ShutdownProbeProtocol(Protocol):
    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    async def close_audio_channel(self):
        self.calls.append("close_audio_channel")

    async def _shutdown_control_channel(self):
        self.calls.append("shutdown_control_channel")


@pytest.mark.asyncio
async def test_protocol_shutdown_closes_session_before_control_channel():
    protocol = _ShutdownProbeProtocol()

    await protocol.shutdown()

    assert protocol.calls == ["close_audio_channel", "shutdown_control_channel"]


class _FakeWebSocket:
    def __init__(self):
        self.close_code = None
        self.close_calls = 0

    async def close(self):
        self.close_calls += 1
        self.close_code = 1000


@pytest.mark.asyncio
async def test_websocket_shutdown_uses_base_lifecycle(monkeypatch):
    from src.protocols import websocket_protocol as websocket_module

    class _Config:
        def get_config(self, key, default=None):
            return {
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL": "wss://example.test",
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN": "test-token",
                "SYSTEM_OPTIONS.DEVICE_ID": "test-device",
                "SYSTEM_OPTIONS.CLIENT_ID": "test-client",
            }.get(key, default)

    protocol = websocket_module.WebsocketProtocol(config=_Config())
    websocket = _FakeWebSocket()
    protocol.websocket = websocket
    protocol.connected = True

    await protocol.shutdown()

    assert websocket.close_calls == 1
    assert protocol.websocket is None
    assert protocol.connected is False
