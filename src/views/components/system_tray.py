"""
系统托盘组件模块 提供系统托盘图标、菜单和状态指示功能.
"""

from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import QAction, QMenu, QSystemTrayIcon, QWidget

from src.utils.logging_config import get_logger


class SystemTray(QObject):
    """
    系统托盘组件.
    """

    # 定义信号
    show_window_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.logger = get_logger("SystemTray")
        self.parent_widget = parent

        # 托盘相关组件
        self.tray_icon = None
        self.tray_menu = None

        # 状态相关
        self.current_status = ""
        self.is_connected = True

        # 初始化托盘
        self._setup_tray()

    def _setup_tray(self):
        """
        设置系统托盘图标.
        """
        try:
            # 检查系统是否支持系统托盘
            if not QSystemTrayIcon.isSystemTrayAvailable():
                self.logger.warning("系统不支持系统托盘功能")
                return

            # 创建托盘菜单
            self._create_tray_menu()

            # 创建系统托盘图标
            self.tray_icon = QSystemTrayIcon(self.parent_widget)
            self.tray_icon.setContextMenu(self.tray_menu)

            # 连接托盘图标的事件
            self.tray_icon.activated.connect(self._on_tray_activated)

            # 设置初始图标
            self.update_status("待命", connected=True)

            # 显示系统托盘图标
            self.tray_icon.show()
            self.logger.info("系统托盘图标已初始化")

        except Exception as e:
            self.logger.error(f"初始化系统托盘图标失败: {e}", exc_info=True)

    def _create_tray_menu(self):
        """
        创建托盘右键菜单.
        """
        self.tray_menu = QMenu()

        # 添加显示主窗口菜单项
        show_action = QAction("显示主窗口", self.parent_widget)
        show_action.triggered.connect(self._on_show_window)
        self.tray_menu.addAction(show_action)

        # 添加分隔线
        self.tray_menu.addSeparator()

        # 添加设置菜单项
        settings_action = QAction("参数配置", self.parent_widget)
        settings_action.triggered.connect(self._on_settings)
        self.tray_menu.addAction(settings_action)

        # 添加分隔线
        self.tray_menu.addSeparator()

        # 添加退出菜单项
        quit_action = QAction("退出程序", self.parent_widget)
        quit_action.triggered.connect(self._on_quit)
        self.tray_menu.addAction(quit_action)

    def _on_tray_activated(self, reason):
        """
        处理托盘图标点击事件.
        """
        if reason == QSystemTrayIcon.Trigger:  # 单击
            self.show_window_requested.emit()

    def _on_show_window(self):
        """
        处理显示窗口菜单项点击.
        """
        self.show_window_requested.emit()

    def _on_settings(self):
        """
        处理设置菜单项点击.
        """
        self.settings_requested.emit()

    def _on_quit(self):
        """
        处理退出菜单项点击.
        """
        self.quit_requested.emit()

    def update_status(self, status: str, connected: bool = True):
        """更新托盘图标状态.

        Args:
            status: 状态文本
            connected: 连接状态
        """
        if not self.tray_icon:
            return

        self.current_status = status
        self.is_connected = connected

        try:
            icon_color = self._get_status_color(status, connected)

            # 创建指定颜色的图标
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(0, 0, 0, 0))  # 透明背景

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setBrush(QBrush(icon_color))
            painter.setPen(QColor(0, 0, 0, 0))  # 透明边框
            painter.drawEllipse(2, 2, 12, 12)
            painter.end()

            # 设置图标
            self.tray_icon.setIcon(QIcon(pixmap))

            # 设置提示文本
            tooltip = f"小智AI助手 - {status}"
            self.tray_icon.setToolTip(tooltip)

        except Exception as e:
            self.logger.error(f"更新系统托盘图标失败: {e}")

    def _get_status_color(self, status: str, connected: bool) -> QColor:
        """根据状态返回对应的颜色.

        Args:
            status: 状态文本
            connected: 连接状态

        Returns:
            QColor: 对应的颜色
        """
        if not connected:
            return QColor(128, 128, 128)  # 灰色 - 未连接

        if "错误" in status:
            return QColor(255, 0, 0)  # 红色 - 错误状态
        elif "聆听中" in status:
            return QColor(255, 200, 0)  # 黄色 - 聆听中状态
        elif "说话中" in status:
            return QColor(0, 120, 255)  # 蓝色 - 说话中状态
        else:
            return QColor(0, 180, 0)  # 绿色 - 待命/已启动状态

    def show_message(
        self,
        title: str,
        message: str,
        icon_type=QSystemTrayIcon.Information,
        duration: int = 2000,
    ):
        """显示托盘通知消息.

        Args:
            title: 通知标题
            message: 通知内容
            icon_type: 图标类型
            duration: 显示时间(毫秒)
        """
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon_type, duration)

    def hide(self):
        """
        隐藏托盘图标.
        """
        if self.tray_icon:
            self.tray_icon.hide()

    def is_visible(self) -> bool:
        """
        检查托盘图标是否可见.
        """
        return self.tray_icon and self.tray_icon.isVisible()

    def is_available(self) -> bool:
        """
        检查系统托盘是否可用.
        """
        return QSystemTrayIcon.isSystemTrayAvailable()
