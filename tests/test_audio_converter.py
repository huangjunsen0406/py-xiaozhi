"""音频转换缓冲与设备重配置的回归测试（不打开音频设备）。"""

from collections import deque
from types import SimpleNamespace

import numpy as np
import pytest

from src.audio_codecs.audio_codec import AudioCodec
from src.audio_codecs.audio_converter import AudioConverter

RATE = 24000
CHUNK = RATE // 50  # 20ms 混音块


@pytest.mark.parametrize("duration_ms", [20, 40, 60])
@pytest.mark.parametrize("channels", [1, 2])
def test_same_rate_output_accumulates_complete_callback(duration_ms, channels):
    converter = AudioConverter()
    converter.setup_output_converter(RATE, RATE, to_channels=channels)
    frames = RATE * duration_ms // 1000
    source = np.arange(frames, dtype=np.float32)

    for start in range(0, frames, CHUNK):
        output = converter.convert_output(source[start : start + CHUNK], frames)
        if start + CHUNK < frames:
            assert output is None

    expected = np.repeat(source[:, None], channels, axis=1)
    np.testing.assert_array_equal(output, expected)
    assert output.dtype == np.float32
    assert converter.drain_output_buffer(frames) is None


@pytest.mark.parametrize("channels", [1, 2])
def test_output_retains_remainder_across_callbacks(channels):
    converter = AudioConverter()
    converter.setup_output_converter(RATE, RATE, to_channels=channels)
    source = np.arange(2 * CHUNK, dtype=np.float32)
    frames = 3 * CHUNK // 4

    first = converter.convert_output(source[:CHUNK], frames)
    second = converter.convert_output(source[CHUNK:], frames)
    tail = converter.drain_output_buffer(frames)

    np.testing.assert_array_equal(first[:, 0], source[:frames])
    np.testing.assert_array_equal(second[:, 0], source[frames : 2 * frames])
    np.testing.assert_array_equal(tail[:, 0], source[2 * frames :])
    for block in (first, second, tail):
        assert block.shape[1] == channels
        np.testing.assert_array_equal(block, np.repeat(block[:, :1], channels, axis=1))
    assert converter.drain_output_buffer(frames) is None


@pytest.mark.parametrize("duration_ms", [20, 40, 60])
@pytest.mark.parametrize("channels", [1, 2])
@pytest.mark.parametrize("partial", [False, True])
def test_output_callback_fills_available_audio(duration_ms, channels, partial):
    converter = AudioConverter()
    converter.setup_output_converter(RATE, RATE, to_channels=channels)
    frames = RATE * duration_ms // 1000
    available = frames // 2 if partial else frames
    source = np.linspace(0.1, 0.8, available, dtype=np.float32)
    chunks = deque(source[i : i + CHUNK] for i in range(0, available, CHUNK))
    codec = SimpleNamespace(
        converter=converter,
        _mix_chunk=CHUNK,
        _pull_mixed=lambda n: chunks.popleft() if chunks else None,
        _aec=None,
        _notify_notification_drained_after_output=lambda: None,
    )
    output = np.full((frames, channels), np.nan, dtype=np.float32)

    AudioCodec._output_callback(codec, output, frames, None, None)

    expected = np.zeros_like(output)
    expected[:available] = source[:, None]
    np.testing.assert_array_equal(output, expected)
    assert converter.drain_output_buffer(frames) is None


def test_output_callback_consumes_remainder_when_queue_exhausted():
    converter = AudioConverter()
    converter.setup_output_converter(RATE, RATE, to_channels=1)
    source = np.linspace(0.1, 0.8, 2 * CHUNK, dtype=np.float32)
    chunks = deque([source[:CHUNK], source[CHUNK:]])
    codec = SimpleNamespace(
        converter=converter,
        _mix_chunk=CHUNK,
        _pull_mixed=lambda n: chunks.popleft() if chunks else None,
        _aec=None,
        _notify_notification_drained_after_output=lambda: None,
    )
    frames = 3 * CHUNK // 4
    outputs = []
    for _ in range(3):
        output = np.full((frames, 1), np.nan, dtype=np.float32)
        AudioCodec._output_callback(codec, output, frames, None, None)
        outputs.append(output[:, 0])

    expected = np.pad(source, (0, 3 * frames - len(source)))
    np.testing.assert_array_equal(np.concatenate(outputs), expected)


@pytest.mark.parametrize("new_rate", [16000, 32000, 48000])
def test_input_reconfiguration_discards_old_resampler_and_buffer(new_rate):
    converter = AudioConverter()
    converter.setup_input_converter(48000, 16000, from_channels=2)
    old_resampler = converter.input_resampler
    old_audio = np.full((4800, 2), 0.75, dtype=np.float32)
    assert converter.convert_input(old_audio, 10000) is None
    assert converter._input_buffer
    converter.setup_output_converter(RATE, 48000, to_channels=2)
    output_resampler = converter.output_resampler
    converter._output_buffer.extend([0.1, 0.2])

    converter.setup_input_converter(new_rate, 16000, from_channels=1)

    assert not converter._input_buffer
    assert converter.input_channels == 1
    assert not converter.needs_input_downmix
    assert converter.input_resampler is not old_resampler
    assert converter.output_resampler is output_resampler
    assert list(converter._output_buffer) == [0.1, 0.2]
    if new_rate == 16000:
        assert converter.input_resampler is None
        source = np.arange(320, dtype=np.float32)
        np.testing.assert_array_equal(converter.convert_input(source, 320), source)
    else:
        assert converter.input_resampler is not None


@pytest.mark.parametrize("new_rate", [24000, 32000, 48000])
def test_output_reconfiguration_discards_old_resampler_and_buffer(new_rate):
    converter = AudioConverter()
    converter.setup_output_converter(RATE, 48000, to_channels=2)
    old_resampler = converter.output_resampler
    assert converter.convert_output(np.ones(CHUNK, dtype=np.float32), 10000) is None
    assert converter._output_buffer
    converter.setup_input_converter(48000, 16000, from_channels=2)
    input_resampler = converter.input_resampler
    converter._input_buffer.extend([0.1, 0.2])

    converter.setup_output_converter(RATE, new_rate, to_channels=1)

    assert not converter._output_buffer
    assert converter.output_channels == 1
    assert not converter.needs_output_upmix
    assert converter.output_resampler is not old_resampler
    assert converter.input_resampler is input_resampler
    assert list(converter._input_buffer) == [0.1, 0.2]
    if new_rate == RATE:
        assert converter.output_resampler is None
        source = np.arange(CHUNK, dtype=np.float32)
        np.testing.assert_array_equal(
            converter.convert_output(source, CHUNK), source[:, None]
        )
    else:
        assert converter.output_resampler is not None


def test_same_rate_reconfiguration_clears_pending_output_and_updates_upmix():
    converter = AudioConverter()
    converter.setup_output_converter(RATE, RATE, to_channels=1)
    assert converter.convert_output(np.ones(CHUNK, dtype=np.float32), 2 * CHUNK) is None

    converter.setup_output_converter(RATE, RATE, to_channels=2)

    assert converter.drain_output_buffer(CHUNK) is None
    source = np.full(CHUNK, 0.25, dtype=np.float32)
    np.testing.assert_array_equal(
        converter.convert_output(source, CHUNK), np.repeat(source[:, None], 2, axis=1)
    )
