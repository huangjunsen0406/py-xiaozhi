"""纯 Python TUI 设置字段、校验和完整草稿提交。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from src.core.settings import requires_protocol_reconnect
from src.i18n import LANGUAGE_CHOICES, t
from src.logging import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger()


@dataclass(frozen=True)
class SettingField:
    """控件元数据；UI 输入始终为字符串，effect 说明生效时机。"""

    path: str
    label_key: str
    kind: str = "str"
    choices: tuple[str, ...] = ()
    help_key: str = ""
    minimum: float | None = None
    maximum: float | None = None
    effect: str = "hot"

    def __post_init__(self) -> None:
        if requires_protocol_reconnect(self.path):
            object.__setattr__(self, "effect", "reconnect")

    @property
    def label(self) -> str:
        return t(self.label_key)

    @property
    def help(self) -> str:
        return t(self.help_key) if self.help_key else ""


SETTING_SECTIONS: list[tuple[str, list[SettingField]]] = [
    (
        "system",
        [
            SettingField(
                "SYSTEM_OPTIONS.LANGUAGE",
                "tui.field.language",
                kind="choice",
                choices=LANGUAGE_CHOICES,
                help_key="tui.field.language_help",
                effect="hot",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL",
                "tui.field.ota_url",
                help_key="tui.field.ota_url_help",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL",
                "tui.field.ws_url",
                help_key="tui.field.ws_url_help",
            ),
            SettingField(
                "SYSTEM_OPTIONS.DEVICE_ID",
                "tui.field.device_id",
                help_key="tui.field.device_id_help",
            ),
            SettingField(
                "SYSTEM_OPTIONS.CLIENT_ID",
                "tui.field.client_id",
                help_key="tui.field.client_id_help",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN",
                "tui.field.ws_token",
                kind="secret",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL",
                "tui.field.auth_url",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION",
                "tui.field.activation_version",
                kind="choice",
                choices=("v1", "v2"),
            ),
        ],
    ),
    (
        "audio",
        [
            SettingField(
                "AUDIO_DEVICES.input_device_name",
                "tui.field.input_device_name",
                help_key="tui.field.input_device_name_help",
                effect="hot",
            ),
            SettingField(
                "AUDIO_DEVICES.output_device_name",
                "tui.field.output_device_name",
                help_key="tui.field.output_device_name_help",
                effect="hot",
            ),
            SettingField(
                "AUDIO_DEVICES.opus_output_sample_rate",
                "tui.field.opus_rate",
                kind="choice",
                choices=("24000", "16000"),
                help_key="tui.field.opus_rate_help",
            ),
            SettingField(
                "AUDIO_DEVICES.frame_duration",
                "tui.field.frame_duration",
                kind="choice",
                choices=("20", "40", "60"),
                help_key="tui.field.frame_duration_help",
            ),
        ],
    ),
    (
        "aec",
        [
            SettingField(
                "AEC_OPTIONS.ENABLED",
                "tui.field.aec_enabled",
                kind="bool",
                effect="hot",
            ),
            SettingField(
                "AEC_OPTIONS.MEDIA_PARALLEL",
                "tui.field.aec_media_parallel",
                kind="bool",
            ),
            SettingField(
                "AEC_OPTIONS.FRAME_DELAY",
                "tui.field.aec_frame_delay",
                kind="int",
                minimum=0,
                maximum=20,
                help_key="tui.field.aec_frame_delay_help",
                effect="hot",
            ),
            SettingField(
                "AEC_OPTIONS.ENABLE_PREPROCESS",
                "tui.field.aec_preprocess",
                kind="bool",
                effect="hot",
            ),
        ],
    ),
    (
        "mqtt",
        [
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint",
                "tui.field.mqtt_endpoint",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id",
                "tui.field.mqtt_client_id",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username",
                "tui.field.mqtt_username",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password",
                "tui.field.mqtt_password",
                kind="secret",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic",
                "tui.field.mqtt_pub",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic",
                "tui.field.mqtt_sub",
            ),
        ],
    ),
    (
        "camera",
        [
            SettingField(
                "CAMERA.backend",
                "tui.field.camera_backend",
                kind="choice",
                choices=("auto", "opencv", "picamera2"),
                help_key="tui.field.camera_backend_help",
                effect="hot",
            ),
            SettingField(
                "CAMERA.device",
                "tui.field.camera_device",
                help_key="tui.field.camera_device_help",
                effect="hot",
            ),
            SettingField(
                "CAMERA.camera_index",
                "tui.field.camera_index",
                kind="int",
                minimum=0,
                help_key="tui.field.camera_index_help",
                effect="hot",
            ),
            SettingField(
                "CAMERA.frame_width",
                "tui.field.camera_width",
                kind="int",
                minimum=320,
                maximum=1920,
                effect="hot",
            ),
            SettingField(
                "CAMERA.frame_height",
                "tui.field.camera_height",
                kind="int",
                minimum=240,
                maximum=1080,
                effect="hot",
            ),
            SettingField(
                "CAMERA.Local_VL_url",
                "tui.field.camera_vl_url",
                effect="restart",
            ),
            SettingField(
                "CAMERA.VLapi_key",
                "tui.field.camera_vl_key",
                kind="secret",
                effect="restart",
            ),
            SettingField(
                "CAMERA.models",
                "tui.field.camera_models",
                effect="restart",
            ),
        ],
    ),
    (
        "wake",
        [
            SettingField(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD",
                "tui.field.wake_enabled",
                kind="bool",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD",
                "tui.field.wake_word",
                help_key="tui.field.wake_word_help",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD_LANG",
                "tui.field.wake_lang",
                kind="readonly",
                help_key="tui.field.wake_lang_help",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.NUM_THREADS",
                "tui.field.wake_threads",
                kind="int",
                minimum=1,
                maximum=16,
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.KEYWORDS_SCORE",
                "tui.field.wake_score",
                kind="float",
                minimum=0.5,
                maximum=3,
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD",
                "tui.field.wake_threshold",
                kind="float",
                minimum=0,
                maximum=1,
                effect="hot",
            ),
        ],
    ),
    (
        "shortcuts",
        [
            SettingField(
                "SHORTCUTS.ENABLED",
                "tui.field.shortcuts_enabled",
                kind="bool",
            ),
            SettingField(
                "SHORTCUTS.MANUAL_PRESS.modifier",
                "tui.field.shortcut_manual_mod",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField(
                "SHORTCUTS.MANUAL_PRESS.key", "tui.field.shortcut_manual_key"
            ),
            SettingField(
                "SHORTCUTS.AUTO_TOGGLE.modifier",
                "tui.field.shortcut_auto_mod",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.AUTO_TOGGLE.key", "tui.field.shortcut_auto_key"),
            SettingField(
                "SHORTCUTS.ABORT.modifier",
                "tui.field.shortcut_abort_mod",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.ABORT.key", "tui.field.shortcut_abort_key"),
            SettingField(
                "SHORTCUTS.MODE_TOGGLE.modifier",
                "tui.field.shortcut_mode_mod",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.MODE_TOGGLE.key", "tui.field.shortcut_mode_key"),
        ],
    ),
]

_NUMERIC_CHOICES = {
    "AUDIO_DEVICES.opus_output_sample_rate",
    "AUDIO_DEVICES.frame_duration",
}
_DEVICE_PATHS = {
    f"AUDIO_DEVICES.{direction}_device_{part}"
    for direction in ("input", "output")
    for part in ("id", "name")
}


def load_setting_values(config: ConfigManager | None = None) -> dict[str, str]:
    """读取配置为控件字符串表，不转换唤醒词或枚举设备。"""
    cfg = config if config is not None else ConfigManager.from_dict()
    values: dict[str, str] = {}
    for _section, fields in SETTING_SECTIONS:
        for field in fields:
            raw = cfg.get_config(field.path, "")
            if field.kind == "bool" and isinstance(raw, bool):
                values[field.path] = "true" if raw else "false"
            else:
                values[field.path] = "" if raw is None else str(raw)
    return values


def parse_field_value(field: SettingField, text: str) -> Any:
    """严格转换字段值；未知布尔值、choice 和非法数值抛出 ValueError。"""
    if not isinstance(text, str):
        raise ValueError(t("tui.validation.must_be_str", label=field.label))
    if field.kind == "secret":
        return text
    if field.path.startswith("SHORTCUTS.") and field.path.endswith(".key"):
        if len(text) != 1 or not text.strip():
            raise ValueError(
                t("tui.validation.must_be_single_char", label=field.label)
            )
        return text.lower()
    value = text.strip()
    if field.kind == "bool":
        normalized = value.lower()
        if normalized in {"1", "true", "yes", "on", "是"}:
            return True
        if normalized in {"0", "false", "no", "off", "否"}:
            return False
        raise ValueError(t("tui.validation.must_be_bool", label=field.label))
    if field.kind == "choice":
        if value not in field.choices:
            raise ValueError(
                t(
                    "tui.validation.must_be_choice",
                    label=field.label,
                    choices=", ".join(field.choices),
                )
            )
        return int(value) if field.path in _NUMERIC_CHOICES else value
    if field.kind in {"int", "float"}:
        try:
            parsed = int(value) if field.kind == "int" else float(value)
            finite = math.isfinite(parsed)
        except (ValueError, OverflowError) as exc:
            expected = t(
                "tui.validation.type_int"
                if field.kind == "int"
                else "tui.validation.type_float"
            )
            raise ValueError(
                t(
                    "tui.validation.must_be_number",
                    label=field.label,
                    expected=expected,
                )
            ) from exc
        if not finite:
            raise ValueError(t("tui.validation.must_be_finite", label=field.label))
        if field.minimum is not None and parsed < field.minimum:
            raise ValueError(
                t(
                    "tui.validation.min_value",
                    label=field.label,
                    min=f"{field.minimum:g}",
                )
            )
        if field.maximum is not None and parsed > field.maximum:
            raise ValueError(
                t(
                    "tui.validation.max_value",
                    label=field.label,
                    max=f"{field.maximum:g}",
                )
            )
        return parsed
    if field.kind in {"str", "readonly"}:
        return value
    raise ValueError(t("tui.validation.unknown_kind", kind=field.kind))


def preview_wake_word(text: str) -> tuple[str, str, str]:
    """返回既有 converter 的 (keyword_line, lang, model_path)，不写入文件。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError(t("settings.wake_word.enter_prompt"))
    from src.audio_processing.keyword_converters import convert_wake_word

    return convert_wake_word(text.strip())


