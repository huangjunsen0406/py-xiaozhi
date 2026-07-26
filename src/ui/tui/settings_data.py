"""TUI 设置：配置字段定义与读写（接 ConfigManager + CONFIG_CHANGED）."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.logging import get_logger
from src.utils.config_manager import get_config

logger = get_logger()


@dataclass(frozen=True)
class SettingField:
    """一个可编辑配置项."""

    path: str
    label: str
    kind: str = "str"  # str | int | bool | choice
    choices: tuple[str, ...] = ()
    help: str = ""


# 第一期：系统 / 音频 / 摄像头 / 唤醒词
SETTING_SECTIONS: list[tuple[str, list[SettingField]]] = [
    (
        "系统",
        [
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL",
                "OTA URL",
                help="OTA / 激活配置地址",
            ),
            SettingField(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL",
                "WebSocket URL",
                help="WebSocket 服务地址",
            ),
            SettingField(
                "SYSTEM_OPTIONS.DEVICE_ID",
                "设备 ID",
                help="Device-Id（通常为 MAC）",
            ),
            SettingField(
                "SYSTEM_OPTIONS.CLIENT_ID",
                "客户端 ID",
                help="Client-Id",
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
            ),
            SettingField(
                "AUDIO_DEVICES.output_device_name",
                "输出设备名",
                help="按名称匹配扬声器/耳机",
            ),
            SettingField(
                "AUDIO_DEVICES.opus_output_sample_rate",
                "Opus 输出采样率",
                kind="choice",
                choices=("24000", "16000"),
                help="官方 24000 / 第三方常 16000",
            ),
            SettingField(
                "AUDIO_DEVICES.frame_duration",
                "帧时长 ms",
                kind="choice",
                choices=("20", "40", "60"),
                help="20 低延迟 / 60 低 CPU",
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
                help="auto 先 OpenCV，失败再 Pi CSI",
            ),
            SettingField(
                "CAMERA.device",
                "设备路径",
                help="如 /dev/video0；非空优先于 index",
            ),
            SettingField(
                "CAMERA.camera_index",
                "设备 index",
                kind="int",
                help="OpenCV 数字索引",
            ),
            SettingField(
                "CAMERA.frame_width",
                "宽度",
                kind="int",
            ),
            SettingField(
                "CAMERA.frame_height",
                "高度",
                kind="int",
            ),
        ],
    ),
    (
        "唤醒词",
        [
            SettingField(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD",
                "启用唤醒词",
                kind="bool",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD",
                "唤醒词",
                help="如：你好小智",
            ),
            SettingField(
                "WAKE_WORD_OPTIONS.WAKE_WORD_LANG",
                "语言",
                kind="choice",
                choices=("zh", "en"),
            ),
        ],
    ),
]


def load_setting_values() -> dict[str, str]:
    """读取当前配置为字符串表（path -> 显示值）."""
    cfg = get_config()
    values: dict[str, str] = {}
    for _section, fields in SETTING_SECTIONS:
        for f in fields:
            raw = cfg.get_config(f.path, "")
            if f.kind == "bool":
                values[f.path] = "true" if bool(raw) else "false"
            elif raw is None:
                values[f.path] = ""
            else:
                values[f.path] = str(raw)
    return values


def parse_field_value(field: SettingField, text: str) -> Any:
    """把输入框字符串转成配置值."""
    s = (text or "").strip()
    if field.kind == "int":
        if s == "":
            return 0
        return int(s)
    if field.kind == "bool":
        return s.lower() in ("1", "true", "yes", "on", "是")
    if field.kind == "choice":
        if field.choices and s not in field.choices:
            # 仍写入用户值，由上层校验提示
            return s
        if field.path.endswith("opus_output_sample_rate") or field.path.endswith(
            "frame_duration"
        ):
            try:
                return int(s)
            except ValueError:
                return s
        return s
    return s


def save_settings(values: dict[str, str]) -> tuple[bool, str]:
    """批量写配置并落盘.

    Returns:
        (ok, message)
    """
    cfg = get_config()
    updates: dict[str, Any] = {}
    try:
        for _section, fields in SETTING_SECTIONS:
            for f in fields:
                if f.path not in values:
                    continue
                updates[f.path] = parse_field_value(f, values[f.path])
        if not updates:
            return True, "无变更"
        ok = cfg.update_configs(updates)
        if not ok:
            return False, "保存失败（写盘错误）"
        logger.info(f"TUI 已保存 {len(updates)} 项配置")
        return True, f"已保存 {len(updates)} 项"
    except Exception as e:
        logger.error(f"TUI 保存配置失败: {e}", exc_info=True)
        return False, f"保存失败: {e}"
