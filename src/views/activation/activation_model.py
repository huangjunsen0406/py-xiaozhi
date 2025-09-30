# -*- coding: utf-8 -*-
"""
激活窗口数据模型 - 用于QML数据绑定
"""

from PyQt5.QtCore import QObject, pyqtProperty, pyqtSignal


class ActivationModel(QObject):
    """
    激活窗口的数据模型，用于Python和QML之间的数据绑定.
    """

    # 属性变化信号
    serialNumberChanged = pyqtSignal()
    macAddressChanged = pyqtSignal()
    activationStatusChanged = pyqtSignal()
    activationCodeChanged = pyqtSignal()
    statusColorChanged = pyqtSignal()

    # 用户操作信号
    copyCodeClicked = pyqtSignal()
    retryClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # 私有属性
        self._serial_number = "--"
        self._mac_address = "--"
        self._activation_status = "检查中..."
        self._activation_code = "--"
        self._status_color = "#6c757d"

    # 序列号属性
    @pyqtProperty(str, notify=serialNumberChanged)
    def serialNumber(self):
        return self._serial_number

    @serialNumber.setter
    def serialNumber(self, value):
        if self._serial_number != value:
            self._serial_number = value
            self.serialNumberChanged.emit()

    # MAC地址属性
    @pyqtProperty(str, notify=macAddressChanged)
    def macAddress(self):
        return self._mac_address

    @macAddress.setter
    def macAddress(self, value):
        if self._mac_address != value:
            self._mac_address = value
            self.macAddressChanged.emit()

    # 激活状态属性
    @pyqtProperty(str, notify=activationStatusChanged)
    def activationStatus(self):
        return self._activation_status

    @activationStatus.setter
    def activationStatus(self, value):
        if self._activation_status != value:
            self._activation_status = value
            self.activationStatusChanged.emit()

    # 激活码属性
    @pyqtProperty(str, notify=activationCodeChanged)
    def activationCode(self):
        return self._activation_code

    @activationCode.setter
    def activationCode(self, value):
        if self._activation_code != value:
            self._activation_code = value
            self.activationCodeChanged.emit()

    # 状态颜色属性
    @pyqtProperty(str, notify=statusColorChanged)
    def statusColor(self):
        return self._status_color

    @statusColor.setter
    def statusColor(self, value):
        if self._status_color != value:
            self._status_color = value
            self.statusColorChanged.emit()

    # 便捷方法
    def update_device_info(self, serial_number=None, mac_address=None):
        """
        更新设备信息.
        """
        if serial_number is not None:
            self.serialNumber = serial_number
        if mac_address is not None:
            self.macAddress = mac_address

    def update_activation_status(self, status, color="#6c757d"):
        """
        更新激活状态.
        """
        self.activationStatus = status
        self.statusColor = color

    def update_activation_code(self, code):
        """
        更新激活码.
        """
        self.activationCode = code

    def reset_activation_code(self):
        """
        重置激活码.
        """
        self.activationCode = "--"

    def set_status_activated(self):
        """
        设置为已激活状态.
        """
        self.update_activation_status("已激活", "#28a745")
        self.reset_activation_code()

    def set_status_not_activated(self):
        """
        设置为未激活状态.
        """
        self.update_activation_status("未激活", "#dc3545")

    def set_status_inconsistent(self, local_activated=False, server_activated=False):
        """
        设置状态不一致.
        """
        if local_activated and not server_activated:
            self.update_activation_status("状态不一致(需重新激活)", "#ff9900")
        else:
            self.update_activation_status("状态不一致(已修复)", "#28a745")
