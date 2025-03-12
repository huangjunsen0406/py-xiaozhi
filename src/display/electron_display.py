import logging
import sys
from typing import Optional, Callable
from src.display.base_display import BaseDisplay

class ElectronDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("ElectronDisplay")
        self._running = True

    def set_callbacks(self,
                     press_callback: Optional[Callable] = None,
                     release_callback: Optional[Callable] = None,
                     status_callback: Optional[Callable] = None,
                     text_callback: Optional[Callable] = None,
                     emotion_callback: Optional[Callable] = None,
                     mode_callback: Optional[Callable] = None,
                     auto_callback: Optional[Callable] = None,
                     abort_callback: Optional[Callable] = None):
        """设置回调函数"""
        self.button_press_callback = press_callback
        self.button_release_callback = release_callback
        self.status_update_callback = status_callback
        self.text_update_callback = text_callback
        self.emotion_update_callback = emotion_callback
        self.mode_callback = mode_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback

    def start(self):
        """启动显示"""
        # Electron 模式下不需要启动 GUI
        self._running = True
        self.start_keyboard_listener()

    def update_status(self, status: str):
        """更新状态"""
        if self._running:
            print(f"STATUS:{status}", flush=True)

    def update_text(self, text: str):
        """更新文本"""
        if self._running:
            print(f"TEXT:{text}", flush=True)

    def update_emotion(self, emotion: str):
        """更新表情"""
        if self._running:
            print(f"EMOTION:{emotion}", flush=True)

    def update_button_status(self, text: str):
        """更新按钮状态"""
        if self._running:
            print(f"BUTTON:{text}", flush=True)

    def start_keyboard_listener(self):
        """启动键盘监听"""
        # Electron 模式下不需要键盘监听，由 Electron 处理按键
        pass

    def stop_keyboard_listener(self):
        """停止键盘监听"""
        # Electron 模式下不需要键盘监听
        pass

    def on_close(self):
        """关闭处理"""
        self._running = False
        self.stop_keyboard_listener()

    def update_mode_button_status(self, text: str):
        """更新模式按钮状态"""
        if self._running:
            print(f"MODE_BUTTON:{text}", flush=True)

    def _on_volume_change(self, value):
        """处理音量变化"""
        if self._running:
            print(f"VOLUME:{value}", flush=True)