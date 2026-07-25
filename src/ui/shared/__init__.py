"""UI 共用：ViewPort 契约、工厂、激活基类、跨端事件 DTO.

Qt ViewModel 在 src.ui.gui.models（仅 GUI 使用）。
"""

from src.ui.shared.activation import BaseActivation
from src.ui.shared.events import UISendTextRequest
from src.ui.shared.factory import create_viewport
from src.ui.shared.viewport import ViewPort

__all__ = [
    "BaseActivation",
    "UISendTextRequest",
    "ViewPort",
    "create_viewport",
]
