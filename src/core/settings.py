"""设置提交后的运行时生效规则，供各界面共用。"""

import asyncio

from src.core.event_bus import EventBus, Events
from src.mcp.tool_catalog import normalize_disabled
from src.utils.config_manager import ConfigManager

# 网络配置整体影响连接；音频设备切换本身无需重新协商协议格式。
RECONNECT_PATHS = (
    "SYSTEM_OPTIONS.NETWORK",
    "SYSTEM_OPTIONS.DEVICE_ID",
    "SYSTEM_OPTIONS.CLIENT_ID",
    "AUDIO_DEVICES.opus_output_sample_rate",
    "AUDIO_DEVICES.frame_duration",
    "MCP_TOOLS.DISABLED",
)


def requires_protocol_reconnect(path: str) -> bool:
    """字段的生效时机与运行时重连判断使用同一份规则。"""
    return any(path == root or path.startswith(root + ".") for root in RECONNECT_PATHS)


class SettingsApplier:
    """串行应用已提交的设置：等待热重载完成，再按需重连。"""

    def __init__(self, config: ConfigManager, event_bus: EventBus) -> None:
        self._config = config
        self._event_bus = event_bus
        self._reconnect_snapshot = self._reconnect_values()
        self._lock = asyncio.Lock()

    def _reconnect_values(self) -> dict:
        values = {path: self._config.get_config(path) for path in RECONNECT_PATHS}
        # 工具列表的顺序和重复项不影响暴露结果。
        values["MCP_TOOLS.DISABLED"] = sorted(
            normalize_disabled(values["MCP_TOOLS.DISABLED"] or [])
        )
        return values

    async def apply(self) -> None:
        async with self._lock:
            current = self._reconnect_values()
            await self._event_bus.emit(Events.CONFIG_CHANGED)
            if current != self._reconnect_snapshot:
                await self._event_bus.emit(Events.PROTOCOL_RECONNECT_REQUEST)
            self._reconnect_snapshot = current
