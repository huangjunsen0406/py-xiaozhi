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

# 导入拼音转换库
try:
    from pypinyin import Style, lazy_pinyin

    PYPINYIN_AVAILABLE = True
except ImportError:
    PYPINYIN_AVAILABLE = False


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

        # 声母表（用于拼音分割）
        self.initials = [
            "b",
            "p",
            "m",
            "f",
            "d",
            "t",
            "n",
            "l",
            "g",
            "k",
            "h",
            "j",
            "q",
            "x",
            "zh",
            "ch",
            "sh",
            "r",
            "z",
            "c",
            "s",
            "y",
            "w",
        ]

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
        从 keywords.txt 文件加载唤醒词，只显示中文部分.
        """
        try:
            # 获取配置的模型路径
            model_path = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH", "models"
            )

            # 使用 resource_finder 统一查找（和运行时保持一致）
            model_dir = resource_finder.find_directory(model_path)

            if model_dir is None:
                self.logger.warning(f"模型目录不存在: {model_path}")
                return ""

            keywords_file = model_dir / "keywords.txt"

            if not keywords_file.exists():
                self.logger.warning(f"关键词文件不存在: {keywords_file}")
                return ""

            keywords = []
            with open(keywords_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and "@" in line and not line.startswith("#"):
                        # 只提取@后面的中文部分显示
                        chinese_part = line.split("@", 1)[1].strip()
                        keywords.append(chinese_part)

            return "\n".join(keywords)

        except Exception as e:
            self.logger.error(f"读取关键词文件失败: {e}")
            return ""

    def _split_pinyin(self, pinyin: str) -> list:
        """将拼音按声母韵母分隔.

        例如: "xiǎo" -> ["x", "iǎo"]       "mǐ" -> ["m", "ǐ"]
        """
        if not pinyin:
            return []

        # 按长度优先尝试匹配声母（zh, ch, sh优先）
        for initial in sorted(self.initials, key=len, reverse=True):
            if pinyin.startswith(initial):
                final = pinyin[len(initial) :]
                if final:
                    return [initial, final]
                else:
                    return [initial]

        # 没有声母（零声母）
        return [pinyin]

    def _chinese_to_keyword_format(self, chinese_text: str) -> str:
        """将中文转换为keyword格式.

        Args:
            chinese_text: 中文文本，如"小米小米"

        Returns:
            keyword格式，如"x iǎo m ǐ x iǎo m ǐ @小米小米"
        """
        if not PYPINYIN_AVAILABLE:
            self.logger.error("pypinyin库未安装，无法自动转换")
            return f"# 转换失败（缺少pypinyin） - {chinese_text}"

        try:
            # 转换为带声调拼音
            pinyin_list = lazy_pinyin(chinese_text, style=Style.TONE)

            # 分割每个拼音
            split_parts = []
            for pinyin in pinyin_list:
                parts = self._split_pinyin(pinyin)
                split_parts.extend(parts)

            # 拼接结果
            pinyin_str = " ".join(split_parts)
            keyword_line = f"{pinyin_str} @{chinese_text}"

            return keyword_line

        except Exception as e:
            self.logger.error(f"转换拼音失败: {e}")
            return f"# 转换失败 - {chinese_text}"

    def _save_keywords_to_file(self, keywords_text: str):
        """
        保存唤醒词到 keywords.txt 文件，自动将中文转换为拼音格式.
        """
        try:
            # 检查pypinyin是否可用
            if not PYPINYIN_AVAILABLE:
                QMessageBox.warning(
                    self,
                    "缺少依赖",
                    "自动拼音转换功能需要安装 pypinyin 库\n\n"
                    "请运行: pip install pypinyin",
                )
                return

            # 获取配置的模型路径
            model_path = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH", "models"
            )

            # 使用 resource_finder 统一查找（和运行时保持一致）
            model_dir = resource_finder.find_directory(model_path)

            if model_dir is None:
                self.logger.error(f"模型目录不存在: {model_path}")
                QMessageBox.warning(
                    self,
                    "错误",
                    f"模型目录不存在: {model_path}\n请先配置正确的模型路径。",
                )
                return

            keywords_file = model_dir / "keywords.txt"

            # 处理输入的关键词文本（每行一个中文）
            lines = [line.strip() for line in keywords_text.split("\n") if line.strip()]

            processed_lines = []
            for chinese_text in lines:
                # 自动转换为拼音格式
                keyword_line = self._chinese_to_keyword_format(chinese_text)
                processed_lines.append(keyword_line)

            # 写入文件
            with open(keywords_file, "w", encoding="utf-8") as f:
                f.write("\n".join(processed_lines) + "\n")

            self.logger.info(
                f"成功保存 {len(processed_lines)} 个关键词到 {keywords_file}"
            )
            QMessageBox.information(
                self,
                "保存成功",
                f"成功保存 {len(processed_lines)} 个唤醒词\n\n" f"已自动转换为拼音格式",
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
        获取默认关键词列表，只返回中文.
        """
        default_keywords = [
            "小爱同学",
            "你好问问",
            "小艺小艺",
            "小米小米",
            "你好小智",
            "贾维斯",
        ]
        return "\n".join(default_keywords)
