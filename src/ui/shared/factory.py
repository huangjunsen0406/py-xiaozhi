"""按 mode 创建界面实现."""

from typing import TYPE_CHECKING, Optional

from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.task_manager import TaskManager
    from src.ui.shared.viewport import ViewPort

logger = get_logger()


def create_viewport(
    mode: str,
    event_bus: "EventBus",
    task_manager: Optional["TaskManager"] = None,
) -> "ViewPort":
    """gui / cli / gpio；不认识的 mode 按 cli 处理."""
    normalized = (mode or "cli").lower()

    if normalized == "gui":
        from src.ui.gui import ViewManager

        logger.debug("create_viewport: gui")
        return ViewManager(event_bus=event_bus, task_manager=task_manager)

    if normalized == "gpio":
        from src.ui.gpio import GPIOViewManager

        logger.info("create_viewport: gpio")
        return GPIOViewManager(event_bus=event_bus, task_manager=task_manager)

    if normalized != "cli":
        logger.warning(f"未知 UI 模式 {mode!r}，回退 cli")

    from src.ui.cli import CLIViewManager

    logger.info("create_viewport: cli")
    return CLIViewManager(event_bus=event_bus, task_manager=task_manager)
