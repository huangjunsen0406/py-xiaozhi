"""An unsuccessful protocol open must release only its owned audio session."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolManager
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager


class Socket:
    close_code = None
    close_reason = ""

    def __init__(self, *, hello=False):
        self.messages = asyncio.Queue()
        if hello:
            self.messages.put_nowait(
                json.dumps({"type": "hello", "transport": "websocket"})
            )
        self.sent = asyncio.Event()
        self.close_calls = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.messages.get()

    async def send(self, payload):
        self.sent.set()

    async def close(self):
        self.close_calls += 1
        self.close_code = 1000
        self.close_reason = "closed locally"


def _config():
    return ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://offline.example.test"}}}
    )


def _manager(monkeypatch, sockets):
    from src.protocols import websocket_protocol as module

    monkeypatch.setattr(module.websockets, "connect", AsyncMock(side_effect=sockets))
    manager = ProtocolManager(EventBus(), config=_config())
    manager.set_protocol("websocket")
    return manager


def _assert_wss_released(protocol, socket):
    assert socket.close_calls == 1
    assert protocol.websocket is None
    assert not protocol.connected
    assert protocol._message_task is None
    assert protocol._connection_monitor_task is None


@pytest.mark.asyncio
async def test_manager_hello_timeout_releases_socket_reader_monitor_and_allows_retry(
    monkeypatch,
):
    first = Socket()
    second = Socket(hello=True)
    manager = _manager(monkeypatch, [first, second])
    closed = AsyncMock()
    manager._event_bus.on(Events.AUDIO_CHANNEL_CLOSED, closed)
    try:
        assert await manager.connect(timeout=0.01) is False
        _assert_wss_released(manager.protocol, first)
        closed.assert_awaited_once()
        assert not manager._connect_lock.locked()
        assert await manager.connect(timeout=1) is True
        assert manager.protocol.websocket is second
        assert manager.is_audio_channel_opened()
        await manager.disconnect()
        _assert_wss_released(manager.protocol, second)
        assert closed.await_count == 2
    finally:
        await manager.shutdown()


@pytest.mark.asyncio
async def test_caller_cancelling_manager_open_propagates_after_releasing_attempt(
    monkeypatch,
):
    socket = Socket()
    manager = _manager(monkeypatch, [socket])
    task = asyncio.create_task(manager.connect(timeout=60))
    try:
        await asyncio.wait_for(socket.sent.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        _assert_wss_released(manager.protocol, socket)
        assert not manager._connect_lock.locked()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await manager.shutdown()


@pytest.mark.asyncio
async def test_direct_websocket_cancel_also_releases_reader_and_monitor(monkeypatch):
    from src.protocols import websocket_protocol as module

    socket = Socket()
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(return_value=socket))
    protocol = WebsocketProtocol(config=_config())
    protocol.on_audio_channel_closed(AsyncMock())
    protocol.on_network_error(AsyncMock())
    task = asyncio.create_task(protocol.open_audio_channel())
    try:
        await asyncio.wait_for(socket.sent.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        _assert_wss_released(protocol, socket)
        protocol._on_audio_channel_closed.assert_awaited_once_with()
        protocol._on_network_error.assert_not_awaited()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_websocket_own_hello_timeout_cancels_monitor_too(monkeypatch):
    from src.protocols import websocket_protocol as module

    socket = Socket()
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(return_value=socket))
    original_wait_for = asyncio.wait_for

    async def short_hello_wait(awaitable, timeout):
        return await original_wait_for(awaitable, 0.01 if timeout == 10.0 else timeout)

    monkeypatch.setattr(module.asyncio, "wait_for", short_hello_wait)
    protocol = WebsocketProtocol(config=_config())
    protocol.on_network_error(AsyncMock())
    protocol.on_audio_channel_closed(AsyncMock())
    try:
        assert await protocol.open_audio_channel() is False
        _assert_wss_released(protocol, socket)
        protocol._on_network_error.assert_awaited_once_with("等待响应超时")
        protocol._on_audio_channel_closed.assert_awaited_once_with()
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_cancelled_lock_waiter_does_not_close_other_callers_open(monkeypatch):
    socket = Socket()
    manager = _manager(monkeypatch, [socket])
    active = asyncio.create_task(manager.connect(timeout=60))
    waiter = None
    try:
        await asyncio.wait_for(socket.sent.wait(), 1)
        waiter = asyncio.create_task(manager.connect(timeout=60))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert manager.protocol.websocket is socket
        assert socket.close_calls == 0
        assert not active.done()
        socket.messages.put_nowait(
            json.dumps({"type": "hello", "transport": "websocket"})
        )
        assert await asyncio.wait_for(active, 1) is True
        assert manager.is_audio_channel_opened()
        assert socket.close_calls == 0
    finally:
        active.cancel()
        if waiter is not None:
            waiter.cancel()
        await asyncio.gather(
            *[t for t in (active, waiter) if t is not None], return_exceptions=True
        )
        await manager.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["false", "error", "timeout", "cancel"])
async def test_unsuccessful_mqtt_open_discards_udp_but_preserves_control(
    monkeypatch, outcome
):
    manager = ProtocolManager(EventBus())
    protocol = MqttProtocol(asyncio.get_running_loop())
    manager._protocol = protocol
    client = SimpleNamespace(
        is_connected=lambda: True, loop_stop=Mock(), disconnect=Mock()
    )
    protocol.mqtt_client = client
    ready = {"value": True}
    resets = []

    def reset():
        ready["value"] = False
        resets.append("reset")

    protocol._udp = SimpleNamespace(
        is_ready=lambda: ready["value"], reset_session=reset
    )
    entered = asyncio.Event()
    blocker = asyncio.Event()
    protocol._connect_control_channel = AsyncMock(return_value=True)

    async def partial_udp_open():
        protocol.session_id = "partially-negotiated"
        entered.set()
        if outcome == "false":
            return False
        if outcome == "error":
            raise OSError("handshake failed")
        await blocker.wait()

    monkeypatch.setattr(protocol, "_open_udp_audio_session", partial_udp_open)
    monkeypatch.setattr(protocol, "send_text", AsyncMock(return_value=True))
    task = None
    try:
        if outcome == "cancel":
            task = asyncio.create_task(manager.connect(timeout=60))
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert (
                await manager.connect(timeout=0.01 if outcome == "timeout" else 1)
                is False
            )
        assert resets == ["reset"]
        assert protocol.session_id == ""
        assert protocol.mqtt_client is client
        client.disconnect.assert_not_called()
        client.loop_stop.assert_not_called()
        assert not manager._connect_lock.locked()
    finally:
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await manager.shutdown()


@pytest.mark.asyncio
async def test_successful_open_is_not_rolled_back():
    manager = ProtocolManager(EventBus())
    protocol = SimpleNamespace(
        is_audio_channel_opened=Mock(return_value=False),
        open_audio_channel=AsyncMock(return_value=True),
        close_audio_channel=AsyncMock(),
    )
    manager._protocol = protocol
    assert await manager.connect() is True
    protocol.close_audio_channel.assert_not_awaited()


@pytest.mark.asyncio
async def test_next_open_waits_until_previous_attempt_cleanup_finishes(monkeypatch):
    first_socket = Socket()
    second_socket = Socket(hello=True)
    manager = _manager(monkeypatch, [first_socket, second_socket])
    entered_close = asyncio.Event()
    release_close = asyncio.Event()
    original_close = first_socket.close

    async def blocked_close():
        entered_close.set()
        await release_close.wait()
        await original_close()

    first_socket.close = blocked_close
    first = asyncio.create_task(manager.connect(timeout=0.01))
    second = None
    try:
        await asyncio.wait_for(entered_close.wait(), 1)
        assert manager._connect_lock.locked()
        second = asyncio.create_task(manager.connect(timeout=1))
        await asyncio.sleep(0)
        assert not second.done()
        assert not second_socket.sent.is_set()
        release_close.set()
        assert await asyncio.wait_for(first, 1) is False
        assert await asyncio.wait_for(second, 1) is True
        assert first_socket.close_calls == 1
        assert manager.protocol.websocket is second_socket
        assert second_socket.close_calls == 0
    finally:
        release_close.set()
        tasks = [t for t in (first, second) if t is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await manager.shutdown()


@pytest.mark.asyncio
async def test_websocket_exception_after_starting_tasks_releases_all_resources(
    monkeypatch,
):
    from src.protocols import websocket_protocol as module

    socket = Socket()
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(return_value=socket))
    protocol = WebsocketProtocol(config=_config())
    original_start_monitor = protocol._start_connection_monitor

    def fail_after_start():
        original_start_monitor()
        raise OSError("partial startup failed")

    monkeypatch.setattr(protocol, "_start_connection_monitor", fail_after_start)
    protocol.on_network_error(AsyncMock())
    protocol.on_audio_channel_closed(AsyncMock())
    try:
        assert await protocol.open_audio_channel() is False
        _assert_wss_released(protocol, socket)
        protocol._on_network_error.assert_awaited_once()
        assert "partial startup failed" in protocol._on_network_error.call_args.args[0]
        protocol._on_audio_channel_closed.assert_awaited_once_with()
    finally:
        await protocol.shutdown()


@pytest.mark.asyncio
async def test_hello_on_already_closed_socket_returns_false_after_stopping_tasks(
    monkeypatch,
):
    from src.protocols import websocket_protocol as module

    socket = Socket(hello=True)
    socket.close_code = 1000
    socket.close_reason = "closed during handshake"
    monkeypatch.setattr(module.websockets, "connect", AsyncMock(return_value=socket))
    protocol = WebsocketProtocol(config=_config())
    try:
        assert await protocol.open_audio_channel() is False
        assert protocol.websocket is None
        assert protocol._message_task is None
        assert protocol._connection_monitor_task is None
        assert not protocol.connected
    finally:
        await protocol.shutdown()
