"""日志处理器模块.

提供多种日志处理器：
- 双重轮转文件处理器（时间 + 大小）
- 异步日志处理器
- 按级别分离的文件处理器
"""

import atexit
import gzip
import logging
import queue
import shutil
import threading
import time
from logging.handlers import BaseRotatingHandler, QueueHandler, QueueListener
from pathlib import Path
from typing import Callable, Union


class TimeSizeRotatingFileHandler(BaseRotatingHandler):
    """双重轮转文件处理器.

    同时支持按时间和按大小轮转，先触发任一条件即执行轮转。
    """

    def __init__(
        self,
        filename: Union[str, Path],
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

        # 查找所有轮转文件
        pattern = f"{base_name}.*"
        log_files = []

        for f in directory.glob(pattern):
            if f.name != Path(self.baseFilename).name:
                log_files.append(f)

        # 按修改时间排序
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 删除超出的文件
        for old_file in log_files[self.backup_count :]:
            try:
                old_file.unlink()
            except OSError:
                pass


class AsyncHandler(QueueHandler):
    """异步日志处理器.

    使用队列将日志写入操作移到后台线程，避免阻塞主线程。
    """

    def __init__(
        self,
        handlers: list[logging.Handler],
        queue_size: int = 10000,
        respect_handler_level: bool = True,
    ) -> None:
        # 创建队列
        self._log_queue: queue.Queue = queue.Queue(maxsize=queue_size)
        super().__init__(self._log_queue)

        # 创建监听器
        self._listener = QueueListener(
            self._log_queue,
            *handlers,
            respect_handler_level=respect_handler_level,
        )
        self._listener.start()

        # 注册退出时的清理
        atexit.register(self.close)

    def close(self) -> None:
        """
        关闭处理器.
        """
        try:
            self._listener.stop()
        except Exception:
            pass
        super().close()

    def emit(self, record: logging.LogRecord) -> None:
        """
        发送日志记录到队列.
        """
        try:
            self.enqueue(record)
        except queue.Full:
            # 队列满时丢弃日志，避免阻塞
            pass


class LevelSeparatedHandler(logging.Handler):
    """按级别分离的处理器.

    将不同级别的日志写入不同的文件。
    """

    def __init__(
        self,
        log_dir: Union[str, Path],
        base_name: str = "app",
        encoding: str = "utf-8",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 30,
    ) -> None:
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.encoding = encoding
        self.max_bytes = max_bytes
        self.backup_count = backup_count

        # 为不同级别创建处理器
        self._handlers: dict[int, logging.Handler] = {}

        # 级别到文件名的映射
        self._level_files = {
            logging.DEBUG: f"{base_name}.debug.log",
            logging.INFO: f"{base_name}.info.log",
            logging.WARNING: f"{base_name}.warning.log",
            logging.ERROR: f"{base_name}.error.log",
            logging.CRITICAL: f"{base_name}.critical.log",
        }

    def _get_handler(self, level: int) -> logging.Handler:
        """
        获取或创建指定级别的处理器.
        """
        if level not in self._handlers:
            filename = self._level_files.get(level, "app.log")
            filepath = self.log_dir / filename

            handler = TimeSizeRotatingFileHandler(
                filepath,
                max_bytes=self.max_bytes,
                backup_count=self.backup_count,
                encoding=self.encoding,
            )
            handler.setLevel(level)
            handler.setFormatter(self.formatter)
            self._handlers[level] = handler

        return self._handlers[level]

    def emit(self, record: logging.LogRecord) -> None:
        """
        发送日志记录到对应级别的处理器.
        """
        try:
            handler = self._get_handler(record.levelno)
            handler.emit(record)
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        """
        关闭所有处理器.
        """
        for handler in self._handlers.values():
            handler.close()
        self._handlers.clear()
        super().close()


class BufferedHandler(logging.Handler):
    """缓冲处理器.

    批量写入日志，减少 I/O 操作次数。
    """

    def __init__(
        self,
        target: logging.Handler,
        capacity: int = 1000,
        flush_interval: float = 5.0,
    ) -> None:
        super().__init__()
        self.target = target
        self.capacity = capacity
        self.flush_interval = flush_interval

        self._buffer: list[logging.LogRecord] = []
        self._lock = threading.Lock()

        # 启动定时刷新线程
        self._shutdown = threading.Event()
        self._flush_thread = threading.Thread(target=self._periodic_flush, daemon=True)
        self._flush_thread.start()

        atexit.register(self.close)

    def emit(self, record: logging.LogRecord) -> None:
        """
        添加日志记录到缓冲区.
        """
        with self._lock:
            self._buffer.append(record)
            if len(self._buffer) >= self.capacity:
                self._flush_buffer()

    def _flush_buffer(self) -> None:
        """
        刷新缓冲区（需要在锁内调用）.
        """
        for record in self._buffer:
            try:
                self.target.emit(record)
            except Exception:
                pass
        self._buffer.clear()

    def _periodic_flush(self) -> None:
        """
        定期刷新缓冲区.
        """
        while not self._shutdown.wait(self.flush_interval):
            with self._lock:
                if self._buffer:
                    self._flush_buffer()

    def flush(self) -> None:
        """
        手动刷新.
        """
        with self._lock:
            self._flush_buffer()
        self.target.flush()

    def close(self) -> None:
        """
        关闭处理器.
        """
        self._shutdown.set()
        self.flush()
        self.target.close()
        super().close()


class CallbackHandler(logging.Handler):
    """回调处理器.

    允许注册回调函数来处理特定级别的日志。
    """

    def __init__(self) -> None:
        super().__init__()
        self._callbacks: dict[int, list[Callable[[logging.LogRecord], None]]] = {}

    def add_callback(
        self, level: int, callback: Callable[[logging.LogRecord], None]
    ) -> None:
        """
        添加回调函数.
        """
        if level not in self._callbacks:
            self._callbacks[level] = []
        self._callbacks[level].append(callback)

    def remove_callback(
        self, level: int, callback: Callable[[logging.LogRecord], None]
    ) -> None:
        """
        移除回调函数.
        """
        if level in self._callbacks:
            try:
                self._callbacks[level].remove(callback)
            except ValueError:
                pass

    def emit(self, record: logging.LogRecord) -> None:
        """
        执行回调函数.
        """
        callbacks = self._callbacks.get(record.levelno, [])
        for callback in callbacks:
            try:
                callback(record)
            except Exception:
                self.handleError(record)
