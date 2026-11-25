# -*- coding: utf-8 -*-
"""系统托盘服务."""

import os
from typing import Callable, Optional

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.i18n import off_locale_changed, on_locale_changed, t
from src.logging import get_logger
from src.utils.resource_finder import get_assets_dir

logger = get_logger()


class TrayService(QObject):
    """系统托盘服务."""

    _localeChangeRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None
        self._show_action = None
        self._quit_action = None
        self._closed = False
        self._enabled = os.getenv("XIAOZHI_DISABLE_TRAY") != "1"
        self._localeChangeRequested.connect(
            self._update_menu_texts, Qt.ConnectionType.QueuedConnection
        )

        if not self._enabled:
            logger.warning("系统托盘已通过环境变量禁用")

    def _on_locale_changed(self, locale_code: str) -> None:
        if self._closed:
            return
        try:
            self._localeChangeRequested.emit(locale_code)
        except RuntimeError:
            pass

    @Slot(str)
    def _update_menu_texts(self, _locale_code: str) -> None:
        if self._closed:
            return
        try:
            if self._show_action is not None:
                self._show_action.setText(t("tray.show_window"))
            if self._quit_action is not None:
                self._quit_action.setText(t("tray.quit"))
        except RuntimeError:
            self._show_action = None
            self._quit_action = None

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

            # 创建菜单（显式实例化 QAction 并挂在 menu 下，避免 PySide6/macOS 提前回收）
            self._menu = QMenu()
            self._show_action = QAction(t("tray.show_window"), self._menu)
            self._show_action.triggered.connect(on_show)
            self._menu.addAction(self._show_action)
            self._menu.addSeparator()
            self._quit_action = QAction(t("tray.quit"), self._menu)
            self._quit_action.triggered.connect(on_quit)
            self._menu.addAction(self._quit_action)
            on_locale_changed(self._on_locale_changed)

            self._tray.setContextMenu(self._menu)

            # 双击激活
            self._tray.activated.connect(
                lambda reason: on_show() if reason == QSystemTrayIcon.DoubleClick else None
            )

            self._tray.show()
            logger.info("系统托盘初始化成功")
            return True

        except Exception as e:
            logger.error(f"系统托盘初始化失败: {e}", exc_info=True)
            return False

    def hide(self):
        """隐藏托盘."""
        self._closed = True
        off_locale_changed(self._on_locale_changed)
        if self._tray:
            self._tray.hide()
