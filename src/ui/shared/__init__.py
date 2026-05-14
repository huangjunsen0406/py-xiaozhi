"""共享 UI 模块.

包含 GUI 和 CLI 共用的事件、模型、激活基类等。
"""

from src.ui.shared.activation import BaseActivation
from src.ui.shared.events import UIStatusUpdate, UITextUpdate

__all__ = ["BaseActivation", "UIStatusUpdate", "UITextUpdate"]
