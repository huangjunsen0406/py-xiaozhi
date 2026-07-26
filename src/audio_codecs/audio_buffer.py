"""采样级 PCM 缓冲.

输出回调混音使用的线程安全 FIFO
"""

import threading
from collections import deque

import numpy as np


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
