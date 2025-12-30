# -*- coding: utf-8 -*-
"""系统托盘服务."""

import os
from typing import Callable, Optional

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.logging import get_logger
from src.utils.resource_finder import get_assets_dir

logger = get_logger()


class TrayService(QObject):
    """系统托盘服务."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._enabled = os.getenv("XIAOZHI_DISABLE_TRAY") != "1"

        if not self._enabled:
            logger.warning("系统托盘已通过环境变量禁用")

    def setup(
        self,
        on_show: Callable,
        on_quit: Callable,
    ) -> bool:
        """设置系统托盘.

        Args:
            on_show: 显示窗口回调
            on_quit: 退出回调

        Returns:
            是否成功
        """
        if not self._enabled:
            return False

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用")
            return False

        try:
            # 创建托盘图标
            self._tray = QSystemTrayIcon(self.parent())

            # 加载图标
            icon_path = get_assets_dir() / "icon.png"
            if icon_path.exists():
                self._tray.setIcon(QIcon(str(icon_path)))
            else:
                # 使用应用图标
                app = QApplication.instance()
                if app:
                    self._tray.setIcon(app.windowIcon())

            # 创建菜单
            self._menu = QMenu()
            self._menu.addAction("显示窗口", on_show)
            self._menu.addSeparator()
            self._menu.addAction("退出", on_quit)

            self._tray.setContextMenu(self._menu)

            # 双击激活
            self._tray.activated.connect(
                lambda reason: on_show() if reason == QSystemTrayIcon.DoubleClick else None
            )

            self._tray.show()
            logger.info("系统托盘初始化成功")
            return True

        except Exception as e:
            logger.error(f"系统托盘初始化失败: {e}")
            return False

    def update_tooltip(self, text: str):
        """更新托盘提示."""
        if self._tray:
            self._tray.setToolTip(text)

    def show_message(self, title: str, message: str):
        """显示托盘通知."""
        if self._tray:
            self._tray.showMessage(title, message)

    def hide(self):
        """隐藏托盘."""
        if self._tray:
            self._tray.hide()

    def is_available(self) -> bool:
        """托盘是否可用."""
        return self._tray is not None and self._tray.isVisible()
