"""日志处理器模块.

提供：
- 双重轮转文件处理器（时间 + 大小）
- 异步日志处理器
"""

import atexit
import gzip
import logging
import queue
import re
import shutil
import threading
import time
from logging.handlers import BaseRotatingHandler, QueueHandler, QueueListener
from pathlib import Path


class TimeSizeRotatingFileHandler(BaseRotatingHandler):
    """双重轮转文件处理器.

    同时支持按时间和按大小轮转，先触发任一条件即执行轮转。
    """

    def __init__(
        self,
        filename: str | Path,
        when: str = "midnight",
        interval: int = 1,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 30,
        encoding: str = "utf-8",
        delay: bool = False,
        compress: bool = False,
    ) -> None:
        self.baseFilename = str(filename)
        self.when = when.upper()
        self.interval = interval
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.compress = compress

        # 时间轮转计算
        self._compute_rollover_time()

        # 初始化父类
        super().__init__(self.baseFilename, "a", encoding=encoding, delay=delay)

    def _compute_rollover_time(self) -> None:
        """
        计算下次轮转时间.
        """
        current_time = int(time.time())

        if self.when == "MIDNIGHT":
            # 计算到午夜的秒数
            t = time.localtime(current_time)
            current_hour = t.tm_hour
            current_minute = t.tm_min
            current_second = t.tm_sec
            seconds_to_midnight = (
                (24 - current_hour - 1) * 3600
                + (60 - current_minute - 1) * 60
                + (60 - current_second)
            )
            self.rollover_at = current_time + seconds_to_midnight
            self.suffix = "%Y-%m-%d"
        elif self.when == "H":
            self.rollover_at = current_time + 3600 * self.interval
            self.suffix = "%Y-%m-%d_%H"
        elif self.when == "D":
            self.rollover_at = current_time + 86400 * self.interval
            self.suffix = "%Y-%m-%d"
        else:
            self.rollover_at = current_time + 86400
            self.suffix = "%Y-%m-%d"

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """
        检查是否需要轮转.
        """
        # 检查时间
        if time.time() >= self.rollover_at:
            return True

        # 检查大小
        if self.max_bytes > 0:
            if self.stream is None:
                self.stream = self._open()
            try:
                self.stream.seek(0, 2)  # 移动到文件末尾
                if self.stream.tell() + len(self.format(record)) >= self.max_bytes:
                    return True
            except (OSError, ValueError):
                pass

        return False

    def doRollover(self) -> None:
        """
        执行轮转.
        """
        if self.stream:
            self.stream.close()
            self.stream = None

        # 生成轮转文件名
        current_time = time.time()
        time_suffix = time.strftime(self.suffix, time.localtime(current_time))

        # 检查是否是大小触发的轮转（同一天可能多次）
        base_path = Path(self.baseFilename)
        base_name = base_path.stem
        base_ext = base_path.suffix
        parent = base_path.parent

        # 构建轮转文件名
        rotated_name = f"{base_name}.{time_suffix}"

        # 如果同名文件已存在，添加序号
        counter = 0
        while True:
            if counter == 0:
                dfn = parent / f"{rotated_name}{base_ext}"
            else:
                dfn = parent / f"{rotated_name}.{counter}{base_ext}"

            if self.compress:
                dfn = Path(str(dfn) + ".gz")

            if not dfn.exists():
                break
            counter += 1

        # 执行轮转
        source_path = Path(self.baseFilename)
        if source_path.exists():
            if self.compress:
                self._compress_file(source_path, dfn)
                source_path.unlink()
            else:
                shutil.move(str(source_path), str(dfn))

        # 清理旧文件
        self._cleanup_old_files(parent, base_name)

        # 重新计算下次轮转时间
        self._compute_rollover_time()

        # 重新打开文件
        if not self.delay:
            self.stream = self._open()

    def _compress_file(self, source: Path, dest: Path) -> None:
        """
        压缩文件.
        """
        with open(source, "rb") as f_in:
            with gzip.open(dest, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

    def _cleanup_old_files(self, directory: Path, base_name: str) -> None:
        """
        清理超出保留数量的旧文件.
        """
        if self.backup_count <= 0:
            return

        base_path = Path(self.baseFilename)
        archive_name = re.compile(
            rf"{re.escape(base_name)}\.\d{{4}}-\d{{2}}-\d{{2}}"
            rf"(?:_\d{{2}})?(?:\.\d+)?{re.escape(base_path.suffix)}(?:\.gz)?"
        )
        log_files = [
            f
            for f in directory.iterdir()
            if f.is_file() and archive_name.fullmatch(f.name)
        ]

        # 按修改时间排序
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 删除超出的文件
        for old_file in log_files[self.backup_count :]:
            try:
                old_file.unlink()
            except OSError:
                pass


class _DrainingQueueListener(QueueListener):
    def enqueue_sentinel(self) -> None:
        # 生产者已停止；等待消费者腾出空间，不能丢失停止信号。
        self.queue.put(self._sentinel)


class AsyncHandler(QueueHandler):
    """异步处理器；拥有传入的 sinks，关闭时排空队列并释放它们。"""

    def __init__(
        self,
        handlers: list[logging.Handler],
        queue_size: int = 10000,
        respect_handler_level: bool = True,
    ) -> None:
        self._log_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        super().__init__(self._log_queue)
        self._accepting = True
        self._close_lock = threading.Lock()
        self.dropped_records = 0
        self._listener = _DrainingQueueListener(
            self._log_queue,
            *handlers,
            respect_handler_level=respect_handler_level,
        )
        self._listener.start()
        atexit.register(self.close)

    def close(self) -> None:
        """停止生产、排空并等待 worker，最后关闭拥有的 sinks；可重复调用。"""
        with self._close_lock:
            if self._closed:
                return
            # 与 emit 串行化，但 join 时不持有日志锁，允许 sink 间接打日志。
            self.acquire()
            try:
                self._accepting = False
            finally:
                self.release()
            self._listener.stop()
            failure = None
            try:
                for handler in self._listener.handlers:
                    try:
                        try:
                            handler.flush()
                        finally:
                            handler.close()
                    except Exception as exc:
                        if failure is None:
                            failure = exc
            finally:
                atexit.unregister(self.close)
                super().close()
            if failure is not None:
                raise failure

    def emit(self, record: logging.LogRecord) -> None:
        """队列满时只计数，禁止重新进入同一个日志队列。"""
        self.acquire()
        try:
            if not self._accepting:
                return
            try:
                prepared = self.prepare(record)
                self.enqueue(prepared)
            except queue.Full:
                self.dropped_records += 1
            except Exception:
                self.handleError(record)
        finally:
            self.release()
