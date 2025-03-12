from abc import ABC, abstractmethod
from typing import Optional, Callable
import logging

class BaseDisplay(ABC):
    """显示接口的抽象基类"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_volume = 70  # 默认音量

    @abstractmethod
    def set_callbacks(self,
                     press_callback: Optional[Callable] = None,
                     release_callback: Optional[Callable] = None,
                     status_callback: Optional[Callable] = None,
                     text_callback: Optional[Callable] = None,
                     emotion_callback: Optional[Callable] = None,
                     mode_callback: Optional[Callable] = None,
                     auto_callback: Optional[Callable] = None,
                     abort_callback: Optional[Callable] = None):  # 添加打断回调参数
        """设置回调函数"""
        pass

    @abstractmethod
    def update_button_status(self, text: str):
        """更新按钮状态"""
        pass

    @abstractmethod
    def update_status(self, status: str):
        """更新状态文本"""
        pass

    @abstractmethod
    def update_text(self, text: str):
        """更新TTS文本"""
        pass

    @abstractmethod
    def update_emotion(self, emotion: str):
        """更新表情"""
        pass

    def update_volume(self, volume: int):
        """更新系统音量 - 跨平台实现"""
        try:
            import platform
            system = platform.system()

            # 记录当前音量值
            self.current_volume = volume
            self.logger.info(f"设置音量: {volume}%")

            # 在ARM架构上可能需要特殊处理
            is_arm = platform.machine().startswith(('arm', 'aarch'))
            if is_arm:
                self.logger.info(f"检测到ARM架构，使用系统自带的音量控制")
                # ARM架构上的替代方法
                return

            if system == "Windows":
                self._set_windows_volume(volume)
            elif system == "Darwin":  # macOS
                self._set_macos_volume(volume)
            elif system == "Linux":
                self._set_linux_volume(volume)
            else:
                self.logger.warning(f"不支持的操作系统: {system}，无法调整音量")
        except Exception as e:
            self.logger.error(f"设置音量失败: {e}", exc_info=True)

    def _set_windows_volume(self, volume: int):
        """设置Windows系统音量"""
        try:
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume_control = cast(interface, POINTER(IAudioEndpointVolume))

            volume_db = -65.25 * (1 - volume / 100.0)
            volume_control.SetMasterVolumeLevel(volume_db, None)
            self.logger.debug(f"Windows音量已设置为: {volume}%")
        except Exception as e:
            self.logger.warning(f"设置Windows音量失败: {e}")

    def _set_macos_volume(self, volume: int):
        """设置macOS系统音量"""
        try:
            import applescript
            applescript.run(f'set volume output volume {volume}')
            self.logger.debug(f"macOS音量已设置为: {volume}%")
        except Exception as e:
            self.logger.warning(f"设置macOS音量失败: {e}")

    def _set_linux_volume(self, volume: int):
        """设置Linux系统音量"""
        import subprocess
        import shutil

        def cmd_exists(cmd):
            return shutil.which(cmd) is not None

        if cmd_exists("amixer"):
            try:
                result = subprocess.run(
                    ["amixer", "-D", "pulse", "sset", "Master", f"{volume}%"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.logger.debug(f"Linux音量(amixer/pulse)已设置为: {volume}%")
                    return

                result = subprocess.run(
                    ["amixer", "sset", "Master", f"{volume}%"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.logger.debug(f"Linux音量(amixer)已设置为: {volume}%")
                    return
            except Exception as e:
                self.logger.debug(f"amixer设置音量失败: {e}")

        if cmd_exists("pactl"):
            try:
                result = subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    self.logger.debug(f"Linux音量(pactl)已设置为: {volume}%")
                    return
            except Exception as e:
                self.logger.debug(f"pactl设置音量失败: {e}")

        self.logger.error("无法设置Linux音量，请确保安装了ALSA或PulseAudio")

    @abstractmethod
    def start(self):
        """启动显示"""
        pass

    @abstractmethod
    def on_close(self):
        """关闭显示"""
        pass

    @abstractmethod
    def start_keyboard_listener(self):
        """启动键盘监听"""
        pass

    @abstractmethod
    def stop_keyboard_listener(self):
        """停止键盘监听"""
        pass