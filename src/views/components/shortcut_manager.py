import asyncio
from dataclasses import dataclass
from typing import Dict, Optional, Set

from src.constants.constants import AbortReason
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ShortcutConfig:
    """
    快捷键配置数据类.
    """

    modifier: str
    key: str
    description: str


class ShortcutManager:
    """
    全局快捷键管理器.
    """

    def __init__(self):
        """
        初始化快捷键管理器.
        """
        self.config = ConfigManager.get_instance()
        self.shortcuts_config = self.config.get_config("SHORTCUTS", {})
        self.enabled = self.shortcuts_config.get("ENABLED", True)

        # 内部状态
        self.pressed_keys: Set[str] = set()
        self.manual_press_active = False
        self.running = False

        # 组件引用
        self.application = None
        self.display = None

        # 事件循环引用
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._listener = None

        # 快捷键配置映射
        self.shortcuts: Dict[str, ShortcutConfig] = {}
        self._load_shortcuts()

    def _load_shortcuts(self):
        """
        从配置加载快捷键设置.
        """
        shortcut_types = [
            "MANUAL_PRESS",
            "AUTO_TOGGLE",
            "ABORT",
            "MODE_TOGGLE",
            "WINDOW_TOGGLE",
        ]

        for shortcut_type in shortcut_types:
            config = self.shortcuts_config.get(shortcut_type, {})
            if config:
                self.shortcuts[shortcut_type] = ShortcutConfig(
                    modifier=config.get("modifier", "ctrl"),
                    key=config.get("key", "").lower(),
                    description=config.get("description", ""),
                )

    async def start(self) -> bool:
        """
        启动快捷键监听.
        """
        if not self.enabled:
            logger.info("全局快捷键已禁用")
            return False

        try:
            # 保存主事件循环引用
            self._main_loop = asyncio.get_running_loop()

            # 导入pynput库
            from pynput import keyboard

            # 获取Application实例
            from src.application import Application

            self.application = Application.get_instance()
            self.display = self.application.display

            # 设置按键回调
            self._listener = keyboard.Listener(
                on_press=self._on_key_press, on_release=self._on_key_release
            )
            self._listener.start()
            self.running = True

            logger.info("全局快捷键监听已启动")
            return True

        except ImportError:
            logger.error("未安装pynput库，无法使用全局快捷键功能")
            return False
        except Exception as e:
            logger.error(f"启动全局快捷键监听失败: {e}")
            return False

    def _on_key_press(self, key):
        """
        按键按下回调.
        """
        if not self.running:
            return

        try:
            key_name = self._get_key_name(key)
            if key_name:
                self.pressed_keys.add(key_name)
                self._check_shortcuts(True)
        except Exception as e:
            logger.error(f"按键处理错误: {e}")

    def _on_key_release(self, key):
        """
        按键释放回调.
        """
        if not self.running:
            return

        try:
            key_name = self._get_key_name(key)
            if key_name:
                if key_name in self.pressed_keys:
                    self.pressed_keys.remove(key_name)
                self._check_shortcuts(False)
        except Exception as e:
            logger.error(f"释放键处理错误: {e}")

    def _get_key_name(self, key) -> Optional[str]:
        """
        获取按键名称.
        """
        try:
            if hasattr(key, "name"):
                return key.name.lower()
            elif hasattr(key, "char") and key.char:
                return key.char.lower()
            return None
        except Exception:
            return None

    def _check_shortcuts(self, is_press: bool):
        """
        检查快捷键组合.
        """
        # 检查修饰键状态
        ctrl_pressed = any(
            key in self.pressed_keys for key in ["ctrl", "ctrl_l", "ctrl_r"]
        )

        if not ctrl_pressed:
            # 如果Ctrl键被释放，且按住说话功能处于激活状态，则停止监听
            if not is_press and self.manual_press_active:
                self._handle_manual_press(False)
            return

        # 检查各个快捷键
        for shortcut_type, config in self.shortcuts.items():
            if config.key in self.pressed_keys:
                self._handle_shortcut(shortcut_type, is_press)

    def _handle_shortcut(self, shortcut_type: str, is_press: bool):
        """
        处理快捷键动作.
        """
        handlers = {
            "MANUAL_PRESS": lambda: self._handle_manual_press(is_press),
            "AUTO_TOGGLE": lambda: self._handle_auto_toggle() if is_press else None,
            "ABORT": lambda: self._handle_abort() if is_press else None,
            "MODE_TOGGLE": lambda: self._handle_mode_toggle() if is_press else None,
            "WINDOW_TOGGLE": lambda: self._handle_window_toggle() if is_press else None,
        }

        handler = handlers.get(shortcut_type)
        if handler:
            handler()

    def _run_coroutine_threadsafe(self, coro):
        """
        线程安全地运行协程.
        """
        if not self._main_loop or not self.running:
            logger.warning("事件循环未运行或快捷键管理器已停止")
            return

        try:
            asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        except Exception as e:
            logger.error(f"线程安全运行协程失败: {e}")

    def _handle_manual_press(self, is_press: bool):
        """
        处理按住说话快捷键.
        """
        if not self.application:
            return

        if is_press and not self.manual_press_active:
            logger.debug("快捷键：开始监听")
            self._run_coroutine_threadsafe(self.application.start_listening())
            self.manual_press_active = True
        elif not is_press and self.manual_press_active:
            logger.debug("快捷键：停止监听")
            self._run_coroutine_threadsafe(self.application.stop_listening())
            self.manual_press_active = False

    def _handle_auto_toggle(self):
        """
        处理自动对话快捷键.
        """
        if self.application:
            self._run_coroutine_threadsafe(self.application.toggle_chat_state())

    def _handle_abort(self):
        """
        处理中断对话快捷键.
        """
        if self.application:
            self._run_coroutine_threadsafe(
                self.application.abort_speaking(AbortReason.NONE)
            )

    def _handle_mode_toggle(self):
        """
        处理模式切换快捷键.
        """
        if self.display:
            self._run_coroutine_threadsafe(self.display.toggle_mode())

    def _handle_window_toggle(self):
        """
        处理窗口显示/隐藏快捷键.
        """
        if self.display:
            self._run_coroutine_threadsafe(self.display.toggle_window_visibility())

    async def stop(self):
        """
        停止快捷键监听.
        """
        self.running = False
        self.manual_press_active = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("全局快捷键监听已停止")


async def start_global_shortcuts_async(
    logger_instance=None,
) -> Optional[ShortcutManager]:
    """异步启动全局快捷键管理器.

    返回:     ShortcutManager实例或None（如果启动失败）
    """
    try:
        shortcut_manager = ShortcutManager()
        success = await shortcut_manager.start()

        if success:
            if logger_instance:
                logger_instance.info("全局快捷键管理器启动成功")
            return shortcut_manager
        else:
            if logger_instance:
                logger_instance.warning("全局快捷键管理器启动失败")
            return None
    except Exception as e:
        if logger_instance:
            logger_instance.error(f"启动全局快捷键管理器时出错: {e}")
        return None
