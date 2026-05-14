"""GUI模式设备激活窗口控制器 - PySide6 + QML."""

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.logging import get_logger
from src.ui.shared.activation import BaseActivation
from src.ui.shared.models import ActivationModel

logger = get_logger()


class GUIActivation(QObject, BaseActivation):
    """GUI激活窗口控制器.

    继承 QObject（Qt Signals/Slots）和 BaseActivation（核心流程）。
    """

    activationCompleted = Signal(bool)

    def __init__(self, activation_service, init_result: dict, parent=None):
        QObject.__init__(self, parent)
        BaseActivation.__init__(self, activation_service, init_result)
        self._engine: QQmlApplicationEngine | None = None
        self._model = ActivationModel()
        self._completion_future: asyncio.Future | None = None

    async def run(self) -> bool:
        """运行激活流程."""
        loop = asyncio.get_event_loop()
        self._completion_future = loop.create_future()

        self._setup_ui()
        self._update_device_info()
        self._show_window()

        QTimer.singleShot(100, self._start_activation)
        result = await self._completion_future
        self._cleanup()
        return result

    # ---- 内部方法 ----

    def _setup_ui(self):
        self._engine = QQmlApplicationEngine()
        ctx = self._engine.rootContext()
        ctx.setContextProperty("activationModel", self._model)
        ctx.setContextProperty("activationController", self)

        qml_dir = Path(__file__).parent / "qml"
        self._engine.addImportPath(str(qml_dir))
        qml_file = qml_dir / "windows" / "ActivationWindow.qml"
        self._engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self._engine.rootObjects():
            logger.error("GUIActivation: QML 加载失败")
            raise RuntimeError("Failed to load ActivationWindow.qml")

        root = self._engine.rootObjects()[0]
        root.closing.connect(self._on_window_closing)
        logger.debug("GUIActivation: UI 初始化完成")

    def _show_window(self):
        if self._engine and self._engine.rootObjects():
            window = self._engine.rootObjects()[0]
            window.show()
            window.raise_()
            window.requestActivate()

    def _update_device_info(self):
        serial = self._service.get_serial_number() or "--"
        mac = self._service.get_mac_address() or "--"
        self._model.update_device_info(serial, mac)

        status = self._service.get_activation_status()
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
        asyncio.ensure_future(self._run_activation())

    async def _run_activation(self):
        try:
            await self._core_activate()
        except asyncio.CancelledError:
            logger.info("GUIActivation: 激活被取消")
            self._complete(False)
        except Exception as e:
            logger.error(f"GUIActivation: 激活异常: {e}", exc_info=True)
            self._complete(False)

    # ---- BaseActivation 展示方法 ----

    def _show_code(self, data: dict) -> None:
        code = data.get("code", "------")
        self._model.update_activation_code(code)
        logger.info(f"GUIActivation: 激活验证码: {code}")

    def _show_result(self, success: bool) -> None:
        if success:
            logger.info("GUIActivation: 激活成功")
            self._model.set_status_activated()
            QTimer.singleShot(1500, lambda: self._complete(True))
        else:
            logger.warning("GUIActivation: 激活失败")
            self._model.set_status_not_activated()

    def _show_error(self, msg: str) -> None:
        logger.error(f"GUIActivation: {msg}")
        self._complete(False)

    def _complete(self, success: bool):
        if self._completion_future and not self._completion_future.done():
            self._completion_future.set_result(success)
        self.activationCompleted.emit(success)

    def _on_window_closing(self):
        logger.info("GUIActivation: 窗口关闭")
        if self._completion_future and not self._completion_future.done():
            self._completion_future.set_result(False)

    def _cleanup(self):
        if self._engine:
            self._engine.deleteLater()
            self._engine = None

    # ========== QML Slots ==========

    @Slot()
    def copyActivationCode(self):
        code = self._model.activationCode
        if code and code != "------":
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(code)
            logger.info(f"GUIActivation: 已复制激活码: {code}")

    @Slot()
    def openActivationUrl(self):
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
        if self._service:
            self._service.cancel_activation()
        self._complete(False)
