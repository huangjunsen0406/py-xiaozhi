from typing import Any

from src.plugins.base import Plugin
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class _AppAdapter:
    """
    为日程提醒服务提供 _send_text_tts 的适配器.
    """

    def __init__(self, app: Any) -> None:
        self._app = app

    async def _send_text_tts(self, text: str):
        try:
            # 通过协议触发TTS（与 ApplicationMain 的行为对齐）
            if not getattr(self._app, "protocol", None):
                return
            try:
                if not self._app.is_audio_channel_opened():
                    await self._app.connect_protocol()
            except Exception:
                pass
            await self._app.protocol.send_wake_word_detected(text)
        except Exception:
            # 兜底：无法TTS时，回退到UI文本
            try:
                if hasattr(self._app, "set_chat_message"):
                    self._app.set_chat_message("assistant", text)
            except Exception:
                pass


class CalendarPlugin(Plugin):
    name = "calendar"

    def __init__(self) -> None:
        super().__init__()
        self.app: Any = None
        self._service = None
        self._adapter: _AppAdapter | None = None

    async def setup(self, app: Any) -> None:
        self.app = app
        self._adapter = _AppAdapter(app)
        try:
            from src.mcp.tools.calendar import get_reminder_service

            self._service = get_reminder_service()
            # 覆盖其应用获取函数，返回适配器对象
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
            # 可选：启动时检查今日日程
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
