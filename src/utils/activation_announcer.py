"""激活验证码播报模块.

使用预录制 WAV 音效播报激活验证码，仅在设备激活流程中使用。
不依赖 FFmpeg，可在无系统 FFmpeg 的干净环境中工作。
"""

import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from src.logging import get_logger
from src.utils.resource_finder import get_app_root

logger = get_logger()

# 音频资源目录
_ASSETS_DIR = get_app_root() / "assets" / "sounds"
# 资源默认采样率（与 assets/sounds 中预置 WAV 对齐）
_DEFAULT_SAMPLE_RATE = 24000


class ActivationAnnouncer:
    """激活验证码播报器."""

    def __init__(self, locale: str = "zh-CN"):
        self._locale = locale
        self._stop_flag = threading.Event()
        self._play_thread: threading.Thread | None = None

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
        """加载 WAV 为 float32 mono，并返回 (samples, sample_rate).

        Args:
            file_path: WAV 文件路径。

        Returns:
            (float32 音频, 采样率)，失败返回 None。
        """
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
                # 8-bit PCM 为无符号
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

    def _play_sounds(self, names: list[str]) -> None:
        """播放音效序列（在工作线程中执行）."""
        for name in names:
            if self._stop_flag.is_set():
                logger.debug("播报被中断")
                break

            sound_path = self._get_sound_path(name)
            if not sound_path:
                logger.warning(f"音效文件不存在: {name}")
                continue

            loaded = self._load_wav(sound_path)
            if loaded is None or self._stop_flag.is_set():
                continue

            audio, sample_rate = loaded
            if sample_rate <= 0:
                sample_rate = _DEFAULT_SAMPLE_RATE

            try:
                sd.play(audio, sample_rate)
                # 分段等待，便于响应中断
                while sd.get_stream().active:
                    if self._stop_flag.is_set():
                        sd.stop()
                        break
                    self._stop_flag.wait(0.05)
            except Exception as e:
                logger.error(f"播放失败: {e}", exc_info=True)

    def announce(self, code: str) -> None:
        """播报验证码（非阻塞）.

        Args:
            code: 验证码字符串，如 "123456"
        """
        if not code or not code.isdigit():
            logger.warning(f"无效的验证码: {code}")
            return

        # 停止之前的播报
        self.stop()

        # 构建播放序列: 激活提示 + 各个数字
        sounds = ["activation"] + list(code)

        logger.info(f"播报验证码: {code}")

        self._stop_flag.clear()
        self._play_thread = threading.Thread(
            target=self._play_sounds,
            args=(sounds,),
            daemon=True,
            name="ActivationAnnouncer",
        )
        self._play_thread.start()

    def stop(self) -> None:
        """停止播报."""
        self._stop_flag.set()

        # 停止音频播放
        try:
            sd.stop()
        except Exception as e:
            logger.debug(f"停止音频播放失败: {e}")

        # 等待线程结束
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1)

        self._play_thread = None


# 全局实例
_announcer: ActivationAnnouncer | None = None


def announce_activation_code(code: str, locale: str = "zh-CN") -> None:
    """播报激活验证码.

    Args:
        code: 验证码字符串
        locale: 语言代码
    """
    global _announcer
    if _announcer is None:
        _announcer = ActivationAnnouncer(locale)
    _announcer.announce(code)


def stop_announcement() -> None:
    """停止验证码播报."""
    global _announcer
    if _announcer:
        _announcer.stop()
