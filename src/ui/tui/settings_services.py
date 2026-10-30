"""Runtime settings lookups without owning UI tasks."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING

from src.core.event_bus import Events

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.utils.config_manager import ConfigManager


class SettingsServices:
    """Queries stay on the application's loop with AudioPlugin reloads."""

    def __init__(
        self,
        config: ConfigManager,
        event_bus: EventBus | None = None,
        runtime_tool_names: Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        self._config = config
        self._event_bus = event_bus
        self._runtime_tool_names = runtime_tool_names

    async def audio_devices(self, *, refresh: bool = False) -> dict:
        if refresh and self._event_bus is not None:
            event = Events.AUDIO_DEVICES_REFRESH_REQUEST
            subscribed = self._event_bus.has_handlers(event)
            future = asyncio.get_running_loop().create_future()
            try:
                await self._event_bus.emit(event, future)
                if future.done():
                    return self._copy_devices(future.result())
                if subscribed:
                    raise RuntimeError("音频设备刷新处理器未返回设备列表")
            finally:
                if not future.done():
                    future.cancel()
                elif not future.cancelled():
                    future.exception()
        from src.utils.audio_utils import list_audio_devices

        return self._copy_devices(list_audio_devices(include_virtual=True))

    def tool_catalog(self, disabled: list[str]) -> list[dict[str, str]]:
        from src.mcp.tool_catalog import full_catalog_rows

        provider = self._runtime_tool_names
        return full_catalog_rows(
            runtime_names=list(provider()) if provider is not None else [],
            extra_disabled=disabled,
            config=self._config,
        )

    def close(self) -> None:
        self._runtime_tool_names = None
        self._event_bus = None

    @staticmethod
    def _copy_devices(devices: object) -> dict:
        if not isinstance(devices, dict):
            raise TypeError("音频设备列表必须是 dict")
        result = {}
        fields = {
            "index": int,
            "name": str,
            "raw_name": str,
            "sample_rate": int,
            "channels": int,
        }
        for kind in ("input", "output"):
            rows = devices.get(kind)
            if not isinstance(rows, list):
                raise TypeError(f"音频设备 {kind} 必须是 list")
            result[kind] = []
            for row in rows:
                if not isinstance(row, dict):
                    raise TypeError(f"音频设备 {kind} 行必须是 dict")
                for field, expected in fields.items():
                    value = row.get(field)
                    if not isinstance(value, expected) or isinstance(value, bool):
                        raise TypeError(f"音频设备 {kind}.{field} 类型错误")
                result[kind].append(dict(row))
        return result
