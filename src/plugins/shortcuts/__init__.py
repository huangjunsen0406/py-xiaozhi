"""快捷键插件模块.

提供跨平台的全局快捷键支持：
- macOS: 使用 Quartz Event Tap (PyObjC)
- Linux/Windows: 使用 pynput
"""

import asyncio
import sys
from typing import TYPE_CHECKING, Callable, Dict, Optional

from src.constants.constants import AbortReason
from src.logging import get_logger
from src.plugins.base import Plugin
from src.utils.config_manager import ConfigManager

from .base import ShortcutBackend, ShortcutConfig

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()

__all__ = ["ShortcutBackend", "ShortcutConfig", "ShortcutsPlugin", "create_backend"]


def create_backend(
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> Optional[ShortcutBackend]:
    """创建适合当前平台的快捷键后端.

    Args:
        loop: asyncio 事件循环

    Returns:
        快捷键后端实例，如果无法创建则返回 None
    """
    if sys.platform == "darwin":
        # macOS: 优先使用 Quartz Event Tap
        try:
            from .macos_backend import MacOSShortcutBackend

            logger.info("使用 macOS Quartz Event Tap 后端")
            return MacOSShortcutBackend(loop)
        except ImportError as e:
            logger.warning(f"无法加载 macOS 后端: {e}")
            logger.info("回退到 pynput 后端")
            # 回退到 pynput
            try:
                from .pynput_backend import PynputShortcutBackend

                return PynputShortcutBackend(loop)
            except ImportError as e2:
                logger.error(f"无法加载 pynput 后端: {e2}")
                return None
    else:
        # Linux/Windows: 使用 pynput
        try:
            from .pynput_backend import PynputShortcutBackend

            logger.info("使用 pynput 后端")
            return PynputShortcutBackend(loop)
        except ImportError as e:
            logger.error(f"无法加载 pynput 后端: {e}")
            return None


class _CmdAdapter:
    """快捷键命令适配器."""

    def __init__(self, cmd: "PluginCommands", ctx: "PluginContext"):
        self._cmd = cmd
        self._ctx = ctx

    async def start_listening(self):
        try:
            await self._cmd.connect_protocol()
            from src.constants.constants import ListeningMode

            await self._cmd.start_listening(ListeningMode.MANUAL)
        except Exception as e:
            logger.error(f"开始监听失败: {e}")

    async def stop_listening(self):
        try:
            await self._cmd.stop_listening()
        except Exception as e:
            logger.error(f"停止监听失败: {e}")

    async def toggle_chat_state(self):
        try:
            await self._cmd.connect_protocol()
            from src.constants.constants import ListeningMode

            mode = (
                ListeningMode.REALTIME
                if self._ctx.get_config().get_config("AEC_OPTIONS.ENABLED", True)
                else ListeningMode.AUTO_STOP
            )
            await self._cmd.start_listening(mode)
        except Exception as e:
            logger.error(f"切换对话状态失败: {e}")

    async def abort_speaking(self, reason):
        try:
            await self._cmd.abort_speaking(reason)
        except Exception as e:
            logger.error(f"中断对话失败: {e}")


class ShortcutsPlugin(Plugin):
    """快捷键插件."""

    name = "shortcuts"
    priority = 70  # 最低优先级，依赖 UIPlugin

    # 快捷键名称常量
    MANUAL_PRESS = "MANUAL_PRESS"
    AUTO_TOGGLE = "AUTO_TOGGLE"
    ABORT = "ABORT"
    MODE_TOGGLE = "MODE_TOGGLE"
    WINDOW_TOGGLE = "WINDOW_TOGGLE"

    def __init__(self) -> None:
        super().__init__()
        self._backend: Optional[ShortcutBackend] = None
        self._adapter: Optional[_CmdAdapter] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._event_bus = None
        self._config = ConfigManager.get_instance()
        self._shortcuts_config: Dict = {}
        self._enabled = True
        self._manual_press_active = False

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self._adapter = _CmdAdapter(cmd, ctx)
        self._loop = asyncio.get_running_loop()
        self._event_bus = ctx.event_bus

        # 加载配置
        self._load_config()

        # 创建后端
        self._backend = create_backend(self._loop)
        if not self._backend:
            logger.warning("无法创建快捷键后端，快捷键功能将不可用")

        # 订阅配置变更事件
        from src.core.event_bus import Events

        ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)

    def _load_config(self) -> None:
        """加载快捷键配置."""
        self._shortcuts_config = self._config.get_config("SHORTCUTS", {}) or {}
        self._enabled = bool(self._shortcuts_config.get("ENABLED", True))

    async def _on_config_changed(self, data=None) -> None:
        """配置变更时重新加载."""
        logger.info("ShortcutsPlugin: 收到配置变更事件，重新加载配置")
        await self.reload_from_config()

    async def start(self) -> None:
        """启动插件."""
        if not self._enabled:
            logger.info("快捷键功能已禁用")
            return

        if not self._backend:
            logger.warning("快捷键后端不可用")
            return

        # 注册快捷键
        self._register_shortcuts()

        # 启动后端
        success = await self._backend.start()
        if success:
            logger.info("快捷键插件已启动")
        else:
            logger.error("快捷键后端启动失败")

    def _register_shortcuts(self) -> None:
        """注册所有快捷键."""
        if not self._backend:
            return

        shortcut_handlers = {
            self.MANUAL_PRESS: self._handle_manual_press,
            self.AUTO_TOGGLE: self._handle_auto_toggle,
            self.ABORT: self._handle_abort,
            self.MODE_TOGGLE: self._handle_mode_toggle,
            self.WINDOW_TOGGLE: self._handle_window_toggle,
        }

        for name, handler in shortcut_handlers.items():
            cfg = self._shortcuts_config.get(name, {}) or {}
            modifier = str(cfg.get("modifier", "ctrl")).lower()
            key = str(cfg.get("key", "")).lower()

            if not key:
                continue

            config = ShortcutConfig(
                modifier=modifier,
                key=key,
                description=cfg.get("description", ""),
            )

            self._backend.register(name, config, handler)

    def _handle_manual_press(self) -> None:
        """处理手动按键快捷键."""
        if not self._adapter or not self._loop:
            return

        if not self._manual_press_active:
            self._manual_press_active = True
            asyncio.run_coroutine_threadsafe(
                self._adapter.start_listening(), self._loop
            )
        else:
            self._manual_press_active = False
            asyncio.run_coroutine_threadsafe(
                self._adapter.stop_listening(), self._loop
            )

    def _handle_auto_toggle(self) -> None:
        """处理自动对话切换快捷键."""
        if not self._adapter or not self._loop:
            return

        asyncio.run_coroutine_threadsafe(
            self._adapter.toggle_chat_state(), self._loop
        )

    def _handle_abort(self) -> None:
        """处理中断快捷键."""
        if not self._adapter or not self._loop:
            return

        asyncio.run_coroutine_threadsafe(
            self._adapter.abort_speaking(AbortReason.NONE), self._loop
        )

    def _handle_mode_toggle(self) -> None:
        """处理模式切换快捷键."""
        if not self._event_bus or not self._loop:
            return

        from src.core.event_bus import Events

        asyncio.run_coroutine_threadsafe(
            self._event_bus.emit(Events.UI_TOGGLE_MODE), self._loop
        )

    def _handle_window_toggle(self) -> None:
        """处理窗口切换快捷键."""
        if not self._event_bus or not self._loop:
            return

        from src.core.event_bus import Events

        asyncio.run_coroutine_threadsafe(
            self._event_bus.emit(Events.UI_TOGGLE_WINDOW), self._loop
        )

    async def stop(self) -> None:
        """停止插件."""
        if self._backend:
            await self._backend.stop()

    async def shutdown(self) -> None:
        """关闭插件."""
        if self._backend:
            await self._backend.stop()
            self._backend = None

    async def reload_from_config(self) -> None:
        """从配置重新加载."""
        self._load_config()

        if not self._backend:
            return

        # 注销所有快捷键
        self._backend.unregister_all()

        if self._enabled:
            # 重新注册
            self._register_shortcuts()
            logger.info("快捷键配置已重新加载")
        else:
            logger.info("快捷键功能已禁用")
