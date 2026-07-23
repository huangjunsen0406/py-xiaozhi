"""启动健康门闩与音频降级策略.

与会话业务无关：只根据插件失败集与环境变量决定是否 exit / 降级继续。
"""

from __future__ import annotations

import os
from typing import Optional, Protocol

# 启动失败时直接退出，避免 zombie wait_shutdown
CRITICAL_PLUGINS = ("ui",)
# audio 默认关键；XIAOZHI_DEGRADED_AUDIO=1 时失败仅降级不 exit
AUDIO_CRITICAL = True

DEGRADED_AUDIO_NOTICE = (
    "降级：音频不可用（无麦/扬声器）。设置仍可用，修复设备后请重启。"
)


class _PluginHealth(Protocol):
    def is_failed(self, name: str) -> bool: ...


def audio_is_fatal() -> bool:
    """audio 失败是否应导致进程退出.

    - XIAOZHI_DISABLE_AUDIO=1：有意禁用，不视为失败
    - XIAOZHI_DEGRADED_AUDIO=1：失败则降级继续（UI/设置可用）
    - 默认：audio 失败即 exit 1
    """
    if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
        return False
    if os.getenv("XIAOZHI_DEGRADED_AUDIO") == "1":
        return False
    return AUDIO_CRITICAL


def check_critical_plugins(plugins: _PluginHealth) -> Optional[str]:
    """检查关键插件是否可用.

    Returns:
        错误描述；全部健康时返回 None
    """
    failed: list[str] = []
    for name in CRITICAL_PLUGINS:
        if plugins.is_failed(name):
            failed.append(name)

    if audio_is_fatal() and plugins.is_failed("audio"):
        failed.append("audio")

    if not failed:
        return None

    hints = []
    if "audio" in failed:
        hints.append(
            "无音频调试可设 XIAOZHI_DISABLE_AUDIO=1；"
            "或设 XIAOZHI_DEGRADED_AUDIO=1 以无麦模式继续（UI/设置可用）。"
        )
    return (
        f"关键插件启动失败: {', '.join(failed)}。"
        "应用将退出以避免空转（zombie）。"
        + (" " + " ".join(hints) if hints else "")
    )
