# -*- coding: utf-8 -*-
"""激活窗口 ViewModel."""

from PySide6.QtCore import Property, Qt, Signal, Slot

from src.i18n import off_locale_changed, on_locale_changed, t
from src.ui.gui.models.base_model import BaseModel


class ActivationModel(BaseModel):
    """激活窗口数据模型 - 管理激活界面状态和数据绑定."""

    # 属性变化信号
    serialNumberChanged = Signal()
    macAddressChanged = Signal()
    activationCodeChanged = Signal()
    activationStatusChanged = Signal()
    statusColorChanged = Signal()
    isActivatedChanged = Signal()
    isActivatingChanged = Signal()
    _localeChangeRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._closed = False
        self._serial_number = "--"
        self._mac_address = "--"
        self._activation_code = "------"
        self._status_key: str | None = "activation.status.not_activated"
        self._activation_status = t(self._status_key)
        self._status_color = "#F53F3F"  # error color
        self._is_activated = False
        self._is_activating = False
        self._localeChangeRequested.connect(
            self._on_locale_changed_ui, Qt.ConnectionType.QueuedConnection
        )
        on_locale_changed(self._on_locale_changed)

    def _on_locale_changed(self, locale_code: str) -> None:
        if self._closed:
            return
        try:
            self._localeChangeRequested.emit(locale_code)
        except RuntimeError:
            pass

    @Slot(str)
    def _on_locale_changed_ui(self, _locale_code: str) -> None:
        if self._closed or not self._status_key:
            return
        text = t(self._status_key)
        if self._activation_status != text:
            self._activation_status = text
            self.activationStatusChanged.emit()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            off_locale_changed(self._on_locale_changed)

    # ========== Properties ==========

    @Property(str, notify=serialNumberChanged)
    def serialNumber(self) -> str:
        return self._serial_number

    @Property(str, notify=macAddressChanged)
    def macAddress(self) -> str:
        return self._mac_address

    @Property(str, notify=activationCodeChanged)
    def activationCode(self) -> str:
        return self._activation_code

    @Property(str, notify=activationStatusChanged)
    def activationStatus(self) -> str:
        return self._activation_status

    @Property(str, notify=statusColorChanged)
    def statusColor(self) -> str:
        return self._status_color

    @Property(bool, notify=isActivatedChanged)
    def isActivated(self) -> bool:
        return self._is_activated

    @Property(bool, notify=isActivatingChanged)
    def isActivating(self) -> bool:
        return self._is_activating

    # ========== Setters ==========

    def set_serial_number(self, value: str):
        if self._serial_number != value:
            self._serial_number = value or "--"
            self.serialNumberChanged.emit()

    def set_mac_address(self, value: str):
        if self._mac_address != value:
            self._mac_address = value or "--"
            self.macAddressChanged.emit()

    def set_activation_code(self, code: str):
        if self._activation_code != code:
            self._activation_code = code or "------"
            self.activationCodeChanged.emit()

    def set_activation_status(
        self, status: str, color: str = None, *, status_key: str | None = None
    ):
        self._status_key = status_key
        if self._activation_status != status:
            self._activation_status = status
            self.activationStatusChanged.emit()
        if color and self._status_color != color:
            self._status_color = color
            self.statusColorChanged.emit()

    def set_activated(self, value: bool):
        if self._is_activated != value:
            self._is_activated = value
            self.isActivatedChanged.emit()

    def set_activating(self, value: bool):
        if self._is_activating != value:
            self._is_activating = value
            self.isActivatingChanged.emit()

    # ========== 便捷方法 ==========

    def update_device_info(self, serial_number: str = None, mac_address: str = None):
        """更新设备信息."""
        if serial_number is not None:
            self.set_serial_number(serial_number)
        if mac_address is not None:
            self.set_mac_address(mac_address)

    def update_activation_code(self, code: str):
        """更新激活码."""
        self.set_activation_code(code)
        if code and code != "------":
            key = "activation.status.activating"
            self.set_activation_status(t(key), "#FF7D00", status_key=key)
            self.set_activating(True)

    def set_status_activated(self):
        """设置为已激活状态."""
        key = "activation.status.activated"
        self.set_activation_status(t(key), "#00B42A", status_key=key)
        self.set_activated(True)
        self.set_activating(False)
        self.set_activation_code("------")

    def set_status_not_activated(self):
        """设置为未激活状态."""
        key = "activation.status.not_activated"
        self.set_activation_status(t(key), "#F53F3F", status_key=key)
        self.set_activated(False)
        self.set_activating(False)

    def set_status_inconsistent(
        self, local_activated: bool = False, server_activated: bool = False
    ):
        """设置状态不一致."""
        if local_activated and not server_activated:
            key = "activation.status.need_reactivate"
            self.set_activation_status(t(key), "#FF7D00", status_key=key)
        else:
            key = "activation.status.auto_fixed"
            self.set_activation_status(t(key), "#00B42A", status_key=key)
