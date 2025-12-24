"""音频缓冲队列.

线程安全的播放队列
"""

import asyncio
from typing import Optional

import numpy as np

from src.logging import get_logger

logger = get_logger()


class AudioBuffer:
    """线程安全的音频缓冲队列

    使用 asyncio.Queue 实现的缓冲队列，支持替换策略。
    """

    def __init__(self, maxsize: int = 500):
        """初始化缓冲队列

        Args:
            maxsize: 队列最大容量
        """
        self._queue = asyncio.Queue(maxsize=maxsize)
        self._maxsize = maxsize

    def put_nowait(self, data: np.ndarray) -> bool:
        """非阻塞放入

        Args:
            data: float32 音频数据

        Returns:
            bool: 是否成功
        """
        try:
            self._queue.put_nowait(data)
            return True
        except asyncio.QueueFull:
            return False

    async def put(
        self, data: np.ndarray, replace_oldest: bool = False, timeout: float = 2.0
    ) -> bool:
        """放入音频数据

        Args:
            data: float32 音频数据
            replace_oldest: 队列满时是否替换最旧数据
            timeout: 超时时间（秒）

        Returns:
            bool: 是否成功
        """
        if replace_oldest and self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            if self._queue.full() and not replace_oldest:
                await asyncio.wait_for(self._queue.put(data), timeout=timeout)
            else:
                self._queue.put_nowait(data)
            return True
        except asyncio.TimeoutError:
            logger.warning("播放队列阻塞超时")
            return False
        except asyncio.QueueFull:
            return False

    def get_nowait(self) -> Optional[np.ndarray]:
        """非阻塞获取

        Returns:
            Optional[np.ndarray]: 音频数据，或 None
        """
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    def clear_sync(self) -> int:
        """同步清空队列（用于析构函数）

        Returns:
            int: 清除的帧数
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    async def clear(self) -> int:
        """异步清空队列，返回清除的帧数

        Returns:
            int: 清除的帧数
        """
        return self.clear_sync()

    def qsize(self) -> int:
        """队列大小

        Returns:
            int: 当前队列中的元素数量
        """
        return self._queue.qsize()

    def empty(self) -> bool:
        """是否为空

        Returns:
            bool: 队列是否为空
        """
        return self._queue.empty()

    def full(self) -> bool:
        """是否满了

        Returns:
            bool: 队列是否已满
        """
        return self._queue.full()
