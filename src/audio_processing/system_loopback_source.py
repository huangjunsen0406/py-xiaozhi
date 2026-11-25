"""系统级音频回环 AEC 远端参考源（支持异常/设备失效自动无感回退至 SelfFarEndSource）."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import numpy as np

from src.audio_processing.aec_engine import FarEndSource, SelfFarEndSource
from src.logging import get_logger

logger = get_logger()

VALID_AEC_REFERENCE_MODES: tuple[str, ...] = ("self", "system")


def normalize_reference_mode(raw: str | None) -> str:
    """规范化 AEC_OPTIONS.REFERENCE_MODE（仅允许 'self' 或 'system'）."""
    value = str(raw or "self").strip().lower()
    if value in VALID_AEC_REFERENCE_MODES:
        return value
    return "self"


def _import_system_loopback():
    """导入 libs.system_loopback（兼容源码、wheel 与 PyInstaller 布局）."""
    try:
        from libs import system_loopback

        return system_loopback
    except ImportError:
        from src.utils.resource_finder import get_resource_root

        root = str(get_resource_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs import system_loopback

        return system_loopback


class SystemLoopbackFarEndSource:
    """系统级远端参考源：读取整机系统输出回环，设备失效时自动回退至 SelfFarEndSource."""

    def __init__(
        self,
        *,
        far_rate: int,
        target_rate: int,
        target_device_name: str | None = None,
        stream_factory: Callable[[str | None], Any] | None = None,
    ) -> None:
        self._far_rate = int(far_rate)
        self._target_rate = int(target_rate)
        self._target_device_name = target_device_name
        self._closed = False
        self._fallback: SelfFarEndSource | None = None
        self._mode = "system"

        if stream_factory is not None:
            self._stream = stream_factory(target_device_name)
        else:
            mod = _import_system_loopback()
            self._stream = mod.SystemLoopbackStream(target_device_name)

        self._loopback_rate = int(getattr(self._stream, "sample_rate", 48000)) or 48000
        self._resampler = None
        if self._loopback_rate != self._target_rate:
            import soxr

            self._resampler = soxr.ResampleStream(
                self._loopback_rate,
                self._target_rate,
                num_channels=1,
                dtype="float32",
                quality="QQ",
            )

        # 单次 drain 上限（约 200ms 原始采样），避免回环堆积引入过大延迟
        self._max_read_frames = max(1024, int(self._loopback_rate * 0.2))

    @property
    def mode(self) -> str:
        """当前实际生效的远端模式：'system' 或 'self_fallback'."""
        return self._mode

    @property
    def loopback_sample_rate(self) -> int:
        return self._loopback_rate

    def _activate_fallback(self, reason: Exception) -> None:
        if self._fallback is not None:
            return
        logger.warning(
            "系统级 AEC 回环读取异常，已自动回退至本应用参考源 (self): %s", reason
        )
        self._mode = "self_fallback"
        self._resampler = None
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        self._fallback = SelfFarEndSource(
            far_rate=self._far_rate, target_rate=self._target_rate
        )

    def feed_self_output(self, outdata: np.ndarray) -> None:
        """系统回环在位时忽略本进程输出（已含在整机回环中）；回退后喂给 SelfFarEndSource."""
        fallback = self._fallback
        if fallback is not None:
            fallback.feed_self_output(outdata)

    def drain_16k(self) -> np.ndarray:
        if self._closed:
            return np.empty(0, dtype=np.float32)

        fallback = self._fallback
        if fallback is not None:
            return fallback.drain_16k()

        stream = self._stream
        if stream is None:
            return np.empty(0, dtype=np.float32)

        try:
            raw = stream.read_f32(self._max_read_frames)
        except Exception as exc:
            self._activate_fallback(exc)
            return np.empty(0, dtype=np.float32)

        if raw is None or len(raw) == 0:
            return np.empty(0, dtype=np.float32)

        if self._resampler is not None:
            resampled = self._resampler.resample_chunk(raw, last=False)
            return np.asarray(resampled, dtype=np.float32)
        return np.asarray(raw, dtype=np.float32)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._resampler = None
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.close()
            except Exception:
                pass
        fallback = self._fallback
        self._fallback = None
        if fallback is not None:
            try:
                fallback.close()
            except Exception:
                pass


def create_far_end_source(
    reference_mode: str | None,
    *,
    far_rate: int,
    target_rate: int,
    target_device_name: str | None = None,
    stream_factory: Callable[[str | None], Any] | None = None,
) -> tuple[FarEndSource, str]:
    """按配置构建 AEC 远端参考源；请求 system 失败时自动回退至 SelfFarEndSource.

    Returns:
        (far_end_source, actual_mode) 其中 actual_mode 为 'self' / 'system' / 'self_fallback'
    """
    mode = normalize_reference_mode(reference_mode)
    if mode == "system":
        try:
            source = SystemLoopbackFarEndSource(
                far_rate=far_rate,
                target_rate=target_rate,
                target_device_name=target_device_name,
                stream_factory=stream_factory,
            )
            logger.info(
                "系统级 AEC 回环已就绪 | loopback %dHz→%dHz",
                source.loopback_sample_rate,
                target_rate,
            )
            return source, "system"
        except Exception as exc:
            logger.warning(
                "系统级 AEC 回环不可用，自动回退至本应用参考源 (self): %s",
                exc,
            )
            return (
                SelfFarEndSource(far_rate=far_rate, target_rate=target_rate),
                "self_fallback",
            )

    return SelfFarEndSource(far_rate=far_rate, target_rate=target_rate), "self"
