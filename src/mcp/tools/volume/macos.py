"""macOS 音量后端（applescript）."""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

logger = get_logger()

DEFAULT_VOLUME = 70


class MacosVolumeBackend:
    def __init__(self) -> None:
        self._module_cache: dict[str, Any] = {}
        self._init()

    def _lazy_import(self, module_name: str) -> Any:
        if module_name not in self._module_cache:
            self._module_cache[module_name] = __import__(module_name)
        return self._module_cache[module_name]

    def _init(self) -> None:
        try:
            applescript = self._lazy_import("applescript")
            result = applescript.run("get volume settings")
            if not result or result.code != 0:
                raise Exception("无法访问macOS音量控制")
            logger.debug("macOS音量控制初始化成功")
        except Exception as e:
            logger.error(f"macOS音量控制初始化失败: {e}", exc_info=True)
            raise

    def get_volume(self) -> int:
        try:
            applescript = self._lazy_import("applescript")
            result = applescript.run("output volume of (get volume settings)")
            if result and result.out:
                return int(result.out.strip())
            return DEFAULT_VOLUME
        except Exception as e:
            logger.warning(f"获取macOS音量失败: {e}", exc_info=True)
            return DEFAULT_VOLUME

    def set_volume(self, volume: int) -> None:
        try:
            applescript = self._lazy_import("applescript")
            applescript.run(f"set volume output volume {volume}")
        except Exception as e:
            logger.warning(f"设置macOS音量失败: {e}", exc_info=True)
