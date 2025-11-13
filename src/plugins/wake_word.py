from typing import Any

from src.constants.constants import AbortReason
from src.plugins.base import Plugin
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordPlugin(Plugin):
    name = "wake_word"
    priority = 30  # 依赖 AudioPlugin

    def __init__(self) -> None:
        super().__init__()
        self.app = None
        self.detector = None

    async def setup(self, app: Any) -> None:
        self.app = app
        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

            self.detector = WakeWordDetector()
            if not getattr(self.detector, "enabled", False):
                self.detector = None
                return

            # 绑定回调
            self.detector.on_detected(self._on_detected)
            self.detector.on_error = self._on_error
        except ImportError as e:
            logger.error(f"无法导入唤醒词检测器: {e}")
            self.detector = None
        except Exception as e:
            logger.error(f"唤醒词插件初始化失败: {e}", exc_info=True)
            self.detector = None

    async def start(self) -> None:
        if not self.detector:
            return
        try:
            # 需要音频编码器以提供原始PCM数据
            audio_codec = getattr(self.app, "audio_codec", None)
            if audio_codec is None:
                logger.warning("未找到audio_codec，无法启动唤醒词检测")
                return
            await self.detector.start(audio_codec)
        except Exception as e:
            logger.error(f"启动唤醒词检测器失败: {e}", exc_info=True)

    async def stop(self) -> None:
        if self.detector:
            try:
                await self.detector.stop()
            except Exception as e:
                logger.warning(f"停止唤醒词检测器失败: {e}")

    async def shutdown(self) -> None:
        if self.detector:
            try:
                await self.detector.stop()
            except Exception as e:
                logger.warning(f"关闭唤醒词检测器失败: {e}")

    async def _on_detected(self, wake_word, full_text):
        # 检测到唤醒词：切到自动对话（根据 AEC 自动选择实时/自动停）
        try:
            # 若正在说话，交给应用的打断/状态机处理
            if hasattr(self.app, "device_state") and hasattr(
                self.app, "start_auto_conversation"
            ):
                if self.app.is_speaking():
                    await self.app.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
                    audio_plugin = self.app.plugins.get_plugin("audio")
                    if audio_plugin and audio_plugin.codec:
                        await audio_plugin.codec.clear_audio_queue()
                else:
                    await self.app.start_auto_conversation()
        except Exception as e:
            logger.error(f"处理唤醒词检测失败: {e}", exc_info=True)

    def _on_error(self, error):
        try:
            logger.error(f"唤醒词检测错误: {error}")
            if hasattr(self.app, "set_chat_message"):
                self.app.set_chat_message("assistant", f"[唤醒词错误] {error}")
        except Exception as e:
            logger.error(f"处理唤醒词错误回调失败: {e}")
