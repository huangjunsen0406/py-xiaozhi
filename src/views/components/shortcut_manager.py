import asyncio
import time
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

        # 按键状态跟踪
        self.key_states = {
            "MANUAL_PRESS": False,  # 按住说话的状态
            "last_manual_press_time": 0,  # 上次触发时间
            "ABORT": False,  # 打断状态
        }

        # Windows按键映射
        self.key_mapping = {
            "\x17": "w",  # Ctrl+W
            "\x01": "a",  # Ctrl+A
            "\x13": "s",  # Ctrl+S
            "\x04": "d",  # Ctrl+D
            "\x05": "e",  # Ctrl+E
            "\x12": "r",  # Ctrl+R
            "\x14": "t",  # Ctrl+T
            "\x06": "f",  # Ctrl+F
            "\x07": "g",  # Ctrl+G
            "\x08": "h",  # Ctrl+H
            "\x0a": "j",  # Ctrl+J
            "\x0b": "k",  # Ctrl+K
            "\x0c": "l",  # Ctrl+L
            "\x1a": "z",  # Ctrl+Z
            "\x18": "x",  # Ctrl+X
            "\x03": "c",  # Ctrl+C
            "\x16": "v",  # Ctrl+V
            "\x02": "b",  # Ctrl+B
            "\x0e": "n",  # Ctrl+N
            "\x0d": "m",  # Ctrl+M
            "\x11": "q",  # Ctrl+Q
        }

        # 组件引用
        self.application = None
        self.display = None

        # 事件循环引用
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None
        self._listener = None

        # 快捷键配置映射
        self.shortcuts: Dict[str, ShortcutConfig] = {}
        self._load_shortcuts()

        # 错误恢复机制
        self._last_activity_time = 0
        self._listener_error_count = 0
        self._max_error_count = 3
        self._health_check_task = None
        self._restart_in_progress = False

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

            # 导入pynput库并检查平台兼容性
            try:
                from pynput import keyboard

                logger.info(f"pynput库导入成功，当前平台: {self._get_platform_info()}")
            except ImportError as e:
                logger.error(f"未安装pynput库: {e}")
                logger.error("请安装pynput: pip install pynput")
                return False

            # 检查平台权限
            if not self._check_platform_permissions():
                return False

            # 获取Application实例
            from src.application import Application

            self.application = Application.get_instance()
            self.display = self.application.display

            # 记录配置的快捷键
            self._log_shortcut_config()

            # 设置按键回调
            self._listener = keyboard.Listener(
                on_press=self._on_key_press, on_release=self._on_key_release
            )
            self._listener.start()
            self.running = True

            # 启动健康检查任务
            self._start_health_check_task()

            logger.info("全局快捷键监听已启动")
            return True

        except ImportError:
            logger.error("未安装pynput库，无法使用全局快捷键功能")
            return False
        except Exception as e:
            logger.error(f"启动全局快捷键监听失败: {e}", exc_info=True)
            return False

    def _check_platform_permissions(self) -> bool:
        """
        检查平台权限.
        """
        import platform

        system = platform.system()

        if system == "Darwin":  # macOS
            logger.info("检测到 macOS 系统，请确认以下权限:")
            logger.info("1. 系统偏好设置 > 安全性与隐私 > 隐私 > 辅助功能")
            logger.info("2. 确保应用程序已添加到辅助功能列表并启用")
            logger.info("3. 如果使用终端运行，需要给终端辅助功能权限")

        elif system == "Linux":
            logger.info("检测到 Linux 系统，请确认:")
            logger.info("1. 用户在 input 组中: sudo usermod -a -G input $USER")
            logger.info("2. X11 或 Wayland 环境正常运行")

        elif system == "Windows":
            logger.info("检测到 Windows 系统，请确认:")
            logger.info("1. 以管理员权限运行（某些情况下需要）")
            logger.info("2. 防病毒软件未阻止键盘监听")

        return True

    def _get_platform_info(self) -> str:
        """
        获取平台信息.
        """
        import platform

        return f"{platform.system()} {platform.release()}"

    def _log_shortcut_config(self):
        """
        记录快捷键配置.
        """
        logger.info("已配置的快捷键:")
        for shortcut_type, config in self.shortcuts.items():
            logger.info(
                f"  {shortcut_type}: {config.modifier}+{config.key} - {config.description}"
            )
        if not self.shortcuts:
            logger.warning("未配置任何快捷键")

    def _on_key_press(self, key):
        """
        按键按下回调.
        """
        if not self.running:
            return

        try:
            # 更新活动时间
            self._last_activity_time = time.time()

            key_name = self._get_key_name(key)
            if key_name:
                logger.debug(f"按键按下: {key_name}")
                # 如果是特殊字符且ctrl被按下，直接处理打断功能
                if (
                    hasattr(key, "char")
                    and key.char == "\x11"
                    and any(
                        k in self.pressed_keys for k in ["ctrl", "ctrl_l", "ctrl_r"]
                    )
                ):
                    logger.debug("检测到Ctrl+Q组合，触发打断")
                    self._handle_abort()
                    return

                self.pressed_keys.add(key_name)
                logger.debug(f"当前按下的键: {sorted(self.pressed_keys)}")
                self._check_shortcuts(True)
        except Exception as e:
            logger.error(f"按键处理错误: {e}", exc_info=True)
            self._handle_listener_error()

    def _on_key_release(self, key):
        """
        按键释放回调.
        """
        if not self.running:
            return

        try:
            # 更新活动时间
            self._last_activity_time = time.time()

            key_name = self._get_key_name(key)
            if key_name:
                logger.debug(f"按键释放: {key_name}")
                if key_name in self.pressed_keys:
                    self.pressed_keys.remove(key_name)
                logger.debug(f"当前按下的键: {sorted(self.pressed_keys)}")

                # 检查是否需要停止按住说话
                if (
                    self.key_states["MANUAL_PRESS"] and len(self.pressed_keys) == 0
                ):  # 所有按键都已释放
                    self.key_states["MANUAL_PRESS"] = False
                    self.manual_press_active = False
                    if self.application:
                        logger.debug("强制停止监听")
                        self._run_coroutine_threadsafe(
                            self.application.stop_listening()
                        )

                self._check_shortcuts(False)
        except Exception as e:
            logger.error(f"释放键处理错误: {e}", exc_info=True)
            self._handle_listener_error()

    def _get_key_name(self, key) -> Optional[str]:
        """
        获取按键名称.
        """
        try:
            # 处理特殊按键
            if hasattr(key, "name"):
                # 处理修饰键
                if key.name in ["ctrl_l", "ctrl_r"]:
                    return "ctrl"
                if key.name in ["alt_l", "alt_r"]:
                    return "alt"
                if key.name in ["shift_l", "shift_r"]:
                    return "shift"
                if key.name == "cmd":  # Windows键/Command键
                    return "cmd"
                if key.name == "esc":
                    return "esc"
                if key.name == "enter":
                    return "enter"
                return key.name.lower()
            # 处理字符按键
            elif hasattr(key, "char") and key.char:
                # 处理回车键
                if key.char == "\n":
                    return "enter"
                # 检查是否是Windows特殊字符映射
                if key.char in self.key_mapping:
                    return self.key_mapping[key.char]
                # 统一转换为小写
                return key.char.lower()
            return None
        except Exception as e:
            logger.error(f"获取按键名称时出错: {e}")
            return None

    def _check_shortcuts(self, is_press: bool):
        """
        检查快捷键组合.
        """
        # 检查修饰键状态
        ctrl_pressed = any(
            key in self.pressed_keys
            for key in ["ctrl", "ctrl_l", "ctrl_r", "control", "control_l", "control_r"]
        )

        # 检查Alt键
        alt_pressed = any(
            key in self.pressed_keys
            for key in ["alt", "alt_l", "alt_r", "option", "option_l", "option_r"]
        )

        # 检查Shift键
        shift_pressed = any(
            key in self.pressed_keys for key in ["shift", "shift_l", "shift_r"]
        )

        # 检查Windows/Command键
        cmd_pressed = "cmd" in self.pressed_keys

        # 检查各个快捷键
        for shortcut_type, config in self.shortcuts.items():
            if self._is_shortcut_match(
                config, ctrl_pressed, alt_pressed, shift_pressed, cmd_pressed
            ):
                self._handle_shortcut(shortcut_type, is_press)

    def _is_shortcut_match(
        self,
        config: ShortcutConfig,
        ctrl_pressed: bool,
        alt_pressed: bool,
        shift_pressed: bool,
        cmd_pressed: bool,
    ) -> bool:
        """
        检查快捷键是否匹配.
        """
        # 检查修饰键
        modifier_check = True
        if config.modifier == "ctrl" and not ctrl_pressed:
            modifier_check = False
        elif config.modifier == "alt" and not alt_pressed:
            modifier_check = False
        elif config.modifier == "shift" and not shift_pressed:
            modifier_check = False
        elif config.modifier == "cmd" and not cmd_pressed:
            modifier_check = False
        elif config.modifier == "ctrl+alt" and not (ctrl_pressed and alt_pressed):
            modifier_check = False
        elif config.modifier == "ctrl+shift" and not (ctrl_pressed and shift_pressed):
            modifier_check = False
        elif config.modifier == "alt+shift" and not (alt_pressed and shift_pressed):
            modifier_check = False

        # 检查主键是否按下（不区分大小写）
        key_pressed = config.key.lower() in {k.lower() for k in self.pressed_keys}

        return modifier_check and key_pressed

    def _handle_shortcut(self, shortcut_type: str, is_press: bool):
        """
        处理快捷键动作.
        """
        # 特殊处理按住说话功能
        if shortcut_type == "MANUAL_PRESS":
            current_time = time.time()
            # 如果是按下状态
            if is_press:
                # 如果之前不是按下状态，才触发start_listening
                if not self.key_states["MANUAL_PRESS"]:
                    self.key_states["MANUAL_PRESS"] = True
                    self.key_states["last_manual_press_time"] = current_time
                    logger.info(f"触发快捷键: {shortcut_type}, 按下状态: {is_press}")
                    self._handle_manual_press(True)
            else:
                # 如果之前是按下状态，才触发stop_listening
                if self.key_states["MANUAL_PRESS"]:
                    self.key_states["MANUAL_PRESS"] = False
                    logger.info(f"触发快捷键: {shortcut_type}, 按下状态: {is_press}")
                    self._handle_manual_press(False)
            return

        # 特殊处理打断功能
        if shortcut_type == "ABORT":
            # 只在按下时触发一次
            if is_press and not self.key_states["ABORT"]:
                self.key_states["ABORT"] = True
                logger.info(f"触发快捷键: {shortcut_type}, 按下状态: {is_press}")
                self._handle_abort()
            elif not is_press:
                self.key_states["ABORT"] = False
            return

        # 其他快捷键的处理保持不变
        logger.info(f"触发快捷键: {shortcut_type}, 按下状态: {is_press}")

        handlers = {
            "AUTO_TOGGLE": lambda: self._handle_auto_toggle() if is_press else None,
            "MODE_TOGGLE": lambda: self._handle_mode_toggle() if is_press else None,
            "WINDOW_TOGGLE": lambda: self._handle_window_toggle() if is_press else None,
        }

        handler = handlers.get(shortcut_type)
        if handler:
            try:
                result = handler()
                if result is not None:
                    logger.debug(f"快捷键 {shortcut_type} 处理完成")
            except Exception as e:
                logger.error(f"处理快捷键 {shortcut_type} 时出错: {e}", exc_info=True)
        else:
            logger.warning(f"未找到快捷键处理器: {shortcut_type}")

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

        try:
            if is_press and not self.manual_press_active:
                logger.debug("快捷键：开始监听")
                self._run_coroutine_threadsafe(self.application.start_listening())
                self.manual_press_active = True
            elif not is_press:  # 不管之前状态如何，只要是释放就停止
                logger.debug("快捷键：停止监听")
                self._run_coroutine_threadsafe(self.application.stop_listening())
                self.manual_press_active = False
                self.key_states["MANUAL_PRESS"] = False
        except Exception as e:
            logger.error(f"处理按住说话时出错: {e}", exc_info=True)
            # 发生错误时重置状态
            self.manual_press_active = False
            self.key_states["MANUAL_PRESS"] = False

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
            logger.debug("快捷键：中断对话")
            try:
                self._run_coroutine_threadsafe(
                    self.application.abort_speaking(AbortReason.NONE)
                )
            except Exception as e:
                logger.error(f"执行打断操作时出错: {e}", exc_info=True)

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

    def _start_health_check_task(self):
        """
        启动健康检查任务.
        """
        if self._main_loop and not self._health_check_task:
            self._health_check_task = asyncio.run_coroutine_threadsafe(
                self._health_check_loop(), self._main_loop
            )
            logger.debug("快捷键健康检查任务已启动")

    async def _health_check_loop(self):
        """
        健康检查循环 - 检测键盘监听器是否正常工作.
        """
        import time

        while self.running and not self._restart_in_progress:
            try:
                await asyncio.sleep(30)  # 每30秒检查一次

                if not self.running:
                    break

                # 检查监听器是否存在且正在运行
                if not self._listener or not self._listener.running:
                    logger.warning("检测到键盘监听器已停止，尝试重启")
                    await self._restart_listener()
                    continue

                # 检查是否长时间没有按键活动（可能表示监听器失效）
                current_time = time.time()
                if (
                    self._last_activity_time > 0
                    and current_time - self._last_activity_time > 300
                ):  # 5分钟无活动
                    logger.info("长时间无按键活动，执行监听器健康检查")
                    # 重置活动时间，避免频繁检查
                    self._last_activity_time = current_time

            except Exception as e:
                logger.error(f"健康检查错误: {e}", exc_info=True)
                await asyncio.sleep(10)

    def _handle_listener_error(self):
        """
        处理监听器错误.
        """
        self._listener_error_count += 1
        logger.warning(
            f"键盘监听器错误计数: {self._listener_error_count}/{self._max_error_count}"
        )

        if self._listener_error_count >= self._max_error_count:
            logger.error("键盘监听器错误次数超限，尝试重启")
            if self._main_loop:
                asyncio.run_coroutine_threadsafe(
                    self._restart_listener(), self._main_loop
                )

    async def _restart_listener(self):
        """
        重启键盘监听器.
        """
        if self._restart_in_progress:
            logger.debug("监听器重启已在进行中，跳过")
            return

        self._restart_in_progress = True
        logger.info("开始重启键盘监听器...")

        try:
            # 停止当前监听器
            if self._listener:
                try:
                    self._listener.stop()
                    await asyncio.sleep(1)  # 等待停止完成
                except Exception as e:
                    logger.warning(f"停止监听器时出错: {e}")
                finally:
                    self._listener = None

            # 清理状态
            self.pressed_keys.clear()
            self.manual_press_active = False
            self._listener_error_count = 0

            # 重新导入pynput并创建新的监听器
            try:
                from pynput import keyboard

                self._listener = keyboard.Listener(
                    on_press=self._on_key_press, on_release=self._on_key_release
                )
                self._listener.start()

                # 更新活动时间
                import time

                self._last_activity_time = time.time()

                logger.info("键盘监听器重启成功")

            except Exception as e:
                logger.error(f"重启监听器失败: {e}", exc_info=True)
                # 等待一段时间后再次尝试
                await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"重启监听器过程中发生错误: {e}", exc_info=True)
        finally:
            self._restart_in_progress = False

    async def stop(self):
        """
        停止快捷键监听.
        """
        self.running = False
        self.manual_press_active = False

        # 停止健康检查任务
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await asyncio.wrap_future(self._health_check_task)
            except (asyncio.CancelledError, Exception):
                pass
            self._health_check_task = None

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
