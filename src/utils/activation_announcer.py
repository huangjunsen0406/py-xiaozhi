"""激活验证码播报模块.

使用预录制音频播报激活验证码，仅在设备激活流程中使用。
"""

import subprocess
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

from src.logging import get_logger
from src.utils.resource_finder import get_app_root

logger = get_logger()

# 音频资源目录
_ASSETS_DIR = get_app_root() / "assets" / "sounds"


class ActivationAnnouncer:
    """激活验证码播报器."""

    def __init__(self, locale: str = "zh-CN"):
        self._locale = locale
        self._process: subprocess.Popen | None = None
        self._stop_flag = threading.Event()
        self._play_thread: threading.Thread | None = None

    def _get_sound_path(self, name: str) -> Path | None:
        """获取音效文件路径."""
        sound_file = _ASSETS_DIR / self._locale / f"{name}.ogg"
        if sound_file.exists():
            return sound_file
        # 回退到 zh-CN
        if self._locale != "zh-CN":
            fallback = _ASSETS_DIR / "zh-CN" / f"{name}.ogg"
            if fallback.exists():
                return fallback
        return None

    def _decode_with_ffmpeg(self, file_path: Path) -> np.ndarray | None:
        """使用 ffmpeg 解码音频文件."""
        try:
            cmd = [
                "ffmpeg",
                "-i", str(file_path),
                "-f", "s16le",      # 16位小端 PCM
                "-ar", "24000",     # 采样率
                "-ac", "1",         # 单声道
                "-loglevel", "error",
                "-"
            ]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            stdout, stderr = self._process.communicate(timeout=10)
            self._process = None

            if stderr:
                logger.debug(f"ffmpeg stderr: {stderr.decode('utf-8', errors='ignore')}")

            if stdout:
                # 转换为 float32
                audio = np.frombuffer(stdout, dtype=np.int16).astype(np.float32) / 32768.0
                return audio

        except subprocess.TimeoutExpired:
            if self._process:
                self._process.kill()
                self._process = None
            logger.warning(f"ffmpeg 解码超时: {file_path}")
        except FileNotFoundError:
            logger.error("ffmpeg 未安装")
        except Exception as e:
            logger.error(f"解码失败 {file_path}: {e}")

        return None

    def _play_sounds(self, names: list[str]):
        """播放音效序列（在工作线程中执行）."""
        sample_rate = 24000

        for name in names:
            if self._stop_flag.is_set():
                logger.debug("播报被中断")
                break

            sound_path = self._get_sound_path(name)
            if not sound_path:
                logger.warning(f"音效文件不存在: {name}")
                continue

            audio = self._decode_with_ffmpeg(sound_path)
            if audio is None or self._stop_flag.is_set():
                continue

            try:
                sd.play(audio, sample_rate)
                # 分段等待，便于响应中断
                while sd.get_stream().active:
                    if self._stop_flag.is_set():
                        sd.stop()
                        break
                    self._stop_flag.wait(0.05)
            except Exception as e:
                logger.error(f"播放失败: {e}")

    def announce(self, code: str):
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
            name="ActivationAnnouncer"
        )
        self._play_thread.start()

    def stop(self):
        """停止播报."""
        self._stop_flag.set()

        # 停止 ffmpeg 进程
        if self._process:
            try:
                self._process.kill()
            except Exception as e:
                logger.debug(f"终止播报进程失败: {e}")
            self._process = None

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


def announce_activation_code(code: str, locale: str = "zh-CN"):
    """播报激活验证码.

    Args:
        code: 验证码字符串
        locale: 语言代码
    """
    global _announcer
    if _announcer is None:
        _announcer = ActivationAnnouncer(locale)
    _announcer.announce(code)


def stop_announcement():
    """停止验证码播报."""
    global _announcer
    if _announcer:
        _announcer.stop()
