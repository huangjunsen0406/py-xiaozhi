"""Typed TUI settings form; runtime operations stay with the injected services."""

from __future__ import annotations

import asyncio

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    Select,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from src.mcp.tool_catalog import normalize_disabled
from src.ui.tui.settings_data import (
    SETTING_SECTIONS,
    load_setting_values,
    preview_wake_word,
    save_settings,
)
from src.ui.tui.settings_services import SettingsServices
from src.utils.config_manager import ConfigManager

# Keep the terminal form focused on daily use; other settings remain untouched.
_FIELDS = {field.path: field for _, fields in SETTING_SECTIONS for field in fields}
DISPLAY_SECTIONS = [
    (
        "系统",
        [
            _FIELDS[path]
            for path in (
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL",
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL",
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN",
            )
        ],
    ),
    (
        "音频",
        [
            _FIELDS[path]
            for path in (
                "AUDIO_DEVICES.input_device_name",
                "AUDIO_DEVICES.output_device_name",
                "AUDIO_DEVICES.opus_output_sample_rate",
                "AUDIO_DEVICES.frame_duration",
                "AEC_OPTIONS.ENABLED",
                "AEC_OPTIONS.MUSIC_PARALLEL",
            )
        ],
    ),
    (
        "唤醒",
        [
            _FIELDS[path]
            for path in (
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD",
                "WAKE_WORD_OPTIONS.WAKE_WORD",
            )
        ],
    ),
    (
        "摄像头",
        [
            _FIELDS[path]
            for path in (
                "CAMERA.camera_index",
                "CAMERA.frame_width",
                "CAMERA.frame_height",
                "CAMERA.Local_VL_url",
                "CAMERA.VLapi_key",
                "CAMERA.models",
            )
        ],
    ),
    (
        "音乐",
        [
            _FIELDS[path]
            for path in (
                "MUSIC.SEARCH_URL",
                "MUSIC.URL_API",
                "MUSIC.URL_API_KEY",
                "MUSIC.DEFAULT_QUALITY",
            )
        ],
    ),
]


def field_id(path: str) -> str:
    return "fld-" + path.replace(".", "-")


