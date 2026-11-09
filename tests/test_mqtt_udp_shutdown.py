"""Real UDP receiver shutdown must not block or outlive its audio session."""

import asyncio
import json
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.protocols.mqtt_protocol import MqttProtocol
from src.utils.config_manager import ConfigManager


class IdleSocket:
    """Closing another thread's socket deliberately does not wake recvfrom."""

    def __init__(self, loop):
        self.loop = loop
        self.receiving = asyncio.Event()
        self.release = threading.Event()
        self.timeout = 0.5
        self.close_count = 0
        self.bound = None

    def bind(self, address):
        self.bound = address

    def settimeout(self, timeout):
        self.timeout = timeout

    def recvfrom(self, size):
        self.loop.call_soon_threadsafe(self.receiving.set)
        self.release.wait(self.timeout)
        raise TimeoutError

    def close(self):
        self.close_count += 1


async def active_protocol(monkeypatch):
    loop = asyncio.get_running_loop()
    sockets = []

    def socket_factory(*args):
        sock = IdleSocket(loop)
        sockets.append(sock)
        return sock

    monkeypatch.setattr("src.protocols.mqtt_udp.socket.socket", socket_factory)
    protocol = MqttProtocol(loop, config=ConfigManager.from_dict())
    protocol.mqtt_client = SimpleNamespace(
        is_connected=lambda: True, loop_stop=Mock(), disconnect=Mock()
    )
    protocol._connect_control_channel = AsyncMock(return_value=True)
    protocol.send_text = AsyncMock(return_value=True)
    protocol._schedule_control_reconnect = Mock()
    protocol._udp.configure("127.0.0.1", 9000, "00" * 16, "00" * 16)
    protocol._udp.start()
    protocol.session_id = "old"
    protocol.connected = True
    await asyncio.wait_for(sockets[0].receiving.wait(), 1)
    return protocol, sockets


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["goodbye", "local", "cleanup", "broker"])
async def test_idle_receiver_shutdown_keeps_loop_responsive_and_waits_for_exit(
    monkeypatch, path
):
    protocol, sockets = await active_protocol(monkeypatch)
    sock = sockets[0]
    receiver = protocol._udp.thread
    client = protocol.mqtt_client
    delivered = Mock()
    protocol.on_incoming_audio(delivered)

    async def on_closed():
        assert not receiver.is_alive()
        assert sock.close_count == 1
        assert protocol._udp.aes_key is None

    closed = AsyncMock(side_effect=on_closed)
    protocol.on_audio_channel_closed(closed)
    methods = {
        "goodbye": protocol._handle_goodbye,
        "local": protocol.close_audio_channel,
        "cleanup": protocol._do_cleanup,
        "broker": lambda: protocol._handle_broker_disconnect("offline"),
    }
    closing = asyncio.create_task(methods[path]())
    # Queue a wakeup behind the close request, then try another late frame while
    # recvfrom is blocked. Neither may reach the already invalidated session.
    protocol._udp._dispatch_audio(b"queued-old-frame")
    loop = asyncio.get_running_loop()
    timer = loop.create_future()
    started = loop.time()
    loop.call_later(0.01, lambda: timer.set_result(loop.time() - started))
    try:
        delay = await asyncio.wait_for(timer, 1)
        assert delay < 0.2, f"10ms timer was delayed to {delay:.3f}s"
        assert not closing.done()
        assert not protocol.connected
        assert protocol.session_id == ""
        assert not protocol.udp_running
        assert receiver.is_alive()
        assert sock.close_count == 0
        assert not protocol.is_audio_channel_opened()
        protocol._udp._dispatch_audio(b"late-old-frame")
        delivered.assert_not_called()
        closed.assert_not_awaited()

        sock.release.set()
        await asyncio.wait_for(closing, 1)
        assert not receiver.is_alive()
        assert protocol._udp.thread is None
        assert protocol.udp_socket is None
        assert sock.close_count == 1
        assert not protocol._udp._audio_queue
        if path == "cleanup":
            closed.assert_not_awaited()
        else:
            closed.assert_awaited_once()
        if path in {"goodbye", "local"}:
            assert protocol.mqtt_client is client
            client.disconnect.assert_not_called()
    finally:
        sock.release.set()
        await asyncio.gather(closing, return_exceptions=True)
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_cancelled_goodbye_still_finishes_cleanup_before_next_hello(monkeypatch):
    protocol, sockets = await active_protocol(monkeypatch)
    old_socket = sockets[0]
    old_receiver = protocol._udp.thread
    client = protocol.mqtt_client
    callback_entered = asyncio.Event()
    finish_callback = asyncio.Event()
    published = []

    async def on_closed():
        assert not old_receiver.is_alive()
        assert old_socket.close_count == 1
        callback_entered.set()
        await finish_callback.wait()

    async def publish(payload):
        message = json.loads(payload)
        published.append(message)
        if message["type"] == "hello":
            assert finish_callback.is_set()
            assert not old_receiver.is_alive()
            protocol._handle_mqtt_message(
                json.dumps(
                    {
                        "type": "hello",
                        "transport": "udp",
                        "session_id": "new",
                        "udp": {
                            "server": "127.0.0.1",
                            "port": 9001,
                            "key": "11" * 16,
                            "nonce": "00" * 16,
                        },
                    }
                )
            )
        return True

    protocol.on_audio_channel_closed(on_closed)
    protocol.send_text = AsyncMock(side_effect=publish)
    closing = asyncio.create_task(protocol._handle_goodbye())
    opening = None
    try:
        await asyncio.sleep(0.01)
        assert not protocol.udp_running
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
        assert not protocol._audio_close_task.cancelled()
        opening = asyncio.create_task(protocol.open_audio_channel())
        await asyncio.sleep(0.01)
        assert not opening.done()
        assert published == []
        assert len(sockets) == 1

        old_socket.release.set()
        await asyncio.wait_for(callback_entered.wait(), 1)
        assert not opening.done()
        assert published == []
        finish_callback.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(closing, 1)
        assert await asyncio.wait_for(opening, 1) is True
        assert protocol.session_id == "new"
        assert protocol._udp.aes_key == "11" * 16
        assert protocol._udp.port == 9001
        assert protocol.is_audio_channel_opened()
        assert len(sockets) == 2
        assert protocol._udp.thread is not old_receiver
        assert protocol.mqtt_client is client
        assert [message["type"] for message in published] == ["hello"]
    finally:
        old_socket.release.set()
        finish_callback.set()
        for sock in sockets:
            sock.release.set()
        await asyncio.gather(
            *[task for task in (closing, opening) if task is not None],
            return_exceptions=True,
        )
        protocol.on_audio_channel_closed(None)
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_repeated_local_close_shares_cleanup_when_one_caller_is_cancelled(
    monkeypatch,
):
    protocol, sockets = await active_protocol(monkeypatch)
    sock = sockets[0]
    receiver = protocol._udp.thread
    reset = Mock(wraps=protocol._udp.reset_session)
    monkeypatch.setattr(protocol._udp, "reset_session", reset)
    closed = AsyncMock()
    protocol.on_audio_channel_closed(closed)
    first = asyncio.create_task(protocol.close_audio_channel())
    second = asyncio.create_task(protocol.close_audio_channel())
    try:
        await asyncio.sleep(0.01)
        first.cancel()
        await asyncio.sleep(0)
        assert not first.done()
        assert not second.done()
        assert protocol._is_closing
        assert receiver.is_alive()
        protocol.send_text.assert_awaited_once_with(
            json.dumps({"type": "goodbye", "session_id": "old"})
        )
        sock.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, 1)
        await asyncio.wait_for(second, 1)
        assert reset.call_count == 1
        assert sock.close_count == 1
        assert not receiver.is_alive()
        assert not protocol._is_closing
        closed.assert_awaited_once()
        await protocol.close_audio_channel()
        closed.assert_awaited_once()
        protocol.send_text.assert_awaited_once()
    finally:
        sock.release.set()
        await asyncio.gather(first, second, return_exceptions=True)
        await protocol.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["reset", "cleanup"])
