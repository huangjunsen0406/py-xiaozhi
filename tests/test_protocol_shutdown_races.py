"""Late dial completion cannot resurrect a closed audio session or runtime."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus
from src.core.protocol_manager import ProtocolManager
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager


class Socket:
    close_code = None
    close_reason = ""

    def __init__(self):
        self.close_calls = 0
        self.messages = asyncio.Queue()
        self.messages.put_nowait(
            json.dumps({"type": "hello", "transport": "websocket"})
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.messages.get()

    async def send(self, message):
        pass

    async def close(self):
        self.close_calls += 1
        self.close_code = 1000


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary", ["direct_shutdown", "manager_shutdown", "manager_disconnect"]
)
async def test_closing_during_dial_disposes_late_socket(boundary, monkeypatch):
    from src.protocols import websocket_protocol as module

    entered = asyncio.Event()
    release = asyncio.Event()
    socket = Socket()

    async def dial(*args, **kwargs):
        entered.set()
        await release.wait()
        return socket

    monkeypatch.setattr(module.websockets, "connect", dial)
    config = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://offline.test"}}}
    )
    manager = ProtocolManager(EventBus(), config=config)
    if boundary == "direct_shutdown":
        protocol = WebsocketProtocol(config=config)
        connect = protocol.connect
        close = protocol.shutdown
    else:
        manager.set_protocol("websocket")
        protocol = manager.protocol
        connect = manager.connect
        close = (
            manager.shutdown if boundary == "manager_shutdown" else manager.disconnect
        )
    protocol.on_audio_channel_closed(AsyncMock())
    task = asyncio.create_task(connect())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await close()
        release.set()
        assert await asyncio.wait_for(task, 1) is False
        assert socket.close_calls == 1
        assert protocol.websocket is None
        assert protocol._message_task is None
        assert protocol._connection_monitor_task is None
        assert not protocol.connected
        protocol._on_audio_channel_closed.assert_not_awaited()
        if boundary != "manager_disconnect":
            assert await connect() is False
        else:
            retry_socket = Socket()
            monkeypatch.setattr(
                module.websockets, "connect", AsyncMock(return_value=retry_socket)
            )
            assert await manager.connect() is True
            assert manager.protocol.websocket is retry_socket
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await protocol.shutdown()
        await manager.shutdown()


@pytest.mark.asyncio
async def test_late_dial_close_failure_cannot_clean_replacement(monkeypatch):
    from src.protocols import websocket_protocol as module

    entered = asyncio.Event()
    release = asyncio.Event()
    old = Socket()
    old.close = AsyncMock(side_effect=OSError("old socket close failed"))
    replacement = Socket()
    calls = 0

    async def dial(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            await release.wait()
            return old
        return replacement

    monkeypatch.setattr(module.websockets, "connect", dial)
    config = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"WEBSOCKET_URL": "wss://offline.test"}}}
    )
    protocol = WebsocketProtocol(config=config)
    protocol.on_network_error(AsyncMock())
    first = asyncio.create_task(protocol.connect())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await protocol.close_audio_channel()
        assert await protocol.connect() is True
        release.set()
        assert await asyncio.wait_for(first, 1) is False
        assert protocol.websocket is replacement
        assert protocol.is_audio_channel_opened() is True
        assert replacement.close_calls == 0
        old.close.assert_awaited_once()
        protocol._on_network_error.assert_not_awaited()
    finally:
        release.set()
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)
        await protocol.shutdown()
