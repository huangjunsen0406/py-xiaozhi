import asyncio
import logging
import os
import platform

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


class AsyncShortcutManager:
    """
    异步全局快捷键管理器.
    """

    # 默认快捷键配置
    DEFAULT_SHORTCUTS = {
        ("alt", "shift", "v"): "manual_press",  # 长按说话
        ("alt", "shift", "a"): "auto_toggle",  # 自动对话
        ("alt", "shift", "x"): "abort",  # 打断
        ("alt", "shift", "m"): "mode_toggle",  # 模式切换
        ("alt", "shift", "h"): "window_toggle",  # 显示/隐藏窗口
    }

    def __init__(self, logger: logging.Logger = None):
        from src.utils.logging_config import get_logger

        self.logger = logger or get_logger(__name__)
        self.keyboard_listener = None
        self.pressed_keys = set()  # 按键状态集合
        self.manual_v_pressed = False  # 记录Alt+Shift+V是否被按下
        self._running = False
        self._app_instance = None
        self._mode = None  # 存储应用运行模式 (gui/cli)
        self._task = None  # 保存异步任务

        # 快捷键配置
        self.shortcuts = self.DEFAULT_SHORTCUTS.copy()

    def _get_app_instance(self):
        """
        获取Application实例.
        """
        if self._app_instance is None:
            try:
                # 延迟导入避免循环导入
                from src.application import Application

                self._app_instance = Application.get_instance()

                # 获取应用模式
                if (
                    hasattr(self._app_instance, "display")
                    and self._app_instance.display
                ):
                    if hasattr(self._app_instance.display, "root"):
                        self._mode = "gui"
                    else:
                        self._mode = "cli"

                self.logger.info(f"获取到Application实例，模式: {self._mode}")
            except Exception as e:
                self.logger.error(f"获取Application实例失败: {e}")

        return self._app_instance

    def is_combo(self, *keys) -> bool:
        """
        判断是否同时按下了一组按键.
        """
        return all(k in self.pressed_keys for k in keys)

    def _normalize_key(self, key):
        """
        标准化按键名称.
        """
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
        """
        按键按下事件处理.
        """
        try:
            # 记录按下的键
            normalized_key = self._normalize_key(key)
            if normalized_key:
                self.pressed_keys.add(normalized_key)

            # 检查所有配置的快捷键
            for key_combo, action in self.shortcuts.items():
                if self.is_combo(*key_combo):
                    # 创建异步任务处理快捷键动作
                    task = asyncio.create_task(self._handle_shortcut_action(action))

                    # 添加错误处理回调
                    def task_done_callback(t):
                        if t.exception():
                            self.logger.error(f"快捷键任务执行异常: {t.exception()}")

                    task.add_done_callback(task_done_callback)

                    # 特殊处理：记录Alt+Shift+V按下状态
                    if action == "manual_press":
                        self.manual_v_pressed = True

        except Exception as e:
            self.logger.error(f"键盘按下事件处理错误: {e}")

    def _on_release(self, key):
        """
        按键释放事件处理.
        """
        try:
            # 清除释放的键
            normalized_key = self._normalize_key(key)
            if normalized_key:
                self.pressed_keys.discard(normalized_key)

            # 特殊处理：长按说话的释放事件
            if self.manual_v_pressed and not self.is_combo("alt", "shift", "v"):
                self.manual_v_pressed = False

                # 创建异步任务处理释放动作
                task = asyncio.create_task(
                    self._handle_shortcut_action("manual_release")
                )

                # 添加错误处理回调
                def task_done_callback(t):
                    if t.exception():
                        self.logger.error(f"快捷键释放任务执行异常: {t.exception()}")

                task.add_done_callback(task_done_callback)

        except Exception as e:
            self.logger.error(f"键盘释放事件处理错误: {e}")

    async def _handle_shortcut_action(self, action: str):
        """
        处理快捷键动作.
        """
        app = self._get_app_instance()
        if not app:
            return

        # 检查CLI模式下是否应该跳过窗口相关操作
        if self._mode == "cli" and action == "window_toggle":
            self.logger.info("CLI模式下跳过窗口切换快捷键")
            return

        # 执行对应的操作 - 直接调用Application方法
        try:
            if action == "manual_press":
                # 开始监听 - 通过命令队列确保顺序执行
                await app.start_listening()
            elif action == "manual_release":
                # 停止监听 - 通过命令队列确保顺序执行
                await app.stop_listening()
            elif action == "auto_toggle":
                # 切换聊天状态 - 通过命令队列确保顺序执行
                await app.toggle_chat_state()
            elif action == "abort":
                # 中止语音 - 通过命令队列确保顺序执行
                from src.constants.constants import AbortReason

                await app.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
            elif action == "mode_toggle":
                # 模式切换 - 通过命令队列确保顺序执行
                await app.schedule_command(app._on_mode_changed)
            elif action == "window_toggle" and self._mode == "gui":
                # 窗口切换 - 直接操作GUI，不需要通过命令队列
                await self._toggle_window_visibility(app)
        except Exception as e:
            self.logger.error(f"执行快捷键动作 {action} 失败: {e}", exc_info=True)

    async def _toggle_window_visibility(self, app):
        """
        切换窗口显示状态 - 直接操作GUI组件.
        """
        try:
            if not app.display or not hasattr(app.display, "root"):
                self.logger.warning("GUI窗口不可用")
                return

            if app.display.root:
                if app.display.root.isVisible():
                    app.display.root.hide()
                    self.logger.info("主窗口已隐藏")
                else:
                    app.display.root.show()
                    app.display.root.activateWindow()
                    app.display.root.raise_()
                    self.logger.info("主窗口已显示")
            else:
                self.logger.warning("GUI窗口不可用")

        except Exception as e:
            self.logger.error(f"切换窗口显示状态失败: {e}", exc_info=True)

    async def start_async(self):
        """
        异步启动键盘监听.
        """
        if pynput_keyboard is None:
            self.logger.warning(
                "键盘监听不可用：pynput 库未能正确加载。快捷键功能将不可用。"
            )
            return False

        if self.keyboard_listener is None:
            try:
                self.keyboard_listener = pynput_keyboard.Listener(
                    on_press=self._on_press, on_release=self._on_release
                )
                self.keyboard_listener.start()
                self._running = True
                self.logger.info("全局快捷键监听已启动")
                self.logger.info(f"快捷键列表: {self.get_shortcuts_description()}")
                return True
            except Exception as e:
                self.logger.error(f"启动快捷键监听失败: {e}")
                self.keyboard_listener = None
                return False
        return True

    async def stop_async(self):
        """
        异步停止键盘监听.
        """
        if self.keyboard_listener:
            try:
                self._running = False
                self.keyboard_listener.stop()
                self.keyboard_listener.join()
                self.logger.info("全局快捷键监听已停止")
            except Exception as e:
                self.logger.error(f"停止快捷键监听失败: {e}")
            finally:
                self.keyboard_listener = None

    def add_shortcut(self, key_combo: tuple, action: str):
        """
        添加新的快捷键.
        """
        self.shortcuts[key_combo] = action

    def remove_shortcut(self, key_combo: tuple):
        """
        移除快捷键.
        """
        if key_combo in self.shortcuts:
            del self.shortcuts[key_combo]

    def get_shortcuts_description(self) -> str:
        """
        获取快捷键描述.
        """
        descriptions = []
        action_names = {
            "manual_press": "长按说话",
            "auto_toggle": "自动对话",
            "abort": "打断",
            "mode_toggle": "模式切换",
            "window_toggle": "窗口切换",
        }

        for key_combo, action in self.shortcuts.items():
            # 在CLI模式下跳过窗口相关快捷键的描述
            if self._mode == "cli" and action == "window_toggle":
                continue

            key_str = "+".join([k.title() for k in key_combo])
            action_desc = action_names.get(action, action)
            descriptions.append(f"{key_str} ({action_desc})")

        return " | ".join(descriptions)

    def is_available(self) -> bool:
        """
        检查快捷键功能是否可用.
        """
        return pynput_keyboard is not None

    def is_running(self) -> bool:
        """
        检查快捷键监听是否正在运行.
        """
        return self._running and self.keyboard_listener is not None


# 全局快捷键实例
_global_shortcut_manager = None


async def start_global_shortcuts_async(logger: logging.Logger = None):
    """
    异步启动全局快捷键服务.
    """
    global _global_shortcut_manager
    if _global_shortcut_manager is None:
        _global_shortcut_manager = AsyncShortcutManager(logger)
        # 等待一小段时间确保Application实例已经创建
        await asyncio.sleep(0.5)
        success = await _global_shortcut_manager.start_async()
        if success and logger:
            logger.info("全局快捷键服务已启动")
        return _global_shortcut_manager
    return _global_shortcut_manager


async def stop_global_shortcuts_async():
    """
    异步停止全局快捷键服务.
    """
    global _global_shortcut_manager
    if _global_shortcut_manager:
        await _global_shortcut_manager.stop_async()
        _global_shortcut_manager = None


def get_global_shortcuts_manager():
    """
    获取全局快捷键管理器实例.
    """
    return _global_shortcut_manager
