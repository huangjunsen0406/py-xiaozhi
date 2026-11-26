"""激活验证码播报模块.

使用预录制 WAV 音效播报激活验证码，仅在设备激活流程中使用。
不依赖 FFmpeg，可在无系统 FFmpeg 的干净环境中工作。

线程安全约定：
- 所有 PortAudio (sounddevice) 调用严格局限在单一工作线程内完成；
- stop() 仅设置停止事件并等待工作线程退出 OutputStream 上下文，严禁跨线程调用 sd.stop()，
  避免触发 macOS AUHAL (!obj) / malloc 堆破坏。
"""

from __future__ import annotations

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from src.logging import get_logger
from src.utils.resource_finder import get_assets_dir

logger = get_logger()

# 音频资源目录
_ASSETS_DIR = get_assets_dir() / "sounds"
# 资源默认采样率（与 assets/sounds 中预置 WAV 对齐）
_DEFAULT_SAMPLE_RATE = 24000
# 每次写入 OutputStream 的块时长（50ms），保证停止响应迅速且无跨线程流操作
_CHUNK_MS = 50
# 片段之间的静默间隔（60ms）
_GAP_MS = 60


class ActivationAnnouncer:
    """激活验证码播报器."""

    def __init__(self, locale: str = "zh-CN"):
        self._locale = locale
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._play_thread: threading.Thread | None = None

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._play_thread is not None and self._play_thread.is_alive()

    def _get_sound_path(self, name: str) -> Path | None:
        """获取音效文件路径（仅 WAV）."""
        sound_file = _ASSETS_DIR / self._locale / f"{name}.wav"
        if sound_file.exists():
            return sound_file
        # 回退到 zh-CN
        if self._locale != "zh-CN":
            fallback = _ASSETS_DIR / "zh-CN" / f"{name}.wav"
            if fallback.exists():
                return fallback
        return None

    def _load_wav(self, file_path: Path) -> tuple[np.ndarray, int] | None:
        """加载 WAV 为 float32 mono，并返回 (samples, sample_rate)."""
        try:
            with wave.open(str(file_path), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)

            if sample_width == 2:
                audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                audio = (
                    np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
                )
            elif sample_width == 1:
                audio = (
                    np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0
                ) / 128.0
            else:
                logger.error(f"不支持的 WAV 位深: {sample_width * 8} bit ({file_path})")
                return None

            if channels > 1:
                audio = audio.reshape(-1, channels).mean(axis=1)

            return audio, sample_rate
        except Exception as e:
            logger.error(f"加载 WAV 失败 {file_path}: {e}", exc_info=True)
            return None

    def _build_sequence_audio(self, names: list[str]) -> tuple[np.ndarray, int] | None:
        """将音效序列拼接为单段连续 float32 PCM，避免多次启停音频设备流."""
        segments: list[np.ndarray] = []
        target_rate: int | None = None

        for name in names:
            if self._stop_flag.is_set():
                return None
            sound_path = self._get_sound_path(name)
            if not sound_path:
                logger.warning(f"音效文件不存在: {name}")
                continue
            loaded = self._load_wav(sound_path)
            if loaded is None:
                continue
            audio, sample_rate = loaded
            if sample_rate <= 0:
                sample_rate = _DEFAULT_SAMPLE_RATE
            if target_rate is None:
                target_rate = sample_rate
            elif sample_rate != target_rate:
                # 若个别 WAV 采样率不一致，使用线性插值轻量对齐
                new_len = max(1, int(round(len(audio) * target_rate / sample_rate)))
                xp = np.linspace(0.0, 1.0, len(audio), dtype=np.float32)
                x = np.linspace(0.0, 1.0, new_len, dtype=np.float32)
                audio = np.interp(x, xp, audio).astype(np.float32)
            segments.append(audio)
            gap_samples = int(target_rate * _GAP_MS / 1000)
            if gap_samples > 0:
                segments.append(np.zeros(gap_samples, dtype=np.float32))

        if not segments or target_rate is None:
            return None
        return np.concatenate(segments), target_rate

    def _play_sounds(self, names: list[str]) -> None:
        """在单一工作线程内通过 OutputStream 分块播放，避免跨线程调用 PortAudio."""
        built = self._build_sequence_audio(names)
        if built is None or self._stop_flag.is_set():
            return

        audio, sample_rate = built
        chunk_frames = max(256, int(sample_rate * _CHUNK_MS / 1000))

        try:
            with sd.OutputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="float32",
                blocksize=chunk_frames,
            ) as stream:
                for offset in range(0, len(audio), chunk_frames):
                    if self._stop_flag.is_set():
                        logger.debug("播报被中断")
                        break
                    chunk = audio[offset : offset + chunk_frames]
                    stream.write(chunk)
        except Exception as e:
            logger.error(f"播放激活验证码失败: {e}", exc_info=True)

    def announce(self, code: str, *, interrupt: bool = True) -> None:
        """播报验证码（非阻塞）.

        Args:
            code: 验证码字符串，如 "123456"
            interrupt: True 时先停掉上一轮再重播；False 时若正在播报则跳过本次请求，
                防止轮询重试每 3 秒掐断尚未念完的验证码。
        """
        if not code or not code.isdigit():
            logger.warning(f"无效的验证码: {code}")
            return

        with self._lock:
            alive = self._play_thread is not None and self._play_thread.is_alive()
            if alive and not interrupt:
                logger.debug("验证码仍在播报中，跳过本次重试播报")
                return

        if interrupt:
            self.stop()

        sounds = ["activation"] + list(code)
        logger.info(f"播报验证码: {code}")

        with self._lock:
            self._stop_flag.clear()
            self._play_thread = threading.Thread(
                target=self._play_sounds,
                args=(sounds,),
                daemon=True,
                name="ActivationAnnouncer",
            )
            self._play_thread.start()

    def stop(self) -> None:
        """安全停止播报（仅发信号并等待工作线程自行关闭 OutputStream）."""
        with self._lock:
            thread = self._play_thread
            self._stop_flag.set()

        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

        with self._lock:
            if self._play_thread is thread:
                self._play_thread = None


# 全局实例
_announcer: ActivationAnnouncer | None = None
_announcer_lock = threading.Lock()


def announce_activation_code(
    code: str, locale: str = "zh-CN", *, interrupt: bool = True
) -> None:
    """播报激活验证码."""
    global _announcer
    with _announcer_lock:
        if _announcer is None:
            _announcer = ActivationAnnouncer(locale)
        announcer = _announcer
    announcer.announce(code, interrupt=interrupt)


def stop_activation_announcement() -> None:
    """停止当前正在进行的激活验证码播报."""
    with _announcer_lock:
        announcer = _announcer
    if announcer is not None:
        announcer.stop()
