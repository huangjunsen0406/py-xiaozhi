# -*- coding: utf-8 -*-
"""
设备激活窗口 显示激活流程、设备信息和激活进度.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt5 import uic
from PyQt5.QtCore import QSize, pyqtSignal
from PyQt5.QtWidgets import QApplication

from src.core.system_initializer import SystemInitializer
from src.utils.device_activator import DeviceActivator
from src.utils.logging_config import get_logger

from ..base.async_mixins import AsyncMixin, AsyncSignalEmitter
from ..base.base_window import BaseWindow

logger = get_logger(__name__)


class ActivationWindow(BaseWindow, AsyncMixin):
    """
    设备激活窗口.
    """

    # 自定义信号
    activation_completed = pyqtSignal(bool)  # 激活完成信号

    def __init__(self, parent: Optional = None):
        super().__init__(parent)

        # 组件实例
        self.system_initializer: Optional[SystemInitializer] = None
        self.device_activator: Optional[DeviceActivator] = None

        # 状态管理
        self.current_stage = None
        self.activation_data = None
        self.is_activated = False
        self.initialization_started = False

        # 异步信号发射器
        self.signal_emitter = AsyncSignalEmitter()
        self._setup_signal_connections()

        # 延迟启动初始化（等事件循环运行后）
        self.start_update_timer(100)  # 100ms后开始初始化

    def _setup_ui(self):
        """
        设置UI.
        """
        ui_file = Path(__file__).parent / "activation_window.ui"
        uic.loadUi(str(ui_file), self)

        # 设置窗口属性和自适应尺寸
        self.setWindowTitle("设备激活 - py-xiaozhi")
        self._setup_adaptive_size()

        self.logger.info("激活窗口UI加载完成")

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
            window_width, window_height = 450, 320
            self.setMinimumSize(QSize(450, 320))
            self._apply_compact_styles()
        elif screen_width <= 800 or screen_height <= 480:
            # 小屏幕 (如7寸800x480)
            window_width, window_height = 480, 450
            self.setMinimumSize(QSize(480, 450))
            self._apply_small_screen_styles()
        elif screen_width <= 1024 or screen_height <= 600:
            # 中等屏幕
            window_width, window_height = 580, 500
            self.setMinimumSize(QSize(580, 500))
        else:
            # 大屏幕 (PC显示器)
            window_width, window_height = 600, 550
            self.setMinimumSize(QSize(600, 550))

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

        # 隐藏部分非关键信息以节省空间
        if hasattr(self, "log_text"):
            self.log_text.setMaximumHeight(60)

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

        # 适当调整日志区域高度
        if hasattr(self, "log_text"):
            self.log_text.setMaximumHeight(80)

    def _setup_connections(self):
        """
        设置信号连接.
        """
        # 按钮连接
        self.close_btn.clicked.connect(self.close)
        self.retry_btn.clicked.connect(self._on_retry_clicked)
        self.copy_code_btn.clicked.connect(self._on_copy_code_clicked)

        self.logger.debug("信号连接设置完成")

    def _setup_signal_connections(self):
        """
        设置异步信号连接.
        """
        self.signal_emitter.status_changed.connect(self._on_status_changed)
        self.signal_emitter.error_occurred.connect(self._on_error_occurred)
        self.signal_emitter.data_ready.connect(self._on_data_ready)

    def _setup_styles(self):
        """
        设置样式.
        """
        # 基础样式已在UI文件中定义

    def _on_timer_update(self):
        """定时器更新回调 - 启动初始化"""
        if not self.initialization_started:
            self.initialization_started = True
            self.stop_update_timer()  # 停止定时器

            # 现在事件循环应该正在运行，可以创建异步任务
            try:
                self.create_task(self._start_initialization(), "initialization")
            except RuntimeError as e:
                self.logger.error(f"创建初始化任务失败: {e}")
                # 如果还是失败，再试一次
                self.start_update_timer(500)

    async def _start_initialization(self):
        """
        开始系统初始化流程.
        """
        try:
            self._append_log("开始系统初始化流程")

            self.system_initializer = SystemInitializer()

            # 运行四阶段初始化
            success = await self._run_initialization_stages()

            if success:
                self._append_log("系统初始化完成")
                await self._check_activation_status()
            else:
                self._append_log("系统初始化失败")
                self.signal_emitter.emit_error("系统初始化失败，请检查网络连接和配置")

        except Exception as e:
            self.logger.error(f"初始化过程异常: {e}", exc_info=True)
            self._append_log(f"初始化异常: {e}")
            self.signal_emitter.emit_error(f"初始化异常: {e}")

    async def _run_initialization_stages(self) -> bool:
        """
        运行初始化各阶段.
        """
        try:
            # 第一阶段：设备身份准备
            self._append_log("第一阶段：设备身份准备")
            await self.system_initializer.stage_1_device_fingerprint()
            self._update_device_info()

            # 第二阶段：配置管理初始化
            self._append_log("第二阶段：配置管理初始化")
            await self.system_initializer.stage_2_config_management()

            # 第三阶段：OTA获取配置
            self._append_log("第三阶段：OTA配置获取")
            await self.system_initializer.stage_3_ota_config()

            # 第四阶段：激活流程准备
            self._append_log("第四阶段：激活流程准备")
            self.system_initializer.stage_4_activation_ready()

            return True

        except Exception as e:
            self.logger.error(f"初始化阶段失败: {e}")
            return False

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
        self.serial_value.setText(serial_number if serial_number else "--")

        # 更新MAC地址
        mac_address = device_fp.get_mac_address_from_efuse()
        self.mac_value.setText(mac_address if mac_address else "--")

        # 更新激活状态
        is_activated = device_fp.is_activated()
        self.is_activated = is_activated
        status_text = "已激活" if is_activated else "未激活"
        status_style = "color: #28a745;" if is_activated else "color: #dc3545;"
        self.status_value.setText(status_text)
        self.status_value.setStyleSheet(status_style)

        # 初始化激活码显示
        self.activation_code_value.setText("--")

        activated_text = "已激活" if is_activated else "未激活"
        self._append_log(
            f"📱 设备信息更新 - 序列号: {serial_number}, " f"激活状态: {activated_text}"
        )

    async def _check_activation_status(self):
        """
        检查激活状态.
        """
        if self.is_activated:
            self._append_log("设备已激活，无需重复激活")
            self.activation_completed.emit(True)
        else:
            # 检查是否有激活数据
            activation_data = self.system_initializer.get_activation_data()
            if activation_data:
                self._append_log("检测到激活请求，准备激活流程")
                await self._start_activation_process(activation_data)
            else:
                self._append_log("未获取到激活数据")
                self.signal_emitter.emit_error("未获取到激活数据，请检查网络连接")

    async def _start_activation_process(self, activation_data: dict):
        """
        开始激活流程.
        """
        try:
            self.activation_data = activation_data

            # 显示激活信息
            self._show_activation_info(activation_data)

            # 初始化设备激活器
            config_manager = self.system_initializer.get_config_manager()
            self.device_activator = DeviceActivator(config_manager)

            # 开始激活流程
            self._append_log("开始设备激活流程...")
            activation_success = await self.device_activator.process_activation(
                activation_data
            )

            # 检查是否是因为窗口关闭而取消
            if self.is_shutdown_requested():
                self._append_log("激活流程已取消")
                return

            if activation_success:
                self._append_log("设备激活成功！")
                self._on_activation_success()
            else:
                self._append_log("设备激活失败")
                self.signal_emitter.emit_error("设备激活失败，请重试")

        except Exception as e:
            self.logger.error(f"激活流程异常: {e}", exc_info=True)
            self._append_log(f"激活异常: {e}")
            self.signal_emitter.emit_error(f"激活异常: {e}")

    def _show_activation_info(self, activation_data: dict):
        """
        显示激活信息.
        """
        code = activation_data.get("code", "------")

        # 更新设备信息中的激活码
        self.activation_code_value.setText(code)

        # 信息已在UI界面显示，仅记录简要日志
        self._append_log(f"获取激活验证码: {code}")

    def _on_activation_success(self):
        """
        激活成功处理.
        """
        # 更新状态显示
        self.status_value.setText("已激活")
        self.status_value.setStyleSheet("color: #28a745;")

        # 清除激活码显示
        self.activation_code_value.setText("--")

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
        self._append_log(f"错误: {error_message}")

    def _on_data_ready(self, data):
        """
        数据就绪处理.
        """
        self.logger.debug(f"收到数据: {data}")

    def _on_retry_clicked(self):
        """
        重新激活按钮点击.
        """
        self._append_log("用户请求重新激活")

        # 检查是否已经关闭
        if self.is_shutdown_requested():
            return

        # 重置状态
        self.activation_code_value.setText("--")

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
                self._append_log(f"验证码已复制到剪贴板: {code}")

    def _append_log(self, message: str):
        """
        添加日志信息.
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        self.log_text.append(log_message)
        self.logger.info(message)

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
        self._append_log("正在关闭激活窗口...")

        # 取消激活流程（如果正在进行）
        if self.device_activator:
            self.device_activator.cancel_activation()
            self._append_log("已发送激活取消信号")

        # 先清理异步任务
        await self.cleanup_async_tasks()

        # 然后调用父类关闭
        await super().shutdown_async()
