"""快捷键后端抽象基类."""

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from src.logging import get_logger

logger = get_logger()


@dataclass
class ShortcutConfig:
    """快捷键配置."""

    modifier: str  # ctrl, alt, shift, cmd
    key: str  # 按键
    description: str = ""


class ShortcutBackend(ABC):
    """快捷键后端抽象基类.

    定义了所有快捷键后端必须实现的接口。
    """

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self._loop = loop
        self._running = False
        self._shortcuts: dict[str, ShortcutConfig] = {}
        self._callbacks: dict[str, Callable] = {}
        self._commands = None

    def bind_commands(self, commands) -> None:
        """使用应用已有的任务调度入口。"""
        self._commands = commands

    @abstractmethod
    async def start(self) -> bool:
        """启动快捷键监听.

        Returns:
            是否成功启动
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """停止快捷键监听."""
        pass

    @abstractmethod
    def register(self, name: str, config: ShortcutConfig, callback: Callable) -> bool:
        """注册快捷键.

        Args:
            name: 快捷键名称
            config: 快捷键配置
            callback: 回调函数（无参数）

        Returns:
            是否注册成功
        """
        pass

    @abstractmethod
    def unregister(self, name: str) -> bool:
        """注销快捷键.

        Args:
            name: 快捷键名称

        Returns:
            是否注销成功
        """
        pass

    def unregister_all(self) -> None:
        """注销所有快捷键."""
        for name in list(self._shortcuts.keys()):
            self.unregister(name)

    @property
    def is_running(self) -> bool:
        """是否正在运行."""
        return self._running

    def _run_callback(self, name: str) -> None:
        """运行回调函数（线程安全）.

        Args:
            name: 快捷键名称
        """
        callback = self._callbacks.get(name)
        if not self._running or callback is None:
            return

        def invoke():
            if self._running and self._callbacks.get(name) is callback:
                return callback()

        if self._commands:
            self._commands.schedule_command_nowait(invoke)
        elif self._loop and self._loop.is_running():
            if asyncio.iscoroutinefunction(callback):
                logger.warning(f"无法调用异步回调 {name}，没有任务调度器")
            else:
                self._loop.call_soon_threadsafe(invoke)
        elif not asyncio.iscoroutinefunction(callback):
            try:
                invoke()
            except Exception as e:
                logger.error(f"快捷键回调 {name} 执行失败: {e}", exc_info=True)
