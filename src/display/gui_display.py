import logging
import os
import platform
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from PyQt5.QtCore import (
    Q_ARG,
    QEvent,
    QMetaObject,
    QObject,
    QPropertyAnimation,
    Qt,
    QThread,
    QTimer,
    pyqtSlot,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QMouseEvent,
    QMovie,
    QPainter,
    QPixmap,
)
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QStyle,
    QStyleOptionSlider,
    QSystemTrayIcon,
    QTabBar,
    QVBoxLayout,
    QWidget,
)

from src.utils.config_manager import ConfigManager

# 根据不同操作系统处理 pynput 导入
try:
    if platform.system() == "Windows":
        from pynput import keyboard as pynput_keyboard
    elif os.environ.get("DISPLAY"):
        from pynput import keyboard as pynput_keyboard
    else:
        pynput_keyboard = None
except ImportError:
    pynput_keyboard = None

from abc import ABCMeta

from src.display.base_display import BaseDisplay


def restart_program():
    """重启当前 Python 程序，支持打包环境。"""
    try:
        python = sys.executable
        print(f"尝试使用以下命令重启: {python} {sys.argv}")

        # 尝试关闭 Qt 应用，虽然 execv 会接管，但这样做更规范
        app = QApplication.instance()
        if app:
            app.quit()

        # 在打包环境中使用不同的重启方法
        if getattr(sys, "frozen", False):
            # 打包环境下，使用subprocess启动新进程
            import subprocess

            # 构建完整的命令行
            if sys.platform.startswith("win"):
                # Windows下使用detached创建独立进程
                executable = os.path.abspath(sys.executable)
                subprocess.Popen(
                    [executable] + sys.argv[1:],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                # Linux/Mac下
                executable = os.path.abspath(sys.executable)
                subprocess.Popen([executable] + sys.argv[1:], start_new_session=True)

            # 退出当前进程
            sys.exit(0)
        else:
            # 非打包环境，使用os.execv
            os.execv(python, [python] + sys.argv)
    except Exception as e:
        print(f"重启程序失败: {e}")
        logging.getLogger("Display").error(f"重启程序失败: {e}", exc_info=True)
        # 如果重启失败，可以选择退出或通知用户
        sys.exit(1)  # 或者弹出一个错误消息框


# 创建兼容的元类
class CombinedMeta(type(QObject), ABCMeta):
    pass


class GuiDisplay(BaseDisplay, QObject, metaclass=CombinedMeta):
    def __init__(self):
        # 重要：调用 super() 处理多重继承
        super().__init__()
        QObject.__init__(self)  # 调用 QObject 初始化

        # 初始化日志
        self.logger = logging.getLogger("Display")

        self.app = None
        self.root = None

        # 一些提前初始化的变量
        self.status_label = None
        self.emotion_label = None
        self.tts_text_label = None
        self.volume_scale = None
        self.manual_btn = None
        self.abort_btn = None
        self.auto_btn = None
        self.mode_btn = None
        self.mute = None
        self.stackedWidget = None
        self.nav_tab_bar = None

        # 添加表情动画对象
        self.emotion_movie = None
        # 新增表情动画特效相关变量
        self.emotion_effect = None  # 表情透明度特效
        self.emotion_animation = None  # 表情动画对象
        self.next_emotion_path = None  # 下一个待显示的表情
        self.is_emotion_animating = False  # 是否正在进行表情切换动画

        # 音量控制相关
        self.volume_label = None  # 音量百分比标签
        self.volume_control_available = False  # 系统音量控制是否可用
        self.volume_controller_failed = False  # 标记音量控制是否失败

        self.is_listening = False  # 是否正在监听

        # 设置页面控件
        self.wakeWordEnableSwitch = None
        self.wakeWordsLineEdit = None
        self.saveSettingsButton = None
        # 新增网络和设备ID控件引用
        self.deviceIdLineEdit = None
        self.wsProtocolComboBox = None
        self.wsAddressLineEdit = None
        self.wsTokenLineEdit = None
        # 新增OTA地址控件引用
        self.otaProtocolComboBox = None
        self.otaAddressLineEdit = None
        # Home Assistant 控件引用
        self.haProtocolComboBox = None
        self.ha_server = None
        self.ha_port = None
        self.ha_key = None
        self.Add_ha_devices = None

        self.is_muted = False
        self.pre_mute_volume = self.current_volume

        # 对话模式标志
        self.auto_mode = False

        # 回调函数
        self.button_press_callback = None
        self.button_release_callback = None
        self.status_update_callback = None
        self.text_update_callback = None
        self.emotion_update_callback = None
        self.mode_callback = None
        self.auto_callback = None
        self.abort_callback = None
        self.send_text_callback = None

        # 更新队列
        self.update_queue = queue.Queue()

        # 运行标志
        self._running = True

        # 键盘监听器
        self.keyboard_listener = None
        # 添加按键状态集合
        self.pressed_keys = set()

        # 滑动手势相关
        self.last_mouse_pos = None

        # 保存定时器引用以避免被销毁
        self.update_timer = None
        self.volume_update_timer = None

        # 动画相关
        self.current_effect = None
        self.current_animation = None
        self.animation = None
        self.fade_widget = None
        self.animated_widget = None

        # 检查系统音量控制是否可用
        self.volume_control_available = (
            hasattr(self, "volume_controller") and self.volume_controller is not None
        )

        # 尝试获取一次系统音量，检测音量控制是否正常工作
        self.get_current_volume()

        # 新增iotPage相关变量
        self.devices_list = []
        self.device_labels = {}
        self.history_title = None
        self.iot_card = None
        self.ha_update_timer = None
        self.device_states = {}

        # 新增系统托盘相关变量
        self.tray_icon = None
        self.tray_menu = None
        self.current_status = ""  # 当前状态，用于判断颜色变化
        self.is_connected = True  # 连接状态标志

    def eventFilter(self, source, event):
        if source == self.volume_scale and event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                slider = self.volume_scale
                opt = QStyleOptionSlider()
                slider.initStyleOption(opt)

                # 获取滑块手柄和轨道的矩形区域
                handle_rect = slider.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, slider
                )
                groove_rect = slider.style().subControlRect(
                    QStyle.CC_Slider, opt, QStyle.SC_SliderGroove, slider
                )

                # 如果点击在手柄上，则让默认处理器处理拖动
                if handle_rect.contains(event.pos()):
                    return False

                # 计算点击位置相对于轨道的位置
                if slider.orientation() == Qt.Horizontal:
                    # 确保点击在有效的轨道范围内
                    if (
                        event.pos().x() < groove_rect.left()
                        or event.pos().x() > groove_rect.right()
                    ):
                        return False  # 点击在轨道外部
                    pos = event.pos().x() - groove_rect.left()
                    max_pos = groove_rect.width()
                else:
                    if (
                        event.pos().y() < groove_rect.top()
                        or event.pos().y() > groove_rect.bottom()
                    ):
                        return False  # 点击在轨道外部
                    pos = groove_rect.bottom() - event.pos().y()
                    max_pos = groove_rect.height()

                if max_pos > 0:  # 避免除以零
                    value_range = slider.maximum() - slider.minimum()
                    # 根据点击位置计算新的值
                    new_value = slider.minimum() + round((value_range * pos) / max_pos)

                    # 直接设置滑块的值
                    slider.setValue(int(new_value))

                    return True  # 表示事件已处理

        return super().eventFilter(source, event)

    def _setup_navigation(self):
        """设置导航标签栏 (QTabBar)"""
        # 使用 addTab 添加标签
        self.nav_tab_bar.addTab("聊天")  # index 0
        self.nav_tab_bar.addTab("设备管理")  # index 1
        self.nav_tab_bar.addTab("参数配置")  # index 2

        # 将 QTabBar 的 currentChanged 信号连接到处理函数
        self.nav_tab_bar.currentChanged.connect(self._on_navigation_index_changed)

        # 设置默认选中项 (通过索引)
        self.nav_tab_bar.setCurrentIndex(0)  # 默认选中第一个标签

    def _on_navigation_index_changed(self, index: int):
        """处理导航标签变化 (通过索引)"""
        # 映射回 routeKey 以便复用动画和加载逻辑
        index_to_routeKey = {
            0: "mainInterface",
            1: "iotInterface",
            2: "settingInterface",
        }
        routeKey = index_to_routeKey.get(index)

        if routeKey is None:
            self.logger.warning(f"未知的导航索引: {index}")
            return

        target_index = index  # 直接使用索引
        if target_index == self.stackedWidget.currentIndex():
            return

        self.stackedWidget.setCurrentIndex(target_index)

        # 如果切换到设置页面，加载设置
        if routeKey == "settingInterface":
            self._load_settings()

        # 如果切换到设备管理页面，加载设备
        if routeKey == "iotInterface":
            self._load_iot_devices()

    def set_callbacks(
        self,
        press_callback: Optional[Callable] = None,
        release_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        text_callback: Optional[Callable] = None,
        emotion_callback: Optional[Callable] = None,
        mode_callback: Optional[Callable] = None,
        auto_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        send_text_callback: Optional[Callable] = None,
    ):
        """设置回调函数."""
        self.button_press_callback = press_callback
        self.button_release_callback = release_callback
        self.status_update_callback = status_callback
        self.text_update_callback = text_callback
        self.emotion_update_callback = emotion_callback
        self.mode_callback = mode_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback
        self.send_text_callback = send_text_callback

        # 在初始化后将状态监听添加到应用程序的状态变化回调中
        # 这样当设备状态变化时，我们可以更新系统托盘图标
        from src.application import Application

        app = Application.get_instance()
        if app:
            app.on_state_changed_callbacks.append(self._on_state_changed)

    def _on_state_changed(self, state):
        """监听设备状态变化."""
        # 设置连接状态标志
        from src.constants.constants import DeviceState

        # 检查是否连接中或已连接
        # (CONNECTING, LISTENING, SPEAKING 表示已连接)
        if state == DeviceState.CONNECTING:
            self.is_connected = True
        elif state in [DeviceState.LISTENING, DeviceState.SPEAKING]:
            self.is_connected = True
        elif state == DeviceState.IDLE:
            # 从应用程序中获取协议实例，检查WebSocket连接状态
            from src.application import Application

            app = Application.get_instance()
            if app and app.protocol:
                # 检查协议是否连接
                self.is_connected = app.protocol.is_audio_channel_opened()
            else:
                self.is_connected = False

        # 更新状态的处理已经在 update_status 方法中完成

    def _process_updates(self):
        """处理更新队列."""
        if not self._running:
            return

        try:
            while True:
                try:
                    # 非阻塞方式获取更新
                    update_func = self.update_queue.get_nowait()
                    update_func()
                    self.update_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            self.logger.error(f"处理更新队列时发生错误: {e}")

    def _on_manual_button_press(self):
        """手动模式按钮按下事件处理."""
        try:
            # 更新按钮文本为"松开以停止"
            if self.manual_btn and self.manual_btn.isVisible():
                self.manual_btn.setText("松开以停止")

            # 调用回调函数
            if self.button_press_callback:
                self.button_press_callback()
        except Exception as e:
            self.logger.error(f"按钮按下回调执行失败: {e}")

    def _on_manual_button_release(self):
        """手动模式按钮释放事件处理."""
        try:
            # 更新按钮文本为"按住后说话"
            if self.manual_btn and self.manual_btn.isVisible():
                self.manual_btn.setText("按住后说话")

            # 调用回调函数
            if self.button_release_callback:
                self.button_release_callback()
        except Exception as e:
            self.logger.error(f"按钮释放回调执行失败: {e}")

    def _on_auto_button_click(self):
        """自动模式按钮点击事件处理."""
        try:
            if self.auto_callback:
                self.auto_callback()
        except Exception as e:
            self.logger.error(f"自动模式按钮回调执行失败: {e}")

    def _on_abort_button_click(self):
        """处理中止按钮点击事件."""
        if self.abort_callback:
            self.abort_callback()

    def _on_mode_button_click(self):
        """对话模式切换按钮点击事件."""
        try:
            # 检查是否可以切换模式（通过回调函数询问应用程序当前状态）
            if self.mode_callback:
                # 如果回调函数返回False，表示当前不能切换模式
                if not self.mode_callback(not self.auto_mode):
                    return

            # 切换模式
            self.auto_mode = not self.auto_mode

            # 更新按钮显示
            if self.auto_mode:
                # 切换到自动模式
                self.update_mode_button_status("自动对话")

                # 隐藏手动按钮，显示自动按钮
                self.update_queue.put(self._switch_to_auto_mode)
            else:
                # 切换到手动模式
                self.update_mode_button_status("手动对话")

                # 隐藏自动按钮，显示手动按钮
                self.update_queue.put(self._switch_to_manual_mode)

        except Exception as e:
            self.logger.error(f"模式切换按钮回调执行失败: {e}")

    def _switch_to_auto_mode(self):
        """切换到自动模式的UI更新."""
        if self.manual_btn and self.auto_btn:
            self.manual_btn.hide()
            self.auto_btn.show()

    def _switch_to_manual_mode(self):
        """切换到手动模式的UI更新."""
        if self.manual_btn and self.auto_btn:
            self.auto_btn.hide()
            self.manual_btn.show()

    def update_status(self, status: str):
        """更新状态文本 (只更新主状态)"""
        full_status_text = f"状态: {status}"
        self.update_queue.put(
            lambda: self._safe_update_label(self.status_label, full_status_text)
        )

        # 更新系统托盘图标
        if status != self.current_status:
            self.current_status = status
            self.update_queue.put(lambda: self._update_tray_icon(status))

    def update_text(self, text: str):
        """更新TTS文本."""
        self.update_queue.put(
            lambda: self._safe_update_label(self.tts_text_label, text)
        )

    def update_emotion(self, emotion_path: str):
        """更新表情动画."""
        # 如果路径相同，不重复设置表情
        if (
            hasattr(self, "_last_emotion_path")
            and self._last_emotion_path == emotion_path
        ):
            return

        # 记录当前设置的路径
        self._last_emotion_path = emotion_path

        # 确保在主线程中处理UI更新
        if QApplication.instance().thread() != QThread.currentThread():
            # 如果不在主线程，使用信号-槽方式或QMetaObject调用在主线程执行
            QMetaObject.invokeMethod(
                self,
                "_update_emotion_safely",
                Qt.QueuedConnection,
                Q_ARG(str, emotion_path),
            )
        else:
            # 已经在主线程，直接执行
            self._update_emotion_safely(emotion_path)

    # 新增一个槽函数，用于在主线程中安全地更新表情
    @pyqtSlot(str)
    def _update_emotion_safely(self, emotion_path: str):
        """在主线程中安全地更新表情，避免线程问题."""
        if self.emotion_label:
            self.logger.info(f"设置表情GIF: {emotion_path}")
            try:
                self._set_emotion_gif(self.emotion_label, emotion_path)
            except Exception as e:
                self.logger.error(f"设置表情GIF时发生错误: {str(e)}")

    def _set_emotion_gif(self, label, gif_path):
        """设置表情GIF动画，带渐变效果."""
        # 基础检查
        if not label or self.root.isHidden():
            return

        # 检查GIF是否已经在当前标签上显示
        if hasattr(label, "current_gif_path") and label.current_gif_path == gif_path:
            return

        # 记录当前GIF路径到标签对象
        label.current_gif_path = gif_path

        try:
            # 如果当前已经设置了相同路径的动画，且正在播放，则不重复设置
            if (
                self.emotion_movie
                and getattr(self.emotion_movie, "_gif_path", None) == gif_path
                and self.emotion_movie.state() == QMovie.Running
            ):
                return

            # 如果正在进行动画，则只记录下一个待显示的表情，等当前动画完成后再切换
            if self.is_emotion_animating:
                self.next_emotion_path = gif_path
                return

            # 标记正在进行动画
            self.is_emotion_animating = True

            # 如果已有动画在播放，先淡出当前动画
            if self.emotion_movie and label.movie() == self.emotion_movie:
                # 创建透明度效果（如果尚未创建）
                if not self.emotion_effect:
                    self.emotion_effect = QGraphicsOpacityEffect(label)
                    label.setGraphicsEffect(self.emotion_effect)
                    self.emotion_effect.setOpacity(1.0)

                # 创建淡出动画
                self.emotion_animation = QPropertyAnimation(
                    self.emotion_effect, b"opacity"
                )
                self.emotion_animation.setDuration(180)  # 设置动画持续时间（毫秒）
                self.emotion_animation.setStartValue(1.0)
                self.emotion_animation.setEndValue(0.25)

                # 当淡出完成后，设置新的GIF并开始淡入
                def on_fade_out_finished():
                    try:
                        # 停止当前GIF
                        if self.emotion_movie:
                            self.emotion_movie.stop()

                        # 设置新的GIF并淡入
                        self._set_new_emotion_gif(label, gif_path)
                    except Exception as e:
                        self.logger.error(f"淡出动画完成后设置GIF失败: {e}")
                        self.is_emotion_animating = False

                # 连接淡出完成信号
                self.emotion_animation.finished.connect(on_fade_out_finished)

                # 开始淡出动画
                self.emotion_animation.start()
            else:
                # 如果没有之前的动画，直接设置新的GIF并淡入
                self._set_new_emotion_gif(label, gif_path)

        except Exception as e:
            self.logger.error(f"更新表情GIF动画失败: {e}")
            # 如果GIF加载失败，尝试显示默认表情
            try:
                label.setText("😊")
            except Exception:
                pass
            self.is_emotion_animating = False

    def _set_new_emotion_gif(self, label, gif_path):
        """设置新的GIF动画并执行淡入效果."""
        try:
            # 维护GIF缓存
            if not hasattr(self, "_gif_cache"):
                self._gif_cache = {}

            # 检查缓存中是否有该GIF
            if gif_path in self._gif_cache:
                movie = self._gif_cache[gif_path]
            else:
                # 记录日志(只在首次加载时记录)
                self.logger.info(f"加载GIF文件: {gif_path}")
                # 创建动画对象
                movie = QMovie(gif_path)
                if not movie.isValid():
                    self.logger.error(f"无效的GIF文件: {gif_path}")
                    label.setText("😊")
                    self.is_emotion_animating = False
                    return

                # 配置动画并存入缓存
                movie.setCacheMode(QMovie.CacheAll)
                self._gif_cache[gif_path] = movie

            # 保存GIF路径到movie对象，用于比较
            movie._gif_path = gif_path

            # 连接信号
            movie.error.connect(
                lambda: self.logger.error(f"GIF播放错误: {movie.lastError()}")
            )

            # 保存新的动画对象
            self.emotion_movie = movie

            # 设置标签大小策略
            label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            label.setAlignment(Qt.AlignCenter)

            # 设置动画到标签
            label.setMovie(movie)

            # 设置QMovie的速度为110，使动画更流畅(默认是100)
            movie.setSpeed(105)

            # 确保不透明度是0（完全透明）
            if self.emotion_effect:
                self.emotion_effect.setOpacity(0.0)
            else:
                self.emotion_effect = QGraphicsOpacityEffect(label)
                label.setGraphicsEffect(self.emotion_effect)
                self.emotion_effect.setOpacity(0.0)

            # 开始播放动画
            movie.start()

            # 创建淡入动画
            self.emotion_animation = QPropertyAnimation(self.emotion_effect, b"opacity")
            self.emotion_animation.setDuration(180)  # 淡入时间（毫秒）
            self.emotion_animation.setStartValue(0.25)
            self.emotion_animation.setEndValue(1.0)

            # 淡入完成后检查是否有下一个待显示的表情
            def on_fade_in_finished():
                self.is_emotion_animating = False
                # 如果有下一个待显示的表情，则继续切换
                if self.next_emotion_path:
                    next_path = self.next_emotion_path
                    self.next_emotion_path = None
                    self._set_emotion_gif(label, next_path)

            # 连接淡入完成信号
            self.emotion_animation.finished.connect(on_fade_in_finished)

            # 开始淡入动画
            self.emotion_animation.start()

        except Exception as e:
            self.logger.error(f"设置新的GIF动画失败: {e}")
            self.is_emotion_animating = False
            # 如果设置失败，尝试显示默认表情
            try:
                label.setText("😊")
            except Exception:
                pass

    def _safe_update_label(self, label, text):
        """安全地更新标签文本."""
        if label and not self.root.isHidden():
            try:
                label.setText(text)
            except RuntimeError as e:
                self.logger.error(f"更新标签失败: {e}")

    def start_update_threads(self):
        """启动更新线程."""
        # 初始化表情缓存
        self.last_emotion_path = None

        def update_loop():
            while self._running:
                try:
                    # 更新状态
                    if self.status_update_callback:
                        status = self.status_update_callback()
                        if status:
                            self.update_status(status)

                    # 更新文本
                    if self.text_update_callback:
                        text = self.text_update_callback()
                        if text:
                            self.update_text(text)

                    # 更新表情 - 只在表情变化时更新
                    if self.emotion_update_callback:
                        emotion = self.emotion_update_callback()
                        if emotion:
                            # 直接调用update_emotion方法，它会处理重复检查
                            self.update_emotion(emotion)

                except Exception as e:
                    self.logger.error(f"更新失败: {e}")
                time.sleep(0.1)

        threading.Thread(target=update_loop, daemon=True).start()

    def on_close(self):
        """关闭窗口处理."""
        self._running = False

        # 确保在主线程中停止定时器
        if QThread.currentThread() != QApplication.instance().thread():
            # 如果在非主线程，使用 QMetaObject.invokeMethod 在主线程中执行
            if self.update_timer:
                QMetaObject.invokeMethod(self.update_timer, "stop", Qt.QueuedConnection)

            if self.ha_update_timer:
                QMetaObject.invokeMethod(
                    self.ha_update_timer, "stop", Qt.QueuedConnection
                )
        else:
            # 已在主线程中，直接停止
            if self.update_timer:
                self.update_timer.stop()

            if self.ha_update_timer:
                self.ha_update_timer.stop()

        if self.tray_icon:
            self.tray_icon.hide()
        if self.root:
            self.root.close()
        self.stop_keyboard_listener()

    def start(self):
        """启动GUI."""
        try:
            # 确保QApplication实例在主线程中创建
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication(sys.argv)

            # 设置UI默认字体
            default_font = QFont("ASLantTermuxFont Mono", 12)
            self.app.setFont(default_font)

            # 加载UI文件
            from PyQt5 import uic

            self.root = QWidget()
            ui_path = Path(__file__).parent / "gui_display.ui"
            if not ui_path.exists():
                self.logger.error(f"UI文件不存在: {ui_path}")
                raise FileNotFoundError(f"UI文件不存在: {ui_path}")

            uic.loadUi(str(ui_path), self.root)

            # 获取UI中的控件
            self.status_label = self.root.findChild(QLabel, "status_label")
            self.emotion_label = self.root.findChild(QLabel, "emotion_label")
            self.tts_text_label = self.root.findChild(QLabel, "tts_text_label")
            self.manual_btn = self.root.findChild(QPushButton, "manual_btn")
            self.abort_btn = self.root.findChild(QPushButton, "abort_btn")
            self.auto_btn = self.root.findChild(QPushButton, "auto_btn")
            self.mode_btn = self.root.findChild(QPushButton, "mode_btn")

            # 添加快捷键提示标签
            try:
                # 查找主界面的布局
                main_page = self.root.findChild(QWidget, "mainPage")
                if main_page:
                    main_layout = main_page.layout()
                    if main_layout:
                        # 创建快捷键提示标签
                        shortcut_label = QLabel(
                            "快捷键：Alt+Shift+V (按住说话) | Alt+Shift+A (自动对话) | "
                            "Alt+Shift+X (打断) | Alt+Shift+M (切换模式)"
                        )

                        shortcut_label.setStyleSheet(
                            """
                            font-size: 10px;
                            color: #666;
                            background-color: #f5f5f5;
                            border-radius: 4px;
                            padding: 3px;
                            margin: 2px;
                        """
                        )
                        shortcut_label.setAlignment(Qt.AlignCenter)
                        # 将标签添加到布局末尾
                        main_layout.addWidget(shortcut_label)
                        self.logger.info("已添加快捷键提示标签")
            except Exception as e:
                self.logger.warning(f"添加快捷键提示标签失败: {e}")

            # 获取IOT页面控件
            self.iot_card = self.root.findChild(
                QFrame, "iotPage"
            )  # 注意这里使用 "iotPage" 作为ID
            if self.iot_card is None:
                # 如果找不到 iotPage，尝试其他可能的名称
                self.iot_card = self.root.findChild(QFrame, "iot_card")
                if self.iot_card is None:
                    # 如果还找不到，尝试在 stackedWidget 中获取第二个页面作为 iot_card
                    self.stackedWidget = self.root.findChild(
                        QStackedWidget, "stackedWidget"
                    )
                    if self.stackedWidget and self.stackedWidget.count() > 1:
                        self.iot_card = self.stackedWidget.widget(
                            1
                        )  # 索引1是第二个页面
                        self.logger.info(
                            f"使用 stackedWidget 的第2个页面作为 iot_card: {self.iot_card}"
                        )
                    else:
                        self.logger.warning("无法找到 iot_card，IOT设备功能将不可用")
            else:
                self.logger.info(f"找到 iot_card: {self.iot_card}")

            # 音量控制组件页面
            self.volume_page = self.root.findChild(QWidget, "volume_page")

            # 音量控制组件
            self.volume_scale = self.root.findChild(QSlider, "volume_scale")
            self.mute = self.root.findChild(QPushButton, "mute")

            if self.mute:
                self.mute.setCheckable(True)
                self.mute.clicked.connect(self._on_mute_click)

            # 获取或创建音量百分比标签
            self.volume_label = self.root.findChild(QLabel, "volume_label")
            if not self.volume_label and self.volume_scale:
                # 如果UI中没有音量标签，动态创建一个
                volume_layout = self.root.findChild(QHBoxLayout, "volume_layout")
                if volume_layout:
                    self.volume_label = QLabel(f"{self.current_volume}%")
                    self.volume_label.setObjectName("volume_label")
                    self.volume_label.setMinimumWidth(40)
                    self.volume_label.setAlignment(Qt.AlignCenter)
                    volume_layout.addWidget(self.volume_label)

            # 根据音量控制可用性设置组件状态
            volume_control_working = (
                self.volume_control_available and not self.volume_controller_failed
            )
            if not volume_control_working:
                self.logger.warning("系统不支持音量控制或控制失败，音量控制功能已禁用")
                # 禁用音量相关控件
                if self.volume_scale:
                    self.volume_scale.setEnabled(False)
                if self.mute:
                    self.mute.setEnabled(False)
                if self.volume_label:
                    self.volume_label.setText("不可用")
            else:
                # 正常设置音量滑块初始值
                if self.volume_scale:
                    self.volume_scale.setRange(0, 100)
                    self.volume_scale.setValue(self.current_volume)
                    self.volume_scale.valueChanged.connect(self._on_volume_change)
                    self.volume_scale.installEventFilter(self)  # 安装事件过滤器
                # 更新音量百分比显示
                if self.volume_label:
                    self.volume_label.setText(f"{self.current_volume}%")

            # 获取设置页面控件
            self.wakeWordEnableSwitch = self.root.findChild(
                QCheckBox, "wakeWordEnableSwitch"
            )
            self.wakeWordsLineEdit = self.root.findChild(QLineEdit, "wakeWordsLineEdit")
            self.saveSettingsButton = self.root.findChild(
                QPushButton, "saveSettingsButton"
            )
            # 获取新增的控件
            # 使用 PyQt 标准控件替换
            self.deviceIdLineEdit = self.root.findChild(QLineEdit, "deviceIdLineEdit")
            self.wsProtocolComboBox = self.root.findChild(
                QComboBox, "wsProtocolComboBox"
            )
            self.wsAddressLineEdit = self.root.findChild(QLineEdit, "wsAddressLineEdit")
            self.wsTokenLineEdit = self.root.findChild(QLineEdit, "wsTokenLineEdit")
            # Home Assistant 控件引用
            self.haProtocolComboBox = self.root.findChild(
                QComboBox, "haProtocolComboBox"
            )
            self.ha_server = self.root.findChild(QLineEdit, "ha_server")
            self.ha_port = self.root.findChild(QLineEdit, "ha_port")
            self.ha_key = self.root.findChild(QLineEdit, "ha_key")
            self.Add_ha_devices = self.root.findChild(QPushButton, "Add_ha_devices")

            # 获取 OTA 相关控件
            self.otaProtocolComboBox = self.root.findChild(
                QComboBox, "otaProtocolComboBox"
            )
            self.otaAddressLineEdit = self.root.findChild(
                QLineEdit, "otaAddressLineEdit"
            )

            # 显式添加 ComboBox 选项，以防 UI 文件加载问题
            if self.wsProtocolComboBox:
                # 先清空，避免重复添加 (如果 .ui 文件也成功加载了选项)
                self.wsProtocolComboBox.clear()
                self.wsProtocolComboBox.addItems(["wss://", "ws://"])

            # 显式添加OTA ComboBox选项
            if self.otaProtocolComboBox:
                self.otaProtocolComboBox.clear()
                self.otaProtocolComboBox.addItems(["https://", "http://"])

            # 显式添加 Home Assistant 协议下拉框选项
            if self.haProtocolComboBox:
                self.haProtocolComboBox.clear()
                self.haProtocolComboBox.addItems(["http://", "https://"])

            # 获取导航控件
            self.stackedWidget = self.root.findChild(QStackedWidget, "stackedWidget")
            self.nav_tab_bar = self.root.findChild(QTabBar, "nav_tab_bar")

            # 初始化导航标签栏
            self._setup_navigation()

            # 连接按钮事件
            if self.manual_btn:
                self.manual_btn.pressed.connect(self._on_manual_button_press)
                self.manual_btn.released.connect(self._on_manual_button_release)
            if self.abort_btn:
                self.abort_btn.clicked.connect(self._on_abort_button_click)
            if self.auto_btn:
                self.auto_btn.clicked.connect(self._on_auto_button_click)
                # 默认隐藏自动模式按钮
                self.auto_btn.hide()
            if self.mode_btn:
                self.mode_btn.clicked.connect(self._on_mode_button_click)

            # 初始化文本输入框和发送按钮
            self.text_input = self.root.findChild(QLineEdit, "text_input")
            self.send_btn = self.root.findChild(QPushButton, "send_btn")
            if self.text_input and self.send_btn:
                self.send_btn.clicked.connect(self._on_send_button_click)
                # 绑定Enter键发送文本
                self.text_input.returnPressed.connect(self._on_send_button_click)

            # 连接设置保存按钮事件
            if self.saveSettingsButton:
                self.saveSettingsButton.clicked.connect(self._save_settings)

            # 连接Home Assistant设备导入按钮事件
            if self.Add_ha_devices:
                self.Add_ha_devices.clicked.connect(self._on_add_ha_devices_click)

            # 设置鼠标事件
            self.root.mousePressEvent = self.mousePressEvent
            self.root.mouseReleaseEvent = self.mouseReleaseEvent

            # 设置窗口关闭事件
            self.root.closeEvent = self._closeEvent

            # 初始化系统托盘
            self._setup_tray_icon()

            # 启动键盘监听
            self.start_keyboard_listener()

            # 启动更新线程
            self.start_update_threads()

            # 定时器处理更新队列
            self.update_timer = QTimer()
            self.update_timer.timeout.connect(self._process_updates)
            self.update_timer.start(100)

            # 在主线程中运行主循环
            self.logger.info("开始启动GUI主循环")
            self.root.show()
            # self.root.showFullScreen() # 全屏显示

        except Exception as e:
            self.logger.error(f"GUI启动失败: {e}", exc_info=True)
            # 尝试回退到CLI模式
            print(f"GUI启动失败: {e}，请尝试使用CLI模式")
            raise

    def _setup_tray_icon(self):
        """设置系统托盘图标."""
        try:
            # 检查系统是否支持系统托盘
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self.logger.warning("系统不支持系统托盘功能")
                return

            # 创建托盘菜单
            self.tray_menu = QMenu()

            # 添加菜单项
            show_action = QAction("显示主窗口", self.root)
            show_action.triggered.connect(self._show_main_window)
            self.tray_menu.addAction(show_action)

            # 添加分隔线
            self.tray_menu.addSeparator()

            # 添加退出菜单项
            quit_action = QAction("退出程序", self.root)
            quit_action.triggered.connect(self._quit_application)
            self.tray_menu.addAction(quit_action)

            # 创建系统托盘图标
            self.tray_icon = QSystemTrayIcon(self.root)
            self.tray_icon.setContextMenu(self.tray_menu)

            # 连接托盘图标的事件
            self.tray_icon.activated.connect(self._tray_icon_activated)

            # 设置初始图标为绿色
            self._update_tray_icon("待命")

            # 显示系统托盘图标
            self.tray_icon.show()
            self.logger.info("系统托盘图标已初始化")

        except Exception as e:
            self.logger.error(f"初始化系统托盘图标失败: {e}", exc_info=True)

    def _update_tray_icon(self, status):
        """根据不同状态更新托盘图标颜色.

        绿色：已启动/待命状态
        黄色：聆听中状态
        蓝色：说话中状态
        红色：错误状态
        灰色：未连接状态
        """
        if not self.tray_icon:
            return

        try:
            icon_color = self._get_status_color(status)

            # 创建指定颜色的图标
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(icon_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(2, 2, 12, 12)
            painter.end()

            # 设置图标
            self.tray_icon.setIcon(QIcon(pixmap))

            # 设置提示文本
            tooltip = f"小智AI助手 - {status}"
            self.tray_icon.setToolTip(tooltip)

        except Exception as e:
            self.logger.error(f"更新系统托盘图标失败: {e}")

    def _get_status_color(self, status):
        """根据状态返回对应的颜色."""
        if not self.is_connected:
            return QColor(128, 128, 128)  # 灰色 - 未连接

        if "错误" in status:
            return QColor(255, 0, 0)  # 红色 - 错误状态

        elif "聆听中" in status:
            return QColor(255, 200, 0)  # 黄色 - 聆听中状态

        elif "说话中" in status:
            return QColor(0, 120, 255)  # 蓝色 - 说话中状态

        else:
            return QColor(0, 180, 0)  # 绿色 - 待命/已启动状态

    def _tray_icon_activated(self, reason):
        """处理托盘图标点击事件."""
        if reason == QSystemTrayIcon.Trigger:  # 单击
            self._show_main_window()

    def _show_main_window(self):
        """显示主窗口."""
        if self.root:
            if self.root.isMinimized():
                self.root.showNormal()
            if not self.root.isVisible():
                self.root.show()
            self.root.activateWindow()
            self.root.raise_()

    def _quit_application(self):
        """退出应用程序."""
        self._running = False
        # 停止所有线程和计时器
        if self.update_timer:
            self.update_timer.stop()

        if self.ha_update_timer:
            self.ha_update_timer.stop()

        # 停止键盘监听
        self.stop_keyboard_listener()

        # 隐藏托盘图标
        if self.tray_icon:
            self.tray_icon.hide()

        # 退出应用程序
        QApplication.quit()

    def _closeEvent(self, event):
        """处理窗口关闭事件."""
        # 最小化到系统托盘而不是退出
        if self.tray_icon and self.tray_icon.isVisible():
            self.root.hide()
            self.tray_icon.showMessage(
                "小智AI助手",
                "程序仍在运行中，点击托盘图标可以重新打开窗口。",
                QSystemTrayIcon.Information,
                2000,
            )
            event.ignore()
        else:
            # 如果系统托盘不可用，则正常关闭
            self._quit_application()
            event.accept()

    def update_mode_button_status(self, text: str):
        """更新模式按钮状态."""
        self.update_queue.put(lambda: self._safe_update_button(self.mode_btn, text))

    def update_button_status(self, text: str):
        """更新按钮状态 - 保留此方法以满足抽象基类要求"""
        # 根据当前模式更新相应的按钮
        if self.auto_mode:
            self.update_queue.put(lambda: self._safe_update_button(self.auto_btn, text))
        else:
            # 在手动模式下，不通过此方法更新按钮文本
            # 因为按钮文本由按下/释放事件直接控制
            pass

    def _safe_update_button(self, button, text):
        """安全地更新按钮文本."""
        if button and not self.root.isHidden():
            try:
                button.setText(text)
            except RuntimeError as e:
                self.logger.error(f"更新按钮失败: {e}")

    def _on_volume_change(self, value):
        """处理音量滑块变化，使用节流."""

        def update_volume():
            self.update_volume(value)

        # 取消之前的定时器
        if (
            hasattr(self, "volume_update_timer")
            and self.volume_update_timer
            and self.volume_update_timer.isActive()
        ):
            self.volume_update_timer.stop()

        # 设置新的定时器，300ms 后更新音量
        self.volume_update_timer = QTimer()
        self.volume_update_timer.setSingleShot(True)
        self.volume_update_timer.timeout.connect(update_volume)
        self.volume_update_timer.start(300)

    def update_volume(self, volume: int):
        """重写父类的update_volume方法，确保UI同步更新."""
        # 检查音量控制是否可用
        if not self.volume_control_available or self.volume_controller_failed:
            return

        # 调用父类的update_volume方法更新系统音量
        super().update_volume(volume)

        # 更新UI音量滑块和标签
        if not self.root.isHidden():
            try:
                if self.volume_scale:
                    self.volume_scale.setValue(volume)
                if self.volume_label:
                    self.volume_label.setText(f"{volume}%")
            except RuntimeError as e:
                self.logger.error(f"更新音量UI失败: {e}")

    def is_combo(self, *keys):
        """判断是否同时按下了一组按键."""
        return all(k in self.pressed_keys for k in keys)

    def start_keyboard_listener(self):
        """启动键盘监听."""
        # 如果 pynput 不可用，记录警告并返回
        if pynput_keyboard is None:
            self.logger.warning(
                "键盘监听不可用：pynput 库未能正确加载。快捷键功能将不可用。"
            )
            return

        try:

            def on_press(key):
                try:
                    # 记录按下的键
                    if (
                        key == pynput_keyboard.Key.alt_l
                        or key == pynput_keyboard.Key.alt_r
                    ):
                        self.pressed_keys.add("alt")
                    elif (
                        key == pynput_keyboard.Key.shift_l
                        or key == pynput_keyboard.Key.shift_r
                    ):
                        self.pressed_keys.add("shift")
                    elif hasattr(key, "char") and key.char:
                        self.pressed_keys.add(key.char.lower())

                    # 长按说话 - 在手动模式下处理
                    if not self.auto_mode and self.is_combo("alt", "shift", "v"):
                        if self.button_press_callback:
                            self.button_press_callback()
                            if self.manual_btn:
                                self.update_queue.put(
                                    lambda: self._safe_update_button(
                                        self.manual_btn, "松开以停止"
                                    )
                                )

                    # 自动对话模式
                    if self.is_combo("alt", "shift", "a"):
                        if self.auto_callback:
                            self.auto_callback()

                    # 打断
                    if self.is_combo("alt", "shift", "x"):
                        if self.abort_callback:
                            self.abort_callback()

                    # 模式切换
                    if self.is_combo("alt", "shift", "m"):
                        self._on_mode_button_click()

                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            def on_release(key):
                try:
                    # 清除释放的键
                    if (
                        key == pynput_keyboard.Key.alt_l
                        or key == pynput_keyboard.Key.alt_r
                    ):
                        self.pressed_keys.discard("alt")
                    elif (
                        key == pynput_keyboard.Key.shift_l
                        or key == pynput_keyboard.Key.shift_r
                    ):
                        self.pressed_keys.discard("shift")
                    elif hasattr(key, "char") and key.char:
                        self.pressed_keys.discard(key.char.lower())

                    # 松开按键，停止语音输入（仅在手动模式下）
                    if not self.auto_mode and not self.is_combo("alt", "shift", "v"):
                        if self.button_release_callback:
                            self.button_release_callback()
                            if self.manual_btn:
                                self.update_queue.put(
                                    lambda: self._safe_update_button(
                                        self.manual_btn, "按住后说话"
                                    )
                                )
                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            # 创建并启动监听器
            self.keyboard_listener = pynput_keyboard.Listener(
                on_press=on_press, on_release=on_release
            )
            self.keyboard_listener.start()
            self.logger.info("键盘监听器初始化成功")
        except Exception as e:
            self.logger.error(f"键盘监听器初始化失败: {e}")

    def stop_keyboard_listener(self):
        """停止键盘监听."""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                self.logger.info("键盘监听器已停止")
            except Exception as e:
                self.logger.error(f"停止键盘监听器失败: {e}")

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件处理."""
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件处理 (修改为使用 QTabBar 索引)"""
        if event.button() == Qt.LeftButton and self.last_mouse_pos is not None:
            delta = event.pos().x() - self.last_mouse_pos.x()
            self.last_mouse_pos = None

            if abs(delta) > 100:  # 滑动阈值
                current_index = (
                    self.nav_tab_bar.currentIndex() if self.nav_tab_bar else 0
                )
                tab_count = self.nav_tab_bar.count() if self.nav_tab_bar else 0

                if delta > 0 and current_index > 0:  # 右滑
                    new_index = current_index - 1
                    if self.nav_tab_bar:
                        self.nav_tab_bar.setCurrentIndex(new_index)
                elif delta < 0 and current_index < tab_count - 1:  # 左滑
                    new_index = current_index + 1
                    if self.nav_tab_bar:
                        self.nav_tab_bar.setCurrentIndex(new_index)

    def _on_mute_click(self):
        """静音按钮点击事件处理 (使用 isChecked 状态)"""
        try:
            if (
                not self.volume_control_available
                or self.volume_controller_failed
                or not self.mute
            ):
                return

            self.is_muted = self.mute.isChecked()  # 获取按钮的选中状态

            if self.is_muted:
                # 保存当前音量并设置为0
                self.pre_mute_volume = self.current_volume
                self.update_volume(0)
                self.mute.setText("取消静音")  # 更新文本
                if self.volume_label:
                    self.volume_label.setText("静音")  # 或者 "0%"
            else:
                # 恢复之前的音量
                self.update_volume(self.pre_mute_volume)
                self.mute.setText("点击静音")  # 恢复文本
                if self.volume_label:
                    self.volume_label.setText(f"{self.pre_mute_volume}%")

        except Exception as e:
            self.logger.error(f"静音按钮点击事件处理失败: {e}")

    def _load_settings(self):
        """加载配置文件并更新设置页面UI (使用ConfigManager)"""
        try:
            # 使用ConfigManager获取配置
            config_manager = ConfigManager.get_instance()

            # 获取唤醒词配置
            use_wake_word = config_manager.get_config(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False
            )
            wake_words = config_manager.get_config("WAKE_WORD_OPTIONS.WAKE_WORDS", [])

            if self.wakeWordEnableSwitch:
                self.wakeWordEnableSwitch.setChecked(use_wake_word)

            if self.wakeWordsLineEdit:
                self.wakeWordsLineEdit.setText(", ".join(wake_words))

            # 获取系统选项
            device_id = config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID", "")
            websocket_url = config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", ""
            )
            websocket_token = config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", ""
            )
            ota_url = config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", ""
            )

            if self.deviceIdLineEdit:
                self.deviceIdLineEdit.setText(device_id)

            # 解析 WebSocket URL 并设置协议和地址
            if websocket_url and self.wsProtocolComboBox and self.wsAddressLineEdit:
                try:
                    parsed_url = urlparse(websocket_url)
                    protocol = parsed_url.scheme

                    # 保留URL末尾的斜杠
                    address = parsed_url.netloc + parsed_url.path

                    # 确保地址不以协议开头
                    if address.startswith(f"{protocol}://"):
                        address = address[len(f"{protocol}://") :]

                    index = self.wsProtocolComboBox.findText(
                        f"{protocol}://", Qt.MatchFixedString
                    )
                    if index >= 0:
                        self.wsProtocolComboBox.setCurrentIndex(index)
                    else:
                        self.logger.warning(f"未知的 WebSocket 协议: {protocol}")
                        self.wsProtocolComboBox.setCurrentIndex(0)  # 默认为 wss

                    self.wsAddressLineEdit.setText(address)
                except Exception as e:
                    self.logger.error(
                        f"解析 WebSocket URL 时出错: {websocket_url} - {e}"
                    )
                    self.wsProtocolComboBox.setCurrentIndex(0)
                    self.wsAddressLineEdit.clear()

            if self.wsTokenLineEdit:
                self.wsTokenLineEdit.setText(websocket_token)

            # 解析OTA URL并设置协议和地址
            if ota_url and self.otaProtocolComboBox and self.otaAddressLineEdit:
                try:
                    parsed_url = urlparse(ota_url)
                    protocol = parsed_url.scheme

                    # 保留URL末尾的斜杠
                    address = parsed_url.netloc + parsed_url.path

                    # 确保地址不以协议开头
                    if address.startswith(f"{protocol}://"):
                        address = address[len(f"{protocol}://") :]

                    if protocol == "https":
                        self.otaProtocolComboBox.setCurrentIndex(0)
                    elif protocol == "http":
                        self.otaProtocolComboBox.setCurrentIndex(1)
                    else:
                        self.logger.warning(f"未知的OTA协议: {protocol}")
                        self.otaProtocolComboBox.setCurrentIndex(0)  # 默认为https

                    self.otaAddressLineEdit.setText(address)
                except Exception as e:
                    self.logger.error(f"解析OTA URL时出错: {ota_url} - {e}")
                    self.otaProtocolComboBox.setCurrentIndex(0)
                    self.otaAddressLineEdit.clear()

            # 加载Home Assistant配置
            ha_options = config_manager.get_config("HOME_ASSISTANT", {})
            ha_url = ha_options.get("URL", "")
            ha_token = ha_options.get("TOKEN", "")

            # 解析Home Assistant URL并设置协议和地址
            if ha_url and self.haProtocolComboBox and self.ha_server:
                try:
                    parsed_url = urlparse(ha_url)
                    protocol = parsed_url.scheme
                    port = parsed_url.port
                    # 地址部分不包含端口
                    address = parsed_url.netloc
                    if ":" in address:  # 如果地址中包含端口号
                        address = address.split(":")[0]

                    # 设置协议
                    if protocol == "https":
                        self.haProtocolComboBox.setCurrentIndex(1)
                    else:  # http或其他协议，默认http
                        self.haProtocolComboBox.setCurrentIndex(0)

                    # 设置地址
                    self.ha_server.setText(address)

                    # 设置端口（如果有）
                    if port and self.ha_port:
                        self.ha_port.setText(str(port))
                except Exception as e:
                    self.logger.error(f"解析Home Assistant URL时出错: {ha_url} - {e}")
                    # 出错时使用默认值
                    self.haProtocolComboBox.setCurrentIndex(0)  # 默认为http
                    self.ha_server.clear()

            # 设置Home Assistant Token
            if self.ha_key:
                self.ha_key.setText(ha_token)

        except Exception as e:
            self.logger.error(f"加载配置文件时出错: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"加载设置失败: {e}")

    def _save_settings(self):
        """保存设置页面的更改到配置文件 (使用ConfigManager)"""
        try:
            # 使用ConfigManager获取实例
            config_manager = ConfigManager.get_instance()

            # 收集所有UI界面上的配置值
            # 唤醒词配置
            use_wake_word = (
                self.wakeWordEnableSwitch.isChecked()
                if self.wakeWordEnableSwitch
                else False
            )
            wake_words_text = (
                self.wakeWordsLineEdit.text() if self.wakeWordsLineEdit else ""
            )
            wake_words = [
                word.strip() for word in wake_words_text.split(",") if word.strip()
            ]

            # 系统选项
            new_device_id = (
                self.deviceIdLineEdit.text() if self.deviceIdLineEdit else ""
            )
            selected_protocol_text = (
                self.wsProtocolComboBox.currentText()
                if self.wsProtocolComboBox
                else "wss://"
            )
            selected_protocol = selected_protocol_text.replace("://", "")
            new_ws_address = (
                self.wsAddressLineEdit.text() if self.wsAddressLineEdit else ""
            )
            new_ws_token = self.wsTokenLineEdit.text() if self.wsTokenLineEdit else ""

            # OTA地址配置
            selected_ota_protocol_text = (
                self.otaProtocolComboBox.currentText()
                if self.otaProtocolComboBox
                else "https://"
            )
            selected_ota_protocol = selected_ota_protocol_text.replace("://", "")
            new_ota_address = (
                self.otaAddressLineEdit.text() if self.otaAddressLineEdit else ""
            )

            # 确保地址不以 / 开头
            if new_ws_address.startswith("/"):
                new_ws_address = new_ws_address[1:]

            # 构造WebSocket URL
            new_websocket_url = f"{selected_protocol}://{new_ws_address}"
            if new_websocket_url and not new_websocket_url.endswith("/"):
                new_websocket_url += "/"

            # 构造OTA URL
            new_ota_url = f"{selected_ota_protocol}://{new_ota_address}"
            if new_ota_url and not new_ota_url.endswith("/"):
                new_ota_url += "/"

            # Home Assistant配置
            ha_protocol = (
                self.haProtocolComboBox.currentText().replace("://", "")
                if self.haProtocolComboBox
                else "http"
            )
            ha_server = self.ha_server.text() if self.ha_server else ""
            ha_port = self.ha_port.text() if self.ha_port else ""
            ha_key = self.ha_key.text() if self.ha_key else ""

            # 构建Home Assistant URL
            if ha_server:
                ha_url = f"{ha_protocol}://{ha_server}"
                if ha_port:
                    ha_url += f":{ha_port}"
            else:
                ha_url = ""

            # 获取完整的当前配置
            current_config = config_manager._config.copy()

            # 通过 ConfigManager 获取最新的设备列表
            try:
                # 重新获取 ConfigManager 实例以确保获取最新配置
                fresh_config_manager = ConfigManager.get_instance()
                latest_devices = fresh_config_manager.get_config(
                    "HOME_ASSISTANT.DEVICES", []
                )
                self.logger.info(f"从配置管理器读取了 {len(latest_devices)} 个设备")
            except Exception as e:
                self.logger.error(f"通过配置管理器读取设备列表失败: {e}")
                # 如果读取失败，使用内存中的设备列表
                if (
                    "HOME_ASSISTANT" in current_config
                    and "DEVICES" in current_config["HOME_ASSISTANT"]
                ):
                    latest_devices = current_config["HOME_ASSISTANT"]["DEVICES"]
                else:
                    latest_devices = []

            # 更新配置对象（不写入文件）
            # 1. 更新唤醒词配置
            if "WAKE_WORD_OPTIONS" not in current_config:
                current_config["WAKE_WORD_OPTIONS"] = {}
            current_config["WAKE_WORD_OPTIONS"]["USE_WAKE_WORD"] = use_wake_word
            current_config["WAKE_WORD_OPTIONS"]["WAKE_WORDS"] = wake_words

            # 2. 更新系统选项
            if "SYSTEM_OPTIONS" not in current_config:
                current_config["SYSTEM_OPTIONS"] = {}
            current_config["SYSTEM_OPTIONS"]["DEVICE_ID"] = new_device_id

            if "NETWORK" not in current_config["SYSTEM_OPTIONS"]:
                current_config["SYSTEM_OPTIONS"]["NETWORK"] = {}
            current_config["SYSTEM_OPTIONS"]["NETWORK"][
                "WEBSOCKET_URL"
            ] = new_websocket_url
            current_config["SYSTEM_OPTIONS"]["NETWORK"][
                "WEBSOCKET_ACCESS_TOKEN"
            ] = new_ws_token
            current_config["SYSTEM_OPTIONS"]["NETWORK"]["OTA_VERSION_URL"] = new_ota_url

            # 3. 更新Home Assistant配置
            if "HOME_ASSISTANT" not in current_config:
                current_config["HOME_ASSISTANT"] = {}
            current_config["HOME_ASSISTANT"]["URL"] = ha_url
            current_config["HOME_ASSISTANT"]["TOKEN"] = ha_key

            # 使用最新的设备列表
            current_config["HOME_ASSISTANT"]["DEVICES"] = latest_devices

            # 一次性保存整个配置
            save_success = config_manager._save_config(current_config)

            if save_success:
                self.logger.info("设置已成功保存到 config.json")
                reply = QMessageBox.question(
                    self.root,
                    "保存成功",
                    "设置已保存。\n部分设置需要重启应用程序才能生效。\n\n是否立即重启？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if reply == QMessageBox.Yes:
                    self.logger.info("用户选择重启应用程序。")
                    restart_program()
            else:
                raise Exception("保存配置文件失败")

        except Exception as e:
            self.logger.error(f"保存设置时发生未知错误: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"保存设置失败: {e}")

    def _on_add_ha_devices_click(self):
        """处理添加Home Assistant设备按钮点击事件."""
        try:
            self.logger.info("启动Home Assistant设备管理器...")

            # 使用resource_finder查找脚本路径
            from src.utils.resource_finder import get_project_root

            project_root = get_project_root()
            script_path = project_root / "src" / "ui" / "ha_device_manager" / "index.py"

            if not script_path.exists():
                self.logger.error(f"设备管理器脚本不存在: {script_path}")
                QMessageBox.critical(self.root, "错误", "设备管理器脚本不存在")
                return

            # 构建命令并执行
            cmd = [sys.executable, str(script_path)]

            # 使用subprocess启动新进程
            import subprocess

            subprocess.Popen(cmd)

        except Exception as e:
            self.logger.error(f"启动Home Assistant设备管理器失败: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"启动设备管理器失败: {e}")

    def _on_send_button_click(self):
        """处理发送文本按钮点击事件."""
        if not self.text_input or not self.send_text_callback:
            return

        text = self.text_input.text().strip()
        if not text:
            return

        # 清空输入框
        self.text_input.clear()

        # 获取应用程序的事件循环并在其中运行协程
        from src.application import Application

        app = Application.get_instance()
        if app and app.loop:
            import asyncio

            asyncio.run_coroutine_threadsafe(self.send_text_callback(text), app.loop)
        else:
            self.logger.error("应用程序实例或事件循环不可用")

    def _load_iot_devices(self):
        """加载并显示Home Assistant设备列表."""
        try:
            # 先清空现有设备列表
            if hasattr(self, "devices_list") and self.devices_list:
                for widget in self.devices_list:
                    widget.deleteLater()
                self.devices_list = []

            # 清空设备状态标签引用
            self.device_labels = {}

            # 获取设备布局
            if self.iot_card:
                # 记录原来的标题文本，以便后面重新设置
                title_text = ""
                if self.history_title:
                    title_text = self.history_title.text()

                # 设置self.history_title为None，以避免在清除旧布局时被删除导致引用错误
                self.history_title = None

                # 获取原布局并删除所有子控件
                old_layout = self.iot_card.layout()
                if old_layout:
                    # 清空布局中的所有控件
                    while old_layout.count():
                        item = old_layout.takeAt(0)
                        widget = item.widget()
                        if widget:
                            widget.deleteLater()

                    # 在现有布局中重新添加控件，而不是创建新布局
                    new_layout = old_layout
                else:
                    # 如果没有现有布局，则创建一个新的
                    new_layout = QVBoxLayout()
                    self.iot_card.setLayout(new_layout)

                # 重置布局属性
                new_layout.setContentsMargins(2, 2, 2, 2)  # 进一步减小外边距
                new_layout.setSpacing(2)  # 进一步减小控件间距

                # 创建标题
                self.history_title = QLabel(title_text)
                self.history_title.setFont(
                    QFont(self.app.font().family(), 12)
                )  # 字体缩小
                self.history_title.setAlignment(Qt.AlignCenter)  # 居中对齐
                self.history_title.setContentsMargins(5, 2, 0, 2)  # 设置标题的边距
                self.history_title.setMaximumHeight(25)  # 减小标题高度
                new_layout.addWidget(self.history_title)

                # 尝试通过 ConfigManager 加载设备列表
                try:
                    config_manager = ConfigManager.get_instance()
                    devices = config_manager.get_config("HOME_ASSISTANT.DEVICES", [])

                    # 更新标题
                    self.history_title.setText(f"已连接设备 ({len(devices)})")

                    # 创建滚动区域
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setFrameShape(QFrame.NoFrame)  # 移除边框
                    scroll_area.setStyleSheet("background: transparent;")  # 透明背景

                    # 创建滚动区域的内容容器
                    container = QWidget()
                    container.setStyleSheet("background: transparent;")  # 透明背景

                    # 创建网格布局，设置顶部对齐
                    grid_layout = QGridLayout(container)
                    grid_layout.setContentsMargins(3, 3, 3, 3)  # 增加外边距
                    grid_layout.setSpacing(8)  # 增加网格间距
                    grid_layout.setAlignment(Qt.AlignTop)  # 设置顶部对齐

                    # 设置网格每行显示的卡片数量
                    cards_per_row = 3  # 每行显示3个设备卡片

                    # 遍历设备并添加到网格布局
                    for i, device in enumerate(devices):
                        entity_id = device.get("entity_id", "")
                        friendly_name = device.get("friendly_name", "")

                        # 解析friendly_name - 提取位置和设备名称
                        location = friendly_name
                        device_name = ""
                        if "," in friendly_name:
                            parts = friendly_name.split(",", 1)
                            location = parts[0].strip()
                            device_name = parts[1].strip()

                        # 创建设备卡片 (使用QFrame替代CardWidget)
                        device_card = QFrame()
                        device_card.setMinimumHeight(90)  # 增加最小高度
                        device_card.setMaximumHeight(150)  # 增加最大高度以适应换行文本
                        device_card.setMinimumWidth(200)  # 增加宽度
                        device_card.setProperty("entity_id", entity_id)  # 存储entity_id
                        # 设置卡片样式 - 轻微背景色，圆角，阴影效果
                        device_card.setStyleSheet(
                            """
                            QFrame {
                                border-radius: 5px;
                                background-color: rgba(255, 255, 255, 0.7);
                                border: none;
                            }
                        """
                        )

                        card_layout = QVBoxLayout(device_card)
                        card_layout.setContentsMargins(10, 8, 10, 8)  # 内边距
                        card_layout.setSpacing(2)  # 控件间距

                        # 设备名称 - 显示在第一行（加粗）并允许换行
                        device_name_label = QLabel(f"<b>{device_name}</b>")
                        device_name_label.setFont(QFont(self.app.font().family(), 14))
                        device_name_label.setWordWrap(True)  # 启用自动换行
                        device_name_label.setMinimumHeight(20)  # 设置最小高度
                        device_name_label.setSizePolicy(
                            QSizePolicy.Expanding, QSizePolicy.Minimum
                        )  # 水平扩展，垂直最小
                        card_layout.addWidget(device_name_label)

                        # 设备位置 - 显示在第二行（不加粗）
                        location_label = QLabel(f"{location}")
                        location_label.setFont(QFont(self.app.font().family(), 12))
                        location_label.setStyleSheet("color: #666666;")
                        card_layout.addWidget(location_label)

                        # 添加分隔线
                        line = QFrame()
                        line.setFrameShape(QFrame.HLine)
                        line.setFrameShadow(QFrame.Sunken)
                        line.setStyleSheet("background-color: #E0E0E0;")
                        line.setMaximumHeight(1)
                        card_layout.addWidget(line)

                        # 设备状态 - 根据设备类型设置不同的默认状态
                        state_text = "未知"
                        if "light" in entity_id:
                            state_text = "关闭"
                            status_display = f"状态: {state_text}"
                        elif "sensor" in entity_id:
                            if "temperature" in entity_id:
                                state_text = "0℃"
                                status_display = state_text
                            elif "humidity" in entity_id:
                                state_text = "0%"
                                status_display = state_text
                            else:
                                state_text = "正常"
                                status_display = f"状态: {state_text}"
                        elif "switch" in entity_id:
                            state_text = "关闭"
                            status_display = f"状态: {state_text}"
                        elif "button" in entity_id:
                            state_text = "可用"
                            status_display = f"状态: {state_text}"
                        else:
                            status_display = state_text

                        # 直接显示状态值
                        state_label = QLabel(status_display)
                        state_label.setFont(QFont(self.app.font().family(), 14))
                        state_label.setStyleSheet(
                            "color: #2196F3; border: none;"
                        )  # 添加无边框样式
                        card_layout.addWidget(state_label)

                        # 保存状态标签引用
                        self.device_labels[entity_id] = state_label

                        # 计算行列位置
                        row = i // cards_per_row
                        col = i % cards_per_row

                        # 将卡片添加到网格布局
                        grid_layout.addWidget(device_card, row, col)

                        # 保存引用以便后续清理
                        self.devices_list.append(device_card)

                    # 设置滚动区域内容
                    container.setLayout(grid_layout)
                    scroll_area.setWidget(container)

                    # 将滚动区域添加到主布局
                    new_layout.addWidget(scroll_area)

                    # 设置滚动区域样式
                    scroll_area.setStyleSheet(
                        """
                        QScrollArea {
                            border: none;
                            background-color: transparent;
                        }
                        QScrollBar:vertical {
                            border: none;
                            background-color: #F5F5F5;
                            width: 8px;
                            border-radius: 4px;
                        }
                        QScrollBar::handle:vertical {
                            background-color: #BDBDBD;
                            border-radius: 4px;
                        }
                        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                            height: 0px;
                        }
                    """
                    )

                    # 停止现有的更新定时器（如果存在）
                    if self.ha_update_timer and self.ha_update_timer.isActive():
                        self.ha_update_timer.stop()

                    # 创建并启动一个定时器，每1秒更新一次设备状态
                    self.ha_update_timer = QTimer()
                    self.ha_update_timer.timeout.connect(self._update_device_states)
                    self.ha_update_timer.start(1000)  # 1秒更新一次

                    # 立即执行一次更新
                    self._update_device_states()

                except Exception as e:
                    # 如果加载设备失败，创建一个错误提示布局
                    self.logger.error(f"读取设备配置失败: {e}")
                    self.history_title = QLabel("加载设备配置失败")
                    self.history_title.setFont(
                        QFont(self.app.font().family(), 14, QFont.Bold)
                    )
                    self.history_title.setAlignment(Qt.AlignCenter)
                    new_layout.addWidget(self.history_title)

                    error_label = QLabel(f"错误信息: {str(e)}")
                    error_label.setWordWrap(True)
                    error_label.setStyleSheet("color: red;")
                    new_layout.addWidget(error_label)

        except Exception as e:
            self.logger.error(f"加载IOT设备失败: {e}", exc_info=True)
            try:
                # 在发生错误时尝试恢复界面
                old_layout = self.iot_card.layout()

                # 如果已有布局，清空它
                if old_layout:
                    while old_layout.count():
                        item = old_layout.takeAt(0)
                        widget = item.widget()
                        if widget:
                            widget.deleteLater()

                    # 使用现有布局
                    new_layout = old_layout
                else:
                    # 创建新布局
                    new_layout = QVBoxLayout()
                    self.iot_card.setLayout(new_layout)

                self.history_title = QLabel("加载设备失败")
                self.history_title.setFont(
                    QFont(self.app.font().family(), 14, QFont.Bold)
                )
                self.history_title.setAlignment(Qt.AlignCenter)
                new_layout.addWidget(self.history_title)

                error_label = QLabel(f"错误信息: {str(e)}")
                error_label.setWordWrap(True)
                error_label.setStyleSheet("color: red;")
                new_layout.addWidget(error_label)

            except Exception as e2:
                self.logger.error(f"恢复界面失败: {e2}", exc_info=True)

    def _update_device_states(self):
        """更新Home Assistant设备状态."""
        # 检查当前是否在IOT界面
        if not self.stackedWidget or self.stackedWidget.currentIndex() != 1:
            return

        # 通过 ConfigManager 获取Home Assistant连接信息
        try:
            config_manager = ConfigManager.get_instance()
            ha_url = config_manager.get_config("HOME_ASSISTANT.URL", "")
            ha_token = config_manager.get_config("HOME_ASSISTANT.TOKEN", "")

            if not ha_url or not ha_token:
                self.logger.warning("Home Assistant URL或Token未配置，无法更新设备状态")
                return

            # 为每个设备查询状态
            for entity_id, label in self.device_labels.items():
                threading.Thread(
                    target=self._fetch_device_state,
                    args=(ha_url, ha_token, entity_id, label),
                    daemon=True,
                ).start()

        except Exception as e:
            self.logger.error(f"更新Home Assistant设备状态失败: {e}", exc_info=True)

    def _fetch_device_state(self, ha_url, ha_token, entity_id, label):
        """获取单个设备的状态."""
        import requests

        try:
            # 构造API请求URL
            api_url = f"{ha_url}/api/states/{entity_id}"
            headers = {
                "Authorization": f"Bearer {ha_token}",
                "Content-Type": "application/json",
            }

            # 发送请求
            response = requests.get(api_url, headers=headers, timeout=5)

            if response.status_code == 200:
                state_data = response.json()
                state = state_data.get("state", "unknown")

                # 更新设备状态
                self.device_states[entity_id] = state

                # 更新UI
                self._update_device_ui(entity_id, state, label)
            else:
                self.logger.warning(
                    f"获取设备状态失败: {entity_id}, 状态码: {response.status_code}"
                )

        except requests.RequestException as e:
            self.logger.error(f"请求Home Assistant API失败: {e}")
        except Exception as e:
            self.logger.error(f"处理设备状态时出错: {e}")

    def _update_device_ui(self, entity_id, state, label):
        """更新设备UI显示."""
        # 在主线程中执行UI更新
        self.update_queue.put(
            lambda: self._safe_update_device_label(entity_id, state, label)
        )

    def _safe_update_device_label(self, entity_id, state, label):
        """安全地更新设备状态标签."""
        if not label or self.root.isHidden():
            return

        try:
            display_state = state  # 默认显示原始状态

            # 根据设备类型格式化状态显示
            if "light" in entity_id or "switch" in entity_id:
                if state == "on":
                    display_state = "状态: 开启"
                    label.setStyleSheet(
                        "color: #4CAF50; border: none;"
                    )  # 绿色表示开启，无边框
                else:
                    display_state = "状态: 关闭"
                    label.setStyleSheet(
                        "color: #9E9E9E; border: none;"
                    )  # 灰色表示关闭，无边框
            elif "temperature" in entity_id:
                try:
                    temp = float(state)
                    display_state = f"{temp:.1f}℃"
                    label.setStyleSheet(
                        "color: #FF9800; border: none;"
                    )  # 橙色表示温度，无边框
                except ValueError:
                    display_state = state
            elif "humidity" in entity_id:
                try:
                    humidity = float(state)
                    display_state = f"{humidity:.0f}%"
                    label.setStyleSheet(
                        "color: #03A9F4; border: none;"
                    )  # 浅蓝色表示湿度，无边框
                except ValueError:
                    display_state = state
            elif "battery" in entity_id:
                try:
                    battery = float(state)
                    display_state = f"{battery:.0f}%"
                    # 根据电池电量设置不同颜色
                    if battery < 20:
                        label.setStyleSheet(
                            "color: #F44336; border: none;"
                        )  # 红色表示低电量，无边框
                    else:
                        label.setStyleSheet(
                            "color: #4CAF50; border: none;"
                        )  # 绿色表示正常电量，无边框
                except ValueError:
                    display_state = state
            else:
                display_state = f"状态: {state}"
                label.setStyleSheet("color: #2196F3; border: none;")  # 默认颜色，无边框

            # 显示状态值
            label.setText(f"{display_state}")
        except RuntimeError as e:
            self.logger.error(f"更新设备状态标签失败: {e}")
