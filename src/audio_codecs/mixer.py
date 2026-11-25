"""通用多轨音频混音器（零业务语义）.

按优先级管理输出轨道：
- 前景轨（foreground）：TTS、单向通知等高优先级语音，不闪避。
- 背景轨（background）：任意外部媒体播放流；前景有声时自动闪避（ducking）
  并在帧间隙保持 hangover，避免增益抖动。
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

import numpy as np

from src.audio_codecs.audio_buffer import PcmFifo
from src.logging import get_logger

logger = get_logger()

# 前景语音出现时背景轨的混音增益，以及语音间隙保持块数（每块 20ms）
BACKGROUND_DUCK_GAIN = 0.35
DUCK_HOLD_CHUNKS = 10

# 各轨道 FIFO 容量与背压目标（秒）
TTS_FIFO_MAX_S = 10.0
BACKGROUND_FIFO_MAX_S = 2.0
BACKGROUND_BACKLOG_TARGET_S = 0.30
NOTIFICATION_FIFO_MAX_S = 2.0
NOTIFICATION_BACKLOG_TARGET_S = 0.30


class TrackPriority(str, Enum):
    FOREGROUND = "foreground"
    BACKGROUND = "background"


@dataclass(slots=True)
class MixPullResult:
    """一次混音拉取结果."""

    pcm: np.ndarray | None
    tts_samples: int = 0


class AudioTrackHandle:
    """供上层播放器使用的受限轨道句柄（不暴露底层 AudioCodec/FIFO 细节）."""

    def __init__(
        self,
        mixer: AudioMixer,
        track_name: str,
        *,
        is_closing: Callable[[], bool],
    ) -> None:
        self._mixer = mixer
        self._track_name = track_name
        self._is_closing = is_closing

    @property
    def name(self) -> str:
        return self._track_name

    @property
    def sample_rate(self) -> int:
        return self._mixer.sample_rate

    @property
    def size(self) -> int:
        return self._mixer.track_size(self._track_name)

    async def write_pcm(self, pcm_float32: np.ndarray) -> None:
        await self._mixer.push_with_backpressure(
            self._track_name, pcm_float32, is_closing=self._is_closing
        )

    async def clear(self) -> int:
        return self._mixer.clear_track(self._track_name)


class AudioMixer:
    """多轨 PCM 混音器：前景语音优先，背景轨自动闪避."""

    def __init__(self, sample_rate: int) -> None:
        self._sample_rate = int(sample_rate)
        self._tts_fifo: PcmFifo
        self._notification_fifo: PcmFifo
        self._background_fifo: PcmFifo
        self._duck_hold = 0
        self._notification_had_audio = False
        self._notification_drain_callbacks_remaining = 0
        self._notification_progress_callback: Callable[[int], None] | None = None
        self._notification_drained_callback: Callable[[], None] | None = None
        self.reset(self._sample_rate)

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    def reset(self, sample_rate: int) -> None:
        """采样率变更或管线重建时重置全部轨道缓冲与状态."""
        self._sample_rate = int(sample_rate)
        self._tts_fifo = PcmFifo(int(self._sample_rate * TTS_FIFO_MAX_S))
        self._background_fifo = PcmFifo(
            int(self._sample_rate * BACKGROUND_FIFO_MAX_S)
        )
        self._notification_fifo = PcmFifo(
            int(self._sample_rate * NOTIFICATION_FIFO_MAX_S)
        )
        self._duck_hold = 0
        self._notification_had_audio = False
        self._notification_drain_callbacks_remaining = 0

    def _fifo_and_target(self, track_name: str) -> tuple[PcmFifo, float]:
        if track_name == "tts":
            return self._tts_fifo, 0.0
        if track_name == "background":
            return self._background_fifo, BACKGROUND_BACKLOG_TARGET_S
        if track_name == "notification":
            return self._notification_fifo, NOTIFICATION_BACKLOG_TARGET_S
        raise KeyError(f"Unknown audio track: {track_name}")

    def track_size(self, track_name: str) -> int:
        fifo, _ = self._fifo_and_target(track_name)
        return fifo.size

    def get_track_handle(
        self, track_name: str, *, is_closing: Callable[[], bool]
    ) -> AudioTrackHandle:
        self._fifo_and_target(track_name)
        return AudioTrackHandle(self, track_name, is_closing=is_closing)

    def push_tts(self, pcm_float32: np.ndarray) -> None:
        self._tts_fifo.push(pcm_float32)

    async def push_with_backpressure(
        self,
        track_name: str,
        pcm_float32: np.ndarray,
        *,
        is_closing: Callable[[], bool],
    ) -> None:
        """写入轨道 PCM 并按水位提供解码背压（背压上限 2 秒防死等）."""
        fifo, target_s = self._fifo_and_target(track_name)
        fifo.push(pcm_float32)
        if target_s <= 0:
            return
        target = int(self._sample_rate * target_s)
        for _ in range(100):
            if is_closing() or fifo.size <= target:
                break
            await asyncio.sleep(0.02)

    def set_notification_callbacks(
        self,
        progress_callback: Callable[[int], None] | None = None,
        drained_callback: Callable[[], None] | None = None,
    ) -> None:
        """设置通知轨播放进度/耗尽回调（音频线程触发，须线程安全转发）."""
        self._notification_progress_callback = progress_callback
        self._notification_drained_callback = drained_callback
        self._notification_had_audio = False
        self._notification_drain_callbacks_remaining = 0

    def clear_track(self, track_name: str) -> int:
        fifo, _ = self._fifo_and_target(track_name)
        count = fifo.clear()
        if track_name == "notification":
            self._notification_had_audio = False
            self._notification_drain_callbacks_remaining = 0
        return count

    def clear_all(self) -> int:
        return (
            self.clear_track("tts")
            + self.clear_track("background")
            + self.clear_track("notification")
        )

    def pull(self, n: int, *, flush_silence: bool = False) -> MixPullResult:
        """输出回调线程：拉取各轨道 n 样本并按优先级混音."""
        tts = self._tts_fifo.pull(n)
        tts_samples = n if tts is not None else 0
        notification, notification_samples = self._notification_fifo.pull_with_count(n)
        background = self._background_fifo.pull(n)

        if notification is not None:
            self._notification_had_audio = True
            self._notification_drain_callbacks_remaining = 0
            callback = self._notification_progress_callback
            if callback and notification_samples:
                try:
                    callback(notification_samples)
                except Exception as exc:
                    logger.debug(f"通知播放进度回调失败: {exc}", exc_info=True)
        elif self._notification_had_audio:
            self._notification_had_audio = False
            # converter 可能仍保有上一块重采样余量，等两次设备回调后再报告耗尽。
            self._notification_drain_callbacks_remaining = 2

        if tts is None and notification is None and background is None:
            if flush_silence:
                return MixPullResult(np.zeros(n, dtype=np.float32), 0)
            return MixPullResult(None, 0)

        if tts is not None or notification is not None:
            self._duck_hold = DUCK_HOLD_CHUNKS
        elif self._duck_hold > 0:
            self._duck_hold -= 1

        voice = tts
        if notification is not None:
            if voice is None:
                voice = notification
            else:
                voice = np.clip(voice + notification, -1.0, 1.0)

        if background is None:
            return MixPullResult(voice, tts_samples)
        if voice is None:
            if self._duck_hold > 0:
                background *= BACKGROUND_DUCK_GAIN
            return MixPullResult(background, tts_samples)
        return MixPullResult(
            np.clip(voice + background * BACKGROUND_DUCK_GAIN, -1.0, 1.0),
            tts_samples,
        )

    def notify_output_rendered(self) -> None:
        """设备写出输出缓冲后推进通知轨耗尽计数."""
        if self._notification_drain_callbacks_remaining <= 0:
            return
        self._notification_drain_callbacks_remaining -= 1
        if self._notification_drain_callbacks_remaining > 0:
            return
        callback = self._notification_drained_callback
        if callback:
            try:
                callback()
            except Exception as exc:
                logger.debug(f"通知播放完成回调失败: {exc}", exc_info=True)
