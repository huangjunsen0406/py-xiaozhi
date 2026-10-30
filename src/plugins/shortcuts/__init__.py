"""快捷键插件模块.

提供跨平台的全局快捷键支持：
- macOS: 使用 Quartz Event Tap (PyObjC)
- Linux/Windows: 使用 pynput
"""

import asyncio
import sys
from typing import TYPE_CHECKING

from src.constants.constants import AbortReason
from src.logging import get_logger
from src.plugins.base import Plugin

from .base import ShortcutBackend, ShortcutConfig

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()

__all__ = ["ShortcutBackend", "ShortcutConfig", "ShortcutsPlugin", "create_backend"]


def create_backend(
    loop: asyncio.AbstractEventLoop | None = None,
) -> ShortcutBackend | None:
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
            logger.warning(f"无法加载 macOS 后端: {e}", exc_info=True)
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
            logger.error(f"无法加载 pynput 后端: {e}", exc_info=True)
            return None


class ShortcutsPlugin(Plugin):
    """快捷键插件."""

    name = "shortcuts"

    # 快捷键名称常量
    MANUAL_PRESS = "MANUAL_PRESS"
    AUTO_TOGGLE = "AUTO_TOGGLE"
    ABORT = "ABORT"
    MODE_TOGGLE = "MODE_TOGGLE"
    WINDOW_TOGGLE = "WINDOW_TOGGLE"

    def __init__(self) -> None:
        super().__init__()
        self._backend: ShortcutBackend | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._event_bus = None
        self._config = None
        self._shortcuts_config: dict = {}
        self._enabled = True
        self._active = False
        self._generation = 0
        self._lifecycle_lock = asyncio.Lock()

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self._config = ctx.get_config()
        self._loop = asyncio.get_running_loop()
        self._event_bus = ctx.event_bus

        # 加载配置
        self._load_config()

        # 创建后端
        self._backend = create_backend(self._loop)
        if self._backend:
            self._backend.bind_commands(cmd)
        else:
            logger.warning("无法创建快捷键后端，快捷键功能将不可用")

        # 订阅配置变更事件
        from src.core.event_bus import Events

        ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)

    def _load_config(self) -> None:
        """加载快捷键配置."""
        self._shortcuts_config = self._config.get_config("SHORTCUTS", {}) or {}
        self._enabled = bool(self._shortcuts_config.get("ENABLED", True))

    async def _on_config_changed(self, data=None) -> None:
        """配置变更时重新加载并协调监听状态。"""
        if not self._active:
            return
        self._load_config()
        self._generation += 1
        await self._reconcile_backend()

    async def start(self) -> None:
        """启动插件，包括初始禁用时的配置监听。"""
        from src.core.event_bus import Events

        self._active = True
        self._event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)
        self._load_config()
        await self._reconcile_backend()

    async def _reconcile_backend(self) -> None:
        async with self._lifecycle_lock:
            if not self._active or not self._backend:
                return
            self._backend.unregister_all()
            if not self._enabled:
                await self._backend.stop()
                logger.info("快捷键功能已禁用")
                return
            self._register_shortcuts()
            if not self._backend.is_running:
                if not await self._backend.start():
                    logger.error("快捷键后端启动失败")

    def _register_shortcuts(self) -> None:
        """注册所有快捷键。"""
        if not self._backend:
            return

        shortcut_handlers = {
            self.MANUAL_PRESS: self._handle_manual_press,
            self.AUTO_TOGGLE: self._handle_auto_toggle,
            self.ABORT: self._handle_abort,
            self.MODE_TOGGLE: self._handle_mode_toggle,
            self.WINDOW_TOGGLE: self._handle_window_toggle,
        }

        generation = self._generation
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

            async def guarded_handler(
                handler=handler,
                generation=generation,
            ):
                if (
                    self._active
                    and generation == self._generation
                    and self._enabled
                ):
                    await handler()

            self._backend.register(name, config, guarded_handler)

    async def _handle_manual_press(self) -> None:
        """处理手动按键快捷键 - 使用 UI_MANUAL_TOGGLE 事件。"""
        from src.core.event_bus import Events

        await self._event_bus.emit(Events.UI_MANUAL_TOGGLE)

    async def _handle_auto_toggle(self) -> None:
        """处理自动对话切换快捷键。"""
        await self.cmd.start_auto_conversation()

    async def _handle_abort(self) -> None:
        """处理中断快捷键。"""
        await self.cmd.abort_speaking(AbortReason.NONE)

    async def _handle_mode_toggle(self) -> None:
        """处理模式切换快捷键。"""
        from src.core.event_bus import Events

        await self._event_bus.emit(Events.UI_AUTO_TOGGLE)

    async def _handle_window_toggle(self) -> None:
        """处理窗口切换快捷键。"""
        from src.core.event_bus import Events

        await self._event_bus.emit(Events.UI_TOGGLE_WINDOW)

    async def stop(self) -> None:
        """先撤销回调许可和配置订阅，再停止监听。"""
        from src.core.event_bus import Events

        self._active = False
        self._generation += 1
        if self._event_bus:
            self._event_bus.off(Events.CONFIG_CHANGED, self._on_config_changed)
        async with self._lifecycle_lock:
            if self._backend:
                self._backend.unregister_all()
                await self._backend.stop()

    def register_resources(self, pool) -> None:
        if self._backend:
            pool.register("shortcuts.backend", self.stop)

    def reload_from_config(self) -> None:
        """从同步调用入口调度受管的配置协调任务。"""
        if not self._active:
            return
        self._load_config()
        self._generation += 1
        generation = self._generation

        async def reconcile():
            if self._active and generation == self._generation:
                await self._reconcile_backend()

        self.cmd.schedule_command_nowait(reconcile)
