# -*- coding: utf-8 -*-
"""
系统托盘管理器模块 - 负责系统托盘的创建和管理.
"""

import os
from functools import partial
from typing import Callable, Optional

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget

from src.logging import get_logger

logger = get_logger()


class TrayManager:
    """系统托盘管理器 - 处理系统托盘的创建、信号连接和显示"""

    def __init__(self, parent_window: Optional[QWidget] = None):
        """
        初始化系统托盘管理器.

        Args:
            parent_window: 父窗口
        """
        self.parent_window = parent_window
        self.system_tray = None
        self._is_enabled = os.getenv("XIAOZHI_DISABLE_TRAY") != "1"

        if not self._is_enabled:
            logger.warning("已通过环境变量禁用系统托盘 (XIAOZHI_DISABLE_TRAY=1)")

    def setup(
        self,
        on_show_window: Callable,
        on_settings: Callable,
        on_quit: Callable,
    ) -> bool:
        """
        设置系统托盘.

        Args:
            on_show_window: 显示主窗口的回调函数
            on_settings: 打开设置的回调函数
            on_quit: 退出应用的回调函数

        Returns:
            是否成功创建托盘
        """
        if not self._is_enabled:
            return False

        try:
            from src.views.components.system_tray import SystemTray

            self.system_tray = SystemTray(self.parent_window)

            # 连接托盘信号（使用 QTimer 确保主线程执行）
            tray_signals = {
                "show_window_requested": on_show_window,
                "settings_requested": on_settings,
                "quit_requested": on_quit,
            }

            for signal_name, handler in tray_signals.items():
                try:
                    # 使用 partial 代替 lambda 避免闭包问题
                    getattr(self.system_tray, signal_name).connect(
                        partial(QTimer.singleShot, 0, handler)
                    )
                except AttributeError:
                    logger.warning(f"系统托盘信号 {signal_name} 不存在")

            logger.info("系统托盘初始化成功")
            return True

        except Exception as e:
            logger.error(f"初始化系统托盘失败: {e}", exc_info=True)
            return False

    def update_status(self, status: str, connected: bool):
        """
        更新系统托盘的状态显示.

        Args:
            status: 状态文本
            connected: 是否已连接
        """
        if self.system_tray:
            try:
                self.system_tray.update_status(status, connected)
            except Exception as e:
                logger.debug(f"更新托盘状态失败: {e}")

    def hide(self):
        """隐藏系统托盘"""
        if self.system_tray:
            try:
                self.system_tray.hide()
            except Exception as e:
                logger.debug(f"隐藏托盘失败: {e}")

    def is_available(self) -> bool:
        """
        检查托盘是否可用.

        Returns:
            托盘是否可用
        """
        if not self.system_tray:
            return False

        try:
            return getattr(self.system_tray, "is_available", lambda: False)()
        except Exception:
            return False

    def is_visible(self) -> bool:
        """
        检查托盘是否可见.

        Returns:
            托盘是否可见
        """
        if not self.system_tray:
            return False

        try:
            return getattr(self.system_tray, "is_visible", lambda: False)()
        except Exception:
            return False
