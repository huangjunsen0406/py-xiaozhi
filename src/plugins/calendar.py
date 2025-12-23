"""日历插件.

管理日程提醒服务。
"""

from typing import TYPE_CHECKING

from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class _CmdAdapter:
    """
    为日程提醒服务提供 TTS 功能的适配器.
    """

    def __init__(self, cmd: "PluginCommands", ctx: "PluginContext") -> None:
        self._cmd = cmd
        self._ctx = ctx

    async def _send_text_tts(self, text: str):
        try:
            if not self._ctx.is_audio_channel_opened():
                await self._cmd.connect_protocol()
            await self._cmd.send_text(text)
        except Exception:
            pass


class CalendarPlugin(Plugin):
    name = "calendar"
    priority = 40  # 独立服务，中等优先级

    def __init__(self) -> None:
        super().__init__()
        self._service = None
        self._adapter = None

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self._adapter = _CmdAdapter(cmd, ctx)
        try:
            from src.mcp.tools.calendar import get_reminder_service

            self._service = get_reminder_service()
            try:
                setattr(self._service, "_get_application", lambda: self._adapter)
            except Exception:
                pass
        except Exception as e:
            logger.error(f"初始化日程提醒服务失败: {e}")
            self._service = None

    async def start(self) -> None:
        if not self._service:
            return
        try:
            await self._service.start()
            try:
                await self._service.check_daily_events()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"启动日程提醒服务失败: {e}")

    async def stop(self) -> None:
        try:
            if self._service:
                await self._service.stop()
        except Exception:
            pass

    async def shutdown(self) -> None:
        try:
            if self._service:
                await self._service.stop()
        except Exception:
            pass
