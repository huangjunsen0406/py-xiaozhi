"""快捷键后端抽象基类."""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Dict, Optional

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

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop = loop
        self._running = False
        self._shortcuts: Dict[str, ShortcutConfig] = {}
        self._callbacks: Dict[str, Callable] = {}

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
        if name not in self._callbacks:
            return

        callback = self._callbacks[name]
        if self._loop and self._loop.is_running():
            if asyncio.iscoroutinefunction(callback):
                asyncio.run_coroutine_threadsafe(callback(), self._loop)
            else:
                self._loop.call_soon_threadsafe(callback)
        else:
            # 没有事件循环，直接调用
            if asyncio.iscoroutinefunction(callback):
                logger.warning(f"无法调用异步回调 {name}，没有事件循环")
            else:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"快捷键回调 {name} 执行失败: {e}")
