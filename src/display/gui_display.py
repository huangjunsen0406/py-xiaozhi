# -*- coding: utf-8 -*-
"""
GUI 显示模块 - 使用 QML 实现.
"""

import asyncio
import os
import signal
from abc import ABCMeta
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QCoreApplication, QObject, Qt, QTimer, QUrl
from PyQt5.QtGui import QCursor, QFont
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import QApplication, QVBoxLayout, QWidget

from src.display.base_display import BaseDisplay
from src.display.gui_display_model import GuiDisplayModel
from src.utils.resource_finder import find_assets_dir


# 创建兼容的元类
class CombinedMeta(type(QObject), ABCMeta):
    pass


class GuiDisplay(BaseDisplay, QObject, metaclass=CombinedMeta):
    """GUI 显示类 - 基于 QML 的现代化界面"""

    # 常量定义
    EMOTION_EXTENSIONS = (".gif", ".png", ".jpg", ".jpeg", ".webp")
    DEFAULT_WINDOW_SIZE = (880, 560)
    MINIMUM_WINDOW_SIZE = (480, 360)
    DEFAULT_FONT_SIZE = 12
    QUIT_TIMEOUT_MS = 3000

    def __init__(self):
        super().__init__()
        QObject.__init__(self)

        # Qt 组件
        self.app = None
        self.root = None
        self.qml_widget = None
        self.system_tray = None

        # 数据模型
        self.display_model = GuiDisplayModel()

        # 表情管理
        self._emotion_cache = {}
        self._last_emotion_name = None

        # 状态管理
        self.auto_mode = False
        self._running = True
        self.current_status = ""
        self.is_connected = True

        # 窗口拖动状态
        self._dragging = False
        self._drag_position = None

        # 回调函数映射
        self._callbacks = {
            "button_press": None,
            "button_release": None,
            "mode": None,
            "auto": None,
            "abort": None,
            "send_text": None,
        }

    # =========================================================================
    # 公共 API - 回调与更新
    # =========================================================================

    async def set_callbacks(
        self,
        press_callback: Optional[Callable] = None,
        release_callback: Optional[Callable] = None,
        mode_callback: Optional[Callable] = None,
        auto_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        send_text_callback: Optional[Callable] = None,
    ):
        """
        设置回调函数.
        """
        self._callbacks.update(
            {
                "button_press": press_callback,
                "button_release": release_callback,
                "mode": mode_callback,
                "auto": auto_callback,
                "abort": abort_callback,
                "send_text": send_text_callback,
            }
        )

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
        if (status_changed or connected_changed) and self.system_tray:
            self.system_tray.update_status(status, self.is_connected)

    async def update_text(self, text: str):
        """
        更新 TTS 文本.
        """
        self.display_model.update_text(text)

    async def update_emotion(self, emotion_name: str):
        """
        更新表情显示.
        """
        if emotion_name == self._last_emotion_name:
            return

        self._last_emotion_name = emotion_name
        asset_path = self._get_emotion_asset_path(emotion_name)

        # 将本地文件路径转换为 QML 可用的 URL（file:///...），
        # 非文件（如 emoji 字符）保持原样。
        def to_qml_url(p: str) -> str:
            if not p:
                return ""
            if p.startswith(("qrc:/", "file:")):
                return p
            # 仅当路径存在时才转换为 file URL，避免把 emoji 当作路径
            try:
                if os.path.exists(p):
                    return QUrl.fromLocalFile(p).toString()
            except Exception:
                pass
            return p

        url_or_text = to_qml_url(asset_path)
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
        if self._callbacks["mode"]:
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
        if self.system_tray:
            self.system_tray.hide()
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
        qml_file = Path(__file__).parent / "gui_display.qml"
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
        self._dispatch_callback("button_press")

    def _on_manual_button_release(self):
        """
        手动模式按钮释放.
        """
        self._dispatch_callback("button_release")

    def _on_auto_button_click(self):
        """
        自动模式按钮点击.
        """
        self._dispatch_callback("auto")

    def _on_abort_button_click(self):
        """
        中止按钮点击.
        """
        self._dispatch_callback("abort")

    def _on_mode_button_click(self):
        """
        对话模式切换按钮点击.
        """
        if self._callbacks["mode"] and not self._callbacks["mode"]():
            return

        self.auto_mode = not self.auto_mode
        mode_text = (
            QCoreApplication.translate("GuiDisplay", "自动对话")
            if self.auto_mode
            else QCoreApplication.translate("GuiDisplay", "手动对话")
        )
        self.display_model.update_mode_text(mode_text)
        self.display_model.set_auto_mode(self.auto_mode)

    def _on_send_button_click(self, text: str):
        """
        处理发送文本按钮点击.
        """
        text = text.strip()
        if not text or not self._callbacks["send_text"]:
            return

        try:
            task = asyncio.create_task(self._callbacks["send_text"](text))
            task.add_done_callback(
                lambda t: (
                    t.cancelled()
                    or not t.exception()
                    or self.logger.error(
                        f"发送文本任务异常: {t.exception()}", exc_info=True
                    )
                )
            )
        except Exception as e:
            self.logger.error(f"发送文本时出错: {e}")

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

    def _dispatch_callback(self, callback_name: str, *args):
        """
        通用回调调度器.
        """
        callback = self._callbacks.get(callback_name)
        if callback:
            callback(*args)

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
    # 表情管理
    # =========================================================================

    def _get_emotion_asset_path(self, emotion_name: str) -> str:
        """
        获取表情资源文件路径，自动匹配常见后缀.
        """
        if emotion_name in self._emotion_cache:
            return self._emotion_cache[emotion_name]

        assets_dir = find_assets_dir()
        if not assets_dir:
            path = "😊"
        else:
            emotion_dir = assets_dir / "emojis"
            # 尝试查找表情文件，失败则回退到 neutral
            path = (
                str(self._find_emotion_file(emotion_dir, emotion_name))
                or str(self._find_emotion_file(emotion_dir, "neutral"))
                or "😊"
            )

        self._emotion_cache[emotion_name] = path
        return path

    def _find_emotion_file(self, emotion_dir: Path, name: str) -> Optional[Path]:
        """
        在指定目录查找表情文件.
        """
        for ext in self.EMOTION_EXTENSIONS:
            file_path = emotion_dir / f"{name}{ext}"
            if file_path.exists():
                return file_path
        return None

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
        if os.getenv("XIAOZHI_DISABLE_TRAY") == "1":
            self.logger.warning("已通过环境变量禁用系统托盘 (XIAOZHI_DISABLE_TRAY=1)")
            return

        try:
            from src.views.components.system_tray import SystemTray

            self.system_tray = SystemTray(self.root)

            # 连接托盘信号（使用 QTimer 确保主线程执行）
            tray_signals = {
                "show_window_requested": self._show_main_window,
                "settings_requested": self._on_settings_button_click,
                "quit_requested": self._quit_application,
            }

            for signal_name, handler in tray_signals.items():
                getattr(self.system_tray, signal_name).connect(
                    lambda h=handler: QTimer.singleShot(0, h)
                )

        except Exception as e:
            self.logger.error(f"初始化系统托盘组件失败: {e}", exc_info=True)

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

        if self.system_tray:
            self.system_tray.hide()

        try:
            from src.application import Application

            app = Application.get_instance()
            if not app:
                QApplication.quit()
                return

            loop = asyncio.get_event_loop()
            if not loop.is_running():
                QApplication.quit()
                return

            # 创建关闭任务并设置超时
            shutdown_task = asyncio.create_task(app.shutdown())

            def on_shutdown_complete(task):
                if not task.cancelled() and task.exception():
                    self.logger.error(f"应用程序关闭异常: {task.exception()}")
                else:
                    self.logger.info("应用程序正常关闭")
                QApplication.quit()

            def force_quit():
                if not shutdown_task.done():
                    self.logger.warning("关闭超时，强制退出")
                    shutdown_task.cancel()
                QApplication.quit()

            shutdown_task.add_done_callback(on_shutdown_complete)
            QTimer.singleShot(self.QUIT_TIMEOUT_MS, force_quit)

        except Exception as e:
            self.logger.error(f"关闭应用程序失败: {e}")
            QApplication.quit()

    def _closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        # 如果系统托盘可用，最小化到托盘
        if self.system_tray and (
            getattr(self.system_tray, "is_available", lambda: False)()
            or getattr(self.system_tray, "is_visible", lambda: False)()
        ):
            self.logger.info("关闭窗口：最小化到托盘")
            QTimer.singleShot(0, self.root.hide)
            event.ignore()
        else:
            QTimer.singleShot(0, self._quit_application)
            event.accept()
