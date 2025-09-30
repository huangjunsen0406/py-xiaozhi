from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QWidget,
)

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger
from src.utils.resource_finder import get_project_root, resource_finder


class WakeWordWidget(QWidget):
    """
    唤醒词设置组件.
    """

    # 信号定义
    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager.get_instance()

        # UI控件引用
        self.ui_controls = {}

        # 初始化UI
        self._setup_ui()
        self._connect_events()
        self._load_config_values()

    def _setup_ui(self):
        """
        设置UI界面.
        """
        try:
            from PyQt5 import uic

            ui_path = Path(__file__).parent / "wake_word_widget.ui"
            uic.loadUi(str(ui_path), self)

            # 获取UI控件引用
            self._get_ui_controls()

        except Exception as e:
            self.logger.error(f"设置唤醒词UI失败: {e}", exc_info=True)
            raise

    def _get_ui_controls(self):
        """
        获取UI控件引用.
        """
        self.ui_controls.update(
            {
                "use_wake_word_check": self.findChild(QCheckBox, "use_wake_word_check"),
                "model_path_edit": self.findChild(QLineEdit, "model_path_edit"),
                "model_path_btn": self.findChild(QPushButton, "model_path_btn"),
                "wake_words_edit": self.findChild(QTextEdit, "wake_words_edit"),
            }
        )

    def _connect_events(self):
        """
        连接事件处理.
        """
        if self.ui_controls["use_wake_word_check"]:
            self.ui_controls["use_wake_word_check"].toggled.connect(
                self.settings_changed.emit
            )

        if self.ui_controls["model_path_edit"]:
            self.ui_controls["model_path_edit"].textChanged.connect(
                self.settings_changed.emit
            )

        if self.ui_controls["model_path_btn"]:
            self.ui_controls["model_path_btn"].clicked.connect(
                self._on_model_path_browse
            )

        if self.ui_controls["wake_words_edit"]:
            self.ui_controls["wake_words_edit"].textChanged.connect(
                self.settings_changed.emit
            )

    def _load_config_values(self):
        """
        从配置文件加载值到UI控件.
        """
        try:
            # 唤醒词配置
            use_wake_word = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False
            )
            if self.ui_controls["use_wake_word_check"]:
                self.ui_controls["use_wake_word_check"].setChecked(use_wake_word)

            model_path = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH", ""
            )
            self._set_text_value("model_path_edit", model_path)

            # 从 keywords.txt 文件读取唤醒词
            wake_words_text = self._load_keywords_from_file()
            if self.ui_controls["wake_words_edit"]:
                self.ui_controls["wake_words_edit"].setPlainText(wake_words_text)

        except Exception as e:
            self.logger.error(f"加载唤醒词配置值失败: {e}", exc_info=True)

    def _set_text_value(self, control_name: str, value: str):
        """
        设置文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setText"):
            control.setText(str(value) if value is not None else "")

    def _get_text_value(self, control_name: str) -> str:
        """
        获取文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "text"):
            return control.text().strip()
        return ""

    def _on_model_path_browse(self):
        """
        浏览模型路径.
        """
        try:
            current_path = self._get_text_value("model_path_edit")
            if not current_path:
                # 使用resource_finder查找默认models目录
                models_dir = resource_finder.find_models_dir()
                if models_dir:
                    current_path = str(models_dir)
                else:
                    # 如果找不到，使用项目根目录下的models
                    project_root = resource_finder.get_project_root()
                    current_path = str(project_root / "models")

            selected_path = QFileDialog.getExistingDirectory(
                self, "选择模型目录", current_path
            )

            if selected_path:
                # 转换为相对路径（如果适用）
                relative_path = self._convert_to_relative_path(selected_path)
                self._set_text_value("model_path_edit", relative_path)
                self.logger.info(
                    f"已选择模型路径: {selected_path}，存储为: {relative_path}"
                )

        except Exception as e:
            self.logger.error(f"浏览模型路径失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"浏览模型路径时发生错误: {str(e)}")

    def _convert_to_relative_path(self, model_path: str) -> str:
        """
        将绝对路径转换为相对于项目根目录的相对路径（如果在同一盘符）.
        """
        try:
            import os

            # 获取项目根目录
            project_root = get_project_root()

            # 检查是否在同一盘符（仅在Windows上适用）
            if os.name == "nt":  # Windows系统
                model_path_drive = os.path.splitdrive(model_path)[0]
                project_root_drive = os.path.splitdrive(str(project_root))[0]

                # 如果在同一盘符，计算相对路径
                if model_path_drive.lower() == project_root_drive.lower():
                    relative_path = os.path.relpath(model_path, project_root)
                    return relative_path
                else:
                    # 不在同一盘符，使用绝对路径
                    return model_path
            else:
                # 非Windows系统，直接计算相对路径
                try:
                    relative_path = os.path.relpath(model_path, project_root)
                    # 只有当相对路径不包含".."+os.sep时才使用相对路径
                    if not relative_path.startswith(
                        ".." + os.sep
                    ) and not relative_path.startswith("/"):
                        return relative_path
                    else:
                        # 相对路径包含向上查找，使用绝对路径
                        return model_path
                except ValueError:
                    # 无法计算相对路径（不同卷），使用绝对路径
                    return model_path
        except Exception as e:
            self.logger.warning(f"计算相对路径时出错，使用原始路径: {e}")
            return model_path

    def _load_keywords_from_file(self) -> str:
        """
        从 keywords.txt 文件加载唤醒词，按完整格式显示.
        """
        try:
            # 获取配置的模型路径
            model_path = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH", ""
            )
            if not model_path:
                # 如果没有配置模型路径，使用默认的models目录
                keywords_file = get_project_root() / "models" / "keywords.txt"
            else:
                # 使用配置的模型路径
                keywords_file = Path(model_path) / "keywords.txt"

            if not keywords_file.exists():
                self.logger.warning(f"关键词文件不存在: {keywords_file}")
                return ""

            keywords = []
            with open(keywords_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "@" in line and not line.startswith("#"):
                        # 保持完整格式: 拼音 @中文
                        keywords.append(line)

            return "\n".join(keywords)

        except Exception as e:
            self.logger.error(f"读取关键词文件失败: {e}")
            return ""

    def _save_keywords_to_file(self, keywords_text: str):
        """
        保存唤醒词到 keywords.txt 文件，支持完整格式.
        """
        try:
            # 获取配置的模型路径
            model_path = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH", ""
            )
            if not model_path:
                # 如果没有配置模型路径，使用默认的models目录
                keywords_file = get_project_root() / "models" / "keywords.txt"
            else:
                # 使用配置的模型路径
                keywords_file = Path(model_path) / "keywords.txt"

            # 处理输入的关键词文本
            lines = [line.strip() for line in keywords_text.split("\n") if line.strip()]

            processed_lines = []
            has_invalid_lines = False

            for line in lines:
                if "@" in line:
                    # 完整格式：拼音 @中文
                    processed_lines.append(line)
                else:
                    # 只有中文，没有拼音 - 标记为无效
                    processed_lines.append(f"# 无效：缺少拼音格式 - {line}")
                    has_invalid_lines = True
                    self.logger.warning(
                        f"关键词 '{line}' 缺少拼音，需要格式：拼音 @中文"
                    )

            # 写入文件
            with open(keywords_file, "w", encoding="utf-8") as f:
                f.write("\n".join(processed_lines) + "\n")

            self.logger.info(f"成功保存关键词到 {keywords_file}")

            # 如果有无效格式，提示用户
            if has_invalid_lines:
                QMessageBox.warning(
                    self,
                    "格式错误",
                    "检测到无效的关键词格式！\n\n"
                    "正确格式：拼音 @中文\n"
                    "示例：x iǎo ài t óng x ué @小爱同学\n\n"
                    "无效的行已被注释，请手动修正后重新保存。",
                )

        except Exception as e:
            self.logger.error(f"保存关键词文件失败: {e}")
            QMessageBox.warning(self, "错误", f"保存关键词失败: {str(e)}")

    def get_config_data(self) -> dict:
        """
        获取当前配置数据.
        """
        config_data = {}

        try:
            # 唤醒词配置
            if self.ui_controls["use_wake_word_check"]:
                use_wake_word = self.ui_controls["use_wake_word_check"].isChecked()
                config_data["WAKE_WORD_OPTIONS.USE_WAKE_WORD"] = use_wake_word

            model_path = self._get_text_value("model_path_edit")
            if model_path:
                # 转换为相对路径（如果适用）
                relative_path = self._convert_to_relative_path(model_path)
                config_data["WAKE_WORD_OPTIONS.MODEL_PATH"] = relative_path

        except Exception as e:
            self.logger.error(f"获取唤醒词配置数据失败: {e}", exc_info=True)

        return config_data

    def save_keywords(self):
        """
        保存唤醒词到文件.
        """
        if self.ui_controls["wake_words_edit"]:
            wake_words_text = self.ui_controls["wake_words_edit"].toPlainText().strip()
            self._save_keywords_to_file(wake_words_text)

    def reset_to_defaults(self):
        """
        重置为默认值.
        """
        try:
            # 获取默认配置
            default_config = ConfigManager.DEFAULT_CONFIG

            # 唤醒词配置
            wake_word_config = default_config["WAKE_WORD_OPTIONS"]
            if self.ui_controls["use_wake_word_check"]:
                self.ui_controls["use_wake_word_check"].setChecked(
                    wake_word_config["USE_WAKE_WORD"]
                )

            self._set_text_value("model_path_edit", wake_word_config["MODEL_PATH"])

            if self.ui_controls["wake_words_edit"]:
                # 使用默认的关键词重置
                default_keywords = self._get_default_keywords()
                self.ui_controls["wake_words_edit"].setPlainText(default_keywords)

            self.logger.info("唤醒词配置已重置为默认值")

        except Exception as e:
            self.logger.error(f"重置唤醒词配置失败: {e}", exc_info=True)

    def _get_default_keywords(self) -> str:
        """
        获取默认关键词列表，完整格式.
        """
        default_keywords = [
            "x iǎo ài t óng x ué @小爱同学",
            "n ǐ h ǎo w èn w èn @你好问问",
            "x iǎo y ì x iǎo y ì @小艺小艺",
            "x iǎo m ǐ x iǎo m ǐ @小米小米",
            "n ǐ h ǎo x iǎo zh ì @你好小智",
            "j iā w éi s ī @贾维斯",
        ]
        return "\n".join(default_keywords)