async def test_cancelled_session_cleanup_waits_for_receiver_and_discards_old_wakeup(
    monkeypatch, path
):
    protocol, sockets = await active_protocol(monkeypatch)
    client = protocol.mqtt_client
    channel = protocol._udp
    receiver = channel.thread
    sock = sockets[0]
    delivered = Mock()
    channel.set_audio_handler(delivered)
    reset = asyncio.create_task(
        channel.reset_session_async() if path == "reset" else protocol._do_cleanup()
    )
    channel._dispatch_audio(b"old")
    try:
        await asyncio.sleep(0.01)
        assert not channel.running
        assert not channel._audio_queue
        reset.cancel()
        await asyncio.sleep(0)
        assert not reset.done()
        assert receiver.is_alive()
        delivered.assert_not_called()
        sock.release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(reset, 1)
        assert not receiver.is_alive()
        assert channel.thread is None
        assert channel.socket is None
        assert channel.server == ""
        assert channel.aes_key is None
        assert sock.close_count == 1
        if path == "cleanup":
            assert protocol.mqtt_client is None
            client.loop_stop.assert_called_once()
            client.disconnect.assert_called_once()
        delivered.assert_not_called()
    finally:
        sock.release.set()
        await asyncio.gather(reset, return_exceptions=True)
        await protocol.shutdown()
