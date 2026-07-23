# -*- coding: utf-8 -*-
"""CLI 终端界面."""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

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
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # 状态
        self._auto_mode = False
        self._status = "待命"
        self._connected = False
        self._chat_text = ""
        self._music_line = ""

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
        """安全地发送事件.

        优先经 TaskManager.schedule_nowait（线程安全 + 可追踪）；
        否则回退 run_coroutine_threadsafe。
        """
        def _start_emit():
            if data is None:
                return self._event_bus.emit(event)
            return self._event_bus.emit(event, data)

        if self._task_manager is not None:
            try:
                self._task_manager.schedule_nowait(_start_emit)
                return
            except Exception as e:
                logger.error(
                    f"CliViewManager 经 TaskManager 调度事件 {event} 失败: {e}",
                    exc_info=True,
                )

        if not self._loop or not self._loop.is_running():
            return
        coro = _start_emit()
        try:
            fut = asyncio.run_coroutine_threadsafe(coro, self._loop)

            def _done(f):
                try:
                    exc = f.exception()
                except Exception:
                    return
                if exc:
                    logger.error(
                        f"CliViewManager 发射事件 {event} 失败: {exc}",
                        exc_info=exc,
                    )

            fut.add_done_callback(_done)
        except Exception as e:
            logger.error(f"CliViewManager 调度事件 {event} 失败: {e}", exc_info=True)
            if asyncio.iscoroutine(coro):
                coro.close()

    # ========== 公共 API ==========

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    def set_status(self, status: str, connected: bool = True):
        """设置状态."""
        self._status = status
        self._connected = connected
        self._display.update_status(status, connected)

    def set_chat_text(self, text: str):
        self._chat_text = text
        self._display.update_text(text)

    def set_music_line(self, text: str):
        self._music_line = text
        self._display.update_music_line(text)

    def set_emotion(self, emotion: str):
        self._display.update_emotion(emotion)

    def set_auto_mode(self, auto_mode: bool):
        self._auto_mode = auto_mode
        self._display.update_auto_mode(auto_mode)

    def set_button_text(self, text: str):
        # 终端没有主按钮
        logger.debug(f"CLI set_button_text: {text}")

    def is_auto_mode(self) -> bool:
        return bool(self._auto_mode)
