import logging
import os
import platform
from typing import Callable, Optional

# 根据不同操作系统处理 pynput 导入
try:
    if platform.system() == "Windows":
        from pynput import keyboard as pynput_keyboard
    elif os.environ.get("DISPLAY"):
        from pynput import keyboard as pynput_keyboard
    else:
        pynput_keyboard = None
except ImportError:
    pynput_keyboard = None


class ShortcutManager:
    """管理应用程序的全局快捷键。"""

    # 默认快捷键配置
    DEFAULT_SHORTCUTS = {
        ("alt", "shift", "v"): "manual_press",      # 长按说话
        ("alt", "shift", "a"): "auto_toggle",       # 自动对话
        ("alt", "shift", "x"): "abort",             # 打断
        ("alt", "shift", "m"): "mode_toggle",       # 模式切换
        ("alt", "shift", "h"): "window_toggle",     # 显示/隐藏窗口
    }

    def __init__(
        self,
        logger: logging.Logger,
        shortcuts: Optional[dict] = None,
        manual_press_callback: Optional[Callable] = None,
        manual_release_callback: Optional[Callable] = None,
        auto_toggle_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        mode_toggle_callback: Optional[Callable] = None,
        window_toggle_callback: Optional[Callable] = None,
    ):
        self.logger = logger
        self.keyboard_listener = None
        self.pressed_keys = set()  # 添加按键状态集合
        self.main_loop = None  # 保存主线程的事件循环
        self.manual_v_pressed = False  # 记录Alt+Shift+V是否被按下
        
        # 快捷键配置
        self.shortcuts = shortcuts or self.DEFAULT_SHORTCUTS.copy()
        
        # 注册回调函数
        self.callbacks = {
            "manual_press": manual_press_callback,
            "manual_release": manual_release_callback,
            "auto_toggle": auto_toggle_callback,
            "abort": abort_callback,
            "mode_toggle": mode_toggle_callback,
            "window_toggle": window_toggle_callback,
        }
        
        # 保持向后兼容的属性
        self.manual_press_callback = manual_press_callback
        self.manual_release_callback = manual_release_callback
        self.auto_toggle_callback = auto_toggle_callback
        self.abort_callback = abort_callback
        self.mode_toggle_callback = mode_toggle_callback

    def _safe_call_sync(self, callback):
        """安全地调用同步回调函数"""
        if not callback:
            return
            
        try:
            # ShortcutManager只调用同步回调
            # 异步操作由Application通过命令队列处理
            callback()
        except Exception as e:
            self.logger.error(f"执行快捷键回调失败: {e}", exc_info=True)

    def is_combo(self, *keys) -> bool:
        """判断是否同时按下了一组按键。"""
        return all(k in self.pressed_keys for k in keys)

    def _normalize_key(self, key):
        """标准化按键名称"""
        if key == pynput_keyboard.Key.alt_l or key == pynput_keyboard.Key.alt_r:
            return "alt"
        elif key == pynput_keyboard.Key.shift_l or key == pynput_keyboard.Key.shift_r:
            return "shift"
        elif key == pynput_keyboard.Key.ctrl_l or key == pynput_keyboard.Key.ctrl_r:
            return "ctrl"
        elif hasattr(key, "char") and key.char:
            return key.char.lower()
        else:
            return str(key).replace("Key.", "").lower()

    def _on_press(self, key):
        try:
            # 记录按下的键
            normalized_key = self._normalize_key(key)
            if normalized_key:
                self.pressed_keys.add(normalized_key)

            # 检查所有配置的快捷键
            for key_combo, action in self.shortcuts.items():
                if self.is_combo(*key_combo):
                    callback = self.callbacks.get(action)
                    if callback:
                        self._safe_call_sync(callback)
                    
                    # 特殊处理：记录Alt+Shift+V按下状态
                    if action == "manual_press":
                        self.manual_v_pressed = True

        except Exception as e:
            self.logger.error(f"键盘事件处理错误: {e}")

    def _on_release(self, key):
        try:
            # 清除释放的键
            normalized_key = self._normalize_key(key)
            if normalized_key:
                self.pressed_keys.discard(normalized_key)

            # 特殊处理：长按说话的释放事件
            # 当Alt+Shift+V曾经被按下，但现在组合键不再完整时，触发释放回调
            if self.manual_v_pressed and not self.is_combo("alt", "shift", "v"):
                self.manual_v_pressed = False
                if self.manual_release_callback:
                    self._safe_call_sync(self.manual_release_callback)

        except Exception as e:
            self.logger.error(f"键盘事件处理错误: {e}")

    def start_listener(self):
        """启动键盘监听。"""
        if pynput_keyboard is None:
            self.logger.warning(
                "键盘监听不可用：pynput 库未能正确加载。快捷键功能将不可用。"
            )
            return

        if self.keyboard_listener is None:
            try:
                self.keyboard_listener = pynput_keyboard.Listener(
                    on_press=self._on_press, on_release=self._on_release
                )
                self.keyboard_listener.start()
                self.logger.info("键盘监听已启动。")
            except Exception as e:
                self.logger.error(f"启动键盘监听失败: {e}")
                self.keyboard_listener = None

    def stop_listener(self):
        """停止键盘监听。"""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener.join()
                self.logger.info("键盘监听已停止。")
            except Exception as e:
                self.logger.error(f"停止键盘监听失败: {e}")
            finally:
                self.keyboard_listener = None

    def register_callback(self, action: str, callback: Callable):
        """注册新的回调函数"""
        self.callbacks[action] = callback

    def add_shortcut(self, key_combo: tuple, action: str):
        """添加新的快捷键"""
        self.shortcuts[key_combo] = action

    def remove_shortcut(self, key_combo: tuple):
        """移除快捷键"""
        if key_combo in self.shortcuts:
            del self.shortcuts[key_combo]

    def get_shortcuts_description(self) -> str:
        """获取快捷键描述"""
        descriptions = []
        action_names = {
            "manual_press": "长按说话",
            "auto_toggle": "自动对话",
            "abort": "打断",
            "mode_toggle": "模式切换",
            "window_toggle": "窗口切换"
        }
        
        for key_combo, action in self.shortcuts.items():
            key_str = "+".join([k.title() for k in key_combo])
            action_desc = action_names.get(action, action)
            descriptions.append(f"{key_str} ({action_desc})")
        
        return " | ".join(descriptions)

    def is_available(self) -> bool:
        """检查快捷键功能是否可用"""
        return pynput_keyboard is not None