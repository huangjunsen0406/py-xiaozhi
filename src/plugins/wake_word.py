"""唤醒词插件.

检测唤醒词并触发对话。
"""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import AbortReason
from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class WakeWordPlugin(Plugin):
    name = "wake_word"
    priority = 30
    requires = ["audio"]

    def __init__(self) -> None:
        super().__init__()
        self.detector = None

    @property
    def _audio_plugin(self):
        """通过依赖注入获取 AudioPlugin."""
        return self.get_dep("audio")

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        # 订阅配置变更事件（轻量，不加载模型）
        from src.core.event_bus import Events
        ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)

    async def _on_config_changed(self, data=None):
        """配置变更时重新加载唤醒词模型."""
        logger.info("WakeWordPlugin: 收到配置变更事件，重新加载唤醒词模型")
        await self.reload_model()

    async def start(self) -> None:
        try:
            if not self.ctx.get_config().get_config(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False
            ):
                logger.info("唤醒词功能已禁用")
                return

            # 延迟加载模型到 start() 阶段，避免 setup() 时与 PortAudio DLL 冲突
            if self.detector is None:
                from src.audio_processing.wake_word_detect import WakeWordDetector

                self.detector = WakeWordDetector()
                if not await self.detector.initialize():
                    raise RuntimeError("唤醒词检测器初始化失败")
                self.detector.on_detected(self._on_detected)
                self.detector.on_error = self._on_error

            if not self._audio_plugin or not self._audio_plugin.codec:
                raise RuntimeError("未找到 audio_codec，无法启动唤醒词检测")
            if await self.detector.start(self._audio_plugin.codec) is False:
                raise RuntimeError("唤醒词检测器启动失败")
            await super().start()
        except Exception:
            self.mark_failed()
            try:
                await self._shutdown_detector()
            except Exception as e:
                logger.warning(f"清理失败的唤醒词检测器失败: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        try:
            if self.detector is not None:
                await self.detector.stop()
        finally:
            await super().stop()

    async def _shutdown_detector(self) -> None:
        # 在释放时取当前实例，不能捕获 register_resources 时尚未创建的 detector。
        if self.detector is not None:
            await self.detector.shutdown()
            self.detector = None

    def register_resources(self, pool) -> None:
        pool.register("wake_word.detector", self._shutdown_detector)

    async def reload_model(self, model_path: Optional[str] = None) -> bool:
        """热重载唤醒词模型.

        Args:
            model_path: 新模型路径（如 "models/en"）。如果为 None，从配置读取。

        Returns:
            是否重载成功
        """
        if not self.detector:
            logger.warning("检测器未初始化，无法热重载")
            return False

        try:
            return await self.detector.reload(model_path)
        except Exception as e:
            logger.error(f"热重载唤醒词模型失败: {e}", exc_info=True)
            return False

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

    async def _on_error(self, error):
        """
        唤醒词检测错误回调.
        """
        logger.error(f"唤醒词检测错误: {error}", exc_info=True)
