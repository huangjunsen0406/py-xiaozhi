# -*- coding: utf-8 -*-
"""
Home Assistant设备管理器 - 图形界面
用于查询Home Assistant设备并将其添加到配置文件中
"""
import os
import sys

# 添加项目根目录到系统路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
sys.path.append(project_root)


import json
import logging
from typing import Any, Dict, List, Optional

from src.utils.config_manager import ConfigManager

# 导入项目配置管理器

try:
    from PyQt5 import uic
    from PyQt5.QtCore import Qt, QThread, pyqtSignal
    from PyQt5.QtGui import QColor
    from PyQt5.QtWidgets import QTabBar  # 添加 QFrame
    from PyQt5.QtWidgets import (
        QApplication,
        QHeaderView,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QTableWidgetItem,
    )


except ImportError:
    print("错误: 未安装PyQt5库")
    print("请运行: pip install PyQt5")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("错误: 未安装requests库")
    print("请运行: pip install requests")
    sys.exit(1)

# 设备类型和图标映射
DOMAIN_ICONS = {
    "light": "灯具 💡",
    "switch": "开关 🔌",
    "sensor": "传感器 🌡️",
    "climate": "空调 ❄️",
    "fan": "风扇 💨",
    "media_player": "媒体播放器 📺",
    "camera": "摄像头 📷",
    "cover": "窗帘 🪟",
    "vacuum": "扫地机器人 🧹",
    "binary_sensor": "二元传感器 🔔",
    "lock": "锁 🔒",
    "alarm_control_panel": "安防面板 🚨",
    "automation": "自动化 ⚙️",
    "script": "脚本 📜",
}


