"""macOS 快捷键后端.

使用 Carbon API 的 RegisterEventHotKey 注册全局热键。
这与 Electron 的 globalShortcut 底层使用相同的 API。
"""

import asyncio
import sys
from typing import Callable, Dict, Optional

from src.logging import get_logger

from .base import ShortcutBackend, ShortcutConfig

logger = get_logger()

# 检查是否在 macOS 上
if sys.platform != "darwin":
    raise ImportError("macOS backend only works on macOS")

try:
    import Quartz
except ImportError as e:
    raise ImportError(
        "PyObjC is required for macOS hotkey support. "
        "Install with: pip install pyobjc-framework-Quartz pyobjc-framework-Cocoa"
    ) from e


# Carbon 虚拟键码映射
# https://developer.apple.com/library/archive/technotes/tn2450/_index.html
KEYCODE_MAP = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04,
    "g": 0x05, "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09,
    "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F,
    "y": 0x10, "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14,
    "4": 0x15, "6": 0x16, "5": 0x17, "=": 0x18, "9": 0x19,
    "7": 0x1A, "-": 0x1B, "8": 0x1C, "0": 0x1D, "]": 0x1E,
    "o": 0x1F, "u": 0x20, "[": 0x21, "i": 0x22, "p": 0x23,
    "l": 0x25, "j": 0x26, "'": 0x27, "k": 0x28, ";": 0x29,
    "\\": 0x2A, ",": 0x2B, "/": 0x2C, "n": 0x2D, "m": 0x2E,
    ".": 0x2F, "`": 0x32, " ": 0x31, "space": 0x31,
    "return": 0x24, "enter": 0x24, "tab": 0x30, "escape": 0x35, "esc": 0x35,
    "delete": 0x33, "backspace": 0x33,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76,
    "f5": 0x60, "f6": 0x61, "f7": 0x62, "f8": 0x64,
    "f9": 0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
    "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "home": 0x73, "end": 0x77, "pageup": 0x74, "pagedown": 0x79,
}

# 修饰键掩码
MODIFIER_MAP = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "command": Quartz.kCGEventFlagMaskCommand,
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "control": Quartz.kCGEventFlagMaskControl,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "shift": Quartz.kCGEventFlagMaskShift,
}


