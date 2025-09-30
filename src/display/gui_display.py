# -*- coding: utf-8 -*-
"""
GUI 显示模块 - 使用 QML 实现.
"""

import os

# platform 仅在原生标题栏模式时使用；当前自定义标题栏不依赖
import signal
from abc import ABCMeta
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QObject, Qt, QTimer, QUrl
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtQuickWidgets import QQuickWidget
from PyQt5.QtWidgets import QApplication, QShortcut, QWidget

from src.display.base_display import BaseDisplay
from src.display.gui_display_model import GuiDisplayModel
from src.utils.resource_finder import find_assets_dir


# 创建兼容的元类
class CombinedMeta(type(QObject), ABCMeta):
    pass


class GuiDisplay(BaseDisplay, QObject, metaclass=CombinedMeta):
    def __init__(self):
        super().__init__()
        QObject.__init__(self)
        self.app = None
        self.root = None
        self.qml_widget = None

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

        # 回调函数
        self.button_press_callback = None
        self.button_release_callback = None
        self.mode_callback = None
        self.auto_callback = None
        self.abort_callback = None
        self.send_text_callback = None

        # 系统托盘组件
        self.system_tray = None

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
        self.button_press_callback = press_callback
        self.button_release_callback = release_callback
        self.mode_callback = mode_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback
        self.send_text_callback = send_text_callback

    def _on_manual_button_press(self):
        """
        手动模式按钮按下事件处理.
        """
        if self.button_press_callback:
            self.button_press_callback()

    def _on_manual_button_release(self):
        """
        手动模式按钮释放事件处理.
        """
        if self.button_release_callback:
            self.button_release_callback()

    def _on_auto_button_click(self):
        """
        自动模式按钮点击事件处理.
        """
        if self.auto_callback:
            self.auto_callback()

    def _on_abort_button_click(self):
        """
        处理中止按钮点击事件.
        """
        if self.abort_callback:
            self.abort_callback()

    def _on_mode_button_click(self):
        """
        对话模式切换按钮点击事件.
        """
        if self.mode_callback:
            if not self.mode_callback():
                return

        self.auto_mode = not self.auto_mode

        if self.auto_mode:
            self.display_model.update_mode_text("自动对话")
            self.display_model.set_auto_mode(True)
        else:
            self.display_model.update_mode_text("手动对话")
            self.display_model.set_auto_mode(False)

    async def update_status(self, status: str, connected: bool):
        """
        更新状态文本并处理相关逻辑.
        """
        self.display_model.update_status(status, connected)

        # 既跟踪状态文本变化，也跟踪连接状态变化
        new_connected = bool(connected)
        status_changed = status != self.current_status
        connected_changed = new_connected != self.is_connected

        if status_changed:
            self.current_status = status
        if connected_changed:
            self.is_connected = new_connected

        # 任一变化都更新系统托盘
        if status_changed or connected_changed:
            self._update_system_tray(status)

    async def update_text(self, text: str):
        """
        更新TTS文本.
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

        # 更新模型中的表情路径
        self.display_model.update_emotion(asset_path)

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
            # 支持的后缀优先级：gif > png > jpg > jpeg > webp
            candidates = [
                emotion_dir / f"{emotion_name}.gif",
                emotion_dir / f"{emotion_name}.png",
                emotion_dir / f"{emotion_name}.jpg",
                emotion_dir / f"{emotion_name}.jpeg",
                emotion_dir / f"{emotion_name}.webp",
            ]
            # 依次匹配
            found = next((p for p in candidates if p.exists()), None)

            # 兜底到 neutral 同样规则
            if not found:
                neutral_candidates = [
                    emotion_dir / "neutral.gif",
                    emotion_dir / "neutral.png",
                    emotion_dir / "neutral.jpg",
                    emotion_dir / "neutral.jpeg",
                    emotion_dir / "neutral.webp",
                ]
                found = next((p for p in neutral_candidates if p.exists()), None)

            path = str(found) if found else "😊"

        self._emotion_cache[emotion_name] = path
        return path

    async def close(self):
        """
        关闭窗口处理.
        """
        self._running = False

        if self.system_tray:
            self.system_tray.hide()
        if self.root:
            self.root.close()

    async def start(self):
        """
        启动GUI.
        """
        try:
            # 设置Qt环境变量
            os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.fonts.debug=false")

            self.app = QApplication.instance()
            if self.app is None:
                raise RuntimeError("QApplication未找到，请确保在qasync环境中运行")

            # 关闭最后一个窗口被关闭时自动退出应用的行为，确保托盘常驻
            try:
                self.app.setQuitOnLastWindowClosed(False)
            except Exception:
                pass

            # 设置优雅的 Ctrl+C 处理
            self._setup_signal_handlers()

            # macOS: 使用 applicationStateChanged 替代 eventFilter（更安全）
            self._setup_activation_handler()

            # 设置默认字体
            default_font = QFont()
            default_font.setPointSize(12)
            self.app.setFont(default_font)

            # 创建主窗口（无边框窗体）
            self.root = QWidget()
            # 隐藏标题文本，但保留原生窗口按钮
            self.root.setWindowTitle("")
            try:
                # 无边框：使用自定义标题栏按钮
                from PyQt5.QtCore import Qt as _Qt

                self.root.setWindowFlags(_Qt.FramelessWindowHint | _Qt.Window)
            except Exception:
                pass
            self.root.resize(880, 560)

            # 创建 QML Widget
            self.qml_widget = QQuickWidget()
            self.qml_widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
            self.qml_widget.setClearColor(Qt.white)

            # 注册数据模型到 QML 上下文
            qml_context = self.qml_widget.rootContext()
            qml_context.setContextProperty("displayModel", self.display_model)

            # 加载 QML 文件
            qml_file = Path(__file__).parent / "gui_display.qml"
            self.qml_widget.setSource(QUrl.fromLocalFile(str(qml_file)))

            # 设置为主窗口的中央widget
            from PyQt5.QtWidgets import QVBoxLayout

            layout = QVBoxLayout(self.root)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.qml_widget)

            # 连接 QML 信号到 Python 槽
            self._connect_qml_signals()

            # 设置窗口关闭事件
            self.root.closeEvent = self._closeEvent

            # 设置快捷键
            self._setup_shortcuts()

            # 设置默认表情
            await self._set_default_emotion()

            # 先显示窗口（确保 UI 已在主线程初始化完成）
            self.root.show()

            # 最后初始化系统托盘（避免早期事件触发）
            self._setup_system_tray()

            # 自定义标题栏模式下，不再应用 macOS 原生外观

        except Exception as e:
            self.logger.error(f"GUI启动失败: {e}", exc_info=True)
            raise

    def _setup_signal_handlers(self):
        """
        设置信号处理器，优雅处理 Ctrl+C.
        """
        try:

            def _on_sigint(*_):
                """
                处理 SIGINT (Ctrl+C) 信号.
                """
                self.logger.info("收到 SIGINT (^C)，准备退出...")
                # 用 Qt 的计时器把退出投递回主线程，避免跨线程直接操作 Qt
                QTimer.singleShot(0, self._quit_application)

            signal.signal(signal.SIGINT, _on_sigint)
        except Exception as e:
            self.logger.warning(f"设置信号处理器失败: {e}")

    def _apply_macos_titlebar_native(self):
        """
        MacOS：隐藏标题文本、透明标题栏、启用全尺寸内容视图，保留原生按钮； 同时允许在背景区域拖拽移动窗口。
        """
        try:
            from AppKit import (
                NSWindowStyleMaskFullSizeContentView,
                NSWindowTitleHidden,
            )
            from objc import ObjCInstance

            view = ObjCInstance(int(self.root.winId()))  # NSView*
            window = view.window()
            if window is None:
                return
            # 隐藏标题文本、透明标题栏
            window.setTitleVisibility_(NSWindowTitleHidden)
            window.setTitlebarAppearsTransparent_(True)
            # 内容延伸到标题栏区域
            mask = window.styleMask()
            window.setStyleMask_(mask | NSWindowStyleMaskFullSizeContentView)
            # 允许背景拖动
            window.setMovableByWindowBackground_(True)
        except Exception as e:
            try:
                self.logger.warning(f"macOS 原生标题栏样式设置失败: {e}")
            except Exception:
                pass

    def _setup_activation_handler(self):
        """设置应用激活处理器（macOS Dock 图标点击恢复窗口）.

        使用 applicationStateChanged 信号替代 eventFilter，避免跨线程问题.
        """
        try:
            import platform

            if platform.system() != "Darwin":  # 仅 macOS 需要
                return

            # 连接应用状态变化信号
            self.app.applicationStateChanged.connect(self._on_application_state_changed)
            self.logger.debug("已设置应用激活处理器（macOS Dock 支持）")
        except Exception as e:
            self.logger.warning(f"设置应用激活处理器失败: {e}")

    def _on_application_state_changed(self, state):
        """
        应用状态变化处理（Qt::ApplicationActive = 4）.
        当用户点击 Dock 图标时，如果窗口隐藏则恢复显示.
        """
        try:
            from PyQt5.QtCore import Qt

            # Qt::ApplicationActive = 4，表示应用被激活
            if state == Qt.ApplicationActive:
                if self.root and not self.root.isVisible():
                    # 使用 QTimer 确保在主线程执行
                    QTimer.singleShot(0, self._show_main_window)
        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(f"处理应用状态变化失败: {e}")

    def _connect_qml_signals(self):
        """
        连接 QML 信号到 Python 槽.
        """
        if self.qml_widget and self.qml_widget.rootObject():
            root_object = self.qml_widget.rootObject()
            root_object.manualButtonPressed.connect(self._on_manual_button_press)
            root_object.manualButtonReleased.connect(self._on_manual_button_release)
            root_object.autoButtonClicked.connect(self._on_auto_button_click)
            root_object.abortButtonClicked.connect(self._on_abort_button_click)
            root_object.modeButtonClicked.connect(self._on_mode_button_click)
            root_object.sendButtonClicked.connect(self._on_send_button_click)
            root_object.settingsButtonClicked.connect(self._on_settings_button_click)
            # 标题栏交互（最小化/关闭/拖拽移动）
            try:
                root_object.titleMinimize.connect(
                    lambda: QTimer.singleShot(0, self._minimize_window)
                )
            except Exception:
                pass
            try:
                root_object.titleClose.connect(
                    lambda: QTimer.singleShot(0, self._quit_application)
                )
            except Exception:
                pass
            # 改用屏幕坐标：开始位置 + 当前屏幕位置，避免累计误差抖动
            try:
                self._drag_start_screen_pos = None

                def _drag_start(sx, sy):
                    try:
                        self._drag_start_screen_pos = (int(sx), int(sy))
                        self._drag_start_window_pos = (self.root.x(), self.root.y())
                    except Exception:
                        pass

                def _drag_to(sx, sy):
                    try:
                        if (
                            not hasattr(self, "_drag_start_screen_pos")
                            or self._drag_start_screen_pos is None
                        ):
                            return
                        dx = int(sx) - self._drag_start_screen_pos[0]
                        dy = int(sy) - self._drag_start_screen_pos[1]
                        self.root.move(
                            self._drag_start_window_pos[0] + dx,
                            self._drag_start_window_pos[1] + dy,
                        )
                    except Exception:
                        pass

                root_object.titleDragStart.connect(_drag_start)
                root_object.titleDragMoveTo.connect(_drag_to)
            except Exception:
                pass
            self.logger.debug("QML 信号连接设置完成")
        else:
            self.logger.warning("QML 根对象未找到，无法设置信号连接")

    def _setup_shortcuts(self):
        """
        设置快捷键.
        """
        try:
            # Ctrl+, 与 Cmd+, 打开设置
            QShortcut(
                QKeySequence("Ctrl+,"),
                self.root,
                activated=self._on_settings_button_click,
            )
            QShortcut(
                QKeySequence("Meta+,"),
                self.root,
                activated=self._on_settings_button_click,
            )
        except Exception as e:
            self.logger.warning(f"设置快捷键失败: {e}")

    def _setup_system_tray(self):
        """设置系统托盘.

        注意：所有托盘信号回调都通过 QTimer 投递到主线程，避免跨线程 UI 操作.
        """
        try:
            # 允许通过环境变量禁用系统托盘用于排障
            if os.getenv("XIAOZHI_DISABLE_TRAY") == "1":
                self.logger.warning(
                    "已通过环境变量禁用系统托盘 (XIAOZHI_DISABLE_TRAY=1)"
                )
                return
            from src.views.components.system_tray import SystemTray

            self.system_tray = SystemTray(self.root)

            # 使用 lambda + QTimer 确保所有回调在主线程执行
            self.system_tray.show_window_requested.connect(
                lambda: QTimer.singleShot(0, self._show_main_window)
            )
            self.system_tray.settings_requested.connect(
                lambda: QTimer.singleShot(0, self._on_settings_button_click)
            )
            self.system_tray.quit_requested.connect(
                lambda: QTimer.singleShot(0, self._quit_application)
            )

        except Exception as e:
            self.logger.error(f"初始化系统托盘组件失败: {e}", exc_info=True)

    async def _set_default_emotion(self):
        """
        设置默认表情.
        """
        try:
            await self.update_emotion("neutral")
        except Exception as e:
            self.logger.error(f"设置默认表情失败: {e}", exc_info=True)

    def _update_system_tray(self, status):
        """
        更新系统托盘状态.
        """
        if self.system_tray:
            self.system_tray.update_status(status, self.is_connected)

    def _show_main_window(self):
        """
        显示主窗口.
        """
        if self.root:
            if self.root.isMinimized():
                self.root.showNormal()
            if not self.root.isVisible():
                self.root.show()
            self.root.activateWindow()
            self.root.raise_()

    def _minimize_window(self):
        try:
            self.root.showMinimized()
        except Exception:
            pass

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
            if app:
                # 异步启动关闭流程，但设置超时
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 创建关闭任务，但不等待
                    shutdown_task = asyncio.create_task(app.shutdown())

                    # 设置超时后强制退出
                    def force_quit():
                        if not shutdown_task.done():
                            self.logger.warning("关闭超时，强制退出")
                            shutdown_task.cancel()
                        QApplication.quit()

                    # 3秒后强制退出
                    QTimer.singleShot(3000, force_quit)

                    # 当shutdown完成时正常退出
                    def on_shutdown_complete(task):
                        if not task.cancelled():
                            if task.exception():
                                self.logger.error(
                                    f"应用程序关闭异常: {task.exception()}"
                                )
                            else:
                                self.logger.info("应用程序正常关闭")
                        QApplication.quit()

                    shutdown_task.add_done_callback(on_shutdown_complete)
                else:
                    # 如果事件循环未运行，直接退出
                    QApplication.quit()
            else:
                QApplication.quit()

        except Exception as e:
            self.logger.error(f"关闭应用程序失败: {e}")
            # 异常情况下直接退出
            QApplication.quit()

    def _closeEvent(self, event):
        """
        处理窗口关闭事件.
        """
        # 只要系统托盘可用，就最小化到托盘
        if self.system_tray and (
            getattr(self.system_tray, "is_available", lambda: False)()
            or getattr(self.system_tray, "is_visible", lambda: False)()
        ):
            self.logger.info("关闭窗口：最小化到托盘")
            # 使用 QTimer 确保在主线程执行隐藏操作
            QTimer.singleShot(0, self.root.hide)
            event.ignore()
        else:
            # 使用 QTimer 确保退出在主线程执行
            QTimer.singleShot(0, self._quit_application)
            event.accept()

    async def update_button_status(self, text: str):
        """
        更新按钮状态.
        """
        if self.auto_mode:
            self.display_model.update_button_text(text)

    def _on_send_button_click(self, text: str):
        """
        处理发送文本按钮点击事件.
        """
        if not self.send_text_callback:
            return

        text = text.strip()
        if not text:
            return

        try:
            import asyncio

            task = asyncio.create_task(self.send_text_callback(text))

            def _on_done(t):
                if not t.cancelled() and t.exception():
                    self.logger.error(
                        f"发送文本任务异常: {t.exception()}", exc_info=True
                    )

            task.add_done_callback(_on_done)
        except Exception as e:
            self.logger.error(f"发送文本时出错: {e}")

    def _on_settings_button_click(self):
        """
        处理设置按钮点击事件.
        """
        try:
            from src.views.settings import SettingsWindow

            settings_window = SettingsWindow(self.root)
            settings_window.exec_()

        except Exception as e:
            self.logger.error(f"打开设置窗口失败: {e}", exc_info=True)

    async def toggle_mode(self):
        """
        切换模式.
        """
        # 调用现有的模式切换功能
        if hasattr(self, "mode_callback") and self.mode_callback:
            self._on_mode_button_click()
            self.logger.debug("通过快捷键切换了对话模式")

    async def toggle_window_visibility(self):
        """
        切换窗口可见性.
        """
        if self.root:
            if self.root.isVisible():
                self.logger.debug("通过快捷键隐藏窗口")
                self.root.hide()
            else:
                self.logger.debug("通过快捷键显示窗口")
                self.root.show()
                self.root.activateWindow()
                self.root.raise_()
