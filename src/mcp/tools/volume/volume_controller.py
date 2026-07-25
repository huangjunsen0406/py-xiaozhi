"""跨平台音量控制器门面.

平台实现见 windows / macos / linux 模块；本类负责探测、装配与依赖检查。
"""

from __future__ import annotations

import platform
import shutil

from src.logging import get_logger

from .backend import VolumeBackend


class VolumeController:
    """跨平台音量控制器."""

    DEFAULT_VOLUME = 70

    def __init__(self):
        self.logger = get_logger()
        self.system = platform.system()
        self.is_arm = platform.machine().startswith(("arm", "aarch"))
        self._backend: VolumeBackend = self._create_backend()

    def _create_backend(self) -> VolumeBackend:
        if self.system == "Windows":
            from .windows import WindowsVolumeBackend

            return WindowsVolumeBackend()
        if self.system == "Darwin":
            from .macos import MacosVolumeBackend

            return MacosVolumeBackend()
        if self.system == "Linux":
            from .linux import LinuxVolumeBackend

            return LinuxVolumeBackend()

        self.logger.warning(f"不支持的操作系统: {self.system}")
        raise NotImplementedError(f"不支持的操作系统: {self.system}")

    def get_volume(self) -> int:
        """获取当前音量 (0-100)."""
        try:
            return self._backend.get_volume()
        except Exception as e:
            self.logger.warning(f"获取音量失败: {e}", exc_info=True)
            return self.DEFAULT_VOLUME

    def set_volume(self, volume: int) -> None:
        """设置音量 (0-100)."""
        volume = max(0, min(100, volume))
        try:
            self._backend.set_volume(volume)
        except Exception as e:
            self.logger.warning(f"设置音量失败: {e}", exc_info=True)

    @staticmethod
    def check_dependencies() -> bool:
        """检查并报告缺少的依赖."""
        system = platform.system()
        missing: list[str] = []

        VolumeController._check_python_modules(system, missing)
        if system == "Linux":
            VolumeController._check_linux_tools(missing)
        return VolumeController._report_missing_dependencies(system, missing)

    @staticmethod
    def _check_python_modules(system: str, missing: list[str]) -> None:
        if system == "Windows":
            for module in ["pycaw", "comtypes"]:
                try:
                    __import__(module)
                except ImportError:
                    missing.append(module)
        elif system == "Darwin":
            try:
                __import__("applescript")
            except ImportError:
                missing.append("applescript")

    @staticmethod
    def _check_linux_tools(missing: list[str]) -> None:
        tools = ["pactl", "wpctl", "amixer"]
        if not any(shutil.which(tool) for tool in tools):
            missing.append("pulseaudio-utils、wireplumber 或 alsa-utils")

    @staticmethod
    def _report_missing_dependencies(system: str, missing: list[str]) -> bool:
        if not missing:
            return True
        logger = get_logger()
        logger.warning(f"音量控制需要以下依赖，但未找到: {', '.join(missing)}")
        if system in ["Windows", "Darwin"]:
            logger.warning(f"请使用以下命令安装: pip install {' '.join(missing)}")
        elif system == "Linux":
            logger.warning(
                f"请使用以下命令安装: sudo apt-get install {' '.join(missing)}"
            )
        return False
