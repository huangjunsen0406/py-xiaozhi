# -*- coding: utf-8 -*-
"""
基础窗口类 - 所有PyQt窗口的基类
支持异步操作和qasync集成
"""

import asyncio
from typing import Optional

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QWidget

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class BaseWindow(QMainWindow):
    """
    所有窗口的基类，提供异步支持.
    """

    # 定义信号
    window_closed = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger(self.__class__.__name__)

        # 异步任务管理
        self._tasks = set()
        self._shutdown_event = asyncio.Event()

        # 定时器用于定期更新UI（与异步操作配合）
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._on_timer_update)

        # 初始化UI
        self._setup_ui()
        self._setup_connections()
        self._setup_styles()

        self.logger.debug(f"{self.__class__.__name__} 初始化完成")

    def _setup_ui(self):
        """设置UI - 子类重写"""

    def _setup_connections(self):
        """设置信号连接 - 子类重写"""

    def _setup_styles(self):
        """设置样式 - 子类重写"""

    def _on_timer_update(self):
        """定时器更新回调 - 子类重写"""

    def start_update_timer(self, interval_ms: int = 1000):
        """
        启动定时更新.
        """
        self._update_timer.start(interval_ms)
        self.logger.debug(f"启动定时更新，间隔: {interval_ms}ms")

    def stop_update_timer(self):
        """
        停止定时更新.
        """
        self._update_timer.stop()
        self.logger.debug("停止定时更新")

    def create_task(self, coro, name: str = None):
        """
        创建异步任务并管理.
        """
        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)

        def done_callback(t):
            self._tasks.discard(t)
            if not t.cancelled() and t.exception():
                self.logger.error(f"异步任务异常: {t.exception()}", exc_info=True)

        task.add_done_callback(done_callback)
        return task

    async def shutdown_async(self):
        """
        异步关闭窗口.
        """
        self.logger.info("开始异步关闭窗口")

        # 设置关闭事件
        self._shutdown_event.set()

        # 停止定时器
        self.stop_update_timer()

        # 取消所有任务
        for task in self._tasks.copy():
            if not task.done():
                task.cancel()

        # 等待任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self.logger.info("窗口异步关闭完成")

    def closeEvent(self, event):
        """
        窗口关闭事件.
        """
        self.logger.info("窗口关闭事件触发")

        # 设置关闭事件标志
        self._shutdown_event.set()

        # 如果是激活窗口，取消激活流程
        if hasattr(self, "device_activator") and self.device_activator:
            self.device_activator.cancel_activation()
            self.logger.info("已发送激活取消信号")

        # 发射关闭信号
        self.window_closed.emit()

        # 停止定时器
        self.stop_update_timer()

        # 取消所有任务（同步方式）
        for task in self._tasks.copy():
            if not task.done():
                task.cancel()

        # 接受关闭事件
        event.accept()

        self.logger.info("窗口关闭处理完成")

    def update_status(self, message: str):
        """
        更新状态消息.
        """
        self.status_updated.emit(message)
        self.logger.debug(f"状态更新: {message}")

    def is_shutdown_requested(self) -> bool:
        """
        检查是否请求关闭.
        """
        return self._shutdown_event.is_set()
