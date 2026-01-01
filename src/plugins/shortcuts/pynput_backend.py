"""pynput 快捷键后端.

用于 Linux 和 Windows 系统。
"""

import asyncio
import time
from typing import Callable, Optional, Set

from src.logging import get_logger

from .base import ShortcutBackend, ShortcutConfig

logger = get_logger()

try:
    from pynput import keyboard
except ImportError as e:
    raise ImportError(
        "pynput is required for keyboard shortcut support. "
        "Install with: pip install pynput"
    ) from e


class PynputShortcutBackend(ShortcutBackend):
    """pynput 快捷键后端.

    适用于 Linux 和 Windows 系统。
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__(loop)
        self._listener = None
        self._pressed_keys: Set[str] = set()
        self._last_activity_time = 0.0
        self._health_check_task = None
        self._check_interval = 10.0  # 健康检查间隔（秒）
        self._activity_timeout = 300.0  # 活动超时（秒）

        # 控制字符映射
        self._key_mapping = {
            "\x17": "w", "\x01": "a", "\x13": "s", "\x04": "d",
            "\x05": "e", "\x12": "r", "\x14": "t", "\x06": "f",
            "\x07": "g", "\x08": "h", "\x0a": "j", "\x0b": "k",
            "\x0c": "l", "\x1a": "z", "\x18": "x", "\x03": "c",
            "\x16": "v", "\x02": "b", "\x0e": "n", "\x0d": "m",
            "\x11": "q",
        }

    async def start(self) -> bool:
        """启动快捷键监听."""
        if self._running:
            return True

        try:
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.start()
            self._running = True
            self._last_activity_time = time.time()

            # 启动健康检查
            self._start_health_check()

            logger.info("pynput 全局快捷键监听已启动")
            return True
        except Exception as e:
            logger.error(f"启动 pynput 快捷键监听失败: {e}")
            return False

    async def stop(self) -> None:
        """停止快捷键监听."""
        self._running = False

        # 停止健康检查
        if self._health_check_task:
            self._health_check_task.cancel()
            # concurrent.futures.Future 不能直接 await，需要特殊处理
            try:
                # 等待 Future 完成（忽略取消异常）
                self._health_check_task.result(timeout=1.0)
            except Exception:
                pass
            self._health_check_task = None

        # 停止监听器
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.warning(f"停止监听器时出错: {e}")
            self._listener = None

        self._pressed_keys.clear()
        logger.info("pynput 全局快捷键监听已停止")

    def register(self, name: str, config: ShortcutConfig, callback: Callable) -> bool:
        """注册快捷键."""
        self._shortcuts[name] = config
        self._callbacks[name] = callback
        logger.info(f"已注册快捷键: {name} -> {config.modifier}+{config.key}")
        return True

    def unregister(self, name: str) -> bool:
        """注销快捷键."""
        if name not in self._shortcuts:
            return False

        del self._shortcuts[name]
        if name in self._callbacks:
            del self._callbacks[name]

        logger.info(f"已注销快捷键: {name}")
        return True

    def _on_key_press(self, key) -> None:
        """按键按下回调."""
        if not self._running:
            return

        self._last_activity_time = time.time()
        key_name = self._get_key_name(key)
        if not key_name:
            return

        self._pressed_keys.add(key_name)
        self._check_shortcuts()

    def _on_key_release(self, key) -> None:
        """按键释放回调."""
        if not self._running:
            return

        self._last_activity_time = time.time()
        key_name = self._get_key_name(key)
        if not key_name:
            return

        self._pressed_keys.discard(key_name)

    def _get_key_name(self, key) -> Optional[str]:
        """获取按键名称."""
        try:
            if hasattr(key, "name"):
                name = key.name
                # 规范化修饰键名称
                if name in ("ctrl_l", "ctrl_r"):
                    return "ctrl"
                if name in ("alt_l", "alt_r"):
                    return "alt"
                if name in ("shift_l", "shift_r"):
                    return "shift"
                if name == "cmd":
                    return "cmd"
                if name == "esc":
                    return "escape"
                if name == "enter":
                    return "return"
                return name.lower()
            elif hasattr(key, "char") and key.char:
                char = key.char
                if char == "\n":
                    return "return"
                if char in self._key_mapping:
                    return self._key_mapping[char]
                return char.lower()
        except Exception:
            pass
        return None

    def _check_shortcuts(self) -> None:
        """检查是否触发了快捷键."""
        if not self._shortcuts:
            return

        # 检查修饰键状态
        ctrl = any(k in self._pressed_keys for k in ("ctrl", "control"))
        alt = any(k in self._pressed_keys for k in ("alt", "option"))
        shift = "shift" in self._pressed_keys
        cmd = "cmd" in self._pressed_keys

        for name, config in self._shortcuts.items():
            if self._match_shortcut(config, ctrl, alt, shift, cmd):
                logger.debug(f"触发快捷键: {name}")
                self._run_callback(name)

    def _match_shortcut(
        self, config: ShortcutConfig, ctrl: bool, alt: bool, shift: bool, cmd: bool
    ) -> bool:
        """检查是否匹配快捷键配置."""
        modifier = config.modifier.lower()

        # 检查修饰键
        if modifier == "ctrl" and not ctrl:
            return False
        if modifier == "alt" and not alt:
            return False
        if modifier == "shift" and not shift:
            return False
        if modifier == "cmd" and not cmd:
            return False

        # 检查主键
        return config.key.lower() in {k.lower() for k in self._pressed_keys}

    def _start_health_check(self) -> None:
        """启动健康检查任务."""
        if self._loop:
            self._health_check_task = asyncio.run_coroutine_threadsafe(
                self._health_check_loop(), self._loop
            )

    async def _health_check_loop(self) -> None:
        """健康检查循环."""
        while self._running:
            await asyncio.sleep(self._check_interval)

            if not self._running:
                break

            # 检查监听器是否仍在运行
            if self._listener and not self._listener.is_alive():
                logger.warning("pynput 监听器已停止，尝试重启...")
                await self._restart_listener()

    async def _restart_listener(self) -> None:
        """重启监听器."""
        try:
            # 停止旧的监听器
            if self._listener:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

            # 短暂等待
            await asyncio.sleep(0.5)

            # 创建新的监听器
            self._listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )
            self._listener.start()
            self._pressed_keys.clear()
            logger.info("pynput 监听器重启成功")
        except Exception as e:
            logger.error(f"重启 pynput 监听器失败: {e}")
