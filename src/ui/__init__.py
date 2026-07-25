"""UI 模块：gui / cli / gpio 三种界面.

按需导入，避免跨模式依赖：
    from src.ui.gui import GuiViewManager
    from src.ui.cli import CliViewManager
    from src.ui.gpio import GpioViewManager  # 仅 Linux
    from src.ui.shared import ViewPort, create_viewport
"""

__all__ = []
