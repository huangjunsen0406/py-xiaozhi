"""按 mode 创建界面实现（返回 ViewPort）."""

import sys
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.task_manager import TaskManager
    from src.ui.shared.viewport import ViewPort
    from src.utils.config_manager import ConfigManager

logger = get_logger()


def create_viewport(
    mode: str,
    event_bus: "EventBus",
    task_manager: Optional["TaskManager"] = None,
    config_manager: Optional["ConfigManager"] = None,
    runtime_tool_names: Callable[[], tuple[str, ...]] | None = None,
) -> "ViewPort":
    """gui / cli / tui / gpio；gpio 仅 Linux，其它平台回退 cli."""
    normalized = (mode or "cli").lower()

    if normalized == "gui":
        from src.ui.gui import GuiViewManager

        logger.debug("create_viewport: gui")
        return GuiViewManager(
            event_bus=event_bus,
            task_manager=task_manager,
            config_manager=config_manager,
            runtime_tool_names=runtime_tool_names,
        )

    if normalized == "tui":
        from src.ui.tui import TuiViewManager

        logger.info("create_viewport: tui")
        return TuiViewManager(
            event_bus=event_bus,
            task_manager=task_manager,
            config_manager=config_manager,
            runtime_tool_names=runtime_tool_names,
        )

    if normalized == "gpio":
        if sys.platform != "linux":
            logger.warning(f"GPIO 仅支持 Linux（当前 {sys.platform}），回退到 cli 界面")
        else:
            from src.ui.gpio import GpioViewManager

            logger.info("create_viewport: gpio")
            return GpioViewManager(event_bus=event_bus, task_manager=task_manager)

    elif normalized != "cli":
        logger.warning(f"未知 UI 模式 {mode!r}，回退 cli")

    from src.ui.cli import CliViewManager

    logger.info("create_viewport: cli")
    return CliViewManager(event_bus=event_bus, task_manager=task_manager)
