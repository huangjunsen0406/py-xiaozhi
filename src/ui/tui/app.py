"""Textual App：仪表盘 + 设置屏."""

from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Static,
    TabbedContent,
    TabPane,
)

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.ui.tui.settings_data import (
    SETTING_SECTIONS,
    load_setting_values,
    save_settings,
)

logger = get_logger()


class SettingsScreen(ModalScreen[bool]):
    """配置编辑弹层；返回 True 表示已保存."""

    BINDINGS = [
        Binding("escape", "cancel", "取消", show=True),
    ]

    CSS = """
    SettingsScreen {
        align: center middle;
    }
    #settings-dialog {
        width: 90%;
        max-width: 100;
        height: 85%;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }
    #settings-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #settings-hint {
        color: $text-muted;
        margin-bottom: 1;
    }
    .field-row {
        height: auto;
        margin-bottom: 1;
    }
    .field-label {
        width: 20;
        color: $text-muted;
        padding-top: 1;
    }
    .field-input {
        width: 1fr;
    }
    #settings-actions {
        height: 3;
        align: right middle;
        margin-top: 1;
    }
    #settings-status {
        color: $accent;
        height: 1;
        margin-top: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._values = load_setting_values()

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Static("设置", id="settings-title")
            yield Static(
                "编辑后点「保存」写盘并热应用 | Esc 取消 | "
                "choice 字段请填合法值（见占位提示）",
                id="settings-hint",
            )
            with TabbedContent():
                for section_name, fields in SETTING_SECTIONS:
                    with TabPane(section_name):
                        with VerticalScroll():
                            for f in fields:
                                with Horizontal(classes="field-row"):
                                    yield Label(f.label, classes="field-label")
                                    current = self._values.get(f.path, "")
                                    placeholder = f.help or f.path
                                    if f.kind == "choice" and f.choices:
                                        placeholder = f"可选: {', '.join(f.choices)}"
                                    elif f.kind == "bool":
                                        placeholder = "true / false"
                                    yield Input(
                                        value=current,
                                        placeholder=placeholder,
                                        id=f"fld-{f.path.replace('.', '-')}",
                                        classes="field-input",
                                    )
            yield Static("", id="settings-status")
            with Horizontal(id="settings-actions"):
                yield Button("取消", id="btn-cancel", variant="default")
                yield Button("保存", id="btn-save", variant="primary")

    def _collect_values(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for _section, fields in SETTING_SECTIONS:
            for f in fields:
                wid = f"fld-{f.path.replace('.', '-')}"
                try:
                    w = self.query_one(f"#{wid}", Input)
                    out[f.path] = w.value
                except Exception:
                    out[f.path] = self._values.get(f.path, "")
        return out

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel_btn(self) -> None:
        self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    @on(Button.Pressed, "#btn-save")
    def on_save_btn(self) -> None:
        values = self._collect_values()
        ok, msg = save_settings(values)
        try:
            self.query_one("#settings-status", Static).update(msg)
        except Exception:
            pass
        if ok:
            self.dismiss(True)


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
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._on_command = on_command
        self._on_settings_saved = on_settings_saved
        self._log_handler_installed = False
        self._tui_log_handler = None

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
        def _done(saved: bool | None) -> None:
            if saved:
                self.write_log("[green]配置已保存，正在热应用…[/]")
                if self._on_settings_saved:
                    try:
                        self._on_settings_saved()
                    except Exception as e:
                        logger.error(f"设置保存回调失败: {e}", exc_info=True)
                        self.write_log(f"[red]热应用失败: {e}[/]")

        self.push_screen(SettingsScreen(), _done)

    def action_quit_app(self) -> None:
        if self._on_command:
            self._on_command("q")
        self.exit()

    def _install_log_handler(self) -> None:
        if self._log_handler_installed:
            return
        import logging

        app = self

        class TuiLogHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                try:
                    msg = self.format(record)
                    app.call_from_thread(app.write_log, msg)
                except Exception:
                    pass

        handler = TuiLogHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S"
            )
        )
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, logging.StreamHandler) and not isinstance(
                h, logging.FileHandler
            ):
                try:
                    root.removeHandler(h)
                except Exception:
                    pass
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
        self._log_handler_installed = False
        self._tui_log_handler = None
