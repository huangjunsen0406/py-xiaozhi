# -*- coding: utf-8 -*-
"""ViewModel 基类."""

from PySide6.QtCore import QObject, Signal


class BaseModel(QObject):
    """ViewModel 基类 - 提供通用功能."""

    # 通用信号
    loadingChanged = Signal(bool)
    errorOccurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._error = ""

    @property
    def loading(self) -> bool:
        return self._loading

    def set_loading(self, value: bool):
        if self._loading != value:
            self._loading = value
            self.loadingChanged.emit(value)

    def set_error(self, message: str):
        self._error = message
        if message:
            self.errorOccurred.emit(message)
