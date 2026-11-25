"""系统级 AEC 远端参考源、动态库加载、自动回退与设置联动单测."""

from __future__ import annotations

import sys

import numpy as np
import pytest

from libs.system_loopback import (
    SystemLoopbackError,
    SystemLoopbackStatus,
    _ensure_library_loaded,
    is_library_available,
)
from src.audio_processing.aec_engine import AecEngine, SelfFarEndSource
from src.audio_processing.system_loopback_source import (
    SystemLoopbackFarEndSource,
    create_far_end_source,
    normalize_reference_mode,
)
from src.utils.config_manager import ConfigManager


class _FakeLoopbackStream:
    """确定性内存回环流，用于验证重采样、排空与设备失效自动回退."""

    def __init__(self, sample_rate: int = 48000, chunks: list[np.ndarray] | None = None):
        self.sample_rate = sample_rate
        self.channels = 1
        self._chunks = list(chunks or [])
        self.fail_on_read: Exception | None = None
        self.closed = False

    def read_f32(self, max_frames: int = 8192) -> np.ndarray:
        if self.fail_on_read is not None:
            raise self.fail_on_read
        if not self._chunks:
            return np.empty(0, dtype=np.float32)
        chunk = self._chunks.pop(0)
        return chunk[:max_frames].astype(np.float32, copy=False)

    def close(self) -> None:
        self.closed = True


def test_normalize_reference_mode():
    assert normalize_reference_mode(None) == "self"
    assert normalize_reference_mode("") == "self"
    assert normalize_reference_mode("self") == "self"
    assert normalize_reference_mode("SYSTEM") == "system"
    assert normalize_reference_mode("  system ") == "system"
    assert normalize_reference_mode("invalid") == "self"


def test_system_loopback_source_resamples_and_ignores_self_output():
    # 48kHz -> 16kHz（4800 样本 = 100ms -> 约 1600 样本）
    tone_48k = np.full(4800, 0.25, dtype=np.float32)
    fake = _FakeLoopbackStream(sample_rate=48000, chunks=[tone_48k])
    src = SystemLoopbackFarEndSource(
        far_rate=48000,
        target_rate=16000,
        stream_factory=lambda _hint: fake,
    )
    try:
        assert src.mode == "system"
        # 在位期间忽略本进程输出，避免双喂
        src.feed_self_output(np.ones((960, 2), dtype=np.float32))
        out = src.drain_16k()
        assert out.dtype == np.float32
        assert len(out) > 1000
        # 接近 0.25 直流，而非 feed_self_output 的 1.0
        assert float(np.mean(out[200:])) == pytest.approx(0.25, abs=0.05)
    finally:
        src.close()
        assert fake.closed


def test_system_loopback_source_passthrough_16k():
    tone_16k = np.linspace(-0.5, 0.5, 320, dtype=np.float32)
    fake = _FakeLoopbackStream(sample_rate=16000, chunks=[tone_16k])
    src = SystemLoopbackFarEndSource(
        far_rate=48000,
        target_rate=16000,
        stream_factory=lambda _hint: fake,
    )
    try:
        out = src.drain_16k()
        assert np.allclose(out, tone_16k)
    finally:
        src.close()


def test_system_loopback_source_auto_fallback_on_device_lost():
    fake = _FakeLoopbackStream(sample_rate=16000)
    fake.fail_on_read = SystemLoopbackError(
        SystemLoopbackStatus.ERR_DEVICE_LOST, "speaker disconnected"
    )
    src = SystemLoopbackFarEndSource(
        far_rate=16000,
        target_rate=16000,
        stream_factory=lambda _hint: fake,
    )
    try:
        assert src.mode == "system"
        # 首次读取触发设备失效 -> 关闭旧流并切换到 SelfFarEndSource
        first = src.drain_16k()
        assert len(first) == 0
        assert src.mode == "self_fallback"
        assert fake.closed

        # 回退后喂入本进程输出，drain_16k 应无缝返回本进程参考音频
        self_pcm = np.full((320, 2), 0.4, dtype=np.float32)
        src.feed_self_output(self_pcm)
        drained = src.drain_16k()
        assert len(drained) == 320
        assert np.allclose(drained, 0.4)
    finally:
        src.close()


def test_create_far_end_source_modes_and_fallback():
    src_self, mode_self = create_far_end_source(
        "self", far_rate=48000, target_rate=16000
    )
    assert isinstance(src_self, SelfFarEndSource)
    assert mode_self == "self"
    src_self.close()

    def _ok_factory(_hint):
        return _FakeLoopbackStream(sample_rate=48000)

    src_sys, mode_sys = create_far_end_source(
        "system",
        far_rate=48000,
        target_rate=16000,
        stream_factory=_ok_factory,
    )
    assert isinstance(src_sys, SystemLoopbackFarEndSource)
    assert mode_sys == "system"
    src_sys.close()

    def _denied_factory(_hint):
        raise SystemLoopbackError(
            SystemLoopbackStatus.ERR_PERMISSION_DENIED, "permission denied"
        )

    src_fb, mode_fb = create_far_end_source(
        "system",
        far_rate=48000,
        target_rate=16000,
        stream_factory=_denied_factory,
    )
    assert isinstance(src_fb, SelfFarEndSource)
    assert mode_fb == "self_fallback"
    src_fb.close()


