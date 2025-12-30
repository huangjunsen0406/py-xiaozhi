# -*- coding: utf-8 -*-
"""激活窗口 ViewModel."""

from PySide6.QtCore import Property, Signal, Slot

from .base_model import BaseModel


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._serial_number = "--"
        self._mac_address = "--"
        self._activation_code = "------"
        self._activation_status = "未激活"
        self._status_color = "#F53F3F"  # error color
        self._is_activated = False
        self._is_activating = False

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

    def set_activation_status(self, status: str, color: str = None):
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
            self.set_activation_status("激活中...", "#FF7D00")  # warning color
            self.set_activating(True)

    def set_status_activated(self):
        """设置为已激活状态."""
        self.set_activation_status("已激活", "#00B42A")  # success color
        self.set_activated(True)
        self.set_activating(False)
        self.set_activation_code("------")

    def set_status_not_activated(self):
        """设置为未激活状态."""
        self.set_activation_status("未激活", "#F53F3F")  # error color
        self.set_activated(False)
        self.set_activating(False)

    def set_status_inconsistent(self, local_activated: bool = False, server_activated: bool = False):
        """设置状态不一致."""
        if local_activated and not server_activated:
            self.set_activation_status("需重新激活", "#FF7D00")  # warning color
        else:
            self.set_activation_status("已自动修复", "#00B42A")  # success color

    def set_status_checking(self):
        """设置为检查中状态."""
        self.set_activation_status("检查中...", "#86909C")  # placeholder color
        self.set_activating(True)

    def reset(self):
        """重置状态."""
        self._serial_number = "--"
        self._mac_address = "--"
        self._activation_code = "------"
        self._activation_status = "未激活"
        self._status_color = "#F53F3F"
        self._is_activated = False
        self._is_activating = False
        self.serialNumberChanged.emit()
        self.macAddressChanged.emit()
        self.activationCodeChanged.emit()
        self.activationStatusChanged.emit()
        self.statusColorChanged.emit()
        self.isActivatedChanged.emit()
        self.isActivatingChanged.emit()

    # ========== QML Slots ==========

    @Slot(result=str)
    def getActivationCode(self) -> str:
        """获取激活码（供 QML 调用）."""
        return self._activation_code if self._activation_code != "------" else ""
