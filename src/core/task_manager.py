"""任务管理器.

统一管理异步任务的创建、追踪和清理。
"""

import asyncio
from typing import Any, Awaitable, Callable, Optional

from src.logging import get_logger

logger = get_logger()


class TaskManager:
    """异步任务管理器.

    职责:
    - 创建和追踪异步任务
    - 关闭时统一取消所有任务
    - 提供线程安全的任务调度

    用法:
        tm = TaskManager()
        tm.set_loop(asyncio.get_running_loop())

        # 创建任务
        task = tm.spawn(some_coroutine(), "task_name")

        # 线程安全调度
        tm.schedule_nowait(some_function, arg1, arg2)

        # 关闭时清理
        await tm.cancel_all()
    """

    def __init__(self):
        self._tasks: set[asyncio.Task] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self._running: bool = False

    def initialize(self, loop: asyncio.AbstractEventLoop = None) -> None:
        """初始化任务管理器.

        Args:
            loop: 事件循环，为 None 时使用当前运行的循环
        """
        self._loop = loop or asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()
        self._running = True
        logger.debug("TaskManager 已初始化")

    @property
    def loop(self) -> Optional[asyncio.AbstractEventLoop]:
        """
        获取事件循环.
        """
        return self._loop

    @property
    def running(self) -> bool:
        """
        是否正在运行.
        """
        return self._running

    @property
    def shutdown_event(self) -> Optional[asyncio.Event]:
        """
        获取关闭事件.
        """
        return self._shutdown_event

    def spawn(self, coro: Awaitable[Any], name: str) -> Optional[asyncio.Task]:
        """创建异步任务并追踪.

        Args:
            coro: 协程对象
            name: 任务名称

        Returns:
            创建的任务对象，如果应用正在关闭则返回 None
        """
        # 检查是否正在关闭
        if not self._running or (
            self._shutdown_event and self._shutdown_event.is_set()
        ):
            logger.debug(f"跳过任务创建（应用正在关闭）: {name}")
            return None

        task = asyncio.create_task(coro, name=name)
        self._tasks.add(task)

        def _on_done(t: asyncio.Task):
            self._tasks.discard(t)
            if not t.cancelled():
                exc = t.exception()
                if exc:
                    logger.error(f"任务 {name} 异常结束: {exc}", exc_info=True)

        task.add_done_callback(_on_done)
        return task

    def schedule_nowait(self, fn: Callable, *args, **kwargs) -> None:
        """线程安全地调度可调用对象.

        如果可调用对象返回协程，会自动创建任务。

        Args:
            fn: 可调用对象
            *args: 位置参数
            **kwargs: 关键字参数
        """
        # 检查是否正在关闭 - 静默拒绝
        if not self._running or (
            self._shutdown_event and self._shutdown_event.is_set()
        ):
            return

        if not self._loop or self._loop.is_closed():
            # 关闭时静默跳过，不打印警告
            return

        def _runner():
            try:
                result = fn(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    self.spawn(
                        result, name=f"scheduled:{getattr(fn, '__name__', 'anon')}"
                    )
            except Exception as e:
                logger.error(f"调度的可调用执行失败: {e}", exc_info=True)

        self._loop.call_soon_threadsafe(_runner)

    async def wait_shutdown(self) -> None:
        """
        等待关闭信号.
        """
        if self._shutdown_event:
            await self._shutdown_event.wait()

    def request_shutdown(self) -> None:
        """
        请求关闭.
        """
        if self._shutdown_event and not self._shutdown_event.is_set():
            self._shutdown_event.set()
            logger.info("收到关闭请求")

    async def cancel_all(self) -> None:
        """取消所有追踪的任务.

        会等待所有任务完成或取消。
        """
        self._running = False

        if self._shutdown_event:
            self._shutdown_event.set()

        if not self._tasks:
            return

        logger.info(f"正在取消 {len(self._tasks)} 个任务...")

        # 取消所有任务
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

        # 等待所有任务完成
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()

        logger.info("所有任务已取消")

    def task_count(self) -> int:
        """
        获取当前任务数量.
        """
        return len(self._tasks)

    def get_task_names(self) -> list[str]:
        """
        获取所有任务名称.
        """
        return [t.get_name() for t in self._tasks if not t.done()]
