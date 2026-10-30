"""Control helpers must preserve the transport's accepted/rejected result."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import ListeningMode
from src.core.event_bus import EventBus
from src.core.protocol_manager import ProtocolManager
from src.protocols.protocol import Protocol
from src.protocols.websocket_protocol import WebsocketProtocol

COMMANDS = [
    ("send_start_listening", (ListeningMode.MANUAL,)),
    ("send_stop_listening", ()),
    ("send_abort_speaking", ("user_interruption",)),
    ("send_wake_word_detected", ("hello",)),
    ("send_iot_descriptors", ([{"name": "lamp"}],)),
    ("send_iot_states", ({"on": True},)),
    ("send_mcp_message", ({"id": 1},)),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "args"), COMMANDS)
@pytest.mark.parametrize("accepted", [False, True])
async def test_control_result_survives_base_helper_and_manager(method, args, accepted):
    protocol = Protocol()
    protocol.send_text = AsyncMock(return_value=accepted)
    protocol.is_audio_channel_opened = lambda: True
    manager = ProtocolManager(EventBus())
    manager._protocol = protocol
    assert await getattr(manager, method)(*args) is accepted
    protocol.send_text.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "args"),
    COMMANDS + [("send_text", ("hello",)), ("send_audio", (b"frame",))],
)
async def test_unconfigured_manager_returns_false(method, args):
    assert await getattr(ProtocolManager(EventBus()), method)(*args) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["send_text", "send_audio"])
@pytest.mark.parametrize("accepted", [False, True])
async def test_websocket_transport_returns_bool(method, accepted):
    protocol = WebsocketProtocol()
    if accepted:
        socket = SimpleNamespace(close_code=None, send=AsyncMock())
        protocol.websocket = socket
        protocol.connected = True
    assert (
        await getattr(protocol, method)("hello" if method == "send_text" else b"audio")
        is accepted
    )


@pytest.mark.asyncio
async def test_iot_batch_reports_partial_failure():
    protocol = Protocol()
    protocol.send_text = AsyncMock(side_effect=[False, True])
    assert (
        await protocol.send_iot_descriptors([{"name": "one"}, {"name": "two"}]) is False
    )
    assert protocol.send_text.await_count == 2
    assert await protocol.send_iot_descriptors("bad json") is False
    assert await protocol.send_iot_descriptors({"not": "a list"}) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("accepted", [False, True])
async def test_real_paho_publish_result_reaches_manager(accepted):
    import asyncio

    import paho.mqtt.client as mqtt

    from src.protocols.mqtt_protocol import MqttProtocol

    info = mqtt.MQTTMessageInfo(1)
    info.rc = mqtt.MQTT_ERR_SUCCESS if accepted else mqtt.MQTT_ERR_NO_CONN
    if accepted:
        info._set_as_published()
    protocol = MqttProtocol(asyncio.get_running_loop())
    client = SimpleNamespace(
        publish=lambda *args, **kwargs: info,
        loop_stop=lambda: None,
        disconnect=lambda: None,
    )
    protocol.mqtt_client = client
    protocol.is_audio_channel_opened = lambda: True
    manager = ProtocolManager(EventBus())
    manager._protocol = protocol
    try:
        assert await manager.send_start_listening(ListeningMode.MANUAL) is accepted
        assert await manager.send_stop_listening() is accepted
        assert await manager.send_wake_word_detected("hello") is accepted
        assert await manager.send_abort_speaking() is accepted
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["send_text", "send_audio"])
async def test_websocket_send_failure_is_false(method):
    protocol = WebsocketProtocol()
    protocol.websocket = SimpleNamespace(
        close_code=None, send=AsyncMock(side_effect=OSError("offline"))
    )
    protocol.connected = True
    protocol._handle_connection_loss = AsyncMock()
    assert (
        await getattr(protocol, method)("hello" if method == "send_text" else b"audio")
        is False
    )
    protocol._handle_connection_loss.assert_awaited_once()
