"""macOS 音量后端（applescript）."""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

logger = get_logger()


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
        applescript = self._lazy_import("applescript")
        result = applescript.run("output volume of (get volume settings)")
        if not result or result.code != 0 or not result.out:
            raise RuntimeError("Unable to read macOS output volume")
        return int(result.out.strip())

    def set_volume(self, volume: int) -> None:
        applescript = self._lazy_import("applescript")
        result = applescript.run(f"set volume output volume {volume}")
        if not result or result.code != 0:
            raise RuntimeError("Unable to set macOS output volume")
