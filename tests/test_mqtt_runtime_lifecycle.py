"""MQTT control ownership, worker callbacks and UDP session boundaries."""

import asyncio
import json
import secrets
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import paho.mqtt.client as mqtt
import pytest

from src.core.event_bus import EventBus
from src.core.protocol_manager import ProtocolManager
from src.protocols.mqtt_protocol import MqttProtocol
from src.utils.config_manager import ConfigManager


def config():
    return ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {
                "NETWORK": {
                    "MQTT_INFO": {
                        "endpoint": "localhost:1883",
                        "client_id": "offline",
                        "username": "user",
                        "password": secrets.token_hex(16),
                        "publish_topic": "out",
                        "subscribe_topic": "in",
                    }
                }
            }
        }
    )


@pytest.fixture
def broker(monkeypatch):
    from src.protocols import mqtt_protocol as module

    real_client = mqtt.Client
    clients = []
    acknowledge = {"value": False}
    started = asyncio.Event()

    def factory(**kwargs):
        client = real_client(**kwargs)
        client.connect_async = Mock()
        client.loop_start = Mock(side_effect=lambda: on_start(client))
        client.loop_stop = Mock()
        client.disconnect = Mock()
        client.is_connected = Mock(return_value=False)
        client.subscribe = Mock(return_value=(mqtt.MQTT_ERR_SUCCESS, 1))
        clients.append(client)
        return client

    def on_start(client):
        started.set()
        if acknowledge["value"]:
            ack(client)

    def ack(client):
        client.is_connected.return_value = True
        client.on_connect(client, None, None, 0)

    monkeypatch.setattr(module.mqtt, "Client", factory)
    return SimpleNamespace(
        clients=clients,
        acknowledge=acknowledge,
        started=started,
        ack=ack,
        factory=factory,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_mode", ["caller", "manager_timeout"])
async def test_cancelled_connack_attempt_is_disposed_and_retry_subscribes(
    broker, cancel_mode
):
    manager = ProtocolManager(EventBus(), config=config())
    manager.set_protocol("mqtt")
    protocol = manager.protocol
    task = None
    try:
        if cancel_mode == "caller":
            task = asyncio.create_task(protocol.start())
            await asyncio.wait_for(broker.started.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert await manager.connect(timeout=0.01) is False
        old = broker.clients[0]
        assert protocol.mqtt_client is None
        old.loop_stop.assert_called_once()
        old.disconnect.assert_called_once()
        # A late CONNACK must not resurrect the disposed attempt.
        broker.ack(old)
        await asyncio.sleep(0)
        assert protocol.mqtt_client is None
        broker.acknowledge["value"] = True
        assert await protocol.start() is True
        new = broker.clients[1]
        new.subscribe.assert_called_once_with("in", qos=1)
        assert protocol.mqtt_client is new
        assert await protocol.start() is True
        assert len(broker.clients) == 2
    finally:
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await manager.shutdown()


@pytest.mark.asyncio
async def test_application_control_silence_does_not_disconnect_healthy_broker(broker):
    broker.acknowledge["value"] = True
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    try:
        assert await protocol.start()
        client = protocol.mqtt_client
        protocol._udp.configure(
            server="127.0.0.1", port=9000, aes_key="00" * 16, aes_nonce="00" * 16
        )
        protocol._udp.start()
        protocol.connected = True
        socket = protocol.udp_socket
        protocol._last_activity_time = time.time() - 121
        assert protocol._is_connected() is True
        assert protocol.udp_socket is socket
        assert protocol.is_audio_channel_opened() is True
        client.loop_stop.assert_not_called()
        client.disconnect.assert_not_called()
        assert protocol._control_reconnect_task is None
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_monitor_broker_loss_uses_idle_control_reconnect_policy(broker):
    broker.acknowledge["value"] = True
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    protocol._schedule_control_reconnect = Mock()
    try:
        assert await protocol.start()
        client = protocol.mqtt_client
        client.is_connected.return_value = False
        await protocol._handle_connection_loss("broker disconnected")
        assert protocol.mqtt_client is None
        client.loop_stop.assert_called_once()
        protocol._schedule_control_reconnect.assert_called_once()
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_disconnect_queued_by_old_paho_thread_cannot_stop_replacement(broker):
    broker.acknowledge["value"] = True
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    try:
        assert await protocol.start()
        old = protocol.mqtt_client
        thread = threading.Thread(target=lambda: old.on_disconnect(old, None, 7))
        thread.start()
        thread.join(timeout=1)
        assert not thread.is_alive()
        replacement = broker.factory(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
            client_id="replacement",
        )
        replacement.is_connected.return_value = True
        protocol.mqtt_client = replacement
        protocol._control_ready_client = replacement
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert protocol.mqtt_client is replacement
        replacement.loop_stop.assert_not_called()
        replacement.disconnect.assert_not_called()
        assert protocol._control_reconnect_task is None
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_threaded_hello_followed_by_goodbye_does_not_open_udp(
    broker, monkeypatch
):
    broker.acknowledge["value"] = True
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    hello = {
        "type": "hello",
        "transport": "udp",
        "session_id": "ended",
        "udp": {
            "server": "127.0.0.1",
            "port": 9000,
            "key": "00" * 16,
            "nonce": "00" * 16,
        },
    }
    real_start = protocol._udp.start
    monkeypatch.setattr(protocol._udp, "start", Mock(wraps=real_start))

    async def publish(payload):
        if json.loads(payload)["type"] == "hello":
            client = protocol.mqtt_client

            def deliver():
                for message in (hello, {"type": "goodbye", "session_id": "ended"}):
                    client.on_message(
                        client,
                        None,
                        SimpleNamespace(payload=json.dumps(message).encode()),
                    )

            thread = threading.Thread(target=deliver)
            thread.start()
            thread.join(timeout=1)
            assert not thread.is_alive()
        return True

    monkeypatch.setattr(protocol, "send_text", publish)
    try:
        assert await protocol.open_audio_channel() is False
        await asyncio.sleep(0)
        protocol._udp.start.assert_not_called()
        assert not protocol.connected
        assert not protocol.udp_running
        assert protocol.mqtt_client is not None
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_shutdown_while_connack_pending_cannot_install_late_client(broker):
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    task = asyncio.create_task(protocol.start())
    waiter = None
    try:
        await asyncio.wait_for(broker.started.wait(), 1)
        old = broker.clients[0]
        waiter = asyncio.create_task(protocol.start())
        await asyncio.sleep(0)
        await protocol.shutdown()
        broker.ack(old)
        assert await asyncio.wait_for(task, 1) is False
        assert await asyncio.wait_for(waiter, 1) is False
        assert len(broker.clients) == 1
        assert protocol.mqtt_client is None
        assert await protocol.start() is False
        assert protocol._control_reconnect_task is None
    finally:
        tasks = [task] + ([waiter] if waiter is not None else [])
        for pending in tasks:
            pending.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_shutdown_publishes_goodbye_before_disposing_broker(broker):
    broker.acknowledge["value"] = True
    protocol = MqttProtocol(asyncio.get_running_loop(), config=config())
    assert await protocol.start()
    client = protocol.mqtt_client
    protocol.session_id = "active"
    protocol.connected = True
    published = []

    def publish(topic, payload, **kwargs):
        published.append((json.loads(payload), client.loop_stop.call_count))
        info = mqtt.MQTTMessageInfo(1)
        info.rc = mqtt.MQTT_ERR_SUCCESS
        info._set_as_published()
        return info

    client.publish = publish
    try:
        await protocol.shutdown()
        assert published == [({"type": "goodbye", "session_id": "active"}, 0)]
        client.loop_stop.assert_called_once()
        client.disconnect.assert_called_once()
        assert protocol.mqtt_client is None
        assert await protocol.open_audio_channel() is False
    finally:
        await protocol.shutdown()
