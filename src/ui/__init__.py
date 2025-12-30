"""UI 模块.

提供 GUI 和 CLI 两种用户界面实现。

注意：不在顶层导入 GUI 模块，避免 CLI 模式强制依赖 PySide6。
使用时按需从子模块导入：
    - GUI: from src.ui.gui import ViewManager
    - CLI: from src.ui.cli import CLIViewManager
"""

__all__ = []
