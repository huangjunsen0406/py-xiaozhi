from pathlib import Path

from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextEdit,
)

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger
from src.utils.resource_finder import resource_finder
from src.views.settings.components.shortcuts_settings import ShortcutsSettingsWidget


class SettingsWindow(QDialog):
    """
    参数配置窗口.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.config_manager = ConfigManager.get_instance()

        # UI控件
        self.ui_controls = {}

        # 快捷键设置组件
        self.shortcuts_tab = None

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

            ui_path = Path(__file__).parent / "settings_window.ui"
            uic.loadUi(str(ui_path), self)

            # 获取所有UI控件的引用
            self._get_ui_controls()

            # 添加快捷键设置选项卡
            self._add_shortcuts_tab()

        except Exception as e:
            self.logger.error(f"设置UI失败: {e}", exc_info=True)
            raise

    def _add_shortcuts_tab(self):
        """
        添加快捷键设置选项卡.
        """
        try:
            # 获取TabWidget
            tab_widget = self.findChild(QTabWidget, "tabWidget")
            if not tab_widget:
                self.logger.error("未找到TabWidget控件")
                return

            # 创建快捷键设置组件
            self.shortcuts_tab = ShortcutsSettingsWidget()

            # 添加到选项卡
            tab_widget.addTab(self.shortcuts_tab, "快捷键")

            # 连接信号
            self.shortcuts_tab.settings_changed.connect(self._on_settings_changed)

            self.logger.debug("成功添加快捷键设置选项卡")

        except Exception as e:
            self.logger.error(f"添加快捷键设置选项卡失败: {e}", exc_info=True)

    def _on_settings_changed(self):
        """
        设置变更回调.
        """
        # 可以在此添加一些提示或者其他逻辑

    def _get_ui_controls(self):
        """
        获取UI控件引用.
        """
        # 系统选项控件
        self.ui_controls.update(
            {
                "client_id_edit": self.findChild(QLineEdit, "client_id_edit"),
                "device_id_edit": self.findChild(QLineEdit, "device_id_edit"),
                "ota_url_edit": self.findChild(QLineEdit, "ota_url_edit"),
                "websocket_url_edit": self.findChild(QLineEdit, "websocket_url_edit"),
                "websocket_token_edit": self.findChild(
                    QLineEdit, "websocket_token_edit"
                ),
                "authorization_url_edit": self.findChild(
                    QLineEdit, "authorization_url_edit"
                ),
                "activation_version_combo": self.findChild(
                    QComboBox, "activation_version_combo"
                ),
            }
        )

        # MQTT配置控件
        self.ui_controls.update(
            {
                "mqtt_endpoint_edit": self.findChild(QLineEdit, "mqtt_endpoint_edit"),
                "mqtt_client_id_edit": self.findChild(QLineEdit, "mqtt_client_id_edit"),
                "mqtt_username_edit": self.findChild(QLineEdit, "mqtt_username_edit"),
                "mqtt_password_edit": self.findChild(QLineEdit, "mqtt_password_edit"),
                "mqtt_publish_topic_edit": self.findChild(
                    QLineEdit, "mqtt_publish_topic_edit"
                ),
                "mqtt_subscribe_topic_edit": self.findChild(
                    QLineEdit, "mqtt_subscribe_topic_edit"
                ),
            }
        )

        # 唤醒词配置控件
        self.ui_controls.update(
            {
                "use_wake_word_check": self.findChild(QCheckBox, "use_wake_word_check"),
                "model_path_edit": self.findChild(QLineEdit, "model_path_edit"),
                "model_path_btn": self.findChild(QPushButton, "model_path_btn"),
                "wake_words_edit": self.findChild(QTextEdit, "wake_words_edit"),
            }
        )

        # 摄像头配置控件
        self.ui_controls.update(
            {
                "camera_index_spin": self.findChild(QSpinBox, "camera_index_spin"),
                "frame_width_spin": self.findChild(QSpinBox, "frame_width_spin"),
                "frame_height_spin": self.findChild(QSpinBox, "frame_height_spin"),
                "fps_spin": self.findChild(QSpinBox, "fps_spin"),
                "local_vl_url_edit": self.findChild(QLineEdit, "local_vl_url_edit"),
                "vl_api_key_edit": self.findChild(QLineEdit, "vl_api_key_edit"),
                "models_edit": self.findChild(QLineEdit, "models_edit"),
            }
        )

        # 按钮控件
        self.ui_controls.update(
            {
                "save_btn": self.findChild(QPushButton, "save_btn"),
                "cancel_btn": self.findChild(QPushButton, "cancel_btn"),
                "reset_btn": self.findChild(QPushButton, "reset_btn"),
            }
        )

    def _connect_events(self):
        """
        连接事件处理.
        """
        if self.ui_controls["save_btn"]:
            self.ui_controls["save_btn"].clicked.connect(self._on_save_clicked)

        if self.ui_controls["cancel_btn"]:
            self.ui_controls["cancel_btn"].clicked.connect(self.reject)

        if self.ui_controls["reset_btn"]:
            self.ui_controls["reset_btn"].clicked.connect(self._on_reset_clicked)

        if self.ui_controls["model_path_btn"]:
            self.ui_controls["model_path_btn"].clicked.connect(
                self._on_model_path_browse
            )

    def _load_config_values(self):
        """
        从配置文件加载值到UI控件.
        """
        try:
            # 系统选项
            client_id = self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID", "")
            self._set_text_value("client_id_edit", client_id)

            device_id = self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID", "")
            self._set_text_value("device_id_edit", device_id)

            ota_url = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", ""
            )
            self._set_text_value("ota_url_edit", ota_url)

            websocket_url = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", ""
            )
            self._set_text_value("websocket_url_edit", websocket_url)

            websocket_token = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", ""
            )
            self._set_text_value("websocket_token_edit", websocket_token)

            auth_url = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", ""
            )
            self._set_text_value("authorization_url_edit", auth_url)

            # 激活版本
            activation_version = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1"
            )
            if self.ui_controls["activation_version_combo"]:
                combo = self.ui_controls["activation_version_combo"]
                combo.setCurrentText(activation_version)

            # MQTT配置
            mqtt_info = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.MQTT_INFO", {}
            )
            if mqtt_info:
                self._set_text_value(
                    "mqtt_endpoint_edit", mqtt_info.get("endpoint", "")
                )
                self._set_text_value(
                    "mqtt_client_id_edit", mqtt_info.get("client_id", "")
                )
                self._set_text_value(
                    "mqtt_username_edit", mqtt_info.get("username", "")
                )
                self._set_text_value(
                    "mqtt_password_edit", mqtt_info.get("password", "")
                )
                self._set_text_value(
                    "mqtt_publish_topic_edit", mqtt_info.get("publish_topic", "")
                )
                self._set_text_value(
                    "mqtt_subscribe_topic_edit", mqtt_info.get("subscribe_topic", "")
                )

            # 唤醒词配置
            use_wake_word = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.USE_WAKE_WORD", False
            )
            if self.ui_controls["use_wake_word_check"]:
                self.ui_controls["use_wake_word_check"].setChecked(use_wake_word)

            self._set_text_value(
                "model_path_edit",
                self.config_manager.get_config("WAKE_WORD_OPTIONS.MODEL_PATH", ""),
            )

            # 唤醒词列表
            wake_words = self.config_manager.get_config(
                "WAKE_WORD_OPTIONS.WAKE_WORDS", []
            )
            wake_words_text = "\n".join(wake_words) if wake_words else ""
            if self.ui_controls["wake_words_edit"]:
                self.ui_controls["wake_words_edit"].setPlainText(wake_words_text)

            # 摄像头配置
            camera_config = self.config_manager.get_config("CAMERA", {})
            self._set_spin_value(
                "camera_index_spin", camera_config.get("camera_index", 0)
            )
            self._set_spin_value(
                "frame_width_spin", camera_config.get("frame_width", 640)
            )
            self._set_spin_value(
                "frame_height_spin", camera_config.get("frame_height", 480)
            )
            self._set_spin_value("fps_spin", camera_config.get("fps", 30))
            self._set_text_value(
                "local_vl_url_edit", camera_config.get("Local_VL_url", "")
            )
            self._set_text_value("vl_api_key_edit", camera_config.get("VLapi_key", ""))
            self._set_text_value("models_edit", camera_config.get("models", ""))

        except Exception as e:
            self.logger.error(f"加载配置值失败: {e}", exc_info=True)

    def _set_text_value(self, control_name: str, value: str):
        """
        设置文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setText"):
            control.setText(str(value) if value is not None else "")

    def _set_spin_value(self, control_name: str, value: int):
        """
        设置数字控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setValue"):
            control.setValue(int(value) if value is not None else 0)

    def _get_text_value(self, control_name: str) -> str:
        """
        获取文本控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "text"):
            return control.text().strip()
        return ""

    def _get_spin_value(self, control_name: str) -> int:
        """
        获取数字控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "value"):
            return control.value()
        return 0

    def _on_save_clicked(self):
        """
        保存按钮点击事件.
        """
        try:
            # 收集所有配置数据
            success = self._save_all_config()

            if success:
                # 显示保存成功并提示重启
                reply = QMessageBox.question(
                    self,
                    "配置保存成功",
                    "配置已保存成功！\n\n为了使配置生效，建议重启软件。\n是否现在重启？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes,
                )

                if reply == QMessageBox.Yes:
                    self._restart_application()
                else:
                    self.accept()
            else:
                QMessageBox.warning(self, "错误", "配置保存失败，请检查输入的值。")

        except Exception as e:
            self.logger.error(f"保存配置失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"保存配置时发生错误: {str(e)}")

    def _save_all_config(self) -> bool:
        """
        保存所有配置.
        """
        try:
            # 系统选项 - 网络配置
            ota_url = self._get_text_value("ota_url_edit")
            if ota_url:
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL", ota_url
                )

            websocket_url = self._get_text_value("websocket_url_edit")
            if websocket_url:
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", websocket_url
                )

            websocket_token = self._get_text_value("websocket_token_edit")
            if websocket_token:
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", websocket_token
                )

            authorization_url = self._get_text_value("authorization_url_edit")
            if authorization_url:
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", authorization_url
                )

            # 激活版本
            if self.ui_controls["activation_version_combo"]:
                activation_version = self.ui_controls[
                    "activation_version_combo"
                ].currentText()
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", activation_version
                )

            # MQTT配置
            mqtt_config = {}
            mqtt_endpoint = self._get_text_value("mqtt_endpoint_edit")
            if mqtt_endpoint:
                mqtt_config["endpoint"] = mqtt_endpoint

            mqtt_client_id = self._get_text_value("mqtt_client_id_edit")
            if mqtt_client_id:
                mqtt_config["client_id"] = mqtt_client_id

            mqtt_username = self._get_text_value("mqtt_username_edit")
            if mqtt_username:
                mqtt_config["username"] = mqtt_username

            mqtt_password = self._get_text_value("mqtt_password_edit")
            if mqtt_password:
                mqtt_config["password"] = mqtt_password

            mqtt_publish_topic = self._get_text_value("mqtt_publish_topic_edit")
            if mqtt_publish_topic:
                mqtt_config["publish_topic"] = mqtt_publish_topic

            mqtt_subscribe_topic = self._get_text_value("mqtt_subscribe_topic_edit")
            if mqtt_subscribe_topic:
                mqtt_config["subscribe_topic"] = mqtt_subscribe_topic

            if mqtt_config:
                # 获取现有的MQTT配置并更新
                existing_mqtt = self.config_manager.get_config(
                    "SYSTEM_OPTIONS.NETWORK.MQTT_INFO", {}
                )
                existing_mqtt.update(mqtt_config)
                self.config_manager.update_config(
                    "SYSTEM_OPTIONS.NETWORK.MQTT_INFO", existing_mqtt
                )

            # 唤醒词配置
            if self.ui_controls["use_wake_word_check"]:
                use_wake_word = self.ui_controls["use_wake_word_check"].isChecked()
                self.config_manager.update_config(
                    "WAKE_WORD_OPTIONS.USE_WAKE_WORD", use_wake_word
                )

            model_path = self._get_text_value("model_path_edit")
            if model_path:
                self.config_manager.update_config(
                    "WAKE_WORD_OPTIONS.MODEL_PATH", model_path
                )

            # 唤醒词列表
            if self.ui_controls["wake_words_edit"]:
                wake_words_text = (
                    self.ui_controls["wake_words_edit"].toPlainText().strip()
                )
                wake_words = [
                    word.strip() for word in wake_words_text.split("\n") if word.strip()
                ]
                self.config_manager.update_config(
                    "WAKE_WORD_OPTIONS.WAKE_WORDS", wake_words
                )

            # 摄像头配置
            camera_config = {}
            camera_config["camera_index"] = self._get_spin_value("camera_index_spin")
            camera_config["frame_width"] = self._get_spin_value("frame_width_spin")
            camera_config["frame_height"] = self._get_spin_value("frame_height_spin")
            camera_config["fps"] = self._get_spin_value("fps_spin")

            local_vl_url = self._get_text_value("local_vl_url_edit")
            if local_vl_url:
                camera_config["Local_VL_url"] = local_vl_url

            vl_api_key = self._get_text_value("vl_api_key_edit")
            if vl_api_key:
                camera_config["VLapi_key"] = vl_api_key

            models = self._get_text_value("models_edit")
            if models:
                camera_config["models"] = models

            # 获取现有的摄像头配置并更新
            existing_camera = self.config_manager.get_config("CAMERA", {})
            existing_camera.update(camera_config)
            self.config_manager.update_config("CAMERA", existing_camera)

            self.logger.info("配置保存成功")
            return True

        except Exception as e:
            self.logger.error(f"保存配置时出错: {e}", exc_info=True)
            return False

    def _on_reset_clicked(self):
        """
        重置按钮点击事件.
        """
        reply = QMessageBox.question(
            self,
            "确认重置",
            "确定要重置所有配置为默认值吗？\n这将清除当前的所有设置。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._reset_to_defaults()

    def _reset_to_defaults(self):
        """
        重置为默认值.
        """
        try:
            # 获取默认配置
            default_config = ConfigManager.DEFAULT_CONFIG

            # 系统选项
            self._set_text_value(
                "ota_url_edit",
                default_config["SYSTEM_OPTIONS"]["NETWORK"]["OTA_VERSION_URL"],
            )
            self._set_text_value("websocket_url_edit", "")
            self._set_text_value("websocket_token_edit", "")
            self._set_text_value(
                "authorization_url_edit",
                default_config["SYSTEM_OPTIONS"]["NETWORK"]["AUTHORIZATION_URL"],
            )

            if self.ui_controls["activation_version_combo"]:
                self.ui_controls["activation_version_combo"].setCurrentText(
                    default_config["SYSTEM_OPTIONS"]["NETWORK"]["ACTIVATION_VERSION"]
                )

            # 清空MQTT配置
            self._set_text_value("mqtt_endpoint_edit", "")
            self._set_text_value("mqtt_client_id_edit", "")
            self._set_text_value("mqtt_username_edit", "")
            self._set_text_value("mqtt_password_edit", "")
            self._set_text_value("mqtt_publish_topic_edit", "")
            self._set_text_value("mqtt_subscribe_topic_edit", "")

            # 唤醒词配置
            wake_word_config = default_config["WAKE_WORD_OPTIONS"]
            if self.ui_controls["use_wake_word_check"]:
                self.ui_controls["use_wake_word_check"].setChecked(
                    wake_word_config["USE_WAKE_WORD"]
                )

            self._set_text_value("model_path_edit", wake_word_config["MODEL_PATH"])

            if self.ui_controls["wake_words_edit"]:
                wake_words_text = "\n".join(wake_word_config["WAKE_WORDS"])
                self.ui_controls["wake_words_edit"].setPlainText(wake_words_text)

            # 摄像头配置
            camera_config = default_config["CAMERA"]
            self._set_spin_value("camera_index_spin", camera_config["camera_index"])
            self._set_spin_value("frame_width_spin", camera_config["frame_width"])
            self._set_spin_value("frame_height_spin", camera_config["frame_height"])
            self._set_spin_value("fps_spin", camera_config["fps"])
            self._set_text_value("local_vl_url_edit", camera_config["Local_VL_url"])
            self._set_text_value("vl_api_key_edit", camera_config["VLapi_key"])
            self._set_text_value("models_edit", camera_config["models"])

            self.logger.info("配置已重置为默认值")

        except Exception as e:
            self.logger.error(f"重置配置失败: {e}", exc_info=True)
            QMessageBox.critical(self, "错误", f"重置配置时发生错误: {str(e)}")

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
                self._set_text_value("model_path_edit", selected_path)
                self.logger.info(f"已选择模型路径: {selected_path}")

        except Exception as e:
            self.logger.error(f"浏览模型路径失败: {e}", exc_info=True)
            QMessageBox.warning(self, "错误", f"浏览模型路径时发生错误: {str(e)}")

    def _restart_application(self):
        """
        重启应用程序.
        """
        try:
            self.logger.info("用户选择重启应用程序")

            # 关闭设置窗口
            self.accept()

            # 直接重启程序
            self._direct_restart()

        except Exception as e:
            self.logger.error(f"重启应用程序失败: {e}", exc_info=True)
            QMessageBox.warning(
                self, "重启失败", "自动重启失败，请手动重启软件以使配置生效。"
            )

    def _direct_restart(self):
        """
        直接重启程序.
        """
        try:
            import os
            import sys

            # 获取当前执行的程序路径和参数
            python = sys.executable
            script = sys.argv[0]
            args = sys.argv[1:]

            self.logger.info(f"重启命令: {python} {script} {' '.join(args)}")

            # 关闭当前应用
            from PyQt5.QtWidgets import QApplication

            QApplication.quit()

            # 启动新实例
            if getattr(sys, "frozen", False):
                # 打包环境
                os.execv(sys.executable, [sys.executable] + args)
            else:
                # 开发环境
                os.execv(python, [python, script] + args)

        except Exception as e:
            self.logger.error(f"直接重启失败: {e}", exc_info=True)

    def closeEvent(self, event):
        """
        窗口关闭事件.
        """
        self.logger.debug("设置窗口已关闭")
        super().closeEvent(event)
