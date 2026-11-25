"""Windows 音量后端（pycaw / comtypes）."""

from __future__ import annotations

from src.logging import get_logger

logger = get_logger()


class WindowsVolumeBackend:
    def __init__(self) -> None:
        self.volume_control = None
        self._init()

    def _init(self) -> None:
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self.volume_control = cast(interface, POINTER(IAudioEndpointVolume))
            logger.debug("Windows音量控制初始化成功")
        except Exception as e:
            logger.error(f"Windows音量控制初始化失败: {e}", exc_info=True)
            raise

    def get_volume(self) -> int:
        volume_scalar = self.volume_control.GetMasterVolumeLevelScalar()
        return int(volume_scalar * 100)

    def set_volume(self, volume: int) -> None:
        self.volume_control.SetMasterVolumeLevelScalar(volume / 100.0, None)
