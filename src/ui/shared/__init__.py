"""共享 UI 模块.

包含 GUI 和 CLI 共用的事件、模型等。
"""

from src.ui.shared.events import UIStatusUpdate, UITextUpdate

__all__ = ["UIStatusUpdate", "UITextUpdate"]
