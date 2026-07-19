# -*- coding: utf-8 -*-
"""CLI 视图管理器.

管理 CLI 模式下的终端显示界面，与 GUI 的 ViewManager 功能对应。
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

from .display import CLIDisplay

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager

logger = get_logger()


class CLIViewManager:
    """CLI 视图管理器.

    管理 CLI 模式下的终端界面，提供与 GUI ViewManager 一致的接口。
    """

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
        self._tts_text = ""

        # 设置命令回调
        self._display.set_command_callback(self._handle_command)

        # 尽早拦截日志输出
        self._display.intercept_logging()

        # 订阅事件
        self._subscribe_events()

    def _subscribe_events(self):
        """订阅 EventBus 事件."""
        self._event_bus.on(Events.UI_UPDATE_TEXT, self._on_update_text)
        self._event_bus.on(Events.UI_UPDATE_EMOTION, self._on_update_emotion)
        self._event_bus.on(Events.UI_UPDATE_STATUS, self._on_update_status)
        logger.debug("CLIViewManager: 已订阅 UI 事件")

    async def _on_update_text(self, data):
        """处理文本更新."""
        text = data.text if hasattr(data, "text") else str(data)
        self._tts_text = text
        self._display.update_text(text)

    async def _on_update_emotion(self, data):
        """处理表情更新."""
        emotion = data.emotion if hasattr(data, "emotion") else str(data)
        self._display.update_emotion(emotion)

    async def _on_update_status(self, data):
        """处理状态更新."""
        if hasattr(data, "status"):
            self._status = data.status
            self._connected = getattr(data, "connected", True)
        elif isinstance(data, dict):
            self._status = data.get("status", "")
            self._connected = data.get("connected", True)
        self._display.update_status(self._status, self._connected)

    async def start(self, mode: str = "cli"):
        """启动 CLI 视图.

        Args:
            mode: 运行模式（CLI 模式下忽略此参数）
        """
        logger.info("CLIViewManager: 启动 CLI 界面...")
        self._running = True
        self._loop = asyncio.get_running_loop()

        # 启动 CLI 显示
        try:
            await self._display.start()
        except asyncio.CancelledError:
            logger.info("CLIViewManager: 显示任务被取消")

    async def close(self):
        """关闭 CLI 视图."""
        logger.info("CLIViewManager: 正在关闭...")
        self._running = False

        # 取消订阅事件
        try:
            self._event_bus.off(Events.UI_UPDATE_TEXT, self._on_update_text)
            self._event_bus.off(Events.UI_UPDATE_EMOTION, self._on_update_emotion)
            self._event_bus.off(Events.UI_UPDATE_STATUS, self._on_update_status)
        except Exception as e:
            logger.warning(f"CLIViewManager: 取消订阅失败: {e}", exc_info=True)

        await self._display.close()
        logger.info("CLIViewManager: 已关闭")

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
                    f"CLIViewManager 经 TaskManager 调度事件 {event} 失败: {e}",
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
                        f"CLIViewManager 发射事件 {event} 失败: {exc}",
                        exc_info=exc,
                    )

            fut.add_done_callback(_done)
        except Exception as e:
            logger.error(f"CLIViewManager 调度事件 {event} 失败: {e}", exc_info=True)
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

    def set_tts_text(self, text: str):
        """设置 TTS 文本."""
        self._tts_text = text
        self._display.update_text(text)

    def set_emotion(self, emotion: str):
        """设置表情."""
        self._display.update_emotion(emotion)

    def set_auto_mode(self, auto_mode: bool):
        """设置自动模式."""
        self._auto_mode = auto_mode
        self._display.update_auto_mode(auto_mode)

    def set_button_text(self, text: str):
        """CLI 无实体按钮，保留 facade 兼容."""
        logger.debug(f"CLI set_button_text: {text}")

    def is_auto_mode(self) -> bool:
        return bool(self._auto_mode)

    # ========== 兼容 GUI ViewManager 的属性 ==========

    @property
    def main_model(self):
        """返回自身作为 model 代理."""
        return self

    def toggle_auto_mode(self) -> bool:
        """切换自动模式，返回切换后是否为自动."""
        self._auto_mode = not self._auto_mode
        self._display.update_auto_mode(self._auto_mode)
        return self._auto_mode
