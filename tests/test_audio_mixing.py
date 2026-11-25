"""TTS/通知/背景多轨混音回归测试.

覆盖：PcmFifo 采样级语义、AudioMixer 混音/闪避/削波与轨道隔离。
"""

import numpy as np
import pytest

from src.audio_codecs.audio_buffer import PcmFifo
from src.audio_codecs.audio_codec import AudioCodec
from src.audio_codecs.mixer import BACKGROUND_DUCK_GAIN


class TestPcmFifo:
    def test_pull_basic(self):
        f = PcmFifo(1000)
        f.push(np.ones(300, dtype=np.float32))
        out = f.pull(200)
        assert out.shape == (200,)
        assert np.all(out == 1)
        assert f.size == 100

    def test_pull_pads_zeros_when_short(self):
        f = PcmFifo(1000)
        f.push(np.ones(100, dtype=np.float32))
        out = f.pull(200)
        assert np.all(out[:100] == 1)
        assert np.all(out[100:] == 0)
        assert f.size == 0

    def test_pull_with_count_excludes_padding(self):
        f = PcmFifo(1000)
        f.push(np.ones(100, dtype=np.float32))
        out, count = f.pull_with_count(200)
        assert count == 100
        assert np.all(out[:100] == 1)
        assert np.all(out[100:] == 0)

    def test_pull_empty_returns_none(self):
        f = PcmFifo(1000)
        assert f.pull(10) is None

    def test_push_drops_oldest_over_capacity(self):
        f = PcmFifo(1000)
        f.push(np.zeros(600, dtype=np.float32))
        f.push(np.ones(600, dtype=np.float32))
        assert f.size == 1000
        assert f.dropped == 200
        out = f.pull(1000)
        # 最旧的 200 个 0 被丢掉，剩 400 个 0 + 600 个 1
        assert np.all(out[:400] == 0)
        assert np.all(out[400:] == 1)

    def test_clear(self):
        f = PcmFifo(1000)
        f.push(np.ones(500, dtype=np.float32))
        assert f.clear() == 500
        assert f.size == 0
        assert f.pull(10) is None

    def test_multichannel_flattened(self):
        f = PcmFifo(1000)
        f.push(np.ones((100, 2), dtype=np.float32))
        assert f.size == 200


class TestMixing:
    @pytest.fixture()
    def codec(self):
        return AudioCodec()

    def test_background_only_full_gain(self, codec):
        n = codec._mix_chunk
        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
        out = codec.mixer.pull(n).pcm
        assert np.allclose(out, 0.4)

    def test_tts_only(self, codec):
        n = codec._mix_chunk
        codec.mixer.push_tts(np.full(n, 0.5, dtype=np.float32))
        out = codec.mixer.pull(n).pcm
        assert np.allclose(out, 0.5)

    def test_notification_has_voice_priority_and_reports_drain_after_output(
        self, codec
    ):
        n = codec._mix_chunk
        progress = []
        drained = []
        codec.set_notification_playback_callbacks(
            progress.append, lambda: drained.append(True)
        )
        codec.mixer._notification_fifo.push(np.full(n, 0.5, dtype=np.float32))
        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))

        out = codec.mixer.pull(n).pcm
        assert np.allclose(out, 0.5 + BACKGROUND_DUCK_GAIN * 0.4)
        assert progress == [n]

        codec.mixer.pull(n)
        codec.mixer.notify_output_rendered()
        assert drained == []
        codec.mixer.notify_output_rendered()
        assert drained == [True]

    def test_tts_and_background_mixed_with_duck(self, codec):
        n = codec._mix_chunk
        codec.mixer.push_tts(np.full(n, 0.5, dtype=np.float32))
        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
        out = codec.mixer.pull(n).pcm
        assert np.allclose(out, 0.5 + BACKGROUND_DUCK_GAIN * 0.4)

    def test_duck_hangover_then_recover(self, codec):
        n = codec._mix_chunk
        # 一次 TTS 后，背景轨在 hangover 期内仍闪避
        codec.mixer.push_tts(np.full(n, 0.5, dtype=np.float32))
        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
        codec.mixer.pull(n)

        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
        out = codec.mixer.pull(n).pcm
        assert np.allclose(out, BACKGROUND_DUCK_GAIN * 0.4)

        # hangover 耗尽后恢复全量
        for _ in range(15):
            codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
            out = codec.mixer.pull(n).pcm
        assert np.allclose(out, 0.4)

    def test_clip_protection(self, codec):
        n = codec._mix_chunk
        codec.mixer.push_tts(np.full(n, 0.9, dtype=np.float32))
        codec.mixer._background_fifo.push(np.full(n, 0.9, dtype=np.float32))
        out = codec.mixer.pull(n).pcm
        assert out.max() <= 1.0

    def test_both_empty_returns_none(self, codec):
        assert codec.mixer.pull(codec._mix_chunk).pcm is None

    def test_clear_semantics_are_independent(self, codec):
        n = codec._mix_chunk
        codec.mixer.push_tts(np.full(n, 0.5, dtype=np.float32))
        codec.mixer._background_fifo.push(np.full(n, 0.4, dtype=np.float32))
        codec.mixer.clear_track("tts")
        # TTS 清空不影响背景轨
        assert codec.mixer.track_size("background") == n
