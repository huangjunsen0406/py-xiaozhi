"""唤醒词插件：检测唤醒词并触发对话。"""

import asyncio
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class WakeWordPlugin(Plugin):
    name = "wake_word"
    priority = 30
    requires = ["audio"]

    def __init__(self, audio=None) -> None:
        super().__init__()
        self.detector = None
        self._audio_plugin = audio
        self._lifecycle_lock = asyncio.Lock()
        # Configuration can enable detection only while the plugin is running.
        self._active = False

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        from src.core.event_bus import Events

        ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)

    async def _on_config_changed(self, data=None):
        await self.reload_model()

    async def start(self) -> None:
        from src.core.event_bus import Events

        self._active = True
        self.ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)
        async with self._lifecycle_lock:
            if self._active and not self._started:
                await self._apply_config()

    async def _apply_config(self, model_path=None, *, reload=False) -> bool:
        """Apply the current setting while holding the lifecycle lock."""
        config = self.ctx.get_config()
        if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            await self._release_detector()
            self._started = False
            self._failed = False
            return True

        try:
            if self.detector is None:
                # Delay model loading until start, after audio setup.
                from src.audio_processing.wake_word_detect import WakeWordDetector

                self.detector = WakeWordDetector(
                    config=config, audio_config=self.ctx.audio_config
                )
                self.detector.on_detected(self._on_detected)
                self.detector.on_error = self._on_error
                if model_path is None:
                    initialized = await self.detector.initialize()
                else:
                    initialized = await self.detector.initialize(model_path)
                if not initialized:
                    raise RuntimeError("唤醒词检测器初始化失败")
            elif reload:
                if not await self.detector.reload(model_path):
                    raise RuntimeError("唤醒词检测器热重载失败")

            # stop() revokes permission before waiting for this lock. Settings
            # can also change while model initialization/reloading is awaited.
            if not self._active or not config.get_config(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False
            ):
                await self._release_detector()
                self._started = False
                return False
            if not self._audio_plugin or not self._audio_plugin.codec:
                raise RuntimeError("未找到 audio_codec，无法启动唤醒词检测")
            # Detector.reload already restarts an existing running detector.
            if not self._started:
                if await self.detector.start(self._audio_plugin.codec) is False:
                    raise RuntimeError("唤醒词检测器启动失败")
            self._failed = False
            await super().start()
            return True
        except (Exception, asyncio.CancelledError):
            self.mark_failed()
            try:
                await self._release_detector()
            except Exception as exc:
                logger.warning("清理失败的唤醒词检测器失败: %s", exc, exc_info=True)
            raise

    async def stop(self) -> None:
        from src.core.event_bus import Events

        self._active = False
        if self.ctx is not None:
            self.ctx.event_bus.off(Events.CONFIG_CHANGED, self._on_config_changed)
        async with self._lifecycle_lock:
            try:
                if self.detector is not None:
                    await self.detector.stop()
            finally:
                await super().stop()

    async def _release_detector(self) -> None:
        detector, self.detector = self.detector, None
        if detector is not None:
            await detector.shutdown()

    async def _shutdown_detector(self) -> None:
        from src.core.event_bus import Events

        self._active = False
        if self.ctx is not None:
            self.ctx.event_bus.off(Events.CONFIG_CHANGED, self._on_config_changed)
        async with self._lifecycle_lock:
            try:
                await self._release_detector()
            finally:
                self._started = False

    def register_resources(self, pool) -> None:
        # Resolve the detector at cleanup time; disabled starts create it later.
        pool.register("wake_word.detector", self._shutdown_detector)

    async def reload_model(self, model_path: str | None = None) -> bool:
        """Apply enable/disable and reload the model for an active plugin."""
        async with self._lifecycle_lock:
            if not self._active:
                return False
            try:
                return await self._apply_config(model_path, reload=True)
            except Exception as exc:
                logger.error("热重载唤醒词模型失败: %s", exc, exc_info=True)
                return False

    async def _on_detected(self, wake_word, full_text):
        try:
            await self._cmd.wake()
        except Exception as exc:
            logger.error("处理唤醒词检测失败: %s", exc, exc_info=True)

    async def _on_error(self, error):
        logger.error("唤醒词检测错误: %s", error, exc_info=True)
        if self.detector is not None and not self.detector.enabled:
            self.mark_failed()
