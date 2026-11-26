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
            from pycaw.pycaw import AudioUtilities

            device = AudioUtilities.GetSpeakers()
            if device is None:
                raise RuntimeError("未找到默认 Windows 音频输出设备")

            if hasattr(device, "EndpointVolume"):
                # 新版 pycaw（如 2025/2026）：GetSpeakers() 返回 AudioDevice，直接提供 EndpointVolume
                self.volume_control = device.EndpointVolume
            elif hasattr(device, "Activate"):
                # 旧版 pycaw（<= 20240210）：GetSpeakers() 返回原始 IMMDevice COM 指针
                self.volume_control = self._activate_endpoint_volume(device)
            elif hasattr(device, "_dev"):
                # 兜底：部分 pycaw AudioDevice 包装体通过 _dev 暴露原始 IMMDevice
                self.volume_control = self._activate_endpoint_volume(device._dev)
            else:
                raise AttributeError(
                    f"不支持的 pycaw 设备对象类型: {type(device).__name__}"
                )
            logger.debug("Windows音量控制初始化成功")
        except Exception as e:
            logger.error(f"Windows音量控制初始化失败: {e}", exc_info=True)
            raise

    @staticmethod
    def _activate_endpoint_volume(raw_device):
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import IAudioEndpointVolume

        interface = raw_device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    def get_volume(self) -> int:
        volume_scalar = self.volume_control.GetMasterVolumeLevelScalar()
        return int(volume_scalar * 100)

    def set_volume(self, volume: int) -> None:
        self.volume_control.SetMasterVolumeLevelScalar(volume / 100.0, None)
