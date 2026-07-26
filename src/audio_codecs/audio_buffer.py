"""音频缓冲队列.

线程安全的播放队列
"""

import asyncio
import threading
from collections import deque

import numpy as np

from src.logging import get_logger

logger = get_logger()


class PcmFifo:
    """采样级 PCM FIFO（float32 单声道，线程安全）.

    写入端在 asyncio 线程，读取端在音频输出回调线程；
    用于 TTS / 音乐分流后在输出回调中混音。

    - push：超出容量丢最旧（记入 dropped）
    - pull：返回定长块，数据不足补零；完全无数据返回 None
    """

    def __init__(self, max_samples: int):
        self._chunks: deque = deque()
        self._offset = 0  # 首块已消费的样本数
        self._size = 0  # 可读样本总数
        self._max = int(max_samples)
        self._lock = threading.Lock()
        self.dropped = 0

    @property
    def size(self) -> int:
        return self._size

    def push(self, pcm: np.ndarray) -> None:
        """追加 float32 单声道数据；容量超限时丢最旧."""
        if pcm.ndim > 1:
            pcm = pcm.reshape(-1)
        if pcm.dtype != np.float32:
            pcm = pcm.astype(np.float32)
        with self._lock:
            self._chunks.append(pcm)
            self._size += len(pcm)
            while self._size > self._max and self._chunks:
                head = self._chunks[0]
                remain = len(head) - self._offset
                drop = min(remain, self._size - self._max)
                self._offset += drop
                self._size -= drop
                self.dropped += drop
                if self._offset >= len(head):
                    self._chunks.popleft()
                    self._offset = 0

    def pull(self, n: int) -> np.ndarray | None:
        """取 n 个样本；无数据返回 None，不足补零."""
        with self._lock:
            if self._size == 0:
                return None
            out = np.zeros(n, dtype=np.float32)
            filled = 0
            while filled < n and self._chunks:
                head = self._chunks[0]
                avail = len(head) - self._offset
                take = min(avail, n - filled)
                out[filled : filled + take] = head[
                    self._offset : self._offset + take
                ]
                filled += take
                self._offset += take
                self._size -= take
                if self._offset >= len(head):
                    self._chunks.popleft()
                    self._offset = 0
            return out

    def clear(self) -> int:
        """清空，返回丢弃的样本数."""
        with self._lock:
            count = self._size
            self._chunks.clear()
            self._offset = 0
            self._size = 0
            return count


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

    def get_nowait(self) -> np.ndarray | None:
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
