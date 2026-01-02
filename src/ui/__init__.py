"""UI 模块.

提供 GUI、CLI 和 GPIO 三种用户界面实现。

注意：不在顶层导入具体模块，避免跨模式依赖问题。
使用时按需从子模块导入：
    - GUI:  from src.ui.gui import ViewManager
    - CLI:  from src.ui.cli import CLIViewManager
    - GPIO: from src.ui.gpio import GPIOViewManager  # 仅 Linux
"""

__all__ = []

