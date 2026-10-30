"""Connection monitor cleanup must not cancel or await its own task."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from src.protocols.protocol import Protocol


class DisconnectedProtocol(Protocol):
    def __init__(self):
        super().__init__()
        self.connected = True
        self.cleaned = AsyncMock()

    @property
    def _monitor_interval(self):
        return 0

    def _is_connected(self):
        return False

    async def _do_cleanup(self):
        await self.cleaned()


@pytest.mark.asyncio
async def test_monitor_detects_loss_and_finishes_without_cancelling_itself(monkeypatch):
    protocol = DisconnectedProtocol()
    closed = AsyncMock()
    error = AsyncMock()
    protocol.on_audio_channel_closed(closed)
    protocol.on_network_error(error)
    protocol._start_connection_monitor()
    monitor = protocol._connection_monitor_task
    cancel = Mock(wraps=monitor.cancel)
    monkeypatch.setattr(monitor, "cancel", cancel)
    await asyncio.wait_for(monitor, 1)
    assert not protocol.connected
    assert not monitor.cancelled()
    cancel.assert_not_called()
    assert protocol._connection_monitor_task is None
    protocol.cleaned.assert_awaited_once()
    closed.assert_awaited_once()
    error.assert_awaited_once_with("连接丢失: 连接检测失败")


@pytest.mark.asyncio
async def test_external_monitor_cancellation_waits_for_cleanup_and_is_repeatable():
    protocol = DisconnectedProtocol()
    running = asyncio.Event()
    finished = asyncio.Event()

    async def monitor_loop():
        try:
            running.set()
            await asyncio.Event().wait()
        finally:
            finished.set()

    monitor = asyncio.create_task(monitor_loop())
    protocol._connection_monitor_task = monitor
    await running.wait()
    await protocol._cancel_monitor_task()
    assert finished.is_set()
    assert monitor.cancelled()
    assert protocol._connection_monitor_task is None
    await protocol._cancel_monitor_task()
