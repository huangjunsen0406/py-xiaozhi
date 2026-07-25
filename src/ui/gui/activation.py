"""GUI 设备激活窗口：QObject 控制器 + 组合 BaseActivation 流程（无多继承）."""

from __future__ import annotations

import asyncio
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from src.logging import get_logger
from src.ui.gui.models import ActivationModel
from src.ui.shared.activation import BaseActivation

logger = get_logger()


class _ActivationFlow(BaseActivation):
    """纯流程对象：把展示回调接到 GuiActivation 控制器."""

    def __init__(self, controller: "GuiActivation", service, init_result: dict):
        super().__init__(service, init_result)
        self._ui = controller

    def _show_code(self, data: dict) -> None:
        self._ui._show_code(data)

    def _show_result(self, success: bool) -> None:
        self._ui._show_result(success)

    def _show_error(self, msg: str) -> None:
        self._ui._show_error(msg)

    async def run(self) -> bool:
        return await self._core_activate()


class GuiActivation(QObject):
    """GUI 激活窗口控制器（只继承 QObject；流程用组合）."""

    activationCompleted = Signal(bool)

    def __init__(self, activation_service, init_result: dict, parent=None):
        super().__init__(parent)
        self._service = activation_service
        self._flow = _ActivationFlow(self, activation_service, init_result)
        self._engine: QQmlApplicationEngine | None = None
        self._model = ActivationModel()
        self._completion_future: asyncio.Future | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._activation_task: asyncio.Task | None = None

    async def run(self) -> bool:
        loop = asyncio.get_running_loop()
        self._completion_future = loop.create_future()
        self._loop = loop

        self._setup_ui()
        self._update_device_info()
        self._show_window()

        QTimer.singleShot(100, self._start_activation)
        result = await self._completion_future
        self._cleanup()
        return result

    def _setup_ui(self) -> None:
        self._engine = QQmlApplicationEngine()
        ctx = self._engine.rootContext()
        ctx.setContextProperty("activationModel", self._model)
        ctx.setContextProperty("activationController", self)

        qml_dir = Path(__file__).parent / "qml"
        self._engine.addImportPath(str(qml_dir))
        qml_file = qml_dir / "windows" / "ActivationWindow.qml"
        self._engine.load(QUrl.fromLocalFile(str(qml_file)))

        if not self._engine.rootObjects():
            logger.error("GuiActivation: QML 加载失败")
            raise RuntimeError("Failed to load ActivationWindow.qml")

        root = self._engine.rootObjects()[0]
        root.closing.connect(self._on_window_closing)
        logger.debug("GuiActivation: UI 初始化完成")

    def _show_window(self) -> None:
        if self._engine and self._engine.rootObjects():
            window = self._engine.rootObjects()[0]
            window.show()
            window.raise_()
            window.requestActivate()

    def _update_device_info(self) -> None:
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

    def _start_activation(self) -> None:
        try:
            loop = self._loop or asyncio.get_running_loop()
            self._activation_task = loop.create_task(
                self._run_activation(), name="gui:activation"
            )
        except RuntimeError as e:
            logger.error(f"GuiActivation: 无法调度激活协程: {e}", exc_info=True)
            self._complete(False)

    async def _run_activation(self) -> None:
        try:
            await self._flow.run()
        except asyncio.CancelledError:
            logger.info("GuiActivation: 激活被取消")
            self._complete(False)
        except Exception as e:
            logger.error(f"GuiActivation: 激活异常: {e}", exc_info=True)
            self._complete(False)

    def _show_code(self, data: dict) -> None:
        code = data.get("code", "------")
        self._model.update_activation_code(code)
        logger.info(f"GuiActivation: 激活验证码: {code}")

    def _show_result(self, success: bool) -> None:
        if success:
            logger.info("GuiActivation: 激活成功")
            self._model.set_status_activated()
            QTimer.singleShot(1500, lambda: self._complete(True))
        else:
            logger.warning("GuiActivation: 激活失败")
            self._model.set_status_not_activated()

    def _show_error(self, msg: str) -> None:
        logger.error(f"GuiActivation: {msg}")
        self._complete(False)

    def _complete(self, success: bool) -> None:
        if self._completion_future and not self._completion_future.done():
            self._completion_future.set_result(success)
        self.activationCompleted.emit(success)

    def _on_window_closing(self) -> None:
        logger.info("GuiActivation: 窗口关闭")
        if self._completion_future and not self._completion_future.done():
            self._completion_future.set_result(False)

    def _cleanup(self) -> None:
        if self._engine:
            self._engine.deleteLater()
            self._engine = None

    @Slot()
    def copyActivationCode(self):
        code = self._model.activationCode
        if code and code != "------":
            clipboard = QGuiApplication.clipboard()
            clipboard.setText(code)
            logger.info(f"GuiActivation: 已复制激活码: {code}")

    @Slot()
    def openActivationUrl(self):
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices

            from src.utils.config_manager import get_config

            config = get_config()
            url = config.get_config("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")
            if url:
                QDesktopServices.openUrl(QUrl(url))
                logger.info(f"GuiActivation: 已打开激活页面: {url}")
            else:
                logger.warning("GuiActivation: 未配置激活 URL")
        except Exception as e:
            logger.error(f"GuiActivation: 打开激活页面失败: {e}", exc_info=True)

    @Slot()
    def cancelActivation(self):
        if self._service:
            self._service.cancel_activation()
        self._complete(False)
