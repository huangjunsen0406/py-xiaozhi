# -*- coding: utf-8 -*-
"""ViewModel 基类."""

from PySide6.QtCore import QObject, Signal


class BaseModel(QObject):
    """ViewModel 基类 - 提供通用错误信号."""

    errorOccurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._error = ""

    def set_error(self, message: str):
        self._error = message
        if message:
            self.errorOccurred.emit(message)
