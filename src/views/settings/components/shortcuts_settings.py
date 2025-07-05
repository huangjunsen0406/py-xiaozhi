from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ShortcutsSettingsWidget(QWidget):
    """
    快捷键设置组件.
    """

    # 信号定义
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager.get_instance()
        self.shortcuts_config = self.config.get_config("SHORTCUTS", {})
        self.init_ui()

    def init_ui(self):
        """
        初始化UI.
        """
        layout = QVBoxLayout()

        # 启用快捷键选项
        self.enable_checkbox = QCheckBox("启用全局快捷键")
        self.enable_checkbox.setChecked(self.shortcuts_config.get("ENABLED", True))
        self.enable_checkbox.toggled.connect(self.on_settings_changed)
        layout.addWidget(self.enable_checkbox)

        # 快捷键配置组
        shortcuts_group = QGroupBox("快捷键配置")
        shortcuts_layout = QVBoxLayout()

        # 创建各个快捷键配置控件
        self.shortcut_widgets = {}

        # 按住说话
        self.shortcut_widgets["MANUAL_PRESS"] = self.create_shortcut_config(
            "按住说话", self.shortcuts_config.get("MANUAL_PRESS", {})
        )
        shortcuts_layout.addWidget(self.shortcut_widgets["MANUAL_PRESS"])

        # 自动对话
        self.shortcut_widgets["AUTO_TOGGLE"] = self.create_shortcut_config(
            "自动对话", self.shortcuts_config.get("AUTO_TOGGLE", {})
        )
        shortcuts_layout.addWidget(self.shortcut_widgets["AUTO_TOGGLE"])

        # 中断对话
        self.shortcut_widgets["ABORT"] = self.create_shortcut_config(
            "中断对话", self.shortcuts_config.get("ABORT", {})
        )
        shortcuts_layout.addWidget(self.shortcut_widgets["ABORT"])

        # 模式切换
        self.shortcut_widgets["MODE_TOGGLE"] = self.create_shortcut_config(
            "模式切换", self.shortcuts_config.get("MODE_TOGGLE", {})
        )
        shortcuts_layout.addWidget(self.shortcut_widgets["MODE_TOGGLE"])

        # 窗口显示/隐藏
        self.shortcut_widgets["WINDOW_TOGGLE"] = self.create_shortcut_config(
            "窗口显示/隐藏", self.shortcuts_config.get("WINDOW_TOGGLE", {})
        )
        shortcuts_layout.addWidget(self.shortcut_widgets["WINDOW_TOGGLE"])

        shortcuts_group.setLayout(shortcuts_layout)
        layout.addWidget(shortcuts_group)

        # 按钮区域
        btn_layout = QHBoxLayout()
        self.reset_btn = QPushButton("恢复默认")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        btn_layout.addWidget(self.reset_btn)

        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self.apply_settings)
        btn_layout.addWidget(self.apply_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def create_shortcut_config(self, title, config):
        """
        创建单个快捷键配置控件.
        """
        widget = QWidget()
        layout = QHBoxLayout()

        # 标题
        layout.addWidget(QLabel(f"{title}:"))

        # 修饰键选择
        modifier_combo = QComboBox()
        modifier_combo.addItems(["Ctrl", "Alt", "Shift"])
        current_modifier = config.get("modifier", "ctrl").title()
        modifier_combo.setCurrentText(current_modifier)
        modifier_combo.currentTextChanged.connect(self.on_settings_changed)
        layout.addWidget(modifier_combo)

        # 按键选择
        key_combo = QComboBox()
        key_combo.addItems([chr(i) for i in range(ord("a"), ord("z") + 1)])  # a-z
        current_key = config.get("key", "j").lower()
        key_combo.setCurrentText(current_key)
        key_combo.currentTextChanged.connect(self.on_settings_changed)
        layout.addWidget(key_combo)

        widget.setLayout(layout)
        widget.modifier_combo = modifier_combo
        widget.key_combo = key_combo
        return widget

    def on_settings_changed(self):
        """
        设置变更回调.
        """
        self.settings_changed.emit()

    def apply_settings(self):
        """
        应用设置.
        """
        try:
            # 更新启用状态
            self.config.update_config(
                "SHORTCUTS.ENABLED", self.enable_checkbox.isChecked()
            )

            # 更新各个快捷键配置
            for key, widget in self.shortcut_widgets.items():
                modifier = widget.modifier_combo.currentText().lower()
                key_value = widget.key_combo.currentText().lower()

                self.config.update_config(f"SHORTCUTS.{key}.modifier", modifier)
                self.config.update_config(f"SHORTCUTS.{key}.key", key_value)

            # 重新加载配置
            self.config.reload_config()
            self.shortcuts_config = self.config.get_config("SHORTCUTS", {})

            logger.info("快捷键设置已保存")

        except Exception as e:
            logger.error(f"保存快捷键设置失败: {e}")

    def reset_to_defaults(self):
        """
        恢复默认设置.
        """
        # 默认配置
        defaults = {
            "ENABLED": True,
            "MANUAL_PRESS": {"modifier": "ctrl", "key": "j"},
            "AUTO_TOGGLE": {"modifier": "ctrl", "key": "k"},
            "ABORT": {"modifier": "ctrl", "key": "q"},
            "MODE_TOGGLE": {"modifier": "ctrl", "key": "m"},
            "WINDOW_TOGGLE": {"modifier": "ctrl", "key": "w"},
        }

        # 更新UI
        self.enable_checkbox.setChecked(defaults["ENABLED"])

        for key, config in defaults.items():
            if key == "ENABLED":
                continue

            widget = self.shortcut_widgets.get(key)
            if widget:
                widget.modifier_combo.setCurrentText(config["modifier"].title())
                widget.key_combo.setCurrentText(config["key"].lower())

        # 触发变更信号
        self.on_settings_changed()
