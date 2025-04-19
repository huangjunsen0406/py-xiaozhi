import threading
import queue
import logging
import time
import sys
import json
import os
import math
import numpy as np
from typing import Optional, Callable
from urllib.parse import urlparse, urlunparse
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QGraphicsOpacityEffect,
    QDesktopWidget,
    QSizePolicy,
    QMessageBox,
    QLineEdit,
    QComboBox,
    QFrame,
    QStackedWidget,
    QCheckBox,
    QTabBar
)
from PyQt5.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QRect
from PyQt5.QtGui import QMouseEvent, QPainter, QColor, QPen, QBrush, QFont, QIcon
from pynput import keyboard as pynput_keyboard
from src.display.base_display import BaseDisplay
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.json"

def restart_program():
    """使用 os.execv 重启当前 Python 程序。"""
    try:
        python = sys.executable
        print(f"Attempting to restart with: {python} {sys.argv}")
        # 尝试关闭 Qt 应用，虽然 execv 会接管，但这样做更规范
        app = QApplication.instance()
        if app:
            app.quit()
        # 替换当前进程
        os.execv(python, [python] + sys.argv)
    except Exception as e:
        print(f"重启程序失败: {e}")
        logging.getLogger("Display").error(f"重启程序失败: {e}", exc_info=True)
        # 如果重启失败，可以选择退出或通知用户
        sys.exit(1) # 或者弹出一个错误消息框

class GuiDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()  # 调用父类初始化

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
        
        # 音量控制相关
        self.volume_label = None  # 音量百分比标签
        self.volume_control_available = False  # 系统音量控制是否可用
        self.volume_controller_failed = False  # 标记音量控制是否失败
        
        # 麦克风可视化相关
        self.mic_visualizer = None  # 麦克风可视化组件
        self.mic_timer = None  # 麦克风音量更新定时器
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

        # 更新队列
        self.update_queue = queue.Queue()

        # 运行标志
        self._running = True

        # 键盘监听器
        self.keyboard_listener = None

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
        self.volume_control_available = hasattr(self, 'volume_controller') and self.volume_controller is not None
        
        # 尝试获取一次系统音量，检测音量控制是否正常工作
        self.get_current_volume()

    def _setup_navigation(self):
        """设置导航标签栏 (QTabBar)"""
        # 使用 addTab 添加标签
        self.nav_tab_bar.addTab("聊天")  # index 0
        self.nav_tab_bar.addTab("设备")  # index 1
        self.nav_tab_bar.addTab("设置")  # index 2

        # 将 QTabBar 的 currentChanged 信号连接到处理函数
        self.nav_tab_bar.currentChanged.connect(self._on_navigation_index_changed)

        # 设置默认选中项 (通过索引)
        self.nav_tab_bar.setCurrentIndex(0) # 默认选中第一个标签

    def _on_navigation_index_changed(self, index: int):
        """处理导航标签变化 (通过索引)"""
        # 映射回 routeKey 以便复用动画和加载逻辑
        index_to_routeKey = {0: "mainInterface", 1: "iotInterface", 2: "settingInterface"}
        routeKey = index_to_routeKey.get(index)

        if routeKey is None:
            self.logger.warning(f"未知的导航索引: {index}")
            return

        target_index = index # 直接使用索引
        if target_index == self.stackedWidget.currentIndex():
            return

        current_widget = self.stackedWidget.currentWidget()
        self.stackedWidget.setCurrentIndex(target_index)
        new_widget = self.stackedWidget.currentWidget()

        self.animated_widget = new_widget
        self.current_effect = QGraphicsOpacityEffect(self.animated_widget)
        self.current_animation = QPropertyAnimation(self.current_effect, b"opacity")
        self.animated_widget.setGraphicsEffect(self.current_effect)
        self.current_animation.setDuration(300)
        self.current_animation.setStartValue(0.0)
        self.current_animation.setEndValue(1.0)

        def cleanup():
            try:
                effect_to_clean = getattr(self, "current_effect", None)
                widget_to_clean = getattr(self, "animated_widget", None)
                if widget_to_clean and widget_to_clean.isWidgetType():
                     if widget_to_clean.graphicsEffect() == effect_to_clean:
                         widget_to_clean.setGraphicsEffect(None)
                self.current_effect = None
                self.current_animation = None
                self.animated_widget = None
            except RuntimeError as e:
                self.logger.warning(f"清理动画时捕获 RuntimeError: {e}")
                self.current_effect = None
                self.current_animation = None
                self.animated_widget = None
            except Exception as e:
                self.logger.error(f"清理动画时发生意外错误: {e}", exc_info=True)
                self.current_effect = None
                self.current_animation = None
                self.animated_widget = None

        self.current_animation.finished.connect(cleanup)
        self.current_animation.start()

        # 如果切换到设置页面，加载设置
        if routeKey == "settingInterface":
            self._load_settings()

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
    ):
        """设置回调函数"""
        self.button_press_callback = press_callback
        self.button_release_callback = release_callback
        self.status_update_callback = status_callback
        self.text_update_callback = text_callback
        self.emotion_update_callback = emotion_callback
        self.mode_callback = mode_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback

    def _process_updates(self):
        """处理更新队列"""
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
        """手动模式按钮按下事件处理"""
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
        """手动模式按钮释放事件处理"""
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
        """自动模式按钮点击事件处理"""
        try:
            if self.auto_callback:
                self.auto_callback()
        except Exception as e:
            self.logger.error(f"自动模式按钮回调执行失败: {e}")

    def _on_abort_button_click(self):
        """打断按钮点击事件处理"""
        try:
            if self.abort_callback:
                self.abort_callback()
        except Exception as e:
            self.logger.error(f"打断按钮回调执行失败: {e}")

    def _on_mode_button_click(self):
        """对话模式切换按钮点击事件"""
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
        """切换到自动模式的UI更新"""
        if self.manual_btn and self.auto_btn:
            self.manual_btn.hide()
            self.auto_btn.show()

    def _switch_to_manual_mode(self):
        """切换到手动模式的UI更新"""
        if self.manual_btn and self.auto_btn:
            self.auto_btn.hide()
            self.manual_btn.show()

    def update_status(self, status: str):
        """更新状态文本 (只更新主状态)"""
        full_status_text = f"状态: {status}"
        self.update_queue.put(lambda: self._safe_update_label(self.status_label, full_status_text))
        
        # 根据状态更新麦克风可视化
        if "聆听中" in status:
            self.update_queue.put(self._start_mic_visualization)
        elif "待命" in status or "说话中" in status:
            self.update_queue.put(self._stop_mic_visualization)

    def update_text(self, text: str):
        """更新TTS文本"""
        self.update_queue.put(lambda: self._safe_update_label(self.tts_text_label, text))

    def update_emotion(self, emotion: str):
        """更新表情"""
        self.update_queue.put(lambda: self._safe_update_label(self.emotion_label, emotion))
        
    def _safe_update_label(self, label, text):
        """安全地更新标签文本"""
        if label and not self.root.isHidden():
            try:
                label.setText(text)
            except RuntimeError as e:
                self.logger.error(f"更新标签失败: {e}")

    def start_update_threads(self):
        """启动更新线程"""

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

                    # 更新表情
                    if self.emotion_update_callback:
                        emotion = self.emotion_update_callback()
                        if emotion:
                            self.update_emotion(emotion)

                except Exception as e:
                    self.logger.error(f"更新失败: {e}")
                time.sleep(0.1)

        threading.Thread(target=update_loop, daemon=True).start()

    def on_close(self):
        """关闭窗口处理"""
        self._running = False
        if self.update_timer:
            self.update_timer.stop()
        if self.mic_timer:
            self.mic_timer.stop()
        if self.root:
            self.root.close()
        self.stop_keyboard_listener()

    def start(self):
        """启动GUI"""
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
            
            # 音频控制栈组件
            self.audio_control_stack = self.root.findChild(QStackedWidget, "audio_control_stack")
            self.volume_page = self.root.findChild(QWidget, "volume_page")
            self.mic_page = self.root.findChild(QWidget, "mic_page")
            
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
            
            # 初始化麦克风可视化组件 - 使用UI中定义的QFrame
            self.mic_visualizer_card = self.root.findChild(QFrame, "mic_visualizer_card")
            self.mic_visualizer_widget = self.root.findChild(QWidget, "mic_visualizer_widget")
            
            if self.mic_visualizer_widget:
                # 创建可视化组件实例
                self.mic_visualizer = MicrophoneVisualizer(self.mic_visualizer_widget)
                
                # 设置布局以使可视化组件填充整个区域
                layout = QVBoxLayout(self.mic_visualizer_widget)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.addWidget(self.mic_visualizer)
                
                # 创建更新定时器，但不启动
                self.mic_timer = QTimer()
                self.mic_timer.timeout.connect(self._update_mic_visualizer)
            
            # 根据音量控制可用性设置组件状态
            volume_control_working = self.volume_control_available and not self.volume_controller_failed
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
                # 更新音量百分比显示
                if self.volume_label:
                    self.volume_label.setText(f"{self.current_volume}%")
            
            # 获取设置页面控件
            self.wakeWordEnableSwitch = self.root.findChild(QCheckBox, "wakeWordEnableSwitch")
            self.wakeWordsLineEdit = self.root.findChild(QLineEdit, "wakeWordsLineEdit")
            self.saveSettingsButton = self.root.findChild(QPushButton, "saveSettingsButton")
            # 获取新增的控件
            self.deviceIdLineEdit = self.root.findChild(QLineEdit, "deviceIdLineEdit")
            self.wsProtocolComboBox = self.root.findChild(QComboBox, "wsProtocolComboBox")
            self.wsAddressLineEdit = self.root.findChild(QLineEdit, "wsAddressLineEdit")
            self.wsTokenLineEdit = self.root.findChild(QLineEdit, "wsTokenLineEdit")

            # 显式添加 ComboBox 选项，以防 UI 文件加载问题
            if self.wsProtocolComboBox:
                # 先清空，避免重复添加 (如果 .ui 文件也成功加载了选项)
                self.wsProtocolComboBox.clear()
                self.wsProtocolComboBox.addItems(["wss://", "ws://"])

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

            # 连接设置保存按钮事件
            if self.saveSettingsButton:
                self.saveSettingsButton.clicked.connect(self._save_settings)

            # 设置鼠标事件
            self.root.mousePressEvent = self.mousePressEvent
            self.root.mouseReleaseEvent = self.mouseReleaseEvent

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

    def update_mode_button_status(self, text: str):
        """更新模式按钮状态"""
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
        """安全地更新按钮文本"""
        if button and not self.root.isHidden():
            try:
                button.setText(text)
            except RuntimeError as e:
                self.logger.error(f"更新按钮失败: {e}")

    def _on_volume_change(self, value):
        """处理音量滑块变化，使用节流"""

        def update_volume():
            self.update_volume(value)

        # 取消之前的定时器
        if hasattr(self, "volume_update_timer") and self.volume_update_timer and self.volume_update_timer.isActive():
            self.volume_update_timer.stop()

        # 设置新的定时器，300ms 后更新音量
        self.volume_update_timer = QTimer()
        self.volume_update_timer.setSingleShot(True)
        self.volume_update_timer.timeout.connect(update_volume)
        self.volume_update_timer.start(300)

    def update_volume(self, volume: int):
        """重写父类的update_volume方法，确保UI同步更新"""
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

    def start_keyboard_listener(self):
        """启动键盘监听"""
        try:

            def on_press(key):
                try:
                    # F2 按键处理 - 在手动模式下处理
                    if key == pynput_keyboard.Key.f2 and not self.auto_mode:
                        if self.button_press_callback:
                            self.button_press_callback()
                            if self.manual_btn:
                                self.update_queue.put(lambda: self._safe_update_button(self.manual_btn, "松开以停止"))

                    # F3 按键处理 - 打断
                    elif key == pynput_keyboard.Key.f3:
                        if self.abort_callback:
                            self.abort_callback()
                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            def on_release(key):
                try:
                    # F2 释放处理 - 在手动模式下处理
                    if key == pynput_keyboard.Key.f2 and not self.auto_mode:
                        if self.button_release_callback:
                            self.button_release_callback()
                            if self.manual_btn:
                                self.update_queue.put(lambda: self._safe_update_button(self.manual_btn, "按住后说话"))
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
        """停止键盘监听"""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                self.logger.info("键盘监听器已停止")
            except Exception as e:
                self.logger.error(f"停止键盘监听器失败: {e}")

    def mousePressEvent(self, event: QMouseEvent):
        """鼠标按下事件处理"""
        if event.button() == Qt.LeftButton:
            self.last_mouse_pos = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent):
        """鼠标释放事件处理 (修改为使用 QTabBar 索引)"""
        if event.button() == Qt.LeftButton and self.last_mouse_pos is not None:
            delta = event.pos().x() - self.last_mouse_pos.x()
            self.last_mouse_pos = None

            if abs(delta) > 100:  # 滑动阈值
                current_index = self.nav_tab_bar.currentIndex() if self.nav_tab_bar else 0
                tab_count = self.nav_tab_bar.count() if self.nav_tab_bar else 0

                if delta > 0 and current_index > 0:  # 右滑
                    new_index = current_index - 1
                    if self.nav_tab_bar: self.nav_tab_bar.setCurrentIndex(new_index)
                elif delta < 0 and current_index < tab_count - 1:  # 左滑
                    new_index = current_index + 1
                    if self.nav_tab_bar: self.nav_tab_bar.setCurrentIndex(new_index)

    def _on_mute_click(self):
        """静音按钮点击事件处理 (使用 isChecked 状态)"""
        try:
            if not self.volume_control_available or self.volume_controller_failed or not self.mute:
                return

            self.is_muted = self.mute.isChecked() # 获取按钮的选中状态

            if self.is_muted:
                # 保存当前音量并设置为0
                self.pre_mute_volume = self.current_volume
                self.update_volume(0)
                self.mute.setText("取消静音") # 更新文本
                if self.volume_label:
                    self.volume_label.setText("静音") # 或者 "0%"
            else:
                # 恢复之前的音量
                self.update_volume(self.pre_mute_volume)
                self.mute.setText("点击静音") # 恢复文本
                if self.volume_label:
                    self.volume_label.setText(f"{self.pre_mute_volume}%")

        except Exception as e:
            self.logger.error(f"静音按钮点击事件处理失败: {e}")

    def _load_settings(self):
        """加载配置文件并更新设置页面UI (使用标准控件方法)"""
        try:
            if not CONFIG_PATH.exists():
                self.logger.warning(f"配置文件 {CONFIG_PATH} 不存在，无法加载设置。")
                QMessageBox.warning(self.root, "错误", f"配置文件 {CONFIG_PATH} 不存在。")
                return

            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            wake_word_options = config_data.get("WAKE_WORD_OPTIONS", {})
            use_wake_word = wake_word_options.get("USE_WAKE_WORD", False)
            wake_words = wake_word_options.get("WAKE_WORDS", [])

            if self.wakeWordEnableSwitch:
                self.wakeWordEnableSwitch.setChecked(use_wake_word)

            if self.wakeWordsLineEdit:
                self.wakeWordsLineEdit.setText(", ".join(wake_words))

            # 加载系统选项 (逻辑不变)
            system_options = config_data.get("SYSTEM_OPTIONS", {})
            device_id = system_options.get("DEVICE_ID", "")
            network_options = system_options.get("NETWORK", {})
            websocket_url = network_options.get("WEBSOCKET_URL", "")
            websocket_token = network_options.get("WEBSOCKET_ACCESS_TOKEN", "")

            if self.deviceIdLineEdit:
                self.deviceIdLineEdit.setText(device_id)

            # 解析 WebSocket URL 并设置协议和地址 
            if websocket_url and self.wsProtocolComboBox and self.wsAddressLineEdit:
                try:
                    parsed_url = urlparse(websocket_url)
                    protocol = parsed_url.scheme
                    address = parsed_url.netloc + parsed_url.path
                    if address.endswith('/'):
                       address = address[:-1]

                    index = self.wsProtocolComboBox.findText(f"{protocol}://", Qt.MatchFixedString)
                    if index >= 0:
                        self.wsProtocolComboBox.setCurrentIndex(index)
                    else:
                         self.logger.warning(f"未知的 WebSocket 协议: {protocol}")
                         self.wsProtocolComboBox.setCurrentIndex(0) # 默认为 wss

                    self.wsAddressLineEdit.setText(address)
                except Exception as e:
                    self.logger.error(f"解析 WebSocket URL 时出错: {websocket_url} - {e}")
                    self.wsProtocolComboBox.setCurrentIndex(0)
                    self.wsAddressLineEdit.clear()

            if self.wsTokenLineEdit:
                self.wsTokenLineEdit.setText(websocket_token)

        except json.JSONDecodeError:
            self.logger.error(f"配置文件 {CONFIG_PATH} 格式错误。", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"配置文件 {CONFIG_PATH} 格式错误。")
        except Exception as e:
            self.logger.error(f"加载配置文件时出错: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"加载设置失败: {e}")

    def _save_settings(self):
        """保存设置页面的更改到配置文件 (使用标准控件方法)"""
        try:
            if not CONFIG_PATH.exists():
                self.logger.error(f"配置文件 {CONFIG_PATH} 不存在，无法保存设置。")
                QMessageBox.critical(self.root, "错误", f"配置文件 {CONFIG_PATH} 不存在。")
                return

            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            use_wake_word = self.wakeWordEnableSwitch.isChecked() if self.wakeWordEnableSwitch else False
            wake_words_text = self.wakeWordsLineEdit.text() if self.wakeWordsLineEdit else ""
            wake_words = [word.strip() for word in wake_words_text.split(',') if word.strip()]

            # 更新配置字典
            if "WAKE_WORD_OPTIONS" not in config_data: config_data["WAKE_WORD_OPTIONS"] = {}
            config_data["WAKE_WORD_OPTIONS"]["USE_WAKE_WORD"] = use_wake_word
            config_data["WAKE_WORD_OPTIONS"]["WAKE_WORDS"] = wake_words

            # 获取并更新系统选项 (使用 QLineEdit, QComboBox)
            new_device_id = self.deviceIdLineEdit.text() if self.deviceIdLineEdit else ""
            selected_protocol_text = self.wsProtocolComboBox.currentText() if self.wsProtocolComboBox else "wss://"
            selected_protocol = selected_protocol_text.replace("://","")
            new_ws_address = self.wsAddressLineEdit.text() if self.wsAddressLineEdit else ""
            new_ws_token = self.wsTokenLineEdit.text() if self.wsTokenLineEdit else ""

            # 构造 URL (逻辑不变)
            if new_ws_address.startswith('/'): new_ws_address = new_ws_address[1:]
            if not new_ws_address.endswith('/') and new_ws_address: new_ws_address += '/'
            url_parts = urlparse(f"http://{new_ws_address}")
            new_websocket_url = urlunparse((selected_protocol, url_parts.netloc, url_parts.path, '', '', ''))

            # 更新系统选项
            if "SYSTEM_OPTIONS" not in config_data: config_data["SYSTEM_OPTIONS"] = {}
            config_data["SYSTEM_OPTIONS"]["DEVICE_ID"] = new_device_id
            if "NETWORK" not in config_data["SYSTEM_OPTIONS"]: config_data["SYSTEM_OPTIONS"]["NETWORK"] = {}
            config_data["SYSTEM_OPTIONS"]["NETWORK"]["WEBSOCKET_URL"] = new_websocket_url
            config_data["SYSTEM_OPTIONS"]["NETWORK"]["WEBSOCKET_ACCESS_TOKEN"] = new_ws_token

            # 写回配置文件
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)

            self.logger.info("设置已成功保存到 config.json")
            reply = QMessageBox.question(self.root, "保存成功",
                                       "设置已保存。\n部分设置需要重启应用程序才能生效。\n\n是否立即重启？",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

            if reply == QMessageBox.Yes:
                self.logger.info("用户选择重启应用程序。")
                restart_program()

        except json.JSONDecodeError:
            self.logger.error(f"读取配置文件 {CONFIG_PATH} 时格式错误。", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"读取配置文件 {CONFIG_PATH} 格式错误，无法保存。")
        except IOError as e:
            self.logger.error(f"写入配置文件 {CONFIG_PATH} 时出错: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"保存设置失败，无法写入文件: {e}")
        except Exception as e:
            self.logger.error(f"保存设置时发生未知错误: {e}", exc_info=True)
            QMessageBox.critical(self.root, "错误", f"保存设置失败: {e}")

    def _update_mic_visualizer(self):
        """更新麦克风可视化"""
        if not self.is_listening or not self.mic_visualizer:
            return
            
        try:
            # 获取当前麦克风音量级别，范围0-1
            volume_level = self._get_current_mic_level()
                
            # 更新可视化组件
            self.mic_visualizer.set_volume(min(1.0, volume_level))
        except Exception as e:
            self.logger.error(f"更新麦克风可视化失败: {e}")
    
    def _get_current_mic_level(self):
        """获取当前麦克风音量级别"""
        try:
            from src.application import Application
            app = Application.get_instance()
            if app and hasattr(app, 'audio_codec') and app.audio_codec:
                # 从音频编解码器获取原始音频数据
                if hasattr(app.audio_codec, 'input_stream') and app.audio_codec.input_stream:
                    # 读取音频数据并计算音量级别
                    try:
                        # 获取输入流中可读取的数据量
                        available = app.audio_codec.input_stream.get_read_available()
                        if available > 0:
                            # 读取一小块数据用于计算音量
                            chunk_size = min(1024, available)
                            audio_data = app.audio_codec.input_stream.read(
                                chunk_size, 
                                exception_on_overflow=False
                            )
                            
                            # 将字节数据转换为numpy数组进行处理
                            audio_array = np.frombuffer(audio_data, dtype=np.int16)
                            
                            # 计算音量级别 (0.0-1.0)
                            # 16位音频的最大值是32768，计算音量占最大值的比例
                            # 使用均方根(RMS)值计算有效音量
                            rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))
                            # 标准化为0-1范围，32768是16位音频的最大值
                            volume = min(1.0, rms / 32768 * 5)  # 放大5倍使小音量更明显
                            
                            # 应用平滑处理
                            if hasattr(self, '_last_volume'):
                                # 平滑过渡，保留70%上次数值，增加30%新数值
                                self._last_volume = self._last_volume * 0.7 + volume * 0.3
                            else:
                                self._last_volume = volume
                                
                            return self._last_volume
                    except Exception as e:
                        self.logger.debug(f"读取麦克风数据失败: {e}")
        except Exception as e:
            self.logger.debug(f"获取麦克风音量失败: {e}")
            
        # 如果无法获取实际音量，返回上次的音量或默认值
        if hasattr(self, '_last_volume'):
            # 缓慢衰减上次的音量
            self._last_volume *= 0.9
            return self._last_volume
        else:
            self._last_volume = 0.0 # 初始化为 0
            return self._last_volume

    def _start_mic_visualization(self):
        """开始麦克风可视化"""
        if self.mic_visualizer and self.mic_timer and self.audio_control_stack:
            self.is_listening = True
            
            # 切换到麦克风可视化页面
            self.audio_control_stack.setCurrentWidget(self.mic_page)
            
            # 启动定时器更新可视化
            if not self.mic_timer.isActive():
                self.mic_timer.start(50)  # 20fps
                
    def _stop_mic_visualization(self):
        """停止麦克风可视化"""
        self.is_listening = False
        
        # 停止定时器
        if self.mic_timer and self.mic_timer.isActive():
            self.mic_timer.stop()
            # 重置可视化音量
            if self.mic_visualizer:
                 self.mic_visualizer.set_volume(0.0)
                 # 确保动画平滑过渡到0
                 if hasattr(self, '_last_volume'):
                     self._last_volume = 0.0

        # 切换回音量控制页面
        if self.audio_control_stack:
            self.audio_control_stack.setCurrentWidget(self.volume_page)

