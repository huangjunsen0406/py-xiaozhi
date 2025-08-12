import os
from abc import ABCMeta
from pathlib import Path
from typing import Callable, Optional

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtGui import QFont, QKeySequence, QMovie, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from src.display.base_display import BaseDisplay
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

        # UI控件
        self.status_label = None
        self.emotion_label = None
        self.tts_text_label = None
        self.manual_btn = None
        self.abort_btn = None
        self.auto_btn = None
        self.mode_btn = None
        self.text_input = None
        self.send_btn = None

        # 表情管理
        self.emotion_movie = None
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

        # 不再注册状态监听回调，由update_status直接处理所有逻辑

    def _on_manual_button_press(self):
        """
        手动模式按钮按下事件处理.
        """
        if self.manual_btn and self.manual_btn.isVisible():
            self.manual_btn.setText("松开以停止")
        if self.button_press_callback:
            self.button_press_callback()

    def _on_manual_button_release(self):
        """
        手动模式按钮释放事件处理.
        """
        if self.manual_btn and self.manual_btn.isVisible():
            self.manual_btn.setText("按住后说话")
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
            self._update_mode_button_status("自动对话")
            self._switch_to_auto_mode()
        else:
            self._update_mode_button_status("手动对话")
            self._switch_to_manual_mode()

    def _switch_to_auto_mode(self):
        """
        切换到自动模式的UI更新.
        """
        if self.manual_btn and self.auto_btn:
            self.manual_btn.hide()
            self.auto_btn.show()

    def _switch_to_manual_mode(self):
        """
        切换到手动模式的UI更新.
        """
        if self.manual_btn and self.auto_btn:
            self.auto_btn.hide()
            self.manual_btn.show()

    async def update_status(self, status: str, connected: bool):
        """
        更新状态文本并处理相关逻辑.
        """
        full_status_text = f"状态: {status}"
        self._safe_update_label(self.status_label, full_status_text)

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
        self._safe_update_label(self.tts_text_label, text)

    async def update_emotion(self, emotion_name: str):
        """
        更新表情显示.
        """
        if emotion_name == self._last_emotion_name:
            return

        self._last_emotion_name = emotion_name
        asset_path = self._get_emotion_asset_path(emotion_name)

        if self.emotion_label:
            try:
                self._set_emotion_asset(self.emotion_label, asset_path)
            except Exception as e:
                self.logger.error(f"设置表情GIF时发生错误: {str(e)}")

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

    def _set_emotion_asset(self, label, asset_path: str):
        """
        设置表情资源（GIF动图或静态图片）。
        """
        if not label:
            return

        # 如果是emoji字符串，直接设置文本
        if not isinstance(asset_path, str) or "." not in asset_path:
            label.setText(asset_path or "😊")
            return

        try:
            if asset_path.lower().endswith(".gif"):
                # GIF 动图
                if hasattr(self, "_gif_movies") and asset_path in self._gif_movies:
                    movie = self._gif_movies[asset_path]
                else:
                    movie = QMovie(asset_path)
                    if not movie.isValid():
                        label.setText("😊")
                        return
                    movie.setCacheMode(QMovie.CacheAll)
                    if not hasattr(self, "_gif_movies"):
                        self._gif_movies = {}
                    self._gif_movies[asset_path] = movie

                # 如切换到新的movie，停止旧的以避免CPU占用
                if getattr(self, "emotion_movie", None) is not None and self.emotion_movie is not movie:
                    try:
                        self.emotion_movie.stop()
                    except Exception:
                        pass

                self.emotion_movie = movie
                label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                label.setAlignment(Qt.AlignCenter)
                label.setMovie(movie)
                movie.setSpeed(105)
                movie.start()
            else:
                # 静态图片：如有旧的GIF在播放则停止
                if getattr(self, "emotion_movie", None) is not None:
                    try:
                        self.emotion_movie.stop()
                    except Exception:
                        pass
                    self.emotion_movie = None

                pixmap = QPixmap(asset_path)
                if pixmap.isNull():
                    label.setText("😊")
                    return
                label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                label.setAlignment(Qt.AlignCenter)
                label.setPixmap(pixmap)

        except Exception as e:
            self.logger.error(f"设置GIF动画失败: {e}")
            label.setText("😊")

    def _safe_update_label(self, label, text):
        """
        安全地更新标签文本.
        """
        if label:
            try:
                label.setText(text)
            except RuntimeError as e:
                self.logger.error(f"更新标签失败: {e}")

    async def close(self):
        """
        关闭窗口处理.
        """
        self._running = False
        # 停止并清理GIF资源，避免资源泄漏
        try:
            if getattr(self, "emotion_movie", None) is not None:
                try:
                    self.emotion_movie.stop()
                except Exception:
                    pass
                self.emotion_movie = None
            if hasattr(self, "_gif_movies") and isinstance(self._gif_movies, dict):
                for _m in list(self._gif_movies.values()):
                    try:
                        _m.stop()
                    except Exception:
                        pass
                self._gif_movies.clear()
        except Exception:
            pass
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

            # 安装应用级事件过滤器：支持点击Dock图标时恢复窗口
            try:
                self.app.installEventFilter(self)
            except Exception:
                pass

            # 设置默认字体
            default_font = QFont()
            default_font.setPointSize(12)
            self.app.setFont(default_font)

            # 加载UI
            from PyQt5 import uic

            self.root = QWidget()
            ui_path = Path(__file__).parent / "gui_display.ui"
            uic.loadUi(str(ui_path), self.root)

            # 获取控件并连接事件
            self._init_ui_controls()
            self._connect_events()

            # 初始化系统托盘
            self._setup_system_tray()

            # 设置默认表情
            await self._set_default_emotion()

            # 显示窗口
            self.root.show()

        except Exception as e:
            self.logger.error(f"GUI启动失败: {e}", exc_info=True)
            raise

    def eventFilter(self, obj, event):
        """
        应用级事件过滤：
        - macOS 点击 Dock 图标会触发 ApplicationActivate 事件
        - 当主窗口处于隐藏/最小化时，自动恢复显示
        """
        try:
            # 延迟导入，避免顶层循环依赖
            from PyQt5.QtCore import QEvent
            from PyQt5.QtCore import Qt as _Qt

            if event and event.type() == QEvent.ApplicationActivate:
                if self.root and not self.root.isVisible():
                    self._show_main_window()
        except Exception as e:
            if hasattr(self, "logger"):
                self.logger.error(f"处理应用激活事件失败: {e}")
        return False

    def _init_ui_controls(self):
        """
        初始化UI控件.
        """
        self.status_label = self.root.findChild(QLabel, "status_label")
        self.emotion_label = self.root.findChild(QLabel, "emotion_label")
        self.tts_text_label = self.root.findChild(QLabel, "tts_text_label")
        self.manual_btn = self.root.findChild(QPushButton, "manual_btn")
        self.abort_btn = self.root.findChild(QPushButton, "abort_btn")
        self.auto_btn = self.root.findChild(QPushButton, "auto_btn")
        self.mode_btn = self.root.findChild(QPushButton, "mode_btn")
        self.settings_btn = self.root.findChild(QPushButton, "settings_btn")
        self.text_input = self.root.findChild(QLineEdit, "text_input")
        self.send_btn = self.root.findChild(QPushButton, "send_btn")

    def _connect_events(self):
        """
        连接事件.
        """
        if self.manual_btn:
            self.manual_btn.pressed.connect(self._on_manual_button_press)
            self.manual_btn.released.connect(self._on_manual_button_release)
        if self.abort_btn:
            self.abort_btn.clicked.connect(self._on_abort_button_click)
        if self.auto_btn:
            self.auto_btn.clicked.connect(self._on_auto_button_click)
            self.auto_btn.hide()
        if self.mode_btn:
            self.mode_btn.clicked.connect(self._on_mode_button_click)
        if self.text_input and self.send_btn:
            self.send_btn.clicked.connect(self._on_send_button_click)
            self.text_input.returnPressed.connect(self._on_send_button_click)
        if self.settings_btn:
            self.settings_btn.clicked.connect(self._on_settings_button_click)

        # 设置窗口关闭事件
        self.root.closeEvent = self._closeEvent

        # 快捷键：Ctrl+, 与 Cmd+, 打开设置
        try:
            from PyQt5.QtWidgets import QShortcut
            QShortcut(QKeySequence("Ctrl+,"), self.root, activated=self._on_settings_button_click)
            QShortcut(QKeySequence("Meta+,"), self.root, activated=self._on_settings_button_click)
        except Exception:
            pass

    def _setup_system_tray(self):
        """
        设置系统托盘.
        """
        try:
            # 允许通过环境变量禁用系统托盘用于排障
            if os.getenv("XIAOZHI_DISABLE_TRAY") == "1":
                self.logger.warning("已通过环境变量禁用系统托盘 (XIAOZHI_DISABLE_TRAY=1)")
                return
            from src.views.components.system_tray import SystemTray

            self.system_tray = SystemTray(self.root)
            self.system_tray.show_window_requested.connect(self._show_main_window)
            self.system_tray.settings_requested.connect(self._on_settings_button_click)
            self.system_tray.quit_requested.connect(self._quit_application)

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

                from PyQt5.QtCore import QTimer

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
            # 延迟隐藏，避免在closeEvent中直接操作窗口引发macOS图形栈不稳定
            try:
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(0, self.root.hide)
            except Exception:
                try:
                    self.root.hide()
                except Exception:
                    pass
            # 停止GIF动画，规避隐藏时的潜在崩溃
            try:
                if getattr(self, "emotion_movie", None) is not None:
                    self.emotion_movie.stop()
            except Exception:
                pass
            event.ignore()
        else:
            self._quit_application()
            event.accept()

    def _update_mode_button_status(self, text: str):
        """
        更新模式按钮状态.
        """
        if self.mode_btn:
            self.mode_btn.setText(text)

    async def update_button_status(self, text: str):
        """
        更新按钮状态.
        """
        if self.auto_mode and self.auto_btn:
            self.auto_btn.setText(text)

    def _on_send_button_click(self):
        """
        处理发送文本按钮点击事件.
        """
        if not self.text_input or not self.send_text_callback:
            return

        text = self.text_input.text().strip()
        if not text:
            return

        self.text_input.clear()

        try:
            import asyncio

            task = asyncio.create_task(self.send_text_callback(text))

            def _on_done(t):
                if not t.cancelled() and t.exception():
                    self.logger.error(f"发送文本任务异常: {t.exception()}", exc_info=True)
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