class DeviceLoadThread(QThread):
    """加载设备的线程."""

    devices_loaded = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, url, token, domain="all"):
        super().__init__()
        self.url = url
        self.token = token
        self.domain = domain
        self._is_running = True

    def run(self):
        try:
            # 检查线程是否应该继续运行
            if not self._is_running:
                return

            devices = self.get_device_list(self.url, self.token, self.domain)

            # 再次检查线程是否应该继续运行
            if not self._is_running:
                return

            self.devices_loaded.emit(devices)
        except Exception as e:
            if self._is_running:  # 只有在线程仍应运行时才发出错误信号
                self.error_occurred.emit(str(e))

    def terminate(self):
        """安全终止线程."""
        self._is_running = False
        super().terminate()  # 调用QThread的terminate方法

    def get_device_list(
        self, url: str, token: str, domain: str = "all"
    ) -> List[Dict[str, Any]]:
        """从Home Assistant API获取设备列表."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        try:
            # 获取所有状态
            response = requests.get(f"{url}/api/states", headers=headers, timeout=10)

            if response.status_code != 200:
                error_msg = f"错误: 无法获取设备列表(HTTP {response.status_code}): {response.text}"
                self.error_occurred.emit(error_msg)
                return []

            # 检查线程是否应该继续运行
            if not self._is_running:
                return []

            # 解析响应
            entities = response.json()

            # 过滤指定域的实体
            domain_entities = []
            for entity in entities:
                # 检查线程是否应该继续运行
                if not self._is_running:
                    return []

                entity_id = entity.get("entity_id", "")
                entity_domain = entity_id.split(".", 1)[0] if "." in entity_id else ""

                if domain == "all" or entity_domain == domain:
                    domain_entities.append(
                        {
                            "entity_id": entity_id,
                            "domain": entity_domain,
                            "friendly_name": entity.get("attributes", {}).get(
                                "friendly_name", entity_id
                            ),
                            "state": entity.get("state", "unknown"),
                        }
                    )

            # 按域和名称排序
            domain_entities.sort(key=lambda x: (x["domain"], x["friendly_name"]))
            return domain_entities

        except Exception as e:
            if self._is_running:  # 只有在线程仍应运行时才发出错误信号
                self.error_occurred.emit(f"错误: 获取设备列表失败 - {e}")
            return []


class HomeAssistantDeviceManager(QMainWindow):
    """Home Assistant设备管理器GUI."""

    def __init__(self):
        super().__init__()

        # 从配置文件获取Home Assistant配置
        self.config = ConfigManager.get_instance()
        self.ha_url = self.config.get_config("HOME_ASSISTANT.URL", "")
        self.ha_token = self.config.get_config("HOME_ASSISTANT.TOKEN", "")

        if not self.ha_url or not self.ha_token:
            QMessageBox.critical(
                self,
                "配置错误",
                "未找到Home Assistant配置，请确保config/config.json中包含有效的\n"
                "HOME_ASSISTANT.URL和HOME_ASSISTANT.TOKEN",
            )
            sys.exit(1)

        # 已添加的设备
        self.added_devices = self.config.get_config("HOME_ASSISTANT.DEVICES", [])

        # 当前获取的设备列表
        self.current_devices = []

        # 存储域映射关系
        self.domain_mapping = {}

        # 线程管理
        self.threads = []  # 保存活动线程的引用
        self.load_thread = None  # 当前加载线程

        # 初始化logger
        self.logger = logging.getLogger("HADeviceManager")

        # 加载UI文件
        self.load_ui()

        # 应用样式表进行美化
        self.apply_stylesheet()

        # 初始化UI组件
        self.init_ui()

        # 连接信号槽 - 除导航信号外的其他信号
        self.connect_signals()

        # 加载设备
        self.load_devices("all")

    def closeEvent(self, event):
        """窗口关闭事件处理."""
        # 停止所有线程
        self.stop_all_threads()
        super().closeEvent(event)

    def stop_all_threads(self):
        """停止所有线程."""
        # 先停止当前加载线程
        if self.load_thread and self.load_thread.isRunning():
            self.logger.info("停止当前加载线程...")
            try:
                self.load_thread.terminate()  # 使用我们定义的安全终止方法
                if not self.load_thread.wait(1000):  # 等待最多1秒
                    self.logger.warning("加载线程未能在1秒内停止")
            except Exception as e:
                self.logger.error(f"停止加载线程时出错: {e}")

        # 停止所有其他线程
        for thread in self.threads[:]:  # 使用副本进行迭代
            if thread and thread.isRunning():
                self.logger.info(f"停止线程: {thread}")
                try:
                    if hasattr(thread, "terminate"):
                        thread.terminate()  # 使用我们定义的安全终止方法
                    if not thread.wait(1000):  # 等待最多1秒
                        self.logger.warning(f"线程未能在1秒内停止: {thread}")
                except Exception as e:
                    self.logger.error(f"停止线程时出错: {e}")

        # 清空线程列表
        self.threads.clear()
        self.load_thread = None

    def apply_stylesheet(self):
        """应用自定义样式表美化界面."""
        stylesheet = """
            QMainWindow {
                background-color: #f0f0f0; /* 窗口背景色 */
            }
            
            /* 卡片样式 (使用 QFrame 替代) */
            QFrame#available_card, QFrame#added_card {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #dcdcdc;
                padding: 5px; /* 内边距 */
            }

            /* 导航栏样式 (QTabBar) */
            QTabBar::tab {
                background: #e1e1e1;
                border: 1px solid #c4c4c4;
                border-bottom: none; /* 无下边框 */
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                padding: 8px 15px;
                margin-right: 2px;
                color: #333; /* 标签文字颜色 */
            }

            QTabBar::tab:selected {
                background: white; /* 选中时背景与卡片一致 */
                border-color: #c4c4c4;
                margin-bottom: -1px; /* 轻微重叠，消除边框 */
                color: #000; /* 选中标签文字颜色 */
            }

            QTabBar::tab:!selected {
                margin-top: 2px; /* 未选中标签稍低 */
            }
            
            /* Tab Bar下划线 (可选) */
            /* QTabBar {
                border-bottom: 1px solid #c4c4c4;
            } */

            /* 通用控件样式 */
            QComboBox, QLineEdit, QPushButton {
                padding: 6px 10px;
                border: 1px solid #cccccc;
                border-radius: 4px;
                min-height: 20px; /* 保证最小高度 */
                font-size: 10pt; /* 统一字体大小 */
            }

            QLineEdit, QComboBox {
                background-color: white;
            }
            /* 按钮样式 */
            QPushButton {
                background-color: #0078d4; /* 蓝色背景 */
                color: white;
                font-weight: bold;
                min-width: 70px; /* 按钮最小宽度 */
            }

            QPushButton:hover {
                background-color: #005a9e;
            }

            QPushButton:pressed {
                background-color: #003f6e;
            }

            QPushButton#delete_button { /* 可以为特定按钮设置样式，如果需要 */
                background-color: #e74c3c; /* 红色删除按钮 */
            }
            QPushButton#delete_button:hover {
                background-color: #c0392b;
            }

            /* 下拉框箭头 */
            QComboBox::drop-down {
                border: none;
                padding-right: 5px;
            }
            QComboBox::down-arrow {
                 image: url(
                    :/qt-project.org/styles/commonstyle/images/standardbutton-down-arrow-16.png
                 );
                 width: 12px;
                 height: 12px;
            }
            
            /* 表格样式 */
            QTableWidget {
                border: 1px solid #dcdcdc;
                gridline-color: #e0e0e0;
                selection-background-color: #a6d1f4; /* 选中行背景色 */
                selection-color: black; /* 选中行文字颜色 */
                alternate-background-color: #f9f9f9; /* 隔行变色 */
                font-size: 10pt;
            }
            /* QTableWidget::item {
                 padding: 4px; /* 单元格内边距 */
            /* } */
            
            /* 表头样式 */
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 5px;
                border: 1px solid #dcdcdc;
                border-bottom: none; /* 移除表头底部边框 */
                font-weight: bold;
                font-size: 10pt;
            }
            
            /* 滚动条美化 (可选，可能需要根据平台调整) */
            QScrollBar:vertical {
                border: 1px solid #cccccc;
                background: #f0f0f0;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            
            QScrollBar:horizontal {
                border: 1px solid #cccccc;
                background: #f0f0f0;
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #c0c0c0;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            
        """
        self.setStyleSheet(stylesheet)
        self.logger.info("已应用自定义样式表")

    def load_ui(self):
        """加载UI文件."""
        ui_path = os.path.join(current_dir, "index.ui")
        uic.loadUi(ui_path, self)

    def init_ui(self):
        """初始化UI组件."""
        try:
            # 加载UI文件
            ui_path = os.path.join(current_dir, "index.ui")
            uic.loadUi(ui_path, self)

            # 设置表格基本属性，保留功能性设置
            self.device_table.verticalHeader().setVisible(False)
            self.device_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.Stretch
            )  # Prompt列
            self.device_table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeToContents
            )  # 设备ID列
            self.device_table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeToContents
            )  # 类型列
            self.device_table.horizontalHeader().setSectionResizeMode(
                3, QHeaderView.ResizeToContents
            )  # 状态列

            self.added_device_table.verticalHeader().setVisible(False)
            self.added_device_table.horizontalHeader().setSectionResizeMode(
                0, QHeaderView.Stretch
            )  # Prompt列
            self.added_device_table.horizontalHeader().setSectionResizeMode(
                1, QHeaderView.ResizeToContents
            )  # 设备ID列
            self.added_device_table.horizontalHeader().setSectionResizeMode(
                2, QHeaderView.ResizeToContents
            )  # 操作列

            # 初始化导航TabBar
            self._setup_navigation()

            # 连接信号 - SearchLineEdit 替换为 QLineEdit
            self.search_input.textChanged.connect(self.filter_devices)

            # 设置下拉菜单数据 - QComboBox
            self.domain_combo.clear()
            self.domain_mapping = {"全部": "all"}
            self.domain_combo.addItem("全部")
            domains = [
                ("light", "灯光 💡"),
                ("switch", "开关 🔌"),
                ("sensor", "传感器 🌡️"),
                ("binary_sensor", "二元传感器 🔔"),
                ("climate", "温控 ❄️"),
                ("fan", "风扇 💨"),
                ("cover", "窗帘 🪟"),
                ("media_player", "媒体播放器 📺"),
            ]
            for domain_id, domain_name in domains:
                self.domain_mapping[domain_name] = domain_id
                self.domain_combo.addItem(domain_name)

            # 设置默认选中项为 "全部" (索引 0)
            self.domain_combo.setCurrentIndex(0)

            # 使用正确的方法名称连接信号 - QComboBox 使用 currentIndexChanged 或 currentTextChanged
            self.domain_combo.currentTextChanged.connect(self.domain_changed)

            # 加载设备列表
            self.load_devices("all")

        except Exception as e:
            self.logger.error(f"初始化UI失败: {str(e)}")
            raise

    def _setup_navigation(self):
        """设置导航栏 - 使用 QTabBar"""
        # 假设 UI 文件中已将 nav_segment 替换为 QTabBar
        self.logger.info("开始设置导航栏 (QTabBar)")

        try:
            # 获取 QTabBar 实例 (假设 objectName 为 nav_tab_bar)
            # 注意：如果 UI 文件中的 objectName 不同，需要相应修改
            # self.nav_tab_bar = self.findChild(QTabBar, "nav_tab_bar")
            # 如果 uic.loadUi 已经加载了正确的对象名 nav_segment (即使它是 QTabBar)，则可以直接使用
            if not isinstance(self.nav_segment, QTabBar):
                # Fallback or error handling if it's
                # not a QTabBar as expected after UI update
                self.logger.error("导航控件 'nav_segment' 不是 QTabBar 类型！")
                # 可以在这里尝试查找，或者抛出错误
                tab_bar = self.findChild(QTabBar)
                if tab_bar:
                    self.nav_segment = tab_bar
                    self.logger.warning(
                        "已自动查找并设置 QTabBar 实例。请确保 UI 文件中的名称一致。"
                    )
                else:
                    QMessageBox.critical(
                        self, "UI错误", "未能找到导航栏控件 (QTabBar)。请检查UI文件。"
                    )
                    return

            # 清空并添加导航项
            # QTabBar 没有 clear() 方法，需要循环移除
            # self.nav_segment.clear()
            # Remove existing tabs before adding new ones
            while self.nav_segment.count() > 0:
                self.nav_segment.removeTab(0)  # 循环移除第一个tab直到为空

            self.nav_segment.addTab("可用设备")  # index 0
            self.nav_segment.addTab("已添加设备")  # index 1

            # 存储映射关系，如果需要通过 key 访问
            self._nav_keys = ["available", "added"]

            # 连接信号 - QTabBar 使用 currentChanged(int index)
            self.nav_segment.currentChanged.connect(self.on_page_changed_by_index)

            # 设置默认选中项 (索引 0)
            self.nav_segment.setCurrentIndex(0)
            self.logger.info("导航栏设置完成，默认选中索引 0 ('可用设备')")
        except Exception as e:
            self.logger.error(f"设置导航栏失败: {e}")
            # 防止程序崩溃，显示错误提示
            QMessageBox.warning(self, "警告", f"导航栏设置失败: {e}")

    def connect_signals(self):
        """连接信号槽."""
        # 域选择变化
        self.domain_combo.currentTextChanged.connect(self.domain_changed)

        # 搜索框文本变化
        self.search_input.textChanged.connect(self.filter_devices)

        # 刷新按钮点击
        self.refresh_button.clicked.connect(self.refresh_devices)

        # 添加设备按钮点击
        self.add_button.clicked.connect(self.add_selected_device)

        # 已添加设备表格单元格编辑
        self.added_device_table.cellChanged.connect(self.on_prompt_edited)

        # 可用设备表格单元格编辑
        self.device_table.cellChanged.connect(self.on_available_device_prompt_edited)

    def on_page_changed_by_index(self, index: int):
        """当 QTabBar 切换时调用."""
        try:
            routeKey = self._nav_keys[index]
            self.logger.info(f"切换到页面索引 {index}, key: {routeKey}")

            # 页面切换逻辑
            if routeKey == "available":
                self.stackedWidget.setCurrentIndex(0)
            elif routeKey == "added":
                self.stackedWidget.setCurrentIndex(1)
                self.reload_config()  # 先重新加载配置文件
                self.refresh_added_devices()
            else:
                self.logger.warning(f"未知的导航索引: {index}, key: {routeKey}")
        except IndexError:
            self.logger.error(f"导航索引越界: {index}")
        except Exception as e:
            self.logger.error(f"页面切换处理失败: {e}")

    def reload_config(self):
        """重新从磁盘加载配置文件."""
        try:
            # 获取配置文件路径
            config_path = os.path.join(project_root, "config", "config.json")

            # 确保文件存在
            if not os.path.exists(config_path):
                self.logger.warning(f"配置文件不存在: {config_path}")
                return

            # 读取配置文件
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            # 更新内存中的设备列表
            if (
                "HOME_ASSISTANT" in config_data
                and "DEVICES" in config_data["HOME_ASSISTANT"]
            ):
                self.added_devices = config_data["HOME_ASSISTANT"]["DEVICES"]
                self.logger.info(
                    f"已从配置文件重新加载 {len(self.added_devices)} 个设备"
                )
            else:
                self.added_devices = []
                self.logger.warning("配置文件中未找到设备配置")

        except Exception as e:
            self.logger.error(f"重新加载配置文件失败: {e}")
            QMessageBox.warning(self, "警告", f"重新加载配置文件失败: {e}")

    def domain_changed(self):
        """当域选择变化时调用."""
        current_text = self.domain_combo.currentText()
        domain = self.domain_mapping.get(current_text, "all")
        self.load_devices(domain)

    def load_devices(self, domain):
        """加载设备列表."""
        # 清空搜索框
        self.search_input.clear()

        # 显示加载中
        self.device_table.setRowCount(0)
        loading_row = self.device_table.rowCount()
        self.device_table.insertRow(loading_row)
        loading_item = QTableWidgetItem("正在加载设备...")
        loading_item.setTextAlignment(Qt.AlignCenter)
        self.device_table.setItem(loading_row, 0, loading_item)
        self.device_table.setSpan(loading_row, 0, 1, 4)

        # 确保之前的线程已经停止
        if self.load_thread and self.load_thread.isRunning():
            self.logger.info("等待上一个加载线程完成...")
            # 尝试先等待线程完成
            if not self.load_thread.wait(1000):  # 等待最多1秒
                self.logger.warning("上一个加载线程未在1秒内完成，强制终止")
                # 如果线程无法在1秒内完成，从线程列表中移除
                if self.load_thread in self.threads:
                    self.threads.remove(self.load_thread)
                self.load_thread = None

        # 启动加载线程
        self.load_thread = DeviceLoadThread(self.ha_url, self.ha_token, domain)
        self.load_thread.devices_loaded.connect(self.update_device_table)
        self.load_thread.error_occurred.connect(self.show_error)
        self.load_thread.start()

        # 将线程添加到线程列表
        self.threads.append(self.load_thread)

    def update_device_table(self, devices):
        """更新设备表格."""
        # 线程完成后从线程列表中移除
        sender = self.sender()
        if sender in self.threads:
            self.threads.remove(sender)

        self.current_devices = devices
        self.device_table.setRowCount(0)

        if not devices:
            # 显示无设备信息
            no_device_row = self.device_table.rowCount()
            self.device_table.insertRow(no_device_row)
            no_device_item = QTableWidgetItem("未找到设备")
            no_device_item.setTextAlignment(Qt.AlignCenter)
            self.device_table.setItem(no_device_row, 0, no_device_item)
            self.device_table.setSpan(no_device_row, 0, 1, 4)
            return

        # 填充设备表格
        for device in devices:
            row = self.device_table.rowCount()
            self.device_table.insertRow(row)

            # Prompt (第0列) - 设置为可编辑
            friendly_name_item = QTableWidgetItem(device["friendly_name"])
            # QTableWidgetItem 默认是可编辑的
            self.device_table.setItem(row, 0, friendly_name_item)

            # 设备ID (第1列) - 设置为不可编辑
            entity_id_item = QTableWidgetItem(device["entity_id"])
            entity_id_item.setFlags(
                entity_id_item.flags() & ~Qt.ItemIsEditable
            )  # 设置为不可编辑
            self.device_table.setItem(row, 1, entity_id_item)

            # 设备类型 (第2列) - 设置为不可编辑
            domain = device["domain"]
            domain_display = DOMAIN_ICONS.get(domain, domain)
            domain_item = QTableWidgetItem(domain_display)
            domain_item.setFlags(
                domain_item.flags() & ~Qt.ItemIsEditable
            )  # 设置为不可编辑
            self.device_table.setItem(row, 2, domain_item)

            # 设备状态 (第3列) - 设置为不可编辑
            state = device["state"]
            state_item = QTableWidgetItem(state)
            state_item.setFlags(
                state_item.flags() & ~Qt.ItemIsEditable
            )  # 设置为不可编辑
            self.device_table.setItem(row, 3, state_item)

            # 检查设备是否已添加，如果已添加则标记
            # PyQt5 中使用 QColor 设置背景色
            if any(
                d.get("entity_id") == device["entity_id"] for d in self.added_devices
            ):
                for col in range(4):
                    item = self.device_table.item(row, col)
                    if item:  # 确保 item 存在
                        item.setBackground(QColor(Qt.lightGray))  # 使用 QColor

    def refresh_devices(self):
        """刷新设备列表."""
        current_text = self.domain_combo.currentText()
        domain = self.domain_mapping.get(current_text, "all")
        self.load_devices(domain)

    def filter_devices(self):
        """根据搜索框过滤设备."""
        search_text = self.search_input.text().lower()

        for row in range(self.device_table.rowCount()):
            show_row = True

            if search_text:
                prompt = (
                    self.device_table.item(row, 0).text().lower()
                )  # Prompt现在在第0列
                entity_id = (
                    self.device_table.item(row, 1).text().lower()
                )  # 设备ID现在在第1列

                show_row = search_text in prompt or search_text in entity_id

            self.device_table.setRowHidden(row, not show_row)

    def add_selected_device(self):
        """添加选中的设备."""
        # QTableWidget 获取选中行的方式不同
        selected_indexes = self.device_table.selectedIndexes()
        if not selected_indexes:
            QMessageBox.warning(self, "警告", "请先选择一个设备")
            return

        # 由于 selectionBehavior 是 SelectRows，同一行的所有列都会被选中
        # 我们只需要获取一次行号
        row = selected_indexes[0].row()

        # 检查是否为有效行（避免选中表头或空行等）
        if row < 0 or row >= self.device_table.rowCount():
            self.logger.warning(f"无效的选中行: {row}")
            return

        # 检查是否为加载中或无设备提示行
        if self.device_table.item(row, 1) is None:
            self.logger.warning(f"选中的行不是有效的设备行: {row}")
            QMessageBox.warning(self, "警告", "请选择一个有效的设备行")
            return

        entity_id = self.device_table.item(row, 1).text()  # 设备ID现在在第1列

        # 检查设备是否已添加
        if any(d.get("entity_id") == entity_id for d in self.added_devices):
            QMessageBox.information(self, "提示", f"设备 {entity_id} 已添加")
            return

        # 使用标准的 QLineEdit 获取文本
        friendly_name = (
            self.custom_name_input.text().strip()
            or self.device_table.item(row, 0).text()
        )  # Prompt现在在第0列

        # 添加设备到配置
        self.save_device_to_config(entity_id, friendly_name)

        # 更新UI
        # self.refresh_added_devices() # refresh_added_devices 会在切换页面时调用
        # self.refresh_devices()  # 刷新设备列表以更新颜色标记, load_devices 会处理

        # 切换到已添加设备页面以查看结果 (可选)
        added_tab_index = self._nav_keys.index("added")
        if added_tab_index is not None:
            self.nav_segment.setCurrentIndex(added_tab_index)
            # on_page_changed_by_index 会被触发，从而调用 refresh_added_devices
        else:  # 如果找不到 'added' key，手动刷新
            self.reload_config()
            self.refresh_added_devices()

        # 刷新当前（可用设备）页面的颜色标记
        self.refresh_devices()

        # 清空自定义Prompt输入框
        self.custom_name_input.clear()

    def refresh_added_devices(self):
        """刷新已添加设备表格."""
        # 已在on_page_changed_by_index中调用了reload_config，这里直接使用self.added_devices

        # 暂时断开单元格变化信号，避免在填充数据时触发更新
        try:
            self.added_device_table.cellChanged.disconnect(self.on_prompt_edited)
        except Exception as e:
            self.logger.warning(f"重新加载配置时出错: {e}")
            pass  # 如果信号未连接，忽略错误

        # 清空表格
        self.added_device_table.setRowCount(0)

        # 如果没有设备，显示提示
        if not self.added_devices:
            empty_row = self.added_device_table.rowCount()
            self.added_device_table.insertRow(empty_row)
            empty_item = QTableWidgetItem("未添加任何设备")
            empty_item.setTextAlignment(Qt.AlignCenter)
            self.added_device_table.setItem(empty_row, 0, empty_item)
            self.added_device_table.setSpan(empty_row, 0, 1, 3)
            # 重新连接单元格编辑完成信号
            self.added_device_table.cellChanged.connect(self.on_prompt_edited)
            return

        # 填充表格
        for device in self.added_devices:
            row = self.added_device_table.rowCount()
            self.added_device_table.insertRow(row)

            # Prompt - 设置为可编辑状态 (第0列)
            friendly_name = device.get("friendly_name", "")
            friendly_name_item = QTableWidgetItem(friendly_name)
            # friendly_name_item是默认可编辑的
            self.added_device_table.setItem(row, 0, friendly_name_item)

            # 设备ID (第1列)
            entity_id = device.get("entity_id", "")
            entity_id_item = QTableWidgetItem(entity_id)
            entity_id_item.setFlags(
                entity_id_item.flags() & ~Qt.ItemIsEditable
            )  # 设置为不可编辑
            self.added_device_table.setItem(row, 1, entity_id_item)

            # 删除按钮 (第2列) - 使用 QPushButton
            delete_button = QPushButton("删除")
            delete_button.clicked.connect(lambda checked, r=row: self.delete_device(r))
            self.added_device_table.setCellWidget(row, 2, delete_button)

        # 重新连接单元格编辑完成信号
        self.added_device_table.cellChanged.connect(self.on_prompt_edited)

    def delete_device(self, row):
        """删除指定行的设备."""
        entity_id = self.added_device_table.item(row, 1).text()  # 设备ID现在在第1列

        # 询问确认
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除设备 {entity_id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            # 从配置中删除
            success = self.delete_device_from_config(entity_id)

            if success:
                # 重新从磁盘加载配置
                self.reload_config()

                # 更新UI
                self.refresh_added_devices()
                self.refresh_devices()  # 刷新设备列表以更新颜色标记

    def save_device_to_config(
        self, entity_id: str, friendly_name: Optional[str] = None
    ) -> bool:
        """将设备添加到配置文件中."""
        try:
            # 获取配置文件路径
            config_path = os.path.join(project_root, "config", "config.json")

            # 读取当前配置
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 确保HOME_ASSISTANT和DEVICES存在
            if "HOME_ASSISTANT" not in config:
                config["HOME_ASSISTANT"] = {}

            if "DEVICES" not in config["HOME_ASSISTANT"]:
                config["HOME_ASSISTANT"]["DEVICES"] = []

            # 检查设备是否已存在
            for device in config["HOME_ASSISTANT"]["DEVICES"]:
                if device.get("entity_id") == entity_id:
                    # 如果提供了新的friendly_name，则更新
                    if friendly_name and device.get("friendly_name") != friendly_name:
                        device["friendly_name"] = friendly_name

                        # 写入配置
                        with open(config_path, "w", encoding="utf-8") as f:
                            json.dump(config, f, ensure_ascii=False, indent=2)

                        QMessageBox.information(
                            self,
                            "更新成功",
                            f"设备 {entity_id} 的Prompt已更新为: {friendly_name}",
                        )
                    else:
                        QMessageBox.information(
                            self, "提示", f"设备 {entity_id} 已存在于配置中"
                        )

                    return True

            # 添加新设备
            new_device = {"entity_id": entity_id}

            if friendly_name:
                new_device["friendly_name"] = friendly_name

            config["HOME_ASSISTANT"]["DEVICES"].append(new_device)

            # 写入配置
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            QMessageBox.information(
                self,
                "添加成功",
                f"成功添加设备: {entity_id}"
                + (f" (Prompt: {friendly_name})" if friendly_name else ""),
            )

            return True

        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置失败: {e}")
            return False

    def delete_device_from_config(self, entity_id: str) -> bool:
        """从配置文件中删除设备."""
        try:
            # 获取配置文件路径
            config_path = os.path.join(project_root, "config", "config.json")

            # 读取当前配置
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # 检查HOME_ASSISTANT和DEVICES是否存在
            if (
                "HOME_ASSISTANT" not in config
                or "DEVICES" not in config["HOME_ASSISTANT"]
            ):
                QMessageBox.warning(self, "警告", "配置中不存在Home Assistant设备")
                return False

            # 搜索并删除设备
            devices = config["HOME_ASSISTANT"]["DEVICES"]
            initial_count = len(devices)

            config["HOME_ASSISTANT"]["DEVICES"] = [
                device for device in devices if device.get("entity_id") != entity_id
            ]

            if len(config["HOME_ASSISTANT"]["DEVICES"]) < initial_count:
                # 写入配置
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)

                QMessageBox.information(self, "删除成功", f"成功删除设备: {entity_id}")
                return True
            else:
                QMessageBox.warning(self, "警告", f"未找到设备: {entity_id}")
                return False

        except Exception as e:
            QMessageBox.critical(self, "错误", f"删除设备失败: {e}")
            return False

    def show_error(self, error_message):
        """显示错误消息."""
        # 线程完成后从线程列表中移除
        sender = self.sender()
        if sender in self.threads:
            self.threads.remove(sender)

        self.device_table.setRowCount(0)
        error_row = self.device_table.rowCount()
        self.device_table.insertRow(error_row)
        error_item = QTableWidgetItem(f"加载失败: {error_message}")
        error_item.setTextAlignment(Qt.AlignCenter)
        self.device_table.setItem(error_row, 0, error_item)
        self.device_table.setSpan(error_row, 0, 1, 4)

        QMessageBox.critical(self, "错误", f"加载设备失败: {error_message}")

    def on_prompt_edited(self, row, column):
        """处理已添加设备Prompt编辑完成事件."""
        # 只处理Prompt列(现在是列索引为0)的编辑
        if column != 0:
            return

        entity_id = self.added_device_table.item(row, 1).text()  # 设备ID现在在第1列
        new_prompt = self.added_device_table.item(row, 0).text()  # Prompt现在在第0列

        # 保存编辑后的Prompt
        self.save_device_to_config(entity_id, new_prompt)

    def on_available_device_prompt_edited(self, row, column):
        """处理可用设备Prompt编辑完成事件."""
        # 只处理Prompt列(现在是列索引为0)的编辑
        if column != 0:
            return

        # 获取编辑后的Prompt
        new_prompt = self.device_table.item(row, 0).text()

        if row in [index.row() for index in self.device_table.selectedIndexes()]:
            self.custom_name_input.setText(new_prompt)
            self.logger.info(f"已更新自定义名称输入框: {new_prompt}")


def main():
    """主函数."""
    app = QApplication(sys.argv)

    # 创建并显示主窗口
    window = HomeAssistantDeviceManager()
    # 设置最小尺寸，但允许放大
    window.setMinimumSize(800, 480)
    # 设置初始大小
    window.resize(800, 480)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