class MicrophoneVisualizer(QFrame):
    """麦克风音量可视化组件 - 数字显示版"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(50)
        self.setFrameShape(QFrame.NoFrame)
        
        # 可视化样式设置
        self.min_font_size = 14
        self.max_font_size = 40
        self.current_font_size = self.min_font_size
        
        # 初始化音量数据
        self.current_volume = 0.0
        self.target_volume = 0.0
        
        # 创建平滑动画效果
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._update_animation)
        self.animation_timer.start(16)  # 约60fps
        
        # 颜色设置
        self.min_color = QColor(80, 150, 255)  # 低音量时的颜色 (蓝色)
        self.max_color = QColor(255, 100, 100)  # 高音量时的颜色 (红色)
        self.current_color = self.min_color.name()
        
        # 透明背景
        self.setStyleSheet("background-color: transparent;")
        
    def set_volume(self, volume):
        """设置当前音量，范围0.0-1.0"""
        self.target_volume = max(0.0, min(1.0, volume)) # 限制范围
        # self.update() # 动画会触发更新

    def _update_animation(self):
        """更新动画效果"""
        # 平滑过渡到目标音量
        diff = self.target_volume - self.current_volume
        # 使用不同的平滑因子，使得音量下降更快
        smooth_factor = 0.2 if diff > 0 else 0.3
        self.current_volume += diff * smooth_factor

        # 避免非常小的负值或大于1的值
        self.current_volume = max(0.0, min(1.0, self.current_volume))

        # 计算字体大小
        self.current_font_size = self.min_font_size + (self.max_font_size - self.min_font_size) * self.current_volume

        # 计算颜色过渡
        r = int(self.min_color.red() + (self.max_color.red() - self.min_color.red()) * self.current_volume)
        g = int(self.min_color.green() + (self.max_color.green() - self.min_color.green()) * self.current_volume)
        b = int(self.min_color.blue() + (self.max_color.blue() - self.min_color.blue()) * self.current_volume)
        self.current_color = QColor(r, g, b).name()

        self.update()
        
    def paintEvent(self, event):
        """绘制事件"""
        super().paintEvent(event)
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取绘制区域
        rect = self.rect()
        
        # 根据当前音量显示音量值和对应文字
        volume_percent = int(self.current_volume * 100)
        
        # 设置字体
        font = painter.font()
        # 使用 setPointSizeF 可能更平滑
        font.setPointSizeF(self.current_font_size)
        font.setBold(True)  # 设置为粗体
        painter.setFont(font)
        
        # 设置颜色和阴影
        shadow_color = QColor(0, 0, 0, 40)
        painter.setPen(shadow_color)
        shadow_offset = 1
        
        # 计算主数字和状态文本的矩形区域
        main_height = rect.height() - 30
        main_rect = QRect(rect.left(), rect.top(), rect.width(), main_height)
        status_rect = QRect(rect.left(), rect.top() + main_height + 5, rect.width(), 20)
        
        # 绘制阴影文本
        shadow_rect = QRect(main_rect.left() + shadow_offset, main_rect.top() + shadow_offset, 
                          main_rect.width(), main_rect.height())
        painter.drawText(shadow_rect, Qt.AlignCenter, f"{volume_percent}%")
        
        # 绘制主要文本
        painter.setPen(QColor(self.current_color))
        volume_text = f"{volume_percent}%"
        painter.drawText(main_rect, Qt.AlignCenter, volume_text)
        
        # 添加描述文本
        small_font = painter.font()
        small_font.setPointSize(10)
        small_font.setBold(False) # 描述文本不需要粗体
        painter.setFont(small_font)
        painter.setPen(QColor(100, 100, 100))
        
        # 根据音量级别显示相应提示
        if self.current_volume < 0.01: # 增加一个阈值判断是否安静
             status_text = "声音: --"
        elif volume_percent < 20:
            status_text = "声音: 安静"
        elif volume_percent < 40:
            status_text = "声音: 正常"
        elif volume_percent < 70:
            status_text = "声音: 较大"
        else:
            status_text = "声音: 很大"
            
        # 在下方显示状态文本
        painter.drawText(status_rect, Qt.AlignCenter, status_text)
        # painter.end() # 不需要显式调用 end