class SettingsScreen(ModalScreen[bool]):
    """Keep edits local until a validated commit succeeds."""

    BINDINGS = [Binding("escape", "cancel", "取消"), Binding("ctrl+s", "save", "保存")]
    CSS = """
    SettingsScreen { align: center middle; }
    #settings-dialog {
        width: 90%; max-width: 100; height: 85%;
        border: round $primary; background: $surface; padding: 0 2;
    }
    #settings-title { height: 1; margin-bottom: 1; text-style: bold; }
    #settings-content { height: 1fr; min-height: 0; }
    #settings-content > ContentTabs { height: 2; }
    #settings-content TabPane { padding: 1 0 0 0; }
    .field-row { height: auto; min-height: 3; }
    .field-label { width: 18; padding-top: 1; color: $text-muted; }
    .field-value { width: 1fr; height: auto; }
    .field-input { width: 1fr; }
    .runtime-actions { height: 3; }
    .runtime-actions > Select { width: 1fr; }
    .runtime-actions > Button { min-width: 8; width: auto; }
    .runtime-info { height: auto; min-height: 1; color: $text-muted; }
    #devices-status { margin-bottom: 1; }
    #mcp-tools { height: 1fr; min-height: 1; }
    #settings-status { height: 1; color: $accent; margin-top: 1; }
    #settings-actions { height: 3; align: right middle; }
    #settings-shortcuts { width: 1fr; color: $text-muted; padding-top: 1; }
    """

    def __init__(
        self,
        config: ConfigManager | None = None,
        *,
        services: SettingsServices | None = None,
    ):
        super().__init__()
        self._config = config if config is not None else ConfigManager.from_dict()
        self._services = (
            services if services is not None else SettingsServices(self._config)
        )
        self._values = load_setting_values(self._config)
        self._initial_disabled = normalize_disabled(
            self._config.get_config("MCP_TOOLS.DISABLED", [])
        )
        self._disabled_tools = set(self._initial_disabled)
        self._device_lists: dict[str, list[dict]] = {"input": [], "output": []}
        self._devices_loaded = False
        self._refreshing_devices = False
        self._device_generation = 0
        self._missing_devices: dict[str, tuple[str, int]] = {}
        self._catalog: list[dict] = []
        self._visible_tools: list[str] = []
        self._settings_closed = False
        self.changed_paths: set[str] = set()
        self.saved_message = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-dialog"):
            yield Static("设置", id="settings-title")
            with TabbedContent(id="settings-content"):
                for i, (name, fields) in enumerate(DISPLAY_SECTIONS):
                    with TabPane(name, id=f"section-{i}"):
                        with VerticalScroll():
                            if name == "音频":
                                with Horizontal(classes="runtime-actions"):
                                    yield Button("刷新设备", id="devices-refresh")
                                yield Static(
                                    "刷新会短暂中断音频。",
                                    id="devices-status",
                                    classes="runtime-info",
                                )
                            for field in fields:
                                with Horizontal(classes="field-row"):
                                    yield Label(field.label, classes="field-label")
                                    with Vertical(classes="field-value"):
                                        yield self._field_widget(field)
                                        if field.path in (
                                            "AUDIO_DEVICES.input_device_name",
                                            "AUDIO_DEVICES.output_device_name",
                                        ):
                                            direction = (
                                                "input"
                                                if "input_device" in field.path
                                                else "output"
                                            )
                                            yield Static(
                                                "",
                                                id=f"device-info-{direction}",
                                                classes="runtime-info",
                                                markup=False,
                                            )
                            if name == "唤醒":
                                yield Static(
                                    "保存时自动识别语言并生成关键词。",
                                    classes="runtime-info",
                                )
                                yield Button("转换预览", id="wake-preview")
                                yield Static(
                                    "",
                                    id="wake-preview-result",
                                    classes="runtime-info",
                                    markup=False,
                                )
                with TabPane("工具", id="section-mcp"):
                    with Vertical():
                        with Horizontal(classes="runtime-actions"):
                            yield Select(
                                [("全部分组", "")],
                                value="",
                                allow_blank=False,
                                id="mcp-group",
                            )
                            yield Button("全开", id="mcp-enable")
                            yield Button("全关", id="mcp-disable")
                            yield Button("刷新", id="mcp-refresh")
                        yield SelectionList(id="mcp-tools")
                        yield Static(
                            "", id="mcp-count", classes="runtime-info", markup=False
                        )
            yield Static("", id="settings-status", markup=False)
            with Horizontal(id="settings-actions"):
                yield Static("Ctrl+S 保存 · Esc 取消", id="settings-shortcuts")
                yield Button("取消", id="btn-cancel")
                yield Button("保存", id="btn-save", variant="primary")

    def _field_widget(self, field):
        value = self._values.get(field.path, "")
        args = {
            "id": field_id(field.path),
            "classes": "field-input",
            "tooltip": field.help or None,
        }
        if field.path in (
            "AUDIO_DEVICES.input_device_name",
            "AUDIO_DEVICES.output_device_name",
        ):
            direction = "input" if "input_device" in field.path else "output"
            device_id = self._config.get_config(
                f"AUDIO_DEVICES.{direction}_device_id", -1
            )
            configured = bool(value) or isinstance(device_id, int) and device_id >= 0
            options = [("系统默认设备", -1)]
            if configured:
                options.append((f"已配置：{value or f'设备 ID {device_id}'}", -2))
            return Select(
                options, value=-2 if configured else -1, allow_blank=False, **args
            )
        if field.kind == "bool":
            return Switch(value=value.lower() in ("true", "1", "yes"), **args)
        if field.kind == "choice":
            options = [(choice, choice) for choice in field.choices]
            if value not in field.choices:
                options.append((f"待修正：{value or '空值'}", value))
            return Select(options, value=value, allow_blank=False, **args)
        if field.kind == "readonly":
            return Static(value or "自动识别", markup=False, **args)
        return Input(
            value=value, password=field.kind == "secret", placeholder=field.help, **args
        )

    def _status(self, text: str) -> None:
        if self.is_mounted and not self._settings_closed:
            self.query_one("#settings-status", Static).update(text)

    @on(TabbedContent.TabActivated, "#settings-content")
    def _category_changed(self, event: TabbedContent.TabActivated) -> None:
        pane_id = event.pane.id
        if pane_id == "section-mcp":
            self._load_catalog()
        elif (
            pane_id == "section-1"
            and not self._devices_loaded
            and not self._refreshing_devices
        ):
            self._start_device_load(False)

    @on(Button.Pressed, "#devices-refresh")
    def _refresh_devices(self) -> None:
        self._start_device_load(True)

    def _start_device_load(self, refresh: bool) -> None:
        self._device_generation += 1
        self._refreshing_devices = True
        self.query_one("#devices-refresh", Button).disabled = True
        self.query_one("#btn-save", Button).disabled = True
        self.query_one("#devices-status", Static).update("正在读取音频设备…")
        self.run_worker(
            self._load_devices(refresh, self._device_generation),
            group="settings-devices",
            exclusive=True,
            exit_on_error=False,
        )

    async def _load_devices(self, refresh: bool, generation: int) -> None:
        try:
            devices = await self._services.audio_devices(refresh=refresh)
            if (
                self._settings_closed
                or not self.is_mounted
                or generation != self._device_generation
            ):
                return
            selections = {
                direction: self._selected_device(direction)
                for direction in ("input", "output")
            }
            self._device_lists = devices
            self._devices_loaded = True
            for direction in ("input", "output"):
                name, device_id = selections[direction]
                options = [("系统默认设备", -1)] + [
                    (d["name"], d["index"]) for d in devices[direction]
                ]
                match = (
                    next((d for d in devices[direction] if d["raw_name"] == name), None)
                    if name
                    else next(
                        (d for d in devices[direction] if d["index"] == device_id), None
                    )
                )
                selected = match["index"] if match else -1
                if match is None and (name or device_id >= 0):
                    self._missing_devices[direction] = (name, device_id)
                    options.append((f"未找到：{name or f'设备 ID {device_id}'}", -2))
                    selected = -2
                widget = self.query_one(
                    "#" + field_id(f"AUDIO_DEVICES.{direction}_device_name"), Select
                )
                widget.set_options(options)
                widget.value = selected
                self._device_info(direction)
            self.query_one("#devices-status", Static).update(
                f"输入 {len(devices['input'])} 个 / 输出 {len(devices['output'])} 个；可选择系统默认设备。"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if generation == self._device_generation:
                self._status(f"设备刷新失败：{exc}")
                if not self._settings_closed and self.is_mounted:
                    self.query_one("#devices-status", Static).update(
                        "刷新失败，已保留原设备列表；可重试。"
                    )
        finally:
            if generation == self._device_generation:
                self._refreshing_devices = False
                if not self._settings_closed and self.is_mounted:
                    self.query_one("#devices-refresh", Button).disabled = False
                    self.query_one("#btn-save", Button).disabled = False

    def _selected_device(self, direction: str) -> tuple[str, int]:
        path = f"AUDIO_DEVICES.{direction}_device_name"
        value = self.query_one("#" + field_id(path), Select).value
        if value == -1:
            return "", -1
        row = next(
            (d for d in self._device_lists[direction] if d["index"] == value), None
        )
        if row is not None:
            return row["raw_name"], row["index"]
        if direction in self._missing_devices:
            return self._missing_devices[direction]
        original_id = self._config.get_config(
            f"AUDIO_DEVICES.{direction}_device_id", -1
        )
        return self._values.get(path, ""), original_id if isinstance(
            original_id, int
        ) else -1

    @on(Select.Changed)
    def _device_changed(self, event: Select.Changed) -> None:
        if event.value != event.select.value:
            return
        for direction in ("input", "output"):
            if event.select.id == field_id(f"AUDIO_DEVICES.{direction}_device_name"):
                self._device_info(direction)

    def _device_info(self, direction: str) -> None:
        _name, device_id = self._selected_device(direction)
        row = next(
            (d for d in self._device_lists[direction] if d["index"] == device_id), None
        )
        text = (
            f"采样率：{row['sample_rate']} Hz；通道：{row['channels']}"
            if row
            else "使用系统默认设备"
            if device_id == -1
            else "设备当前不可用；保存会保留原配置"
        )
        self.query_one(f"#device-info-{direction}", Static).update(text)

    def _capture_tool_selection(self) -> None:
        selected = set(self.query_one("#mcp-tools", SelectionList).selected)
        self._disabled_tools.update(set(self._visible_tools) - selected)
        self._disabled_tools.difference_update(selected)

    def _load_catalog(self) -> None:
        self._capture_tool_selection()
        try:
            self._catalog = self._services.tool_catalog(sorted(self._disabled_tools))
            groups = {row["group"]: row["groupLabel"] for row in self._catalog}
            group = self.query_one("#mcp-group", Select)
            previous = group.value
            group.set_options(
                [("全部分组", ""), *[(label, name) for name, label in groups.items()]]
            )
            group.value = previous if previous in groups else ""
            self._show_tools()
        except Exception as exc:
            self._status(f"读取工具目录失败：{exc}")

    def _show_tools(self) -> None:
        group = self.query_one("#mcp-group", Select).value
        rows = [row for row in self._catalog if not group or row["group"] == group]
        self._visible_tools = [row["name"] for row in rows]
        widget = self.query_one("#mcp-tools", SelectionList)
        widget.clear_options()
        widget.add_options(
            [
                (
                    f"{row['label']} · {row['name']}",
                    row["name"],
                    row["name"] not in self._disabled_tools,
                )
                for row in rows
            ]
        )
        enabled = sum(row["name"] not in self._disabled_tools for row in rows)
        self.query_one("#mcp-count", Static).update(
            f"当前分组 {enabled}/{len(rows)} 已启用"
        )

    @on(Select.Changed, "#mcp-group")
    def _group_changed(self, event: Select.Changed) -> None:
        if event.value == event.select.value:
            self._capture_tool_selection()
            self._show_tools()

    @on(SelectionList.SelectedChanged, "#mcp-tools")
    def _tools_changed(self) -> None:
        self._capture_tool_selection()
        enabled = len(self.query_one("#mcp-tools", SelectionList).selected)
        self.query_one("#mcp-count", Static).update(
            f"当前分组 {enabled}/{len(self._visible_tools)} 已启用"
        )

    @on(Button.Pressed, "#mcp-enable")
    def _enable_tools(self) -> None:
        self.query_one("#mcp-tools", SelectionList).select_all()
        self._capture_tool_selection()

    @on(Button.Pressed, "#mcp-disable")
    def _disable_tools(self) -> None:
        self.query_one("#mcp-tools", SelectionList).deselect_all()
        self._capture_tool_selection()

    @on(Button.Pressed, "#mcp-refresh")
    def _refresh_catalog(self) -> None:
        self._load_catalog()

    @on(Button.Pressed, "#wake-preview")
    def _preview_wake(self) -> None:
        self.run_worker(
            self._convert_preview(),
            group="settings-preview",
            exclusive=True,
            exit_on_error=False,
        )

    async def _convert_preview(self) -> None:
        text = self.query_one(
            "#" + field_id("WAKE_WORD_OPTIONS.WAKE_WORD"), Input
        ).value
        try:
            line, language, _model = await asyncio.to_thread(preview_wake_word, text)
            if (
                not self._settings_closed
                and self.is_mounted
                and text
                == self.query_one(
                    "#" + field_id("WAKE_WORD_OPTIONS.WAKE_WORD"), Input
                ).value
            ):
                self.query_one("#wake-preview-result", Static).update(
                    f"{language}：{line}"
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._status(f"唤醒词转换失败：{exc}")

    def _collect_values(self) -> tuple[dict[str, str], dict]:
        values = {}
        device_updates = {}
        for _section, fields in DISPLAY_SECTIONS:
            for field in fields:
                widget = self.query_one("#" + field_id(field.path))
                if field.path in (
                    "AUDIO_DEVICES.input_device_name",
                    "AUDIO_DEVICES.output_device_name",
                ):
                    direction = "input" if "input_device" in field.path else "output"
                    name, index = self._selected_device(direction)
                    values[field.path] = name
                    device_updates[field.path] = name
                    device_updates[f"AUDIO_DEVICES.{direction}_device_id"] = index
                elif isinstance(widget, Switch):
                    values[field.path] = "true" if widget.value else "false"
                elif isinstance(widget, Select):
                    values[field.path] = str(widget.value)
                elif isinstance(widget, Input):
                    values[field.path] = widget.value
                else:
                    values[field.path] = self._values.get(field.path, "")
        return values, device_updates

    @on(Button.Pressed, "#btn-save")
    def on_save_btn(self) -> None:
        self.action_save()

    def action_save(self) -> None:
        if self._settings_closed:
            return
        if self._refreshing_devices:
            self._status("设备刷新中，请稍后保存")
            return
        self._capture_tool_selection()
        values, device_updates = self._collect_values()
        changed = {
            path
            for path, value in values.items()
            if value != self._values.get(path, "")
        }
        changed.update(
            path
            for path, value in device_updates.items()
            if value != self._config.get_config(path)
        )
        if sorted(self._disabled_tools) != sorted(self._initial_disabled):
            changed.add("MCP_TOOLS.DISABLED")
        ok, message = save_settings(
            values,
            self._config,
            disabled_tools=sorted(self._disabled_tools),
            device_updates=device_updates,
        )
        self._status(message)
        if not ok:
            return
        self.changed_paths = changed
        effects = {
            getattr(field, "effect", "hot")
            for _, fields in SETTING_SECTIONS
            for field in fields
            if field.path in changed
        }
        notes = []
        if "restart" in effects:
            notes.append("部分设置重启后生效")
        if "reconnect" in effects or "MCP_TOOLS.DISABLED" in changed:
            notes.append("连接设置将重连更新")
        self.saved_message = message + ("；" + "；".join(notes) if notes else "")
        self._settings_closed = True
        self.dismiss(True)

    @on(Button.Pressed, "#btn-cancel")
    def on_cancel_btn(self) -> None:
        self.action_cancel()

    def action_cancel(self) -> None:
        self._settings_closed = True
        self.dismiss(False)

    def on_unmount(self) -> None:
        self._settings_closed = True
