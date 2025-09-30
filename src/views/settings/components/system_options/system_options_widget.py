from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QComboBox, QLineEdit, QWidget

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger


class SystemOptionsWidget(QWidget):
    """
    系统选项设置组件.
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

            ui_path = Path(__file__).parent / "system_options_widget.ui"
            uic.loadUi(str(ui_path), self)

            # 获取UI控件引用
            self._get_ui_controls()

        except Exception as e:
            self.logger.error(f"设置系统选项UI失败: {e}", exc_info=True)
            raise

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

        # AEC配置控件
        self.ui_controls.update(
            {
                "aec_enabled_check": self.findChild(QCheckBox, "aec_enabled_check"),
            }
        )

    def _connect_events(self):
        """
        连接事件处理.
        """
        # 为所有输入控件连接变更信号
        for control in self.ui_controls.values():
            if isinstance(control, QLineEdit):
                control.textChanged.connect(self.settings_changed.emit)
            elif isinstance(control, QComboBox):
                control.currentTextChanged.connect(self.settings_changed.emit)
            elif isinstance(control, QCheckBox):
                control.stateChanged.connect(self.settings_changed.emit)

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

            # AEC配置
            aec_enabled = self.config_manager.get_config("AEC_OPTIONS.ENABLED", True)
            self._set_check_value("aec_enabled_check", aec_enabled)

        except Exception as e:
            self.logger.error(f"加载系统选项配置值失败: {e}", exc_info=True)

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

    def _set_check_value(self, control_name: str, value: bool):
        """
        设置复选框控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "setChecked"):
            control.setChecked(bool(value))

    def _get_check_value(self, control_name: str) -> bool:
        """
        获取复选框控件的值.
        """
        control = self.ui_controls.get(control_name)
        if control and hasattr(control, "isChecked"):
            return control.isChecked()
        return False

    def get_config_data(self) -> dict:
        """
        获取当前配置数据.
        """
        config_data = {}

        try:
            # 系统选项 - 网络配置
            ota_url = self._get_text_value("ota_url_edit")
            if ota_url:
                config_data["SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL"] = ota_url

            websocket_url = self._get_text_value("websocket_url_edit")
            if websocket_url:
                config_data["SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL"] = websocket_url

            websocket_token = self._get_text_value("websocket_token_edit")
            if websocket_token:
                config_data["SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN"] = (
                    websocket_token
                )

            authorization_url = self._get_text_value("authorization_url_edit")
            if authorization_url:
                config_data["SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL"] = (
                    authorization_url
                )

            # 激活版本
            if self.ui_controls["activation_version_combo"]:
                activation_version = self.ui_controls[
                    "activation_version_combo"
                ].currentText()
                config_data["SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION"] = (
                    activation_version
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
                config_data["SYSTEM_OPTIONS.NETWORK.MQTT_INFO"] = existing_mqtt

            # AEC配置
            aec_enabled = self._get_check_value("aec_enabled_check")
            config_data["AEC_OPTIONS.ENABLED"] = aec_enabled

        except Exception as e:
            self.logger.error(f"获取系统选项配置数据失败: {e}", exc_info=True)

        return config_data

    def reset_to_defaults(self):
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

            # AEC配置默认值
            default_aec = default_config.get("AEC_OPTIONS", {})
            self._set_check_value(
                "aec_enabled_check", default_aec.get("ENABLED", False)
            )

            self.logger.info("系统选项配置已重置为默认值")

        except Exception as e:
            self.logger.error(f"重置系统选项配置失败: {e}", exc_info=True)
