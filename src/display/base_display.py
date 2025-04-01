from abc import ABC, abstractmethod
from typing import Optional, Callable
import logging

class BaseDisplay(ABC):
    """显示接口的抽象基类"""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.current_volume = 70  # 默认音量值
        self.volume_controller = None
        
        # 检查音量控制依赖
        try:
            from src.utils.volume_controller import VolumeController
            if VolumeController.check_dependencies():
                self.volume_controller = VolumeController()
                # 获取当前系统音量
                self.current_volume = self.volume_controller.get_volume()
                self.logger.info(f"音量控制器初始化成功，当前音量: {self.current_volume}%")
            else:
                self.logger.warning("音量控制依赖不满足，将使用默认音量控制")
        except Exception as e:
            self.logger.warning(f"音量控制器初始化失败: {e}，将使用模拟音量控制")

    @abstractmethod
    def set_callbacks(self,
                     press_callback: Optional[Callable] = None,
                     release_callback: Optional[Callable] = None,
                     status_callback: Optional[Callable] = None,
                     text_callback: Optional[Callable] = None,
                     emotion_callback: Optional[Callable] = None,
                     mode_callback: Optional[Callable] = None,
                     auto_callback: Optional[Callable] = None,
                     abort_callback: Optional[Callable] = None,
                     send_text_callback: Optional[Callable] = None):  # 添加打断回调参数
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

    def get_current_volume(self):
        """获取当前音量"""
        if self.volume_controller:
            try:
                # 从系统获取最新音量
                self.current_volume = self.volume_controller.get_volume()
            except Exception as e:
                self.logger.debug(f"获取系统音量失败: {e}")
        return self.current_volume

    def update_volume(self, volume: int):
        """更新系统音量"""
        # 确保音量在有效范围内
        volume = max(0, min(100, volume))
        
        # 更新内部音量值
        self.current_volume = volume
        self.logger.info(f"设置音量: {volume}%")
        
        # 尝试更新系统音量
        if self.volume_controller:
            try:
                self.volume_controller.set_volume(volume)
                self.logger.debug(f"系统音量已设置为: {volume}%")
            except Exception as e:
                self.logger.warning(f"设置系统音量失败: {e}")

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