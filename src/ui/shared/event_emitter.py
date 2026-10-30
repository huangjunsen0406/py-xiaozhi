"""非 Qt 视图共用的线程安全事件提交。"""

import asyncio
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.task_manager import TaskManager

logger = get_logger()


def safe_emit(
    event_bus: "EventBus",
    event: str,
    data: Any = None,
    *,
    task_manager: "TaskManager | None" = None,
    loop: asyncio.AbstractEventLoop | None = None,
    source: str = "View",
) -> None:
    """延迟创建协程，优先交给 TaskManager，缺省时向视图 loop 提交。

    schedule_nowait 正常返回也可能表示关闭期间拒绝；此时不能回退，
    否则会绕过 TaskManager 的生命周期控制。两条路径均支持外部线程。
    """

    def _start_emit():
        if data is None:
            return event_bus.emit(event)
        return event_bus.emit(event, data)

    if task_manager is not None:
        try:
            task_manager.schedule_nowait(_start_emit)
            return
        except Exception as exc:
            logger.error(
                f"{source} 经 TaskManager 调度事件 {event} 失败: {exc}",
                exc_info=True,
            )

    if loop is None or not loop.is_running():
        return

    coro = None
    try:
        coro = _start_emit()
        future = asyncio.run_coroutine_threadsafe(coro, loop)

        def _done(result):
            try:
                exc = result.exception()
            except Exception:
                # Future 取消属于正常退出，不作为事件失败记录。
                return
            if exc is not None:
                logger.error(f"{source} 发射事件 {event} 失败: {exc}", exc_info=exc)

        future.add_done_callback(_done)
    except Exception as exc:
        logger.error(f"{source} 调度事件 {event} 失败: {exc}", exc_info=True)
        if asyncio.iscoroutine(coro):
            coro.close()