def _set_path(draft: dict, path: str, value: Any) -> None:
    from src.ui.shared.settings_helpers import set_draft_value

    set_draft_value(draft, path, value)


def _validate_extras(disabled_tools, device_updates) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if disabled_tools is not None:
        if not isinstance(disabled_tools, list) or any(
            not isinstance(name, str) or not name.strip() for name in disabled_tools
        ):
            raise ValueError(t("tui.validation.disabled_tools_invalid"))
        updates["MCP_TOOLS.DISABLED"] = list(
            dict.fromkeys(n.strip() for n in disabled_tools)
        )
    if device_updates is not None:
        if not isinstance(device_updates, dict):
            raise ValueError(t("tui.validation.device_updates_dict"))
        for path, value in device_updates.items():
            if path not in _DEVICE_PATHS:
                raise ValueError(
                    t("tui.validation.unsupported_device_key", path=path)
                )
            if path.endswith("_id"):
                if value is not None and (type(value) is not int or value < -1):
                    raise ValueError(
                        t("tui.validation.device_id_invalid", path=path)
                    )
            elif value is not None and not isinstance(value, str):
                raise ValueError(
                    t("tui.validation.device_name_invalid", path=path)
                )
            updates[path] = value
    return updates


def save_settings(
    values: dict[str, str],
    config: ConfigManager | None = None,
    *,
    disabled_tools: list[str] | None = None,
    device_updates: dict | None = None,
) -> tuple[bool, str]:
    """先校验全部输入，再提交独立完整草稿。失败保留调用方输入。

    关键词先原子写入再 commit_draft；配置未落盘时恢复旧关键词。
    运行时加载失败但磁盘已保存新配置时保留匹配的新关键词，错误返回供重试。
    """
    cfg = config if config is not None else ConfigManager.from_dict()
    try:
        if not isinstance(values, dict):
            raise ValueError(t("tui.validation.values_dict"))
        updates = _validate_extras(disabled_tools, device_updates)
        for _section, fields in SETTING_SECTIONS:
            for field in fields:
                if field.path in values and field.kind != "readonly":
                    parsed = parse_field_value(field, values[field.path])
                    # 设备选择器提供的成对 id/name 覆盖原有名称控件值。
                    updates.setdefault(field.path, parsed)
        if not updates:
            return True, t("tui.settings.no_changes")

        # get_config("") 契约返回深拷贝，未知配置保留且校验期间不修改运行时。
        draft = cfg.get_config("", {})
        if not isinstance(draft, dict):
            raise ValueError(t("tui.validation.root_object"))
        word_path = "WAKE_WORD_OPTIONS.WAKE_WORD"
        converted = None
        if word_path in updates and updates[word_path] != cfg.get_config(word_path, ""):
            converted = preview_wake_word(updates[word_path])
            keyword_line, lang, model_path = converted
            if (
                lang not in {"zh", "en"}
                or not isinstance(keyword_line, str)
                or not keyword_line.strip()
                or not isinstance(model_path, str)
                or not model_path
            ):
                raise ValueError(t("tui.validation.wake_convert_invalid"))
            updates["WAKE_WORD_OPTIONS.WAKE_WORD_LANG"] = lang
            updates["WAKE_WORD_OPTIONS.MODEL_PATH"] = model_path

        for path, value in updates.items():
            # 保留 null 与空白的既有语义，避免无编辑保存将 MQTT null 变成空对象。
            if cfg.get_config(path, None) is None and value == "":
                continue
            _set_path(draft, path, value)
        if converted is not None:
            from src.utils.keyword_writer import commit_with_keywords

            error = commit_with_keywords(cfg, draft, lang, keyword_line)
        else:
            error = cfg.commit_draft(draft)
        if error is not None:
            return False, str(error)
        logger.info("TUI 已保存 %s 项配置", len(updates))
        return True, t("tui.settings.saved_count", count=len(updates))
    except Exception as exc:
        logger.error("TUI 保存配置失败: %s", exc, exc_info=True)
        return False, t("tui.settings.save_failed", error=exc)
