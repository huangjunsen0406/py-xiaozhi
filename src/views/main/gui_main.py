# -*- coding: utf-8 -*-
"""
GUI 主窗口模块 - 使用 QML 实现.
"""

import asyncio
import os
import signal
from pathlib import Path
from typing import Optional, Set

from PyQt5.QtCore import QObject, Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor, QFont
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.logging import get_logger

from .emotion_manager import EmotionManager
from .gui_main_model import GuiMainModel
from .tray_manager import TrayManager


class GuiMain(QObject):
    """GUI 主窗口类 - 基于 QML 的现代化界面"""

    # 常量定义
    DEFAULT_WINDOW_SIZE = (880, 560)
    MINIMUM_WINDOW_SIZE = (480, 360)
    DEFAULT_FONT_SIZE = 12
    QUIT_TIMEOUT_MS = 3000

    def __init__(self, event_bus=None):
        super().__init__()
        self.logger = get_logger()
        self._event_bus = event_bus

        # 任务管理
        self._managed_tasks: Set[asyncio.Task] = set()

        # Qt 组件
        self.app = None
        self.root = None
        self.qml_widget = None

        # 管理器
        self.emotion_manager = EmotionManager()
        self.tray_manager = None  # 将在窗口创建后初始化

        # 数据模型
        self.display_model = GuiMainModel()

        # 状态管理
        self.auto_mode = False
        self._running = True
        self.current_status = ""
        self.is_connected = True

        # 窗口拖动状态
        self._dragging = False
        self._drag_position = None

        # 订阅 UI 更新事件
        if self._event_bus:
            self._subscribe_ui_events()
        else:
            self.logger.warning("GuiMain 初始化时未提供 EventBus，UI 事件功能将不可用")

    def _subscribe_ui_events(self):
        """订阅来自插件的 UI 更新事件"""
        from src.core.event_bus import Events

        self._event_bus.on(Events.UI_UPDATE_TEXT, self._on_ui_update_text)
        self._event_bus.on(Events.UI_UPDATE_EMOTION, self._on_ui_update_emotion)
        self._event_bus.on(Events.UI_UPDATE_STATUS, self._on_ui_update_status)
        self._event_bus.on(Events.UI_TOGGLE_MODE, self._on_ui_toggle_mode)
        self._event_bus.on(Events.UI_TOGGLE_WINDOW, self._on_ui_toggle_window)
        self.logger.info("GuiMain 已订阅 UI 事件")

    # ===== 任务管理 =====

    def create_task(self, coro, *, name: Optional[str] = None) -> asyncio.Task:
        """创建并追踪异步任务."""
        task = asyncio.create_task(coro, name=name)
        self._managed_tasks.add(task)
        task.add_done_callback(self._managed_tasks.discard)
        return task

    def cancel_tasks_sync(self):
        """同步取消所有任务."""
        for task in self._managed_tasks.copy():
            if not task.done():
                task.cancel()

    async def cancel_all_tasks(self, timeout: float = 2.0):
        """异步取消所有任务."""
        if not self._managed_tasks:
            return
        for task in self._managed_tasks.copy():
            if not task.done():
                task.cancel()
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._managed_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            pass
        self._managed_tasks.clear()

    # ===== EventBus 事件处理器 =====

    async def _on_ui_update_text(self, data):
        """处理 UI 文本更新事件"""
        try:
            from src.views.events import UITextUpdate

            if isinstance(data, UITextUpdate):
                text = data.text
            elif isinstance(data, dict):
                text = data.get("text", "")
            elif isinstance(data, str):
                text = data
            else:
                self.logger.warning(f"无效的 UI 文本更新数据: {type(data)}")
                return

            await self.update_text(text)
        except Exception as e:
            self.logger.error(f"处理 UI 文本更新失败: {e}", exc_info=True)

    async def _on_ui_update_emotion(self, data):
        """处理 UI 表情更新事件"""
        try:
            from src.views.events import UIEmotionUpdate

            if isinstance(data, UIEmotionUpdate):
                emotion = data.emotion
            elif isinstance(data, dict):
                emotion = data.get("emotion", "")
            elif isinstance(data, str):
                emotion = data
            else:
                self.logger.warning(f"无效的 UI 表情更新数据: {type(data)}")
                return

            await self.update_emotion(emotion)
        except Exception as e:
            self.logger.error(f"处理 UI 表情更新失败: {e}", exc_info=True)

    async def _on_ui_update_status(self, data):
        """处理 UI 状态更新事件"""
        try:
            from src.views.events import UIStatusUpdate

            if isinstance(data, UIStatusUpdate):
                status = data.status
                connected = data.connected
            elif isinstance(data, dict):
                status = data.get("status", "")
                connected = data.get("connected", True)
            else:
                self.logger.warning(f"无效的 UI 状态更新数据: {type(data)}")
                return

            await self.update_status(status, connected)
        except Exception as e:
            self.logger.error(f"处理 UI 状态更新失败: {e}", exc_info=True)

    async def _on_ui_toggle_mode(self, data=None):
        """处理切换对话模式事件"""
        try:
            await self.toggle_mode()
        except Exception as e:
            self.logger.error(f"处理模式切换失败: {e}", exc_info=True)

    async def _on_ui_toggle_window(self, data=None):
        """处理切换窗口可见性事件"""
        try:
            await self.toggle_window_visibility()
        except Exception as e:
            self.logger.error(f"处理窗口切换失败: {e}", exc_info=True)

    # =========================================================================
    # 公共 API - 更新方法
    # =========================================================================

    async def update_status(self, status: str, connected: bool):
        """
        更新状态文本并处理相关逻辑.
        """
        self.display_model.update_status(status, connected)

        # 跟踪状态变化
        status_changed = status != self.current_status
        connected_changed = bool(connected) != self.is_connected

        if status_changed:
            self.current_status = status
        if connected_changed:
            self.is_connected = bool(connected)

        # 更新系统托盘
        if (status_changed or connected_changed) and self.tray_manager:
            self.tray_manager.update_status(status, self.is_connected)

    async def update_text(self, text: str):
        """
        更新 TTS 文本.
        """
        self.display_model.update_text(text)

    async def update_emotion(self, emotion_name: str):
        """
        更新表情显示.
        """
        url_or_text = self.emotion_manager.get_emotion_url(emotion_name)
        self.display_model.update_emotion(url_or_text)

    async def update_button_status(self, text: str):
        """
        更新按钮状态.
        """
        if self.auto_mode:
            self.display_model.update_button_text(text)

    async def toggle_mode(self):
        """
        切换对话模式.
        """
        self._on_mode_button_click()
        self.logger.debug("通过快捷键切换了对话模式")

    async def toggle_window_visibility(self):
        """
        切换窗口可见性.
        """
        if not self.root:
            return

        if self.root.isVisible():
            self.logger.debug("通过快捷键隐藏窗口")
            self.root.hide()
        else:
            self.logger.debug("通过快捷键显示窗口")
            self._show_main_window()

    async def close(self):
        """
        关闭窗口处理.
        """
        self._running = False

        # 取消所有管理的任务
        await self.cancel_all_tasks(timeout=1.0)

        if self.tray_manager:
            self.tray_manager.hide()
        if self.root:
            self.root.close()

    # =========================================================================
    # 启动流程
    # =========================================================================

    async def start(self):
        """
        启动 GUI.
        """
        try:
            self._configure_environment()
            self._create_main_window()
            self._load_qml()
            self._setup_interactions()
            await self._finalize_startup()
        except Exception as e:
            self.logger.error(f"GUI启动失败: {e}", exc_info=True)
            raise

    def _configure_environment(self):
        """
        配置环境.
        """
        os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.debug=false")

        self.app = QApplication.instance()
        if self.app is None:
            raise RuntimeError("QApplication 未找到，请确保在 qasync 环境中运行")

        self.app.setQuitOnLastWindowClosed(False)
        self.app.setFont(QFont("PingFang SC", self.DEFAULT_FONT_SIZE))

        self._setup_signal_handlers()
        self._setup_activation_handler()

    def _create_main_window(self):
        """
        创建主窗口.
        """
        self.root = QWidget()
        self.root.setWindowTitle("")
        self.root.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        # 根据配置计算窗口大小
        window_size, is_fullscreen = self._calculate_window_size()
        self.root.resize(*window_size)

        # 设置最小窗口尺寸
        self.root.setMinimumSize(*self.MINIMUM_WINDOW_SIZE)

        # 保存是否全屏的状态，在 show 时使用
        self._is_fullscreen = is_fullscreen

        self.root.closeEvent = self._closeEvent

    def _calculate_window_size(self) -> tuple:
        """
        根据配置计算窗口大小，返回 (宽, 高, 是否全屏)
        """
        try:
            from src.utils.config_manager import ConfigManager

            config_manager = ConfigManager.get_instance()
            window_size_mode = config_manager.get_config(
                "SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "default"
            )

            # 获取屏幕尺寸（可用区域，排除任务栏等）
            desktop = QApplication.desktop()
            screen_rect = desktop.availableGeometry()
            screen_width = screen_rect.width()
            screen_height = screen_rect.height()

            # 根据模式计算窗口大小
            if window_size_mode == "default":
                # 默认使用 50%
                width = int(screen_width * 0.5)
                height = int(screen_height * 0.5)
                is_fullscreen = False
            elif window_size_mode == "screen_75":
                width = int(screen_width * 0.75)
                height = int(screen_height * 0.75)
                is_fullscreen = False
            elif window_size_mode == "screen_100":
                # 100% 使用真正的全屏模式
                width = screen_width
                height = screen_height
                is_fullscreen = True
            else:
                # 未知模式使用 50%
                width = int(screen_width * 0.5)
                height = int(screen_height * 0.5)
                is_fullscreen = False

            return ((width, height), is_fullscreen)

        except Exception as e:
            self.logger.error(f"计算窗口大小失败: {e}", exc_info=True)
            # 错误时返回屏幕 50%
            try:
                desktop = QApplication.desktop()
                screen_rect = desktop.availableGeometry()
                return (
                    (int(screen_rect.width() * 0.5), int(screen_rect.height() * 0.5)),
                    False,
                )
            except Exception:
                return (self.DEFAULT_WINDOW_SIZE, False)

    def _load_qml(self):
        """
        加载 QML 界面.
        """
        self.qml_widget = QQuickWidget()
        self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.qml_widget.setClearColor(Qt.white)

        # 注册数据模型到 QML 上下文
        qml_context = self.qml_widget.rootContext()
        qml_context.setContextProperty("displayModel", self.display_model)

        # 加载 QML 文件
        qml_file = Path(__file__).parent / "gui_main.qml"
        self.qml_widget.setSource(QUrl.fromLocalFile(str(qml_file)))

        # 设置为主窗口的中央 widget
        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.qml_widget)

    def _setup_interactions(self):
        """
        设置交互（信号、托盘）
        """
        self._connect_qml_signals()

    async def _finalize_startup(self):
        """
        完成启动流程.
        """
        await self.update_emotion("neutral")

        # 根据配置决定显示模式
        if getattr(self, "_is_fullscreen", False):
            self.root.showFullScreen()
        else:
            self.root.show()

        # 初始化系统托盘
        self._setup_system_tray()

    # =========================================================================
    # 信号连接
    # =========================================================================

    def _connect_qml_signals(self):
        """
        连接 QML 信号到 Python 槽.
        """
        root_object = self.qml_widget.rootObject()
        if not root_object:
            self.logger.warning("QML 根对象未找到，无法设置信号连接")
            return

        # 按钮事件信号映射
        button_signals = {
            "manualButtonPressed": self._on_manual_button_press,
            "manualButtonReleased": self._on_manual_button_release,
            "autoButtonClicked": self._on_auto_button_click,
            "abortButtonClicked": self._on_abort_button_click,
            "modeButtonClicked": self._on_mode_button_click,
            "sendButtonClicked": self._on_send_button_click,
            "settingsButtonClicked": self._on_settings_button_click,
        }

        # 标题栏控制信号映射
        titlebar_signals = {
            "titleMinimize": self._minimize_window,
            "titleClose": self._quit_application,
            "titleDragStart": self._on_title_drag_start,
            "titleDragMoveTo": self._on_title_drag_move,
            "titleDragEnd": self._on_title_drag_end,
        }

        # 批量连接信号
        for signal_name, handler in {**button_signals, **titlebar_signals}.items():
            try:
                getattr(root_object, signal_name).connect(handler)
            except AttributeError:
                self.logger.debug(f"信号 {signal_name} 不存在（可能是可选功能）")

        self.logger.debug("QML 信号连接设置完成")

    # =========================================================================
    # 按钮事件处理
    # =========================================================================

    def _on_manual_button_press(self):
        """
        手动模式按钮按下.
        """
        if not self._event_bus:
            return
        from src.core.event_bus import Events

        try:
            self.create_task(
                self._event_bus.emit(Events.UI_BUTTON_PRESS),
                name="emit_button_press",
            )
        except Exception as e:
            self.logger.error(f"发射 UI_BUTTON_PRESS 事件失败: {e}")

    def _on_manual_button_release(self):
        """
        手动模式按钮释放.
        """
        if not self._event_bus:
            return
        from src.core.event_bus import Events

        try:
            self.create_task(
                self._event_bus.emit(Events.UI_BUTTON_RELEASE),
                name="emit_button_release",
            )
        except Exception as e:
            self.logger.error(f"发射 UI_BUTTON_RELEASE 事件失败: {e}")

    def _on_auto_button_click(self):
        """
        自动模式按钮点击.
        """
        if not self._event_bus:
            return
        from src.core.event_bus import Events

        try:
            self.create_task(
                self._event_bus.emit(Events.UI_AUTO_TOGGLE), name="emit_auto_toggle"
            )
        except Exception as e:
            self.logger.error(f"发射 UI_AUTO_TOGGLE 事件失败: {e}")

    def _on_abort_button_click(self):
        """
        中止按钮点击.
        """
        if not self._event_bus:
            return
        from src.core.event_bus import Events

        try:
            self.create_task(
                self._event_bus.emit(Events.UI_ABORT_REQUEST), name="emit_abort_request"
            )
        except Exception as e:
            self.logger.error(f"发射 UI_ABORT_REQUEST 事件失败: {e}")

    def _on_mode_button_click(self):
        """
        对话模式切换按钮点击.
        """
        if self._event_bus:
            from src.core.event_bus import Events

            try:
                self.create_task(
                    self._event_bus.emit(Events.UI_AUTO_TOGGLE),
                    name="emit_mode_toggle",
                )
            except Exception as e:
                self.logger.error(f"发射 UI_AUTO_TOGGLE 事件失败: {e}")

        self.auto_mode = not self.auto_mode
        mode_text = "自动对话" if self.auto_mode else "手动对话"
        self.display_model.update_mode_text(mode_text)
        self.display_model.set_auto_mode(self.auto_mode)

    def _on_send_button_click(self, text: str):
        """
        处理发送文本按钮点击.
        """
        text = text.strip()
        if not text or not self._event_bus:
            return

        from src.core.event_bus import Events
        from src.views.events import UISendTextRequest

        try:
            self.create_task(
                self._event_bus.emit(Events.UI_SEND_TEXT, UISendTextRequest(text=text)),
                name="emit_send_text",
            )
        except Exception as e:
            self.logger.error(f"发射 UI_SEND_TEXT 事件失败: {e}")

    def _on_settings_button_click(self):
        """
        处理设置按钮点击.
        """
        try:
            from src.views.settings import SettingsWindow

            settings_window = SettingsWindow(self.root)
            settings_window.exec_()
        except Exception as e:
            self.logger.error(f"打开设置窗口失败: {e}", exc_info=True)

    # =========================================================================
    # 窗口拖动
    # =========================================================================

    def _on_title_drag_start(self, _x, _y):
        """
        标题栏拖动开始.
        """
        self._dragging = True
        self._drag_position = QCursor.pos() - self.root.pos()

    def _on_title_drag_move(self, _x, _y):
        """
        标题栏拖动移动.
        """
        if self._dragging and self._drag_position:
            self.root.move(QCursor.pos() - self._drag_position)

    def _on_title_drag_end(self):
        """
        标题栏拖动结束.
        """
        self._dragging = False
        self._drag_position = None

    # =========================================================================
    # 系统设置
    # =========================================================================

    def _setup_signal_handlers(self):
        """
        设置信号处理器（Ctrl+C）
        """
        try:
            signal.signal(
                signal.SIGINT,
                lambda *_: QTimer.singleShot(0, self._quit_application),
            )
        except Exception as e:
            self.logger.warning(f"设置信号处理器失败: {e}")

    def _setup_activation_handler(self):
        """
        设置应用激活处理器（macOS Dock 图标点击恢复窗口）
        """
        try:
            import platform

            if platform.system() != "Darwin":
                return

            self.app.applicationStateChanged.connect(self._on_application_state_changed)
            self.logger.debug("已设置应用激活处理器（macOS Dock 支持）")
        except Exception as e:
            self.logger.warning(f"设置应用激活处理器失败: {e}")

    def _on_application_state_changed(self, state):
        """
        应用状态变化处理（macOS Dock 点击时恢复窗口）
        """
        if state == Qt.ApplicationActive and self.root and not self.root.isVisible():
            QTimer.singleShot(0, self._show_main_window)

    def _setup_system_tray(self):
        """
        设置系统托盘.
        """
        self.tray_manager = TrayManager(self.root)
        self.tray_manager.setup(
            on_show_window=self._show_main_window,
            on_settings=self._on_settings_button_click,
            on_quit=self._quit_application,
        )

    # =========================================================================
    # 窗口控制
    # =========================================================================

    def _show_main_window(self):
        """
        显示主窗口.
        """
        if not self.root:
            return

        if self.root.isMinimized():
            self.root.showNormal()
        if not self.root.isVisible():
            self.root.show()
        self.root.activateWindow()
        self.root.raise_()

    def _minimize_window(self):
        """
        最小化窗口.
        """
        if self.root:
            self.root.showMinimized()

    def _quit_application(self):
        """
        退出应用程序.
        """
        self.logger.info("开始退出应用程序...")
        self._running = False

        if self.tray_manager:
            self.tray_manager.hide()

        # 取消所有管理的任务
        self.cancel_tasks_sync()

        # 通过 EventBus 请求优雅关闭
        if self._event_bus:
            from src.core.event_bus import Events

            try:
                self.create_task(
                    self._event_bus.emit(Events.UI_QUIT_REQUEST), name="emit_quit"
                )
                self.logger.debug("已发射 UI_QUIT_REQUEST 事件")
            except Exception as e:
                self.logger.error(f"发射 UI_QUIT_REQUEST 事件失败: {e}")
                # 失败时直接退出
                QApplication.quit()
        else:
            # 没有 EventBus 时直接退出（兼容独立运行场景）
            QApplication.quit()

    def _closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        # 如果系统托盘可用，最小化到托盘
        if self.tray_manager and (
            self.tray_manager.is_available() or self.tray_manager.is_visible()
        ):
            self.logger.info("关闭窗口：最小化到托盘")
            QTimer.singleShot(0, self.root.hide)
            event.ignore()
        else:
            QTimer.singleShot(0, self._quit_application)
            event.accept()
