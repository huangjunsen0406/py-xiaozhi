"""TUI ViewManager：ViewPort 实现，驱动 Textual App."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.core.event_bus import EventBus, Events
from src.logging import get_logger
from src.ui.shared.event_emitter import safe_emit
from src.ui.tui.settings_services import SettingsServices
from src.utils.config_manager import ConfigManager

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager
    from src.ui.tui.app import XiaozhiTuiApp

logger = get_logger()


class TuiViewManager:
    """TUI 界面（ViewPort：与 GUI/GPIO 同一套 set_*）."""

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: TaskManager | None = None,
        config_manager: ConfigManager | None = None,
        runtime_tool_names: Callable[[], tuple[str, ...]] | None = None,
    ):
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._config_manager = (
            config_manager if config_manager is not None else ConfigManager.from_dict()
        )
        self._settings_services = SettingsServices(
            self._config_manager, event_bus, runtime_tool_names
        )
        self._reconnect_snapshot = self._reconnect_values()
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
            config=self._config_manager,
            settings_services=self._settings_services,
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
            self._settings_services.close()
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
        self._settings_services.close()
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

    def _reconnect_values(self) -> dict:
        from src.mcp.tool_catalog import normalize_disabled
        from src.ui.tui.settings_data import SETTING_SECTIONS

        values = {
            field.path: self._config_manager.get_config(field.path)
            for _, fields in SETTING_SECTIONS
            for field in fields
            if getattr(field, "effect", "hot") == "reconnect"
        }
        values["MCP_TOOLS.DISABLED"] = sorted(
            normalize_disabled(
                self._config_manager.get_config("MCP_TOOLS.DISABLED", [])
            )
        )
        return values

    def _on_settings_saved(self) -> None:
        """配置提交成功后统一应用；关闭拒绝不另起任务。"""
        current = self._reconnect_values()
        reconnect = current != self._reconnect_snapshot
        self._reconnect_snapshot = current

        async def apply_settings():
            await self._event_bus.emit(Events.CONFIG_CHANGED)
            if reconnect:
                await self._event_bus.emit(Events.PROTOCOL_RECONNECT_REQUEST)

        if self._task_manager is not None:
            self._task_manager.schedule_nowait(apply_settings)
        elif self._app is not None and self._app.is_running:
            self._app.run_worker(
                apply_settings(), group="settings-apply", exit_on_error=False
            )

    def _safe_emit(self, event: str, data=None):
        safe_emit(
            self._event_bus,
            event,
            data,
            task_manager=self._task_manager,
            loop=self._loop,
            source=type(self).__name__,
        )

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
