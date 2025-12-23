"""唤醒词插件.

检测唤醒词并触发对话。
"""

from typing import TYPE_CHECKING

from src.constants.constants import AbortReason
from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class WakeWordPlugin(Plugin):
    name = "wake_word"
    priority = 30  # 依赖 AudioPlugin

    def __init__(self) -> None:
        super().__init__()
        self.detector = None
        self._audio_plugin = None  # 引用 AudioPlugin 获取 codec

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

            self.detector = WakeWordDetector()
            if not getattr(self.detector, "enabled", False):
                self.detector = None
                return

            self.detector.on_detected(self._on_detected)
            self.detector.on_error = self._on_error
        except ImportError as e:
            logger.error(f"无法导入唤醒词检测器: {e}")
            self.detector = None
        except Exception as e:
            logger.error(f"唤醒词插件初始化失败: {e}", exc_info=True)
            self.detector = None

    def set_audio_plugin(self, audio_plugin) -> None:
        """
        设置 AudioPlugin 引用（由 ServiceContainer 调用）.
        """
        self._audio_plugin = audio_plugin

    async def start(self) -> None:
        if not self.detector:
            return
        try:
            if not self._audio_plugin or not self._audio_plugin.codec:
                logger.warning("未找到 audio_codec，无法启动唤醒词检测")
                return
            await self.detector.start(self._audio_plugin.codec)
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
        """
        唤醒词检测回调.
        """
        try:
            if self._ctx.is_speaking():
                await self._cmd.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
                if self._audio_plugin and self._audio_plugin.codec:
                    await self._audio_plugin.codec.clear_audio_queue()
            else:
                # 启动自动对话
                await self._cmd.connect_protocol()
                from src.constants.constants import ListeningMode

                mode = (
                    ListeningMode.REALTIME
                    if self._ctx.get_config().get_config("AEC_OPTIONS.ENABLED", True)
                    else ListeningMode.AUTO_STOP
                )
                await self._cmd.start_listening(mode)
        except Exception as e:
            logger.error(f"处理唤醒词检测失败: {e}", exc_info=True)

    def _on_error(self, error):
        """
        唤醒词检测错误回调.
        """
        logger.error(f"唤醒词检测错误: {error}")
