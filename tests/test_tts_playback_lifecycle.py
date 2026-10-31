"""Real FIFO/Opus regressions without opening a device or network connection."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from src.audio_codecs import audio_codec as codec_module
from src.audio_codecs.audio_codec import AudioCodec
from src.bootstrap.session import ConversationSession
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolManager
from src.core.state_manager import StateManager
from src.plugins.audio import AudioPlugin


def protocol_stub():
    return SimpleNamespace(
        is_audio_channel_opened=lambda: True,
        send_start_listening=AsyncMock(return_value=True),
        send_abort_speaking=AsyncMock(return_value=True),
        send_stop_listening=AsyncMock(return_value=True),
    )


@pytest.fixture
def codec():
    instance = AudioCodec()
    instance.converter.setup_output_converter(24000, 24000, to_channels=1)
    instance.converter.setup_input_converter(16000, 16000, from_channels=1)
    yield instance
    instance._closed = True
    instance.opus_codec.close()
    instance.converter.close()


@pytest.mark.parametrize("keep_listening", [False, True])
@pytest.mark.parametrize("output_rate", [24000, 44100, 48000])
@pytest.mark.asyncio
async def test_normal_stop_retains_tail_and_waits_for_device_output(
    codec, monkeypatch, keep_listening, output_rate
):
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(
        codec_module, "time", SimpleNamespace(monotonic=lambda: clock.now)
    )
    codec.device_config = SimpleNamespace(output_sample_rate=output_rate)
    codec.converter.setup_output_converter(24000, output_rate, to_channels=1)
    bus = EventBus()
    state = StateManager(bus)
    state.set_keep_listening(keep_listening)
    state.set_listening_mode(ListeningMode.AUTO_STOP)
    protocol = protocol_stub()
    session = ConversationSession(state, protocol, audio=codec)
    await session._handle_tts_start()
    codec._tts_fifo.push(np.full(2400, 0.25, dtype=np.float32))
    stopping = asyncio.create_task(
        session._on_incoming_json({"type": "tts", "state": "stop"})
    )
    await asyncio.sleep(0)
    assert codec._tts_fifo.size == 2400
    assert not stopping.done()
    assert not state.should_capture_audio()
    blocks = []
    frames = output_rate // 50
    try:
        for _ in range(8):
            output = np.zeros((frames, 1), dtype=np.float32)
            codec._output_callback(
                output,
                frames,
                SimpleNamespace(outputBufferDacTime=0.1, currentTime=0.0),
                None,
            )
            blocks.append(output.copy())
            clock.now += 0.02
        assert codec._tts_fifo.size == 0
        assert not stopping.done()
        # The samples reach the device; they were not cleared on network EOF.
        assert sum(np.count_nonzero(block > 0.2) for block in blocks) >= int(
            output_rate * 0.099
        )
        protocol.send_start_listening.assert_not_awaited()
        clock.now = 1.0
        await asyncio.wait_for(stopping, 0.2)
        assert state.device_state == (
            DeviceState.LISTENING if keep_listening else DeviceState.IDLE
        )
        assert protocol.send_start_listening.await_count == int(keep_listening)
    finally:
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)


@pytest.mark.asyncio
async def test_abort_discards_queued_and_late_opus_but_accepts_next_first_frame(codec):
    codec.opus_codec.initialize()
    # The decoder is 24 kHz; the encoder is 16 kHz. This is an actual 20 ms packet.
    packet = codec.opus_codec.encode(np.full(320, 0.1, dtype=np.float32), 320)
    bus = EventBus()
    manager = ProtocolManager(bus)
    manager._protocol = protocol_stub()
    plugin = AudioPlugin()
    plugin.codec = codec
    manager.set_audio_handler(plugin.on_incoming_audio)
    state = StateManager(bus)
    session = ConversationSession(state, manager, audio=codec)
    session.bind_events(bus)
    await session._handle_tts_start()
    codec._tts_fifo.push(np.ones(2400, dtype=np.float32))
    manager._on_incoming_audio(packet)
    manager._on_incoming_audio(packet)
    try:
        await session.abort_speaking("user_interruption")
        await manager.wait_for_incoming_audio()
        assert codec._tts_fifo.size == 0
        manager._on_incoming_audio(packet)
        await manager.wait_for_incoming_audio()
        assert codec._tts_fifo.size == 0
        # No await between JSON and binary: start must open the gate before
        # the session's asynchronous JSON handler runs.
        manager._on_incoming_json({"type": "tts", "state": "start"})
        manager._on_incoming_audio(packet)
        await manager.wait_for_incoming_audio()
        assert codec._tts_fifo.size == 480
    finally:
        session.unbind_events()
        await manager._stop_audio_consumer()


@pytest.mark.parametrize("event", ["_on_audio_channel_closed", "_on_network_error"])
@pytest.mark.asyncio
async def test_disconnect_and_error_discard_pcm_and_pending_downlink(codec, event):
    manager = ProtocolManager(EventBus())
    session = ConversationSession(StateManager(EventBus()), manager, audio=codec)
    codec._tts_fifo.push(np.ones(2400, dtype=np.float32))
    manager._enqueue_audio(b"old")
    await getattr(session, event)()
    assert codec._tts_fifo.size == 0
    assert manager._audio_queue.empty()
    await asyncio.wait_for(manager.wait_for_incoming_audio(), 0.1)


@pytest.mark.asyncio
async def test_new_tts_start_is_not_blocked_by_previous_playback_wait(codec):
    bus = EventBus()
    state = StateManager(bus)
    session = ConversationSession(state, protocol_stub(), audio=codec, event_bus=bus)
    await session._handle_tts_start()
    codec._tts_fifo.push(np.ones(2400, dtype=np.float32))
    received = []
    bus.on(Events.SESSION_MESSAGE, lambda message: received.append(message))
    stopping = asyncio.create_task(
        session._on_incoming_json({"type": "tts", "state": "stop"})
    )
    await asyncio.sleep(0)
    try:
        await asyncio.wait_for(
            session._on_incoming_json({"type": "tts", "state": "start"}), 0.1
        )
        assert session._tts_active
        assert state.device_state == DeviceState.SPEAKING
        await asyncio.wait_for(stopping, 0.2)
        assert codec._tts_fifo.size == 2400
        assert session._tts_active
        assert state.device_state == DeviceState.SPEAKING
        assert received == [{"type": "tts", "state": "start"}]
    finally:
        stopping.cancel()
        await asyncio.gather(stopping, return_exceptions=True)


@pytest.mark.parametrize("allow", [False, True])
def test_capture_gate_skips_encoder_but_preserves_pcm_listener_and_aec(codec, allow):
    codec.opus_codec.encode = Mock(return_value=b"opus")
    callback = Mock()
    listener = SimpleNamespace(on_audio_data=Mock())
    codec._aec = SimpleNamespace(
        active=True, process_near=Mock(side_effect=lambda pcm: pcm)
    )
    codec.set_encoded_callback(callback)
    codec.set_encode_gate(lambda: allow)
    codec.add_audio_listener(listener)
    codec._input_callback(np.zeros((320, 1), dtype=np.float32), 320, None, None)
    assert codec.opus_codec.encode.call_count == int(allow)
    assert callback.call_count == int(allow)
    codec._aec.process_near.assert_called_once()
    listener.on_audio_data.assert_called_once()


@pytest.mark.parametrize("rate", [44100, 48000])
@pytest.mark.asyncio
async def test_abort_resets_delayed_resampler_output(codec, rate):
    codec.converter.setup_output_converter(24000, rate)
    codec.converter.convert_output(np.ones(480, dtype=np.float32), rate)
    await codec.clear_audio_queue()
    output = codec.converter.convert_output(np.zeros(480, dtype=np.float32), 1)
    assert output is not None
    assert not np.any(output)


@pytest.mark.asyncio
async def test_duplicate_stop_does_not_publish_completion_before_playback(codec):
    bus = EventBus()
    session = ConversationSession(
        StateManager(bus), protocol_stub(), audio=codec, event_bus=bus
    )
    await session._handle_tts_start()
    codec._tts_fifo.push(np.ones(480, dtype=np.float32))
    received = []
    bus.on(Events.SESSION_MESSAGE, lambda message: received.append(message))
    first = asyncio.create_task(
        session._on_incoming_json({"type": "tts", "state": "stop"})
    )
    await asyncio.sleep(0)
    try:
        await session._on_incoming_json({"type": "tts", "state": "stop"})
        assert received == []
        assert not first.done()
        await codec.clear_audio_queue()
        await asyncio.wait_for(first, 0.2)
        assert received == [{"type": "tts", "state": "stop"}]
    finally:
        first.cancel()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_stopping_consumer_cannot_lose_stop_when_queue_is_discarded():
    manager = ProtocolManager(EventBus())
    manager.set_audio_handler(AsyncMock())
    # The consumer first blocks on get. Stop and discard run on the same loop
    # turn, reproducing the old poison-pill removal race without sleeps.
    await asyncio.sleep(0)
    stopping = asyncio.create_task(manager._stop_audio_consumer())
    asyncio.get_running_loop().call_soon(manager.discard_incoming_audio)
    await asyncio.wait_for(stopping, 0.2)
    await asyncio.wait_for(manager.wait_for_incoming_audio(), 0.2)
    assert manager._audio_consumer_task is None


@pytest.mark.asyncio
async def test_failed_device_reload_releases_existing_playback_waiter(codec):
    codec._tts_fifo.push(np.ones(480, dtype=np.float32))
    codec.stream_manager = SimpleNamespace(stop=lambda: True)
    codec.device_manager.load_or_detect_devices = Mock(side_effect=OSError("unplugged"))
    codec.device_manager.config.reload_config = Mock(return_value=True)
    pending = asyncio.create_task(codec.wait_for_tts_playback())
    await asyncio.sleep(0)
    assert not pending.done()
    assert await codec.reload_devices(reenumerate=False) is False
    await asyncio.wait_for(pending, 0.2)
    assert codec._tts_fifo.size == 0


@pytest.mark.parametrize("rate", [44100, 48000])
def test_single_twenty_ms_packet_preserves_resampled_impulse_tail(
    codec, monkeypatch, rate
):
    import soxr

    # Compare to the identical streaming resampler fed sufficient silence. A
    # pulse in the final samples detects even a 3-4 sample tail left in soxr.
    source = np.zeros(480, dtype=np.float32)
    source[-12:] = np.linspace(0.1, 0.9, 12, dtype=np.float32)
    reference = soxr.ResampleStream(24000, rate, 1, dtype="float32", quality="QQ")
    expected = np.concatenate(
        [
            reference.resample_chunk(source),
            reference.resample_chunk(np.zeros(480, dtype=np.float32)),
        ]
    )
    codec.device_config = SimpleNamespace(output_sample_rate=rate)
    codec.converter.setup_output_converter(24000, rate, to_channels=1)
    codec._tts_fifo.push(source)
    frames = rate // 50
    output = np.zeros((frames, 1), dtype=np.float32)
    codec._output_callback(output, frames, None, None)
    np.testing.assert_allclose(output[:, 0], expected[:frames], atol=1e-7)
    assert codec._tts_fifo.size == 0


@pytest.mark.asyncio
async def test_new_start_during_stop_task_cleanup_keeps_new_reply_active(
    codec, monkeypatch
):
    from src.bootstrap import session as session_module

    bus = EventBus()
    session = ConversationSession(
        StateManager(bus), protocol_stub(), audio=codec, event_bus=bus
    )
    await session._handle_tts_start()
    received = []
    bus.on(Events.SESSION_MESSAGE, lambda message: received.append(message))
    original_gather = asyncio.gather
    interrupted = False

    class AsyncioProxy:
        def __getattr__(self, name):
            return getattr(asyncio, name)

        async def gather(self, *tasks, **kwargs):
            nonlocal interrupted
            result = await original_gather(*tasks, **kwargs)
            if not interrupted and {task.get_name() for task in tasks} == {
                "session:tts_drain",
                "session:tts_changed",
            }:
                interrupted = True
                # Interleave exactly at the cleanup await after successful
                # drain, rather than during playback as in the earlier test.
                await session._on_incoming_json({"type": "tts", "state": "start"})
            return result

    monkeypatch.setattr(session_module, "asyncio", AsyncioProxy())
    await session._on_incoming_json({"type": "tts", "state": "stop"})
    assert interrupted
    assert session._tts_active
    assert session.state.device_state == DeviceState.SPEAKING
    assert received == [{"type": "tts", "state": "start"}]
