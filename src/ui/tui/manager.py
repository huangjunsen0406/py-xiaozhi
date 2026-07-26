"""TUI ViewManager：ViewPort 实现，驱动 Textual App."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager
    from src.ui.tui.app import XiaozhiTuiApp

logger = get_logger()


class TuiViewManager:
    """TUI 界面（ViewPort：与 GUI/CLI/GPIO 同一套 set_*）."""

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: TaskManager | None = None,
    ):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._app: XiaozhiTuiApp | None = None
        self._app_task: asyncio.Task | None = None

        self._auto_mode = False
        self._status = "待命"
        self._connected = False
        self._chat_text = ""
        self._music_line = ""
        self._emotion = "neutral"

    async def start(self, mode: str = "tui"):
        """启动 TUI（await 直到用户退出或任务取消）."""
        try:
            from src.ui.tui.app import XiaozhiTuiApp
        except ImportError as e:
            logger.error(
                "TUI 模式需要 textual。请安装:\n"
                "  uv sync --extra tui\n"
                "  pip install '.[tui]'\n"
                f"(原始错误: {e})"
            )
            raise

        logger.info("TuiViewManager: 启动 TUI 界面...")
        self._running = True
        self._loop = asyncio.get_running_loop()

        self._app = XiaozhiTuiApp(
            on_command=self._handle_command,
            on_settings_saved=self._on_settings_saved,
        )
        self._app.status_text = self._status
        self._app.connected = self._connected
        self._app.auto_mode = self._auto_mode
        self._app.chat_text = self._chat_text
        self._app.music_line = self._music_line
        self._app.emotion = self._emotion

        # UIPlugin 经 TaskManager.spawn 启动本协程；这里 await run_async
        # 直到用户 q/Ctrl+C 或 close() 调用 app.exit()
        try:
            await self._app.run_async()
        except asyncio.CancelledError:
            logger.info("TuiViewManager: TUI 任务被取消")
            app = self._app
            if app is not None:
                try:
                    app.exit()
                except Exception:
                    pass
            raise
        finally:
            self._running = False
            if self._app is not None:
                try:
                    self._app.uninstall_log_handler()
                except Exception:
                    pass
            logger.info("TuiViewManager: TUI 已结束")

    async def close(self):
        """关闭 TUI."""
        logger.info("TuiViewManager: 正在关闭...")
        self._running = False
        app = self._app
        if app is not None:
            try:
                app.exit()
            except Exception:
                pass
            try:
                app.uninstall_log_handler()
            except Exception:
                pass
        logger.info("TuiViewManager: 已关闭")

    def _handle_command(self, cmd: str):
        """处理用户命令."""
        cmd_lower = cmd.lower().strip()
        if cmd_lower == "r":
            self._safe_emit(Events.UI_MANUAL_TOGGLE)
        elif cmd_lower == "x":
            self._safe_emit(Events.UI_ABORT_REQUEST)
        elif cmd_lower == "q":
            self._safe_emit(Events.UI_QUIT_REQUEST)
        else:
            self._safe_emit(Events.UI_SEND_TEXT, {"text": cmd})

    def _on_settings_saved(self) -> None:
        """设置保存后通知运行时热重载."""
        self._safe_emit(Events.CONFIG_CHANGED)

    def _safe_emit(self, event: str, data=None):
        """安全发射 EventBus 事件."""

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
                    f"TuiViewManager 经 TaskManager 调度事件 {event} 失败: {e}",
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
                        f"TuiViewManager 发射事件 {event} 失败: {exc}",
                        exc_info=exc,
                    )

            fut.add_done_callback(_done)
        except Exception as e:
            logger.error(f"TuiViewManager 调度事件 {event} 失败: {e}", exc_info=True)
            if asyncio.iscoroutine(coro):
                coro.close()

    def _set_app_attr(self, name: str, value) -> None:
        app = self._app
        if app is None:
            return

        def _apply() -> None:
            setattr(app, name, value)

        try:
            app.call_from_thread(_apply)
        except Exception:
            try:
                _apply()
            except Exception as e:
                logger.debug(f"TUI set {name} 失败: {e}")

    # ----- ViewPort -----

    @property
    def is_running(self) -> bool:
        return self._running

    def set_status(self, status: str, connected: bool = True):
        self._status = status
        self._connected = connected
        self._set_app_attr("status_text", status)
        self._set_app_attr("connected", connected)

    def set_chat_text(self, text: str):
        self._chat_text = text
        self._set_app_attr("chat_text", text)

    def set_music_line(self, text: str):
        self._music_line = text
        self._set_app_attr("music_line", text)

    def set_emotion(self, emotion: str):
        self._emotion = emotion
        self._set_app_attr("emotion", emotion)

    def set_auto_mode(self, auto_mode: bool):
        self._auto_mode = auto_mode
        self._set_app_attr("auto_mode", auto_mode)

    def set_button_text(self, text: str):
        logger.debug(f"TUI set_button_text: {text}")

    def is_auto_mode(self) -> bool:
        return bool(self._auto_mode)
