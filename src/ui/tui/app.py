"""Textual App：仪表盘 + 设置屏."""

from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, Input, RichLog, Static

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.ui.tui.settings_screen import SettingsScreen
from src.ui.tui.settings_services import SettingsServices
from src.utils.config_manager import ConfigManager

logger = get_logger()


class XiaozhiTuiApp(App[None]):
    """小智 TUI 主应用."""

    TITLE = SystemConstants.APP_DISPLAY_NAME
    SUB_TITLE = "TUI"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status-panel {
        height: auto;
        max-height: 8;
        border: solid $primary;
        margin: 0 1;
        padding: 0 1;
    }
    #status-line {
        text-style: bold;
    }
    #meta-line {
        color: $text-muted;
    }
    #log-panel {
        height: 1fr;
        border: solid $accent;
        margin: 0 1;
    }
    #input-row {
        height: 3;
        margin: 0 1 1 1;
    }
    #cmd-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit_app", "退出", show=True, priority=True),
        Binding("f2", "open_settings", "设置", show=True),
        Binding("f1", "show_help", "帮助", show=True),
    ]

    status_text: reactive[str] = reactive("待命")
    connected: reactive[bool] = reactive(False)
    auto_mode: reactive[bool] = reactive(False)
    chat_text: reactive[str] = reactive("")
    music_line: reactive[str] = reactive("")
    emotion: reactive[str] = reactive("neutral")

    def __init__(
        self,
        on_command: Callable[[str], None] | None = None,
        on_settings_saved: Callable[[], None] | None = None,
        config: ConfigManager | None = None,
        settings_services: SettingsServices | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._config = config if config is not None else ConfigManager.from_dict()
        self._settings_services = (
            settings_services
            if settings_services is not None
            else SettingsServices(self._config)
        )
        self._on_command = on_command
        self._on_settings_saved = on_settings_saved
        self._log_handler_installed = False
        self._tui_log_handler = None
        self._muted_console_handlers = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="status-panel"):
            yield Static("状态: 待命", id="status-line")
            yield Static("连接: 未连接 | 模式: 手动 | 表情: neutral", id="meta-line")
            yield Static("对话: —", id="chat-line")
            yield Static("音乐: —", id="music-line")
        yield RichLog(id="log-panel", highlight=True, markup=True, max_lines=500)
        with Horizontal(id="input-row"):
            yield Input(
                placeholder=(
                    "输入文本发送 | r 对话 | x 打断 | s 设置 | q 退出 | h 帮助"
                ),
                id="cmd-input",
            )
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#cmd-input", Input).focus()
        self._install_log_handler()
        self._refresh_status_widgets()
        self.write_log(
            f"[bold cyan]{SystemConstants.APP_DISPLAY_NAME} TUI[/]  "
            "F2 设置 · F1 帮助 · Ctrl+C 退出"
        )

    def on_unmount(self) -> None:
        self.uninstall_log_handler()

    def watch_status_text(self, _value: str) -> None:
        self._refresh_status_widgets()

    def watch_connected(self, _value: bool) -> None:
        self._refresh_status_widgets()

    def watch_auto_mode(self, _value: bool) -> None:
        self._refresh_status_widgets()

    def watch_chat_text(self, _value: str) -> None:
        self._refresh_status_widgets()

    def watch_music_line(self, _value: str) -> None:
        self._refresh_status_widgets()

    def watch_emotion(self, _value: str) -> None:
        self._refresh_status_widgets()

    def _refresh_status_widgets(self) -> None:
        try:
            conn = "已连接" if self.connected else "未连接"
            mode = "自动" if self.auto_mode else "手动"
            self.query_one("#status-line", Static).update(f"状态: {self.status_text}")
            self.query_one("#meta-line", Static).update(
                f"连接: {conn} | 模式: {mode} | 表情: {self.emotion}"
            )
            self.query_one("#chat-line", Static).update(
                f"对话: {self.chat_text or '—'}"
            )
            self.query_one("#music-line", Static).update(
                f"音乐: {self.music_line or '—'}"
            )
        except Exception:
            pass

    def write_log(self, message: str) -> None:
        try:
            self.query_one("#log-panel", RichLog).write(message)
        except Exception:
            pass

    @on(Input.Submitted, "#cmd-input")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = (event.value or "").strip()
        event.input.value = ""
        if text:
            self._dispatch_command(text)

    def _dispatch_command(self, text: str) -> None:
        raw = text.strip()
        key = raw.lower()
        if key.startswith("/"):
            key = key[1:]

        if key in ("s", "settings", "set"):
            self.action_open_settings()
            return
        if key in ("h", "help", "?"):
            self.action_show_help()
            return
        if key in ("q", "quit", "exit"):
            self.action_quit_app()
            return

        if self._on_command:
            if key in ("r", "x") and raw.startswith("/"):
                self._on_command(key)
            else:
                self._on_command(raw)

    def action_show_help(self) -> None:
        self.write_log(
            "[bold cyan]帮助[/]\n"
            "  文本 → 发送给助手\n"
            "  r → 开始/停止对话\n"
            "  x → 打断\n"
            "  s / F2 → 设置\n"
            "  q / Ctrl+C → 退出\n"
            "  h / F1 → 帮助"
        )

    def action_open_settings(self) -> None:
        if isinstance(self.screen, SettingsScreen):
            return
        screen = SettingsScreen(self._config, services=self._settings_services)

        def _done(saved: bool | None) -> None:
            if saved:
                from rich.markup import escape

                self.write_log(f"[green]{escape(screen.saved_message)}[/]")
                if screen.changed_paths and self._on_settings_saved:
                    try:
                        self._on_settings_saved()
                    except Exception as e:
                        logger.error(f"设置保存回调失败: {e}", exc_info=True)
                        self.write_log("[red]配置已保存，运行时应用失败，请重启应用[/]")

        self.push_screen(screen, _done)

    def action_quit_app(self) -> None:
        if self._on_command:
            self._on_command("q")
        self.exit()

    def _install_log_handler(self) -> None:
        if self._log_handler_installed:
            return
        import logging

        import src.logging as app_logging

        app = self

        class TuiLogHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    msg = self.format(record)
                    # Never wait for the UI while holding the logging handler's
                    # lock: the UI thread may be logging to this handler too.
                    app.call_later(app.write_log, msg)
                except Exception:
                    pass

        handler = TuiLogHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"
            )
        )
        handler.setLevel(logging.INFO)
        # Leave host handlers attached. Temporarily silence only our console sinks,
        # including those owned by an asynchronous queue listener.
        class MuteConsole(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                return False

        owned = list(app_logging._owned_handlers)
        owned.extend(h for h, _ in app_logging._bootstrap_handlers.values())
        for h in owned:
            sinks = (
                h._listener.handlers
                if isinstance(h, app_logging.AsyncHandler)
                else (h,)
            )
            for sink in sinks:
                if isinstance(sink, logging.StreamHandler) and not isinstance(
                    sink, logging.FileHandler
                ):
                    mute = MuteConsole()
                    sink.addFilter(mute)
                    self._muted_console_handlers.append((sink, mute))
        root = logging.getLogger()
        root.addHandler(handler)
        self._tui_log_handler = handler
        self._log_handler_installed = True

    def uninstall_log_handler(self) -> None:
        if not self._log_handler_installed:
            return
        import logging

        h = self._tui_log_handler
        if h is not None:
            try:
                logging.getLogger().removeHandler(h)
            except Exception:
                pass
            h.close()
        for sink, mute in self._muted_console_handlers:
            sink.removeFilter(mute)
        self._muted_console_handlers.clear()
        self._log_handler_installed = False
        self._tui_log_handler = None
