# -*- coding: utf-8 -*-
"""GUI模式设备激活窗口控制器 - PySide6 + QML."""

import asyncio
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.activation import ActivationService
from src.logging import get_logger
from src.ui.shared.models import ActivationModel

logger = get_logger()


class GUIActivation(QObject):
    """GUI激活窗口控制器."""

    # 信号
    activationCompleted = Signal(bool)
    windowClosed = Signal()

    def __init__(self, activation_service: ActivationService, parent=None):
        super().__init__(parent)
        self._activation_service = activation_service
        self._engine: Optional[QQmlApplicationEngine] = None
        self._model = ActivationModel()
        self._is_activated = False
        self._activation_data = None

    async def run(self) -> bool:
        """运行激活流程.

        Returns:
            bool: 激活是否成功
        """
        # 创建 Future 等待激活完成
        loop = asyncio.get_event_loop()
        self._completion_future = loop.create_future()

        # 初始化 UI
        self._setup_ui()

        # 更新设备信息
        self._update_device_info()

        # 显示窗口
        self._show_window()

        # 延迟启动激活流程
        QTimer.singleShot(100, self._start_activation)

        # 等待激活完成
        result = await self._completion_future

        # 清理
        self._cleanup()

        return result

    def _setup_ui(self):
        """设置 UI."""
        self._engine = QQmlApplicationEngine()

        # 注入上下文
        ctx = self._engine.rootContext()
        ctx.setContextProperty("activationModel", self._model)
        ctx.setContextProperty("activationController", self)

        # 加载 QML
        qml_dir = Path(__file__).parent / "qml"
        self._engine.addImportPath(str(qml_dir))

        qml_file = qml_dir / "windows" / "ActivationWindow.qml"
        self._engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self._engine.rootObjects():
            logger.error("GUIActivation: QML 加载失败")
            raise RuntimeError("Failed to load ActivationWindow.qml")

        # 连接窗口关闭信号
        root = self._engine.rootObjects()[0]
        root.closing.connect(self._on_window_closing)

        logger.debug("GUIActivation: UI 初始化完成")

    def _show_window(self):
        """显示窗口."""
        if self._engine and self._engine.rootObjects():
            window = self._engine.rootObjects()[0]
            window.show()
            window.raise_()
            window.requestActivate()

    def _update_device_info(self):
        """更新设备信息."""
        serial = self._activation_service.get_serial_number() or "--"
        mac = self._activation_service.get_mac_address() or "--"
        self._model.update_device_info(serial, mac)

        # 更新状态
        status = self._activation_service.get_activation_status()
        local = status.get("local_activated", False)
        server = status.get("server_activated", False)
        consistent = status.get("status_consistent", True)

        if not consistent:
            self._model.set_status_inconsistent(local, server)
        elif local:
            self._model.set_status_activated()
        else:
            self._model.set_status_not_activated()

    def _start_activation(self):
        """启动激活流程."""
        asyncio.ensure_future(self._run_activation())

    async def _run_activation(self):
        """运行激活流程."""
        try:
            # 获取激活数据
            self._activation_data = self._activation_service.get_activation_data()

            if not self._activation_data:
                logger.error("GUIActivation: 未获取到激活数据")
                self._complete(False)
                return

            # 显示激活码
            code = self._activation_data.get("code", "------")
            self._model.update_activation_code(code)
            logger.info(f"GUIActivation: 激活验证码: {code}")

            # 执行激活
            success = await self._activation_service.activate(self._activation_data)

            if success:
                logger.info("GUIActivation: 激活成功")
                self._model.set_status_activated()
                self._is_activated = True
                # 延迟关闭窗口
                QTimer.singleShot(1500, lambda: self._complete(True))
            else:
                logger.warning("GUIActivation: 激活失败")
                self._model.set_status_not_activated()
                # 不自动完成，让用户可以重试

        except asyncio.CancelledError:
            logger.info("GUIActivation: 激活被取消")
            self._complete(False)
        except Exception as e:
            logger.error(f"GUIActivation: 激活异常: {e}", exc_info=True)
            self._complete(False)

    def _complete(self, success: bool):
        """完成激活流程."""
        if hasattr(self, '_completion_future') and not self._completion_future.done():
            self._completion_future.set_result(success)
        self.activationCompleted.emit(success)

    def _on_window_closing(self):
        """窗口关闭处理."""
        logger.info("GUIActivation: 窗口关闭")
        self.windowClosed.emit()
        if hasattr(self, '_completion_future') and not self._completion_future.done():
            self._completion_future.set_result(self._is_activated)

    def _cleanup(self):
        """清理资源."""
        if self._engine:
            self._engine.deleteLater()
            self._engine = None

    # ========== QML Slots ==========

    @Slot()
    def copyActivationCode(self):
        """复制激活码到剪贴板."""
        if self._activation_data:
            code = self._activation_data.get("code", "")
            if code:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(code)
                logger.info(f"GUIActivation: 已复制激活码: {code}")

    @Slot()
    def openActivationUrl(self):
        """打开激活页面."""
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            from src.utils.config_manager import ConfigManager

            config = ConfigManager.get_instance()
            url = config.get_config("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")
            if url:
                QDesktopServices.openUrl(QUrl(url))
                logger.info(f"GUIActivation: 已打开激活页面: {url}")
            else:
                logger.warning("GUIActivation: 未配置激活 URL")
        except Exception as e:
            logger.error(f"GUIActivation: 打开激活页面失败: {e}")

    @Slot()
    def cancelActivation(self):
        """取消激活."""
        if self._activation_service:
            self._activation_service.cancel_activation()
        self._complete(False)
        self._complete(False)
