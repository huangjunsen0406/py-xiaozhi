"""CLI 终端界面."""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.core.event_bus import EventBus, Events
from src.logging import get_logger
from src.ui.shared.event_emitter import safe_emit

from .display import CLIDisplay

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager

logger = get_logger()


class CliViewManager:
    """CLI 界面（ViewPort：与 GUI/GPIO 同一套 set_*）."""

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: Optional["TaskManager"] = None,
    ):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._display = CLIDisplay()
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None

        # 设置命令回调
        self._display.set_command_callback(self._handle_command)

        # 尽早拦截日志输出
        self._display.intercept_logging()

    async def start(self, mode: str = "cli"):
        """启动 CLI 视图.

        Args:
            mode: 运行模式（CLI 模式下忽略此参数）
        """
        logger.info("CliViewManager: 启动 CLI 界面...")
        self._running = True
        self._loop = asyncio.get_running_loop()

        # 启动 CLI 显示
        try:
            await self._display.start()
        except asyncio.CancelledError:
            logger.info("CliViewManager: 显示任务被取消")
            raise
        finally:
            self._running = False

    async def close(self):
        """关闭 CLI 视图."""
        logger.info("CliViewManager: 正在关闭...")
        self._running = False
        await self._display.close()
        logger.info("CliViewManager: 已关闭")

    def _handle_command(self, cmd: str):
        """处理用户命令 - 统一入口."""
        cmd_lower = cmd.lower()

        if cmd_lower == "r":
            # 开始/停止对话
            self._safe_emit(Events.UI_MANUAL_TOGGLE)
        elif cmd_lower == "x":
            # 中断
            self._safe_emit(Events.UI_ABORT_REQUEST)
        elif cmd_lower == "q":
            # 退出
            self._safe_emit(Events.UI_QUIT_REQUEST)
        elif cmd_lower == "h":
            # 显示帮助
            self._display.show_help()
        else:
            # 发送文本
            self._safe_emit(Events.UI_SEND_TEXT, {"text": cmd})

    def _safe_emit(self, event: str, data=None):
        safe_emit(
            self._event_bus,
            event,
            data,
            task_manager=self._task_manager,
            loop=self._loop,
            source=type(self).__name__,
        )

    # ========== 公共 API ==========

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    def set_status(self, status: str, connected: bool = True):
        """设置状态."""
        self._display.update_status(status, connected)

    def set_chat_text(self, text: str):
        self._display.update_text(text)

    def set_music_line(self, text: str):
        self._display.update_music_line(text)

    def set_emotion(self, emotion: str):
        self._display.update_emotion(emotion)

    def set_auto_mode(self, auto_mode: bool):
        self._display.update_auto_mode(auto_mode)

    def set_button_text(self, text: str):
        # 终端没有主按钮
        logger.debug(f"CLI set_button_text: {text}")
