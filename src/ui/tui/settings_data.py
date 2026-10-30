"""纯 Python TUI 设置字段、校验和完整草稿提交。"""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import ConfigManager

logger = get_logger()


@dataclass(frozen=True)
class SettingField:
    """控件元数据；UI 输入始终为字符串，effect 说明生效时机。"""

    path: str
    label: str
    kind: str = "str"
    choices: tuple[str, ...] = ()
    help: str = ""
    minimum: float | None = None
    maximum: float | None = None
    effect: str = "hot"


SETTING_SECTIONS: list[tuple[str, list[SettingField]]] = [
    (
        "系统",
        [
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL",
                "OTA URL",
                help="OTA / 激活配置地址",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL",
                "WebSocket URL",
                help="WebSocket 服务地址",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.DEVICE_ID",
                "设备 ID",
                help="Device-Id（通常为 MAC）",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.CLIENT_ID",
                "客户端 ID",
                help="Client-Id",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN",
                "WebSocket 访问令牌",
                kind="secret",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL",
                "授权 URL",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION",
                "激活版本",
                kind="choice",
                choices=("v1", "v2"),
                effect="reconnect",
            ),
        ],
    ),
    (
        "音频",
        [
            SettingField(
                "AUDIO_DEVICES.input_device_name",
                "输入设备名",
                help="按名称匹配麦克风（热插拔后 ID 会变）",
                effect="hot",
            ),
            SettingField(
                "AUDIO_DEVICES.output_device_name",
                "输出设备名",
                help="按名称匹配扬声器/耳机",
                effect="hot",
            ),
            SettingField(
                "AUDIO_DEVICES.opus_output_sample_rate",
                "Opus 输出采样率",
                kind="choice",
                choices=("24000", "16000"),
                help="官方 24000 / 第三方常 16000",
                effect="reconnect",
            ),
            SettingField(
                "AUDIO_DEVICES.frame_duration",
                "帧时长 ms",
                kind="choice",
                choices=("20", "40", "60"),
                help="20 低延迟 / 60 低 CPU",
                effect="reconnect",
            ),
        ],
    ),
    (
        "回声消除",
        [
            SettingField("AEC_OPTIONS.ENABLED", "启用 AEC", kind="bool", effect="hot"),
            SettingField("AEC_OPTIONS.MUSIC_PARALLEL", "音乐并行播放", kind="bool"),
            SettingField(
                "AEC_OPTIONS.FRAME_DELAY",
                "帧延迟补偿",
                kind="int",
                minimum=0,
                maximum=20,
                help="实际延迟 = 40ms + N × 帧长",
                effect="hot",
            ),
            SettingField(
                "AEC_OPTIONS.ENABLE_PREPROCESS",
                "启用音频预处理",
                kind="bool",
                effect="hot",
            ),
        ],
    ),
    (
        "MQTT（高级）",
        [
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint",
                "MQTT 地址",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id",
                "MQTT 客户端 ID",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username",
                "MQTT 用户名",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password",
                "MQTT 密码",
                kind="secret",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic",
                "MQTT 发布主题",
                effect="reconnect",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic",
                "MQTT 订阅主题",
                effect="reconnect",
            ),
        ],
    ),
    (
        "音乐",
        [
            SettingField("MUSIC.SEARCH_URL", "搜索 URL"),
            SettingField("MUSIC.URL_API", "音乐 URL API"),
            SettingField("MUSIC.URL_API_KEY", "音乐 API 密钥", kind="secret"),
            SettingField(
                "MUSIC.DEFAULT_QUALITY",
                "默认音质",
                kind="choice",
                choices=("128k", "320k"),
            ),
        ],
    ),
    (
        "摄像头",
        [
            SettingField(
                "CAMERA.backend",
                "采集后端",
                kind="choice",
                choices=("auto", "opencv", "picamera2"),
                help="auto 先 OpenCV，失败再试 Pi CSI",
                effect="hot",
            ),
            SettingField(
                "CAMERA.device",
                "设备路径",
                help="如 /dev/video0；非空优先于 index",
                effect="hot",
            ),
            SettingField(
                "CAMERA.camera_index",
                "设备 index",
                kind="int",
                minimum=0,
                help="OpenCV 数字索引",
                effect="hot",
            ),
            SettingField(
                "CAMERA.frame_width",
                "宽度",
                kind="int",
                minimum=320,
                maximum=1920,
                effect="hot",
            ),
            SettingField(
                "CAMERA.frame_height",
                "高度",
                kind="int",
                minimum=240,
                maximum=1080,
                effect="hot",
            ),
            SettingField(
                "CAMERA.fps", "帧率", kind="int", minimum=10, maximum=60, effect="hot"
            ),
            SettingField("CAMERA.Local_VL_url", "视觉模型 URL", effect="restart"),
            SettingField(
                "CAMERA.VLapi_key", "视觉模型 API 密钥", kind="secret", effect="restart"
            ),
            SettingField("CAMERA.models", "视觉模型", effect="restart"),
        ],
    ),
    (
        "唤醒词",
        [
            SettingField(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD",
                "启用唤醒词",
                kind="bool",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD",
                "唤醒词",
                help="如：你好小智；修改时自动识别语言并生成关键词",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD_LANG",
                "自动识别语言",
                kind="readonly",
                help="由唤醒词自动识别",
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.NUM_THREADS",
                "唤醒词线程数",
                kind="int",
                minimum=1,
                maximum=16,
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.KEYWORDS_SCORE",
                "关键词分数",
                kind="float",
                minimum=0.5,
                maximum=3,
                effect="hot",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD",
                "关键词阈值",
                kind="float",
                minimum=0,
                maximum=1,
                effect="hot",
            ),
        ],
    ),
    (
        "快捷键",
        [
            SettingField("SHORTCUTS.ENABLED", "启用快捷键", kind="bool"),
            SettingField(
                "SHORTCUTS.MANUAL_PRESS.modifier",
                "手动模式修饰键",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.MANUAL_PRESS.key", "手动模式按键"),
            SettingField(
                "SHORTCUTS.AUTO_TOGGLE.modifier",
                "自动模式修饰键",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.AUTO_TOGGLE.key", "自动模式按键"),
            SettingField(
                "SHORTCUTS.ABORT.modifier",
                "中断修饰键",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.ABORT.key", "中断按键"),
            SettingField(
                "SHORTCUTS.MODE_TOGGLE.modifier",
                "模式切换修饰键",
                kind="choice",
                choices=("ctrl", "alt", "shift", "cmd"),
            ),
            SettingField("SHORTCUTS.MODE_TOGGLE.key", "模式切换按键"),
        ],
    ),
    (
        "目录",
        [
            SettingField(
                "PATHS.CACHE_DIR",
                "缓存目录",
                help="留空使用默认目录；下次启动迁移",
                effect="restart",
            ),
            SettingField(
                "PATHS.LOG_DIR",
                "日志目录",
                help="留空使用默认目录；下次启动迁移",
                effect="restart",
            ),
            SettingField(
                "PATHS.MUSIC_CACHE_DIR",
                "音乐缓存目录",
                help="留空使用默认目录；下次启动迁移",
                effect="restart",
            ),
            SettingField(
                "PATHS.KEYWORDS_DIR",
                "唤醒词目录",
                help="留空使用默认目录；下次启动迁移",
                effect="restart",
            ),
            SettingField(
                "MCP_PLUGINS.DIR",
                "MCP 插件目录",
                help="留空使用默认目录；下次启动生效",
                effect="restart",
            ),
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
        raise ValueError(f"{field.label} 必须是字符串输入")
    if field.kind == "secret":
        return text
    if field.path.startswith("SHORTCUTS.") and field.path.endswith(".key"):
        if len(text) != 1 or not text.strip():
            raise ValueError(f"{field.label} 必须是单个非空字符")
        return text.lower()
    value = text.strip()
    if field.kind == "bool":
        normalized = value.lower()
        if normalized in {"1", "true", "yes", "on", "是"}:
            return True
        if normalized in {"0", "false", "no", "off", "否"}:
            return False
        raise ValueError(f"{field.label} 必须是 true 或 false")
    if field.kind == "choice":
        if value not in field.choices:
            raise ValueError(
                f"{field.label} 必须是以下选项之一: {', '.join(field.choices)}"
            )
        return int(value) if field.path in _NUMERIC_CHOICES else value
    if field.kind in {"int", "float"}:
        try:
            parsed = int(value) if field.kind == "int" else float(value)
            finite = math.isfinite(parsed)
        except (ValueError, OverflowError) as exc:
            expected = "整数" if field.kind == "int" else "有限数"
            raise ValueError(f"{field.label} 必须是{expected}") from exc
        if not finite:
            raise ValueError(f"{field.label} 必须是有限数")
        if field.minimum is not None and parsed < field.minimum:
            raise ValueError(f"{field.label} 不能小于 {field.minimum:g}")
        if field.maximum is not None and parsed > field.maximum:
            raise ValueError(f"{field.label} 不能大于 {field.maximum:g}")
        return parsed
    if field.kind in {"str", "secret", "readonly"}:
        return value
    raise ValueError(f"未知字段类型: {field.kind}")


def preview_wake_word(text: str) -> tuple[str, str, str]:
    """返回既有 converter 的 (keyword_line, lang, model_path)，不写入文件。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("请输入唤醒词")
    from src.audio_processing.keyword_converters import convert_wake_word

    return convert_wake_word(text.strip())


def _set_path(draft: dict, path: str, value: Any) -> None:
    current = draft
    *parents, final = path.split(".")
    for part in parents:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[final] = value


def _validate_extras(disabled_tools, device_updates) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    if disabled_tools is not None:
        if not isinstance(disabled_tools, list) or any(
            not isinstance(name, str) or not name.strip() for name in disabled_tools
        ):
            raise ValueError("MCP 禁用工具必须是非空字符串组成的列表")
        updates["MCP_TOOLS.DISABLED"] = list(
            dict.fromkeys(n.strip() for n in disabled_tools)
        )
    if device_updates is not None:
        if not isinstance(device_updates, dict):
            raise ValueError("设备更新必须是路径字典")
        for path, value in device_updates.items():
            if path not in _DEVICE_PATHS:
                raise ValueError(f"不支持的设备配置键: {path}")
            if path.endswith("_id"):
                if value is not None and (type(value) is not int or value < -1):
                    raise ValueError(f"设备 ID 必须是大于等于 -1 的整数或 null: {path}")
            elif value is not None and not isinstance(value, str):
                raise ValueError(f"设备名称必须是字符串或 null: {path}")
            updates[path] = value
    return updates


def _write_keywords(lang: str, keyword_line: str) -> Path:
    """原子替换当前生效目录下的关键词；PATHS 新草稿下次启动应用。"""
    from src.utils.resource_finder import get_keywords_dir

    directory = Path(get_keywords_dir())
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{lang}_keywords.txt"
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(keyword_line + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        # temporary is created by mkstemp in the checked keywords directory.
        temporary_path = Path(temporary)
        if temporary_path.exists():
            temporary_path.unlink()
    return target


def save_settings(
    values: dict[str, str],
    config: ConfigManager | None = None,
    *,
    disabled_tools: list[str] | None = None,
    device_updates: dict | None = None,
) -> tuple[bool, str]:
    """先校验全部输入，再提交独立完整草稿。失败保留调用方输入。

    关键词先原子写入再 commit_draft，沿用 GUI 顺序。配置提交失败时关键词
    可能已经生成；运行时加载失败时磁盘新配置保留，错误原样返回供重试。
    """
    cfg = config if config is not None else ConfigManager.from_dict()
    try:
        if not isinstance(values, dict):
            raise ValueError("设置输入必须是路径字典")
        updates = _validate_extras(disabled_tools, device_updates)
        for _section, fields in SETTING_SECTIONS:
            for field in fields:
                if field.path in values and field.kind != "readonly":
                    parsed = parse_field_value(field, values[field.path])
                    # 设备选择器提供的成对 id/name 覆盖原有名称控件值。
                    updates.setdefault(field.path, parsed)
        if not updates:
            return True, "无变更"

        # get_config("") 契约返回深拷贝，未知配置保留且校验期间不修改运行时。
        draft = cfg.get_config("", {})
        if not isinstance(draft, dict):
            raise ValueError("当前配置根节点必须是对象")
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
                raise ValueError("唤醒词转换结果无效")
            updates["WAKE_WORD_OPTIONS.WAKE_WORD_LANG"] = lang
            updates["WAKE_WORD_OPTIONS.MODEL_PATH"] = model_path

        for path, value in updates.items():
            # 保留 null 与空白的既有语义，避免无编辑保存将 MQTT null 变成空对象。
            if cfg.get_config(path, None) is None and value == "":
                continue
            _set_path(draft, path, value)
        if converted is not None:
            _write_keywords(lang, keyword_line)
        error = cfg.commit_draft(draft)
        if error is not None:
            return False, str(error)
        logger.info("TUI 已保存 %s 项配置", len(updates))
        return True, f"已保存 {len(updates)} 项"
    except Exception as exc:
        logger.error("TUI 保存配置失败: %s", exc, exc_info=True)
        return False, f"保存失败: {exc}"
