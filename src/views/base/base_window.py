# -*- coding: utf-8 -*-
"""
基础窗口类 - 所有PyQt窗口的基类.

支持异步操作、任务管理和qasync集成。
"""

import asyncio
from typing import Callable, Optional, Set

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QWidget

from src.logging import get_logger

logger = get_logger()


class BaseWindow(QMainWindow):
    """
    所有窗口的基类，提供异步支持和任务管理.

    特性:
    - 自动追踪创建的异步任务
    - 任务完成时自动清理
    - 窗口关闭时自动取消任务
    """

    # 定义信号
    window_closed = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.logger = get_logger()

        # 任务管理
        self._managed_tasks: Set[asyncio.Task] = set()
        self._task_cleanup_in_progress = False

        # 关闭事件标志
        self._shutdown_event = asyncio.Event()

        # 定时器用于定期更新UI
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._on_timer_update)

        # 初始化UI
        self._setup_ui()
        self._setup_connections()
        self._setup_styles()

        self.logger.debug(f"{self.__class__.__name__} 初始化完成")

    # ========== 子类重写 ==========

    def _setup_ui(self):
        """设置UI - 子类重写"""

    def _setup_connections(self):
        """设置信号连接 - 子类重写"""

    def _setup_styles(self):
        """设置样式 - 子类重写"""

    def _on_timer_update(self):
        """定时器更新回调 - 子类重写"""

    # ========== 任务管理 ==========

    def create_task(
        self,
        coro,
        *,
        name: Optional[str] = None,
        callback: Optional[Callable] = None,
        error_callback: Optional[Callable] = None,
    ) -> asyncio.Task:
        """
        创建并管理异步任务.

        Args:
            coro: 协程对象
            name: 任务名称（用于调试）
            callback: 任务成功完成时的回调
            error_callback: 任务出错时的回调

        Returns:
            创建的 asyncio.Task 对象
        """
        task = asyncio.create_task(coro, name=name)
        self._managed_tasks.add(task)

        def done_callback(t: asyncio.Task):
            self._managed_tasks.discard(t)

            if t.cancelled():
                self.logger.debug(f"任务已取消: {name or t.get_name()}")
                return

            try:
                result = t.result()
                if callback:
                    callback(result)
            except Exception as e:
                self.logger.error(f"任务执行失败 [{name or t.get_name()}]: {e}")
                if error_callback:
                    try:
                        error_callback(e)
                    except Exception as cb_error:
                        self.logger.error(f"错误回调执行失败: {cb_error}")

        task.add_done_callback(done_callback)
        return task

    async def cancel_all_tasks(self, timeout: float = 2.0):
        """取消所有管理的任务."""
        if self._task_cleanup_in_progress or not self._managed_tasks:
            return

        self._task_cleanup_in_progress = True
        try:
            task_count = len(self._managed_tasks)
            self.logger.info(f"开始取消 {task_count} 个任务")

            for task in self._managed_tasks.copy():
                if not task.done():
                    task.cancel()

            if self._managed_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._managed_tasks, return_exceptions=True),
                        timeout=timeout,
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(f"任务取消超时（{timeout}秒）")

            self._managed_tasks.clear()
            self.logger.info(f"已取消 {task_count} 个任务")
        finally:
            self._task_cleanup_in_progress = False

    def cancel_tasks_sync(self):
        """同步方式取消任务（用于 closeEvent）."""
        if not self._managed_tasks:
            return

        task_count = len(self._managed_tasks)
        for task in self._managed_tasks.copy():
            if not task.done():
                task.cancel()

        self.logger.debug(f"已请求取消 {task_count} 个任务")

    # ========== 定时器 ==========

    def start_update_timer(self, interval_ms: int = 1000):
        """启动定时更新."""
        self._update_timer.start(interval_ms)

    def stop_update_timer(self):
        """停止定时更新."""
        self._update_timer.stop()

    # ========== 窗口生命周期 ==========

    async def shutdown_async(self):
        """异步关闭窗口."""
        self.logger.info("开始异步关闭窗口")
        self._shutdown_event.set()
        self.stop_update_timer()
        await self.cancel_all_tasks()
        self.logger.info("窗口异步关闭完成")

    def closeEvent(self, event):
        """窗口关闭事件."""
        self.logger.info("窗口关闭事件触发")
        self._shutdown_event.set()
        self.window_closed.emit()
        self.stop_update_timer()
        self.cancel_tasks_sync()
        event.accept()

    def update_status(self, message: str):
        """更新状态消息."""
        self.status_updated.emit(message)

    def is_shutdown_requested(self) -> bool:
        """检查是否请求关闭."""
        return self._shutdown_event.is_set()
