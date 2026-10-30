"""Thread-to-loop microphone backpressure and session invalidation regressions."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bootstrap.session import ConversationSession
from src.constants.constants import AudioConfig, DeviceState, ListeningMode
from src.core.event_bus import EventBus
from src.core.state_manager import StateManager
from src.core.task_manager import TaskManager
from src.plugins.audio import AudioPlugin


@pytest.fixture
async def uplink():
    tasks = TaskManager()
    tasks.initialize()
    ctx = SimpleNamespace(
        audio_config=AudioConfig(),
        audio_generation=0,
        event_bus=EventBus(),
        is_audio_channel_opened=lambda: True,
        should_capture_audio=lambda: True,
    )
    cmd = SimpleNamespace(
        spawn=tasks.spawn,
        sync_audio_state=AsyncMock(return_value=True),
        send_audio=AsyncMock(),
    )
    plugin = AudioPlugin()
    plugin.codec = SimpleNamespace()
    plugin._ctx = ctx
    plugin._cmd = cmd
    await plugin.start()
    try:
        yield plugin, ctx, cmd, tasks
    finally:
        await plugin.stop()
        await tasks.cancel_all()


@pytest.mark.asyncio
async def test_audio_thread_burst_bounds_queue_tasks_and_loop_wakeups(uplink):
    plugin, _ctx, cmd, _tasks = uplink
    started = asyncio.Event()
    release = asyncio.Event()
    sent = []

    async def slow_send(data):
        sent.append(data)
        started.set()
        await release.wait()

    cmd.send_audio.side_effect = slow_send
    loop = asyncio.get_running_loop()
    wakeups = []

    def wake(callback):
        wakeups.append(callback)
        loop.call_soon_threadsafe(callback)

    plugin._loop = SimpleNamespace(call_soon_threadsafe=wake)
    plugin._on_encoded_audio(b"first")
    await asyncio.wait_for(started.wait(), 1)
    consumer = plugin._sender_task

    def burst():
        for index in range(10000):
            plugin._on_encoded_audio(str(index).encode())

    thread = threading.Thread(target=burst)
    thread.start()
    thread.join(timeout=1)
    assert not thread.is_alive()
    assert len(plugin._uplink) == 25
    assert plugin._uplink[0][1] == b"9975"
    assert plugin._uplink[-1][1] == b"9999"
    assert len(wakeups) == 1
    assert plugin._sender_task is consumer
    assert sent == [b"first"]
    release.set()
    # Wait for the consumer itself to reach the last frame.
    finished = asyncio.Event()

    async def finish(data):
        sent.append(data)
        if data == b"9999":
            finished.set()

    cmd.send_audio.side_effect = finish
    await asyncio.wait_for(finished.wait(), 1)
    assert sent == [b"first"] + [str(index).encode() for index in range(9975, 10000)]


@pytest.mark.asyncio
async def test_old_session_frames_are_dropped_after_slow_send(uplink):
    plugin, ctx, cmd, _tasks = uplink
    started = asyncio.Event()
    release = asyncio.Event()
    delivered = asyncio.Event()
    sent = []

    async def send(data):
        sent.append(data)
        if data == b"old-in-flight":
            started.set()
            await release.wait()
        elif data == b"new":
            delivered.set()

    cmd.send_audio.side_effect = send
    plugin._on_encoded_audio(b"old-in-flight")
    await asyncio.wait_for(started.wait(), 1)
    for _ in range(100):
        plugin._on_encoded_audio(b"old-queued")
    ctx.audio_generation += 1
    plugin._on_encoded_audio(b"new")
    release.set()
    await asyncio.wait_for(delivered.wait(), 1)
    assert sent == [b"old-in-flight", b"new"]


@pytest.mark.asyncio
async def test_frame_invalidated_while_aec_state_is_checked_is_not_sent(uplink):
    plugin, ctx, cmd, _tasks = uplink
    checking = asyncio.Event()
    release = asyncio.Event()

    async def sync():
        checking.set()
        await release.wait()
        return True

    cmd.sync_audio_state.side_effect = sync
    checking_frame = asyncio.create_task(plugin._send_audio_async(b"old", 0))
    await checking.wait()
    ctx.audio_generation += 1
    release.set()
    await checking_frame
    cmd.send_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_stopping_cancels_consumer_and_refuses_more_frames(uplink):
    plugin, _ctx, cmd, _tasks = uplink
    consumer = plugin._sender_task
    await plugin.stop()
    plugin._on_encoded_audio(b"after-stop")
    assert not plugin._uplink
    assert consumer.done()
    assert plugin._sender_task is None
    cmd.send_audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_connect_cannot_restart_stopped_recording():
    bus = EventBus()
    state = StateManager(bus)
    connecting = asyncio.Event()
    release = asyncio.Event()

    async def connect():
        connecting.set()
        await release.wait()
        return True

    protocol = SimpleNamespace(
        is_audio_channel_opened=lambda: False,
        connect=connect,
        send_start_listening=AsyncMock(),
        send_stop_listening=AsyncMock(),
    )
    session = ConversationSession(state, protocol)
    starting = asyncio.create_task(session.start_listening(ListeningMode.MANUAL))
    await connecting.wait()
    await session.stop_listening()
    release.set()
    assert await starting is False
    assert state.device_state == DeviceState.IDLE
    protocol.send_start_listening.assert_not_awaited()
