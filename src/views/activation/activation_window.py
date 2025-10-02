# -*- coding: utf-8 -*-
"""
设备激活窗口 显示激活流程、设备信息和激活进度.
"""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QPainterPath, QRegion
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.core.system_initializer import SystemInitializer
from src.utils.device_activator import DeviceActivator
from src.utils.logging_config import get_logger

from ..base.async_mixins import AsyncMixin, AsyncSignalEmitter
from ..base.base_window import BaseWindow
from .activation_model import ActivationModel

logger = get_logger(__name__)


class ActivationWindow(BaseWindow, AsyncMixin):
    """
    设备激活窗口.
    """

    # 自定义信号
    activation_completed = pyqtSignal(bool)  # 激活完成信号
    window_closed = pyqtSignal()  # 窗口关闭信号

    def __init__(
        self,
        system_initializer: Optional[SystemInitializer] = None,
        parent: Optional = None,
    ):
        # QML相关 - 必须在super().__init__之前创建
        self.qml_widget = None
        self.activation_model = ActivationModel()

        super().__init__(parent)

        # 组件实例
        self.system_initializer = system_initializer
        self.device_activator: Optional[DeviceActivator] = None

        # 状态管理
        self.current_stage = None
        self.activation_data = None
        self.is_activated = False
        self.initialization_started = False
        self.status_message = ""

        # 异步信号发射器
        self.signal_emitter = AsyncSignalEmitter()
        self._setup_signal_connections()

        # 窗口拖拽相关
        self.drag_position = None

        # 延迟启动初始化（等事件循环运行后）
        self.start_update_timer(100)  # 100ms后开始初始化

    def _setup_ui(self):
        """
        设置UI.
        """
        # 设置无边框窗口
        # 检测显示服务器类型以兼容Wayland
        import os
        is_wayland = os.environ.get('WAYLAND_DISPLAY') or os.environ.get('XDG_SESSION_TYPE') == 'wayland'

        if is_wayland:
            # Wayland环境：不使用WindowStaysOnTopHint（不支持）
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
            self.logger.info("检测到Wayland环境，使用兼容窗口标志")
        else:
            # X11环境：使用完整特性
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.logger.info("检测到X11环境，使用完整窗口标志")

        self.setAttribute(Qt.WA_TranslucentBackground)

        # 创建中央widget
        central_widget = QWidget()
        central_widget.setStyleSheet("background: transparent;")
        self.setCentralWidget(central_widget)

        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建QML widget
        self.qml_widget = QQuickWidget()
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)

        # 仅在X11环境下使用WA_AlwaysStackOnTop（Wayland不支持）
        if not is_wayland:
            self.qml_widget.setAttribute(Qt.WA_AlwaysStackOnTop)

        self.qml_widget.setClearColor(Qt.transparent)

        # 注册数据模型到QML上下文
        qml_context = self.qml_widget.rootContext()
        qml_context.setContextProperty("activationModel", self.activation_model)

        # 加载QML文件
        qml_file = Path(__file__).parent / "activation_window.qml"
        self.qml_widget.setSource(QUrl.fromLocalFile(str(qml_file)))

        # 检查QML是否加载成功
        if self.qml_widget.status() == QQuickWidget.Error:
            self.logger.error("QML加载失败，可能原因：")
            for error in self.qml_widget.errors():
                self.logger.error(f"  - {error.toString()}")

            # 在Wayland环境下，如果QML加载失败，提示用户使用CLI模式
            if is_wayland:
                self.logger.warning("Wayland环境下QML加载失败，建议使用CLI模式激活")
                self.logger.info("使用命令: python main.py --mode cli")

        # 添加到布局
        layout.addWidget(self.qml_widget)

        # 设置自适应尺寸
        self._setup_adaptive_size()

        # 延迟设置连接，确保QML完全加载
        self._setup_qml_connections()

    def _setup_adaptive_size(self):
        """
        设置自适应窗口尺寸.
        """
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_size = screen.size()
        screen_width = screen_size.width()
        screen_height = screen_size.height()

        self.logger.info(f"检测到屏幕分辨率: {screen_width}x{screen_height}")

        # 根据屏幕尺寸选择合适的窗口大小
        if screen_width <= 480 or screen_height <= 320:
            # 极小屏幕 (如3.5寸480x320)
            window_width, window_height = 450, 250
            self.setMinimumSize(QSize(450, 250))
            self._apply_compact_styles()
        elif screen_width <= 800 or screen_height <= 480:
            # 小屏幕 (如7寸800x480)
            window_width, window_height = 480, 280
            self.setMinimumSize(QSize(480, 280))
            self._apply_small_screen_styles()
        elif screen_width <= 1024 or screen_height <= 600:
            # 中等屏幕
            window_width, window_height = 520, 300
            self.setMinimumSize(QSize(520, 300))
        else:
            # 大屏幕 (PC显示器)
            window_width, window_height = 550, 320
            self.setMinimumSize(QSize(550, 320))

        # 确保窗口不超过屏幕尺寸
        max_width = min(window_width, screen_width - 50)
        max_height = min(window_height, screen_height - 50)

        self.resize(max_width, max_height)

        # 居中显示
        self.move((screen_width - max_width) // 2, (screen_height - max_height) // 2)

        self.logger.info(f"设置窗口尺寸: {max_width}x{max_height}")

    def _apply_compact_styles(self):
        """应用紧凑样式 - 适用于极小屏幕"""
        # 调整字体大小
        self.setStyleSheet(
            """
            QLabel { font-size: 10px; }
            QPushButton { font-size: 10px; padding: 4px 8px; }
            QTextEdit { font-size: 8px; }
        """
        )

    def _apply_small_screen_styles(self):
        """
        应用小屏幕样式.
        """
        # 调整字体大小
        self.setStyleSheet(
            """
            QLabel { font-size: 11px; }
            QPushButton { font-size: 11px; padding: 6px 10px; }
            QTextEdit { font-size: 9px; }
        """
        )

    def _setup_connections(self):
        """
        设置信号连接.
        """
        # 连接数据模型信号
        self.activation_model.copyCodeClicked.connect(self._on_copy_code_clicked)
        self.activation_model.retryClicked.connect(self._on_retry_clicked)
        self.activation_model.closeClicked.connect(self.close)

        self.logger.debug("基础信号连接设置完成")

    def _setup_qml_connections(self):
        """
        设置QML信号连接.
        """
        # 连接QML信号到Python槽
        if self.qml_widget and self.qml_widget.rootObject():
            root_object = self.qml_widget.rootObject()
            root_object.copyCodeClicked.connect(self._on_copy_code_clicked)
            root_object.retryClicked.connect(self._on_retry_clicked)
            root_object.closeClicked.connect(self.close)
            self.logger.debug("QML信号连接设置完成")
        else:
            self.logger.warning("QML根对象未找到，无法设置信号连接")

    def _setup_signal_connections(self):
        """
        设置异步信号连接.
        """
        self.signal_emitter.status_changed.connect(self._on_status_changed)
        self.signal_emitter.error_occurred.connect(self._on_error_occurred)
        self.signal_emitter.data_ready.connect(self._on_data_ready)

    def _on_timer_update(self):
        """定时器更新回调 - 启动初始化"""
        if not self.initialization_started:
            self.initialization_started = True
            self.stop_update_timer()  # 停止定时器

            # 只有在有系统初始化器时才启动初始化
            if self.system_initializer is not None:
                # 现在事件循环应该正在运行，可以创建异步任务
                try:
                    self.create_task(self._start_initialization(), "initialization")
                except RuntimeError as e:
                    self.logger.error(f"创建初始化任务失败: {e}")
                    # 如果还是失败，再试一次
                    self.start_update_timer(500)
            else:
                self.logger.info("无系统初始化器，跳过自动初始化")

    async def _start_initialization(self):
        """
        开始系统初始化流程.
        """
        try:
            # 如果已经提供了SystemInitializer实例，直接使用
            if self.system_initializer:
                self._update_device_info()
                await self._start_activation_process()
            else:
                # 否则创建新的实例并运行初始化
                self.system_initializer = SystemInitializer()

                # 运行初始化流程
                init_result = await self.system_initializer.run_initialization()

                if init_result.get("success", False):
                    self._update_device_info()

                    # 显示状态消息
                    self.status_message = init_result.get("status_message", "")
                    if self.status_message:
                        self.signal_emitter.emit_status(self.status_message)

                    # 检查是否需要激活
                    if init_result.get("need_activation_ui", True):
                        await self._start_activation_process()
                    else:
                        # 无需激活，直接完成
                        self.is_activated = True
                        self.activation_completed.emit(True)
                else:
                    error_msg = init_result.get("error", "初始化失败")
                    self.signal_emitter.emit_error(error_msg)

        except Exception as e:
            self.logger.error(f"初始化过程异常: {e}", exc_info=True)
            self.signal_emitter.emit_error(f"初始化异常: {e}")

    def _update_device_info(self):
        """
        更新设备信息显示.
        """
        if (
            not self.system_initializer
            or not self.system_initializer.device_fingerprint
        ):
            return

        device_fp = self.system_initializer.device_fingerprint

        # 更新序列号
        serial_number = device_fp.get_serial_number()
        self.activation_model.serialNumber = serial_number if serial_number else "--"

        # 更新MAC地址
        mac_address = device_fp.get_mac_address_from_efuse()
        self.activation_model.macAddress = mac_address if mac_address else "--"

        # 获取激活状态
        activation_status = self.system_initializer.get_activation_status()
        local_activated = activation_status.get("local_activated", False)
        server_activated = activation_status.get("server_activated", False)
        status_consistent = activation_status.get("status_consistent", True)

        # 更新激活状态显示
        self.is_activated = local_activated

        if not status_consistent:
            self.activation_model.set_status_inconsistent(
                local_activated, server_activated
            )
        else:
            if local_activated:
                self.activation_model.set_status_activated()
            else:
                self.activation_model.set_status_not_activated()

        # 初始化激活码显示
        self.activation_model.reset_activation_code()

    async def _start_activation_process(self):
        """
        开始激活流程.
        """
        try:
            # 获取激活数据
            activation_data = self.system_initializer.get_activation_data()

            if not activation_data:
                self.signal_emitter.emit_error("未获取到激活数据，请检查网络连接")
                return

            self.activation_data = activation_data

            # 显示激活信息
            self._show_activation_info(activation_data)

            # 初始化设备激活器
            config_manager = self.system_initializer.get_config_manager()
            self.device_activator = DeviceActivator(config_manager)

            # 开始激活流程
            self.signal_emitter.emit_status("开始设备激活流程...")
            activation_success = await self.device_activator.process_activation(
                activation_data
            )

            # 检查是否是因为窗口关闭而取消
            if self.is_shutdown_requested():
                self.signal_emitter.emit_status("激活流程已取消")
                return

            if activation_success:
                self.signal_emitter.emit_status("设备激活成功！")
                self._on_activation_success()
            else:
                self.signal_emitter.emit_status("设备激活失败")
                self.signal_emitter.emit_error("设备激活失败，请重试")

        except Exception as e:
            self.logger.error(f"激活流程异常: {e}", exc_info=True)
            self.signal_emitter.emit_error(f"激活异常: {e}")

    def _show_activation_info(self, activation_data: dict):
        """
        显示激活信息.
        """
        code = activation_data.get("code", "------")

        # 更新设备信息中的激活码
        self.activation_model.update_activation_code(code)

        # 信息已在UI界面显示，仅记录简要日志
        self.logger.info(f"获取激活验证码: {code}")

    def _on_activation_success(self):
        """
        激活成功处理.
        """
        # 更新状态显示
        self.activation_model.set_status_activated()

        # 发射完成信号
        self.activation_completed.emit(True)
        self.is_activated = True

    def _on_status_changed(self, status: str):
        """
        状态变化处理.
        """
        self.update_status(status)

    def _on_error_occurred(self, error_message: str):
        """
        错误处理.
        """
        self.logger.error(f"错误: {error_message}")
        self.update_status(f"错误: {error_message}")

    def _on_data_ready(self, data):
        """
        数据就绪处理 - 更新设备信息.
        """
        self.logger.debug(f"收到数据: {data}")
        if isinstance(data, dict):
            serial = data.get("serial_number")
            mac = data.get("mac_address")
            if serial or mac:
                self.logger.info(f"通过信号更新设备信息: SN={serial}, MAC={mac}")
                self.activation_model.update_device_info(
                    serial_number=serial, mac_address=mac
                )

    def _on_retry_clicked(self):
        """
        重新激活按钮点击.
        """
        self.logger.info("用户请求重新激活")

        # 检查是否已经关闭
        if self.is_shutdown_requested():
            return

        # 重置状态
        self.activation_model.reset_activation_code()

        # 重新开始初始化
        self.create_task(self._start_initialization(), "retry_initialization")

    def _on_copy_code_clicked(self):
        """
        复制验证码按钮点击.
        """
        if self.activation_data:
            code = self.activation_data.get("code", "")
            if code:
                clipboard = QApplication.clipboard()
                clipboard.setText(code)
                self.update_status(f"验证码已复制到剪贴板: {code}")
        else:
            # 从模型获取激活码
            code = self.activation_model.activationCode
            if code and code != "--":
                clipboard = QApplication.clipboard()
                clipboard.setText(code)
                self.update_status(f"验证码已复制到剪贴板: {code}")

    def update_status(self, message: str):
        """
        更新状态信息.
        """
        self.logger.info(message)

        # 如果有状态标签，更新它
        if hasattr(self, "status_label"):
            self.status_label.setText(message)

    def get_activation_result(self) -> dict:
        """
        获取激活结果.
        """
        device_fingerprint = None
        config_manager = None

        if self.system_initializer:
            device_fingerprint = self.system_initializer.device_fingerprint
            config_manager = self.system_initializer.config_manager

        return {
            "is_activated": self.is_activated,
            "device_fingerprint": device_fingerprint,
            "config_manager": config_manager,
        }

    async def shutdown_async(self):
        """
        异步关闭.
        """
        self.logger.info("正在关闭激活窗口...")

        # 取消激活流程（如果正在进行）
        if self.device_activator:
            self.device_activator.cancel_activation()
            self.logger.info("已发送激活取消信号")

        # 先清理异步任务
        await self.cleanup_async_tasks()

        # 然后调用父类关闭
        await super().shutdown_async()

    def mousePressEvent(self, event):
        """
        鼠标按下事件 - 用于窗口拖拽.
        """
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """
        鼠标移动事件 - 实现窗口拖拽.
        """
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        """
        鼠标释放事件.
        """
        self.drag_position = None

    def _apply_native_rounded_corners(self):
        """
        应用原生圆角窗口形状.
        """
        try:
            # 获取窗口尺寸
            width = self.width()
            height = self.height()

            # 创建圆角路径
            radius = 16  # 圆角半径
            path = QPainterPath()
            path.addRoundedRect(0, 0, width, height, radius, radius)

            # 创建区域并应用到窗口
            region = QRegion(path.toFillPolygon().toPolygon())
            self.setMask(region)

            self.logger.info(
                f"已应用原生圆角窗口形状: {width}x{height}, 圆角半径: {radius}px"
            )

        except Exception as e:
            self.logger.error(f"应用原生圆角形状失败: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def closeEvent(self, event):
        """
        窗口关闭事件处理.
        """
        self.logger.info("激活窗口关闭事件触发")
        self.window_closed.emit()
        event.accept()
