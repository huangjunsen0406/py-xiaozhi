"""日志处理器模块.

提供：
- 双重轮转文件处理器（时间 + 大小）
- 异步日志处理器
"""

import atexit
import gzip
import logging
import queue
import shutil
import time
from logging.handlers import BaseRotatingHandler, QueueHandler, QueueListener
from pathlib import Path
from typing import Union


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
        except Exception as e:
            logging.getLogger(__name__).debug(f"停止日志监听器失败: {e}")
        super().close()

    def emit(self, record: logging.LogRecord) -> None:
        """
        发送日志记录到队列.
        """
        try:
            self.enqueue(record)
        except queue.Full:
            logging.getLogger(__name__).debug("日志队列已满，丢弃一条日志")


