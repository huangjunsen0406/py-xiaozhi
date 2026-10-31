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
    """创建 gui、tui 或 gpio 界面；GPIO 仅 Linux，其它情况回退 TUI。"""
    normalized = (mode or "tui").lower()

    if normalized == "gui":
        from src.ui.gui import GuiViewManager

        logger.debug("create_viewport: gui")
        return GuiViewManager(
            event_bus=event_bus,
            task_manager=task_manager,
            config_manager=config_manager,
            runtime_tool_names=runtime_tool_names,
        )

    if normalized == "gpio" and sys.platform == "linux":
        from src.ui.gpio import GpioViewManager

        logger.info("create_viewport: gpio")
        return GpioViewManager(event_bus=event_bus, task_manager=task_manager)

    if normalized == "gpio":
        logger.warning(f"GPIO 仅支持 Linux（当前 {sys.platform}），回退到 tui 界面")
    elif normalized != "tui":
        logger.warning(f"未知 UI 模式 {mode!r}，回退 tui")

    from src.ui.tui import TuiViewManager

    logger.info("create_viewport: tui")
    return TuiViewManager(
        event_bus=event_bus,
        task_manager=task_manager,
        config_manager=config_manager,
        runtime_tool_names=runtime_tool_names,
    )
