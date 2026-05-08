"""资源池.

统一的资源注册与释放机制。所有需要清理的资源（C扩展、音频流、网络连接等）
注册到池中，shutdown 时按注册的逆序统一释放，避免重复释放和遗漏。
"""

import asyncio
from typing import Awaitable, Callable, Union

from src.logging import get_logger

logger = get_logger()

CleanupFunc = Callable[[], Union[None, Awaitable[None]]]


class ResourcePool:
    """资源池 — 注册清理函数，逆序统一释放.

    用法:
        pool = ResourcePool()
        pool.register("opus_codec", opus_codec.close)
        pool.register("audio_stream", stream_manager.stop)
        await pool.shutdown()  # 逆序执行所有清理函数
    """

    def __init__(self):
        self._resources: list[tuple[str, CleanupFunc]] = []
        self._shutting_down = False

    def register(self, name: str, cleanup: CleanupFunc) -> None:
        """注册一个清理函数.

        Args:
            name: 资源名称（用于日志和排查）
            cleanup: 清理函数，可以是普通函数或 async 函数
        """
        if self._shutting_down:
            logger.warning(f"资源池正在关闭，跳过注册: {name}")
            return
        self._resources.append((name, cleanup))

    async def shutdown(self) -> None:
        """释放所有已注册的资源，按注册顺序的逆序执行."""
        if self._shutting_down:
            return
        self._shutting_down = True

        for name, cleanup in reversed(self._resources):
            try:
                result = cleanup()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"释放资源失败 [{name}]: {e}")

        self._resources.clear()
        logger.debug(f"资源池已清空")