class MacOSShortcutBackend(ShortcutBackend):
    """macOS 快捷键后端.

    使用 Quartz Event Tap 监听全局热键事件。
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        super().__init__(loop)
        self._tap = None
        self._run_loop_source = None
        self._hotkey_ids: Dict[str, int] = {}  # name -> hotkey_id
        self._registered_hotkeys: Dict[int, str] = {}  # hotkey_id -> name
        self._next_hotkey_id = 1
        self._monitor_thread = None
        self._pressed_modifiers = 0
        self._check_interval = 5.0  # 健康检查间隔（秒）
        self._health_check_task = None

    async def start(self) -> bool:
        """启动快捷键监听."""
        if self._running:
            return True

        try:
            # 创建事件监听
            self._create_event_tap()
            self._running = True

            # 启动健康检查
            self._start_health_check()

            logger.info("macOS 全局快捷键监听已启动 (Quartz Event Tap)")
            return True
        except Exception as e:
            logger.error(f"启动 macOS 快捷键监听失败: {e}")
            return False

    def _create_event_tap(self):
        """创建 Quartz Event Tap."""
        # 监听键盘按下事件
        event_mask = (
            Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown) |
            Quartz.CGEventMaskBit(Quartz.kCGEventFlagsChanged)
        )

        self._tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            event_mask,
            self._event_callback,
            None,
        )

        if self._tap is None:
            raise RuntimeError(
                "无法创建 Event Tap。请确保已授予辅助功能权限：\n"
                "系统偏好设置 → 安全性与隐私 → 隐私 → 辅助功能"
            )

        # 将 tap 添加到当前运行循环
        self._run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
            None, self._tap, 0
        )
        Quartz.CFRunLoopAddSource(
            Quartz.CFRunLoopGetCurrent(),
            self._run_loop_source,
            Quartz.kCFRunLoopCommonModes,
        )
        Quartz.CGEventTapEnable(self._tap, True)

    def _event_callback(self, proxy, event_type, event, refcon):
        """事件回调函数."""
        try:
            if event_type == Quartz.kCGEventKeyDown:
                # 获取键码和修饰键
                keycode = Quartz.CGEventGetIntegerValueField(
                    event, Quartz.kCGKeyboardEventKeycode
                )
                flags = Quartz.CGEventGetFlags(event)

                # 检查是否匹配已注册的热键
                self._check_hotkey(keycode, flags)

            elif event_type == Quartz.kCGEventFlagsChanged:
                # 更新修饰键状态
                self._pressed_modifiers = Quartz.CGEventGetFlags(event)

        except Exception as e:
            logger.error(f"事件回调错误: {e}")

        return event

    def _check_hotkey(self, keycode: int, flags: int) -> None:
        """检查是否匹配已注册的热键."""
        for name, config in self._shortcuts.items():
            # 获取期望的键码
            expected_keycode = KEYCODE_MAP.get(config.key.lower())
            if expected_keycode is None:
                continue

            if keycode != expected_keycode:
                continue

            # 检查修饰键
            expected_modifier = MODIFIER_MAP.get(config.modifier.lower(), 0)
            if expected_modifier == 0:
                continue

            # 检查修饰键是否匹配（只检查期望的修饰键是否按下）
            if flags & expected_modifier:
                logger.debug(f"触发快捷键: {name}")
                self._run_callback(name)

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
            except Exception as e:
                logger.debug(f"MacOS 健康检查超时: {e}")
            self._health_check_task = None

        # 移除 event tap
        if self._tap:
            Quartz.CGEventTapEnable(self._tap, False)
            if self._run_loop_source:
                Quartz.CFRunLoopRemoveSource(
                    Quartz.CFRunLoopGetCurrent(),
                    self._run_loop_source,
                    Quartz.kCFRunLoopCommonModes,
                )
            self._tap = None
            self._run_loop_source = None

        logger.info("macOS 全局快捷键监听已停止")

    def register(self, name: str, config: ShortcutConfig, callback: Callable) -> bool:
        """注册快捷键."""
        # 验证键码
        if config.key.lower() not in KEYCODE_MAP:
            logger.warning(f"不支持的按键: {config.key}")
            return False

        # 验证修饰键
        if config.modifier.lower() not in MODIFIER_MAP:
            logger.warning(f"不支持的修饰键: {config.modifier}")
            return False

        self._shortcuts[name] = config
        self._callbacks[name] = callback

        hotkey_id = self._next_hotkey_id
        self._next_hotkey_id += 1
        self._hotkey_ids[name] = hotkey_id
        self._registered_hotkeys[hotkey_id] = name

        logger.info(f"已注册快捷键: {name} -> {config.modifier}+{config.key}")
        return True

    def unregister(self, name: str) -> bool:
        """注销快捷键."""
        if name not in self._shortcuts:
            return False

        del self._shortcuts[name]
        del self._callbacks[name]

        if name in self._hotkey_ids:
            hotkey_id = self._hotkey_ids[name]
            del self._hotkey_ids[name]
            if hotkey_id in self._registered_hotkeys:
                del self._registered_hotkeys[hotkey_id]

        logger.info(f"已注销快捷键: {name}")
        return True

    def _start_health_check(self):
        """启动健康检查任务."""
        if self._loop:
            self._health_check_task = asyncio.run_coroutine_threadsafe(
                self._health_check_loop(), self._loop
            )

    async def _health_check_loop(self):
        """健康检查循环."""
        while self._running:
            await asyncio.sleep(self._check_interval)

            if not self._running:
                break

            # 检查 event tap 是否仍然有效
            if self._tap and not Quartz.CGEventTapIsEnabled(self._tap):
                logger.warning("Event Tap 已被禁用，尝试重新启用...")
                try:
                    Quartz.CGEventTapEnable(self._tap, True)
                    logger.info("Event Tap 重新启用成功")
                except Exception as e:
                    logger.error(f"重新启用 Event Tap 失败: {e}")
                    # 尝试完全重建
                    try:
                        await self.stop()
                        await self.start()
                        # 重新注册所有快捷键
                        for name, config in list(self._shortcuts.items()):
                            callback = self._callbacks.get(name)
                            if callback:
                                self.register(name, config, callback)
                        logger.info("Event Tap 重建成功")
                    except Exception as rebuild_error:
                        logger.error(f"重建 Event Tap 失败: {rebuild_error}")
