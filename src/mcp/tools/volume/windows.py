"""Windows 音量后端（pycaw / comtypes）."""

from __future__ import annotations

from typing import Any

from src.logging import get_logger

logger = get_logger()


class WindowsVolumeBackend:
    def __init__(self) -> None:
        self._module_cache: dict[str, Any] = {}
        self.volume_control = None
        self._init()

    def _lazy_import(self, module_name: str, attr: str | None = None) -> Any:
        if module_name in self._module_cache:
            module = self._module_cache[module_name]
        else:
            module = __import__(
                module_name, fromlist=["*"] if "." in module_name else []
            )
            self._module_cache[module_name] = module
        if attr:
            return getattr(module, attr)
        return module

    def _init(self) -> None:
        try:
            POINTER = self._lazy_import("ctypes", "POINTER")
            cast = self._lazy_import("ctypes", "cast")
            CLSCTX_ALL = self._lazy_import("comtypes", "CLSCTX_ALL")
            AudioUtilities = self._lazy_import("pycaw.pycaw", "AudioUtilities")
            IAudioEndpointVolume = self._lazy_import(
                "pycaw.pycaw", "IAudioEndpointVolume"
            )

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(
                IAudioEndpointVolume._iid_, CLSCTX_ALL, None
            )
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            logger.debug("Windows音量控制初始化成功")
        except Exception as e:
            logger.error(f"Windows音量控制初始化失败: {e}", exc_info=True)
            raise

    def get_volume(self) -> int:
        try:
            volume_scalar = self.volume_control.GetMasterVolumeLevelScalar()
            return int(volume_scalar * 100)
        except Exception as e:
            logger.warning(f"获取Windows音量失败: {e}", exc_info=True)
            return 70

    def set_volume(self, volume: int) -> None:
        try:
            self.volume_control.SetMasterVolumeLevelScalar(volume / 100.0, None)
        except Exception as e:
            logger.warning(f"设置Windows音量失败: {e}", exc_info=True)
