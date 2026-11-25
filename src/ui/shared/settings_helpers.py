"""GUI 与 TUI 共用的 UI 无关设置辅助函数."""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.event_bus import Events
from src.logging import get_logger

logger = get_logger()


def get_draft_value(draft: dict, path: str, default: Any = None) -> Any:
    """按点号路径读取配置草稿中的值."""
    value: Any = draft
    for key in path.split("."):
        if isinstance(value, dict) and key in value:
            value = value[key]
        else:
            return default
    return value


def set_draft_value(draft: dict, path: str, value: Any) -> None:
    """按点号路径写入配置草稿，缺失的中间节点自动建 dict."""
    current = draft
    *parents, final = path.split(".")
    for part in parents:
        if not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[final] = value


def match_audio_device(
    devices: list[dict], *, current_name: str, current_id: int
) -> tuple[int, dict | None]:
    """按 raw_name 优先、index 其次匹配设备，返回 (列表下标, 设备字典) 或 (-1, None)."""
    if current_name:
        for i, device in enumerate(devices):
            if device.get("raw_name") == current_name:
                return i, device
    for i, device in enumerate(devices):
        if device.get("index") == current_id:
            return i, device
    return -1, None


async def request_audio_devices_refresh(
    event_bus,
    *,
    strict_if_subscribed: bool = False,
) -> dict:
    """经 EventBus 请求 AudioPlugin 停流热刷新设备，未响应时按策略抛错或回退本地枚举."""
    from src.utils.audio_utils import list_audio_devices

    if event_bus is not None:
        event = Events.AUDIO_DEVICES_REFRESH_REQUEST
        subscribed = strict_if_subscribed and event_bus.has_handlers(event)
        future = asyncio.get_running_loop().create_future()
        try:
            await event_bus.emit(event, future)
            if future.done():
                return future.result()
            if subscribed:
                raise RuntimeError("音频设备刷新处理器未返回设备列表")
            if not strict_if_subscribed:
                logger.warning("AudioPlugin 未完成设备刷新 Future，本地枚举兜底")
        finally:
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    return await asyncio.to_thread(list_audio_devices, include_virtual=True)
