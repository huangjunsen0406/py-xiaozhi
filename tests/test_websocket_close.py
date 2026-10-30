"""Classify WebSocket termination and notify each connection close once."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, Mock

import pytest
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from websockets.frames import Close

from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager

_END = object()


class Socket:
    def __init__(self, code=None, reason="", *, ended=False, error=None, hello=False):
        self.close_code = code
        self.close_reason = reason
        self.close_calls = 0
        self.queue = asyncio.Queue()
        self.error = error
        if hello:
            self.queue.put_nowait(
                json.dumps({"type": "hello", "transport": "websocket"})
            )
        if ended:
            self.queue.put_nowait(_END)

    def __aiter__(self):
        return self

    async def __anext__(self):
        message = await self.queue.get()
        if message is _END:
            if self.error:
                raise self.error
            raise StopAsyncIteration
        return message

    async def send(self, message):
        if self.error:
            raise self.error

    async def close(self):
        self.close_calls += 1
        self.close_code = 1000
        self.close_reason = "client shutdown"
        self.queue.put_nowait(_END)

    def server_close(self, code, reason):
        self.close_code = code
        self.close_reason = reason
        self.queue.put_nowait(_END)


def _protocol(socket):
    protocol = WebsocketProtocol()
    protocol.websocket = socket
    protocol.connected = True
    protocol.on_audio_channel_closed(AsyncMock())
    protocol.on_network_error(AsyncMock())
    protocol.on_connection_state_changed(Mock())
    return protocol


async def _read_to_end(protocol):
    task = asyncio.create_task(protocol._message_handler())
    protocol._message_task = task
    await asyncio.wait_for(task, 1)
    assert not task.cancelled()
    assert protocol._message_task is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "clean"),
    [
        (1000, True),
        (1001, True),
        (1005, True),
        (1006, False),
        (1011, False),
        (None, False),
    ],
)
async def test_normal_iterator_end_classifies_known_status_and_keeps_reason(
    code, clean, caplog
):
    socket = Socket(code, "server finished", ended=True)
    protocol = _protocol(socket)
    protocol.enable_auto_reconnect(True)
    protocol._attempt_reconnect = AsyncMock()
    with caplog.at_level(logging.INFO):
        await _read_to_end(protocol)
    assert not protocol.connected
    assert protocol.websocket is None
    protocol._on_audio_channel_closed.assert_awaited_once_with()
    protocol._on_connection_state_changed.assert_called_once()
    details = protocol.get_connection_info()["last_close"]
    assert details == {
        "code": code,
        "reason": "server finished",
        "clean": clean,
        "local": False,
    }
    assert f"code={code}" in caplog.text
    assert "server finished" in caplog.text
    if clean:
        protocol._on_network_error.assert_not_awaited()
        protocol._attempt_reconnect.assert_not_awaited()
    else:
        protocol._attempt_reconnect.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [1000, 1011, 1006])
async def test_close_exceptions_use_received_status_without_self_cancellation(code):
    if code == 1006:
        error = ConnectionClosedError(None, None)
    else:
        cls = ConnectionClosedOK if code == 1000 else ConnectionClosedError
        error = cls(Close(code, "peer reason"), Close(code, "peer reason"), True)
    socket = Socket(ended=True, error=error)
    protocol = _protocol(socket)
    await _read_to_end(protocol)
    assert protocol.get_connection_info()["last_close"]["code"] == code
    protocol._on_audio_channel_closed.assert_awaited_once_with()
    if code == 1000:
        protocol._on_network_error.assert_not_awaited()
    else:
        protocol._on_network_error.assert_awaited_once()
        assert f"code={code}" in protocol._on_network_error.call_args.args[0]
        if code == 1011:
            assert "peer reason" in protocol._on_network_error.call_args.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [1000, 1011, None])
async def test_monitor_fallback_uses_socket_status_instead_of_generic_failure(
    code, monkeypatch
):
    socket = Socket(code, "monitor saw closure")
    protocol = _protocol(socket)
    monkeypatch.setattr(
        WebsocketProtocol, "_monitor_interval", property(lambda self: 0)
    )
    if code is None:
        # Unknown status must remain a failure if the health check reports loss.
        monkeypatch.setattr(protocol, "_is_connected", lambda: False)
    protocol._start_connection_monitor()
    monitor = protocol._connection_monitor_task
    await asyncio.wait_for(monitor, 1)
    protocol._on_audio_channel_closed.assert_awaited_once_with()
    assert protocol.get_connection_info()["last_close"]["code"] == code
    if code == 1000:
        protocol._on_network_error.assert_not_awaited()
    else:
        protocol._on_network_error.assert_awaited_once()
        assert "monitor saw closure" in protocol._on_network_error.call_args.args[0]


@pytest.mark.asyncio
async def test_reader_send_and_monitor_race_notifies_close_once():
    socket = Socket(1011, "server failure", ended=True)
    protocol = _protocol(socket)
    entered = asyncio.Event()
    release = asyncio.Event()

    async def on_closed():
        entered.set()
        await release.wait()

    protocol._on_audio_channel_closed.side_effect = on_closed
    reader = asyncio.create_task(protocol._message_handler())
    protocol._message_task = reader
    await asyncio.wait_for(entered.wait(), 1)
    contenders = [
        asyncio.create_task(protocol._handle_connection_loss("monitor")),
        asyncio.create_task(protocol.send_text("hello")),
        asyncio.create_task(protocol.close_audio_channel()),
    ]
    release.set()
    await asyncio.wait_for(asyncio.gather(reader, *contenders), 1)
    protocol._on_audio_channel_closed.assert_awaited_once_with()
    protocol._on_network_error.assert_awaited_once()
    assert protocol.get_connection_info()["last_close"]["local"] is False


@pytest.mark.asyncio
async def test_active_close_cancels_reader_without_duplicate_or_network_error():
    socket = Socket()
    protocol = _protocol(socket)
    reader = asyncio.create_task(protocol._message_handler())
    protocol._message_task = reader
    protocol._start_connection_monitor()
    await asyncio.sleep(0)
    await asyncio.wait_for(protocol.close_audio_channel(), 1)
    await protocol.close_audio_channel()
    await protocol.shutdown()
    assert reader.done()
    assert socket.close_calls == 1
    assert protocol.websocket is None
    assert not protocol.connected
    protocol._on_audio_channel_closed.assert_awaited_once_with()
    protocol._on_network_error.assert_not_awaited()
    assert protocol.get_connection_info()["last_close"] == {
        "code": 1000,
        "reason": "client shutdown",
        "clean": True,
        "local": True,
    }


@pytest.mark.asyncio
async def test_new_connection_resets_close_notification_latch(monkeypatch):
    from src.protocols import websocket_protocol as module

    protocol = WebsocketProtocol(
        config=ConfigManager.from_dict(
            {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://test.example"}}}
        )
    )
    sockets = [Socket(hello=True), Socket(hello=True)]
    connect = AsyncMock(side_effect=sockets)
    monkeypatch.setattr(module.websockets, "connect", connect)
    protocol.on_audio_channel_closed(AsyncMock())
    protocol.on_network_error(AsyncMock())
    try:
        for i, socket in enumerate(sockets, 1):
            assert await protocol.connect()
            reader = protocol._message_task
            socket.server_close(1000, f"session {i} done")
            await asyncio.wait_for(reader, 1)
            assert protocol._on_audio_channel_closed.await_count == i
            assert not protocol.connected
        protocol._on_network_error.assert_not_awaited()
    finally:
        await protocol.shutdown()
    assert protocol._on_audio_channel_closed.await_count == 2


@pytest.mark.asyncio
async def test_hello_followed_by_close_does_not_resurrect_connected_flag(monkeypatch):
    from src.protocols import websocket_protocol as module

    protocol = WebsocketProtocol(
        config=ConfigManager.from_dict(
            {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://test.example"}}}
        )
    )
    socket = Socket(1000, "done immediately", hello=True, ended=True)
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(return_value=socket))
    protocol.on_audio_channel_closed(AsyncMock())
    protocol.on_network_error(AsyncMock())
    try:
        assert await asyncio.wait_for(protocol.connect(), 1) is False
        assert not protocol.connected
        assert protocol.websocket is None
        protocol._on_audio_channel_closed.assert_awaited_once_with()
        protocol._on_network_error.assert_not_awaited()
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_late_send_failure_from_old_socket_does_not_close_reconnected_socket(
    monkeypatch,
):
    from src.protocols import websocket_protocol as module

    protocol = WebsocketProtocol(
        config=ConfigManager.from_dict(
            {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://test.example"}}}
        )
    )
    old = Socket(hello=True)
    new = Socket(hello=True)
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(side_effect=[old, new]))
    protocol.on_audio_channel_closed(AsyncMock())
    protocol.on_network_error(AsyncMock())
    entered = asyncio.Event()
    release = asyncio.Event()
    sender = None

    async def fail_after_reconnect(message):
        entered.set()
        await release.wait()
        raise ConnectionClosedError(
            Close(1011, "old failure"), Close(1011, "old failure"), True
        )

    try:
        assert await protocol.connect()
        old.send = fail_after_reconnect
        sender = asyncio.create_task(protocol.send_text("old request"))
        await asyncio.wait_for(entered.wait(), 1)
        reader = protocol._message_task
        old.server_close(1000, "old session done")
        await asyncio.wait_for(reader, 1)
        assert await protocol.connect()
        release.set()
        await asyncio.wait_for(sender, 1)
        assert protocol.websocket is new
        assert protocol.connected
        protocol._on_audio_channel_closed.assert_awaited_once_with()
        protocol._on_network_error.assert_not_awaited()
    finally:
        release.set()
        if sender is not None:
            await asyncio.gather(sender, return_exceptions=True)
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_real_loopback_server_normal_close_finishes_reader_cleanly():
    import websockets

    close_requested = asyncio.Event()

    async def serve_connection(socket):
        hello = json.loads(await socket.recv())
        assert hello["type"] == "hello"
        await socket.send(json.dumps({"type": "hello", "transport": "websocket"}))
        await close_requested.wait()
        await socket.close(code=1000, reason="loopback session complete")

    async with websockets.serve(serve_connection, "127.0.0.1", 0) as server:
        port = server.sockets[0].getsockname()[1]
        protocol = WebsocketProtocol(
            config=ConfigManager.from_dict(
                {
                    "SYSTEM_OPTIONS": {
                        "NETWORK": {"WEBSOCKET_URL": f"ws://127.0.0.1:{port}"}
                    }
                }
            )
        )
        protocol.on_audio_channel_closed(AsyncMock())
        protocol.on_network_error(AsyncMock())
        try:
            assert await asyncio.wait_for(protocol.connect(), 3)
            reader = protocol._message_task
            close_requested.set()
            await asyncio.wait_for(reader, 3)
            assert not reader.cancelled()
            assert not protocol.connected
            assert protocol.websocket is None
            protocol._on_audio_channel_closed.assert_awaited_once_with()
            protocol._on_network_error.assert_not_awaited()
            assert protocol.get_connection_info()["last_close"] == {
                "code": 1000,
                "reason": "loopback session complete",
                "clean": True,
                "local": False,
            }
        finally:
            close_requested.set()
            await protocol.shutdown()
