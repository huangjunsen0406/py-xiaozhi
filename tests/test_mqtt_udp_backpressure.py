"""Bound thread-to-loop ingress before scheduling MQTT UDP audio delivery."""

import asyncio
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.protocols.mqtt_udp import _RX_QUEUE_SIZE, MqttUdpChannel


class StalledLoop:
    def __init__(self):
        self.pending = deque()
        self.scheduled = 0
        self.max_pending = 0

    def call_soon_threadsafe(self, callback, *args):
        self.pending.append((callback, args))
        self.scheduled += 1
        self.max_pending = max(self.max_pending, len(self.pending))

    def drain(self):
        while self.pending:
            callback, args = self.pending.popleft()
            callback(*args)


def _channel(handler):
    loop = StalledLoop()
    channel = MqttUdpChannel(loop)
    channel.set_audio_handler(handler)
    channel.running = True
    return channel, loop


def test_stalled_loop_retains_newest_bounded_frames_with_one_wakeup():
    received = []
    channel, loop = _channel(received.append)
    for frame in range(10000):
        channel._dispatch_audio(str(frame).encode())
    assert len(channel._audio_queue) == _RX_QUEUE_SIZE
    assert len(loop.pending) == 1
    assert loop.scheduled == 1
    loop.drain()
    assert received == [str(i).encode() for i in range(10000 - _RX_QUEUE_SIZE, 10000)]
    assert not channel._audio_queue
    channel._dispatch_audio(b"next")
    assert len(loop.pending) == 1
    loop.drain()
    assert received[-1] == b"next"
    channel.stop()


def test_stop_discards_pending_frames_and_stale_wakeup_cannot_drain_new_session():
    received = []
    channel, loop = _channel(received.append)
    channel._dispatch_audio(b"old")
    channel.stop()
    channel._dispatch_audio(b"after-stop")
    assert len(loop.pending) == 1
    channel.running = True
    channel._dispatch_audio(b"new")
    assert len(loop.pending) == 2
    old_callback, args = loop.pending.popleft()
    old_callback(*args)
    assert received == []
    assert list(channel._audio_queue) == [b"new"]
    loop.drain()
    assert received == [b"new"]
    channel.stop()


def test_continuous_ingress_yields_after_bounded_batch_without_extra_wakeups():
    received = []
    channel, loop = _channel(None)

    def handler(frame):
        received.append(frame)
        if len(received) < 2 * _RX_QUEUE_SIZE:
            channel._dispatch_audio(b"new")

    channel.set_audio_handler(handler)
    channel._dispatch_audio(b"first")
    callback, args = loop.pending.popleft()
    callback(*args)
    assert len(received) == _RX_QUEUE_SIZE
    assert len(loop.pending) == 1
    loop.drain()
    assert len(received) == 2 * _RX_QUEUE_SIZE
    assert loop.max_pending == 1
    channel.stop()


def test_handler_failure_does_not_strand_queue_or_wakeup():
    received = []

    def handler(frame):
        if frame == b"bad":
            raise ValueError("decode failed")
        received.append(frame)

    channel, loop = _channel(handler)
    channel._dispatch_audio(b"bad")
    channel._dispatch_audio(b"good")
    loop.drain()
    assert received == [b"good"]
    channel._dispatch_audio(b"later")
    loop.drain()
    assert received == [b"good", b"later"]
    channel.stop()


def test_closed_loop_drops_pending_frames_and_releases_wakeup_latch():
    channel, loop = _channel(lambda frame: None)
    schedule = loop.call_soon_threadsafe

    def fail(*args):
        raise RuntimeError("event loop is closed")

    loop.call_soon_threadsafe = fail
    channel._dispatch_audio(b"discard")
    assert not channel._audio_queue
    assert not channel._audio_wake_pending
    loop.call_soon_threadsafe = schedule
    channel._dispatch_audio(b"retry")
    assert len(loop.pending) == 1
    loop.drain()
    channel.stop()


@pytest.mark.asyncio
async def test_real_thread_burst_creates_one_loop_wakeup_and_no_per_frame_tasks():
    delivered = []
    channel = MqttUdpChannel(asyncio.get_running_loop())
    channel.running = True
    channel.set_audio_handler(delivered.append)
    baseline = len(asyncio.all_tasks())

    # Wait synchronously so the event loop is deliberately unable to drain.
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(
            lambda: [channel._dispatch_audio(str(i).encode()) for i in range(10000)]
        ).result(timeout=2)
    assert len(channel._audio_queue) == _RX_QUEUE_SIZE
    assert len(asyncio.all_tasks()) == baseline
    await asyncio.sleep(0)
    assert delivered == [str(i).encode() for i in range(10000 - _RX_QUEUE_SIZE, 10000)]
    assert len(asyncio.all_tasks()) == baseline
    channel.stop()