def test_aec_engine_reports_far_end_mode_with_system_source():
    fake = _FakeLoopbackStream(
        sample_rate=16000,
        chunks=[np.zeros(320, dtype=np.float32)],
    )
    far_src = SystemLoopbackFarEndSource(
        far_rate=16000,
        target_rate=16000,
        stream_factory=lambda _hint: fake,
    )
    engine = AecEngine(
        near_rate=16000,
        far_rate=16000,
        delay_ms=60,
        enable_preprocess=True,
        far_end_source=far_src,
    )
    try:
        if not engine.active:
            pytest.skip("webrtc_apm native library unavailable on this platform")
        assert engine.far_end_mode == "system"
        out = engine.process_near(np.zeros(320, dtype=np.float32))
        assert out.shape == (320,)

        # 运行中设备失效后，AecEngine.far_end_mode 同步反映 self_fallback
        fake.fail_on_read = SystemLoopbackError(
            SystemLoopbackStatus.ERR_DEVICE_LOST, "lost"
        )
        engine.process_near(np.zeros(320, dtype=np.float32))
        assert engine.far_end_mode == "self_fallback"
    finally:
        engine.close()
        assert engine.far_end_mode == "off"


def test_config_and_tui_settings_include_reference_mode():
    cfg = ConfigManager.from_dict()
    assert cfg.get_config("AEC_OPTIONS.REFERENCE_MODE") == "self"

    from src.ui.tui.settings_data import SETTING_SECTIONS

    fields = {f.path: f for _, items in SETTING_SECTIONS for f in items}
    field = fields["AEC_OPTIONS.REFERENCE_MODE"]
    assert field.kind == "choice"
    assert field.choices == ("self", "system")
    assert field.effect == "hot"


def test_audio_plugin_tracks_aec_reference_mode_for_hot_reload():
    from src.plugins.audio import AudioPlugin

    cfg = ConfigManager.from_dict()

    class _FakeCtx:
        def get_config(self):
            return cfg

    plugin = AudioPlugin()
    plugin._ctx = _FakeCtx()
    snap1 = plugin._audio_settings()
    assert snap1["aec"]["REFERENCE_MODE"] == "self"

    cfg.update_config("AEC_OPTIONS.REFERENCE_MODE", "system")
    snap2 = plugin._audio_settings()
    assert snap2["aec"]["REFERENCE_MODE"] == "system"
    assert snap2 != snap1


def test_audio_codec_setup_aec_with_real_device_config(monkeypatch):
    """回归：AudioCodec._setup_aec 使用真实 DeviceConfig 不应访问不存在属性."""
    from src.audio_codecs.audio_codec import AudioCodec
    from src.audio_processing import system_loopback_source as sls
    from src.utils.audio_device import DeviceConfig

    cfg = ConfigManager.from_dict()
    cfg.update_config("AEC_OPTIONS.ENABLED", True)
    cfg.update_config("AEC_OPTIONS.REFERENCE_MODE", "system")
    cfg.update_config("AUDIO_DEVICES.output_device_name", "Test Speaker")

    captured: dict = {}

    def _fake_create(mode, *, far_rate, target_rate, target_device_name=None):
        captured["mode"] = mode
        captured["target_device_name"] = target_device_name
        return SelfFarEndSource(far_rate=far_rate, target_rate=target_rate), "self_fallback"

    monkeypatch.setattr(sls, "create_far_end_source", _fake_create)

    codec = AudioCodec(config=cfg)
    codec.device_config = DeviceConfig(
        input_device_id=0,
        output_device_id=1,
        input_sample_rate=48000,
        output_sample_rate=48000,
        input_channels=1,
        output_channels=2,
        input_frame_size=960,
        output_frame_size=960,
    )
    try:
        codec._setup_aec()
        assert captured == {"mode": "system", "target_device_name": "Test Speaker"}
        if codec.aec_active:
            assert codec.aec_reference_mode == "self_fallback"
    finally:
        codec._is_closing = True
        if codec._aec is not None:
            codec._aec.close()


def test_aec_engine_near_delay_fifo_and_startup_preroll_trim():
    """系统回环启动积压超过 1 个采集块时应裁剪，且 near_delay_ms 应保持输出长度不变."""
    # 启动前积压 200ms（3200 样本），首块 mic 仅 60ms（960 样本）
    fake = _FakeLoopbackStream(
        sample_rate=16000,
        chunks=[np.zeros(3200, dtype=np.float32)],
    )
    far_src = SystemLoopbackFarEndSource(
        far_rate=16000,
        target_rate=16000,
        stream_factory=lambda _hint: fake,
    )
    engine = AecEngine(
        near_rate=16000,
        far_rate=16000,
        delay_ms=80,
        enable_preprocess=False,
        far_end_source=far_src,
        near_delay_ms=100,
    )
    try:
        if not engine.active:
            pytest.skip("webrtc_apm native library unavailable on this platform")
        out = engine.process_near(np.zeros(960, dtype=np.float32))
        assert out.shape == (960,)
        # 首块裁剪为 <=960 样本并被 6 帧 10ms 消耗完，不应残留 200ms 积压
        assert len(engine._far_buffer) < 320
    finally:
        engine.close()


def test_native_system_loopback_library_loads_when_present():
    if sys.platform == "darwin":
        assert is_library_available(), "macOS system_loopback dylib should be built"
    if not is_library_available():
        pytest.skip("Native system_loopback library not compiled on this host")
    lib = _ensure_library_loaded()
    for sym in (
        "slb_create",
        "slb_start",
        "slb_read_f32",
        "slb_last_error",
        "slb_stop",
        "slb_destroy",
    ):
        assert hasattr(lib, sym), f"Missing exported symbol {sym}"
    assert lib.slb_last_error(None) == b""
