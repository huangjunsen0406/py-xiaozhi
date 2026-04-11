from pathlib import Path

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QComboBox, QGroupBox, QLabel, QLineEdit, QWidget

from src.utils.config_manager import ConfigManager
from src.utils.language_manager import LanguageManager
from src.utils.logging_config import get_logger


# Translation dictionary for UI strings
UI_TRANSLATIONS = {
    "zh_CN": {
        "client_id": "客户端ID:",
        "device_id": "设备ID:",
        "ota_url": "OTA版本URL:",
        "websocket_url": "WebSocket URL:",
        "websocket_token": "WebSocket Token:",
        "authorization_url": "授权URL:",
        "activation_version": "激活版本:",
        "aec_enabled": "启用AEC回声消除:",
        "aec_enable": "启用",
        "window_size": "主界面宽高:",
        "window_default": "默认",
        "language": "语言:",
        "mqtt_config": "MQTT配置",
        "mqtt_endpoint": "端点:",
        "mqtt_client_id": "客户端ID:",
        "mqtt_username": "用户名:",
        "mqtt_password": "密码:",
        "mqtt_publish_topic": "发布主题:",
        "mqtt_subscribe_topic": "订阅主题:",
    },
    "en_US": {
        "client_id": "Client ID:",
        "device_id": "Device ID:",
        "ota_url": "OTA Version URL:",
        "websocket_url": "WebSocket URL:",
        "websocket_token": "WebSocket Token:",
        "authorization_url": "Authorization URL:",
        "activation_version": "Activation Version:",
        "aec_enabled": "Enable AEC Echo Cancellation:",
        "aec_enable": "Enable",
        "window_size": "Main Window Size:",
        "window_default": "Default",
        "language": "Language:",
        "mqtt_config": "MQTT Configuration",
        "mqtt_endpoint": "Endpoint:",
        "mqtt_client_id": "Client ID:",
        "mqtt_username": "Username:",
        "mqtt_password": "Password:",
        "mqtt_publish_topic": "Publish Topic:",
        "mqtt_subscribe_topic": "Subscribe Topic:",
    },
    "ru_RU": {
        "client_id": "ID клиента:",
        "device_id": "ID устройства:",
        "ota_url": "URL версии OTA:",
        "websocket_url": "URL WebSocket:",
        "websocket_token": "Токен WebSocket:",
        "authorization_url": "URL авторизации:",
        "activation_version": "Версия активации:",
        "aec_enabled": "Включить AEC (подавление эха):",
        "aec_enable": "Включить",
        "window_size": "Размер окна:",
        "window_default": "По умолчанию",
        "language": "Язык:",
        "mqtt_config": "Настройки MQTT",
        "mqtt_endpoint": "Конечная точка:",
        "mqtt_client_id": "ID клиента:",
        "mqtt_username": "Имя пользователя:",
        "mqtt_password": "Пароль:",
        "mqtt_publish_topic": "Тема публикации:",
        "mqtt_subscribe_topic": "Тема подписки:",
    },
}



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
                "window_size_combo": self.findChild(QComboBox, "window_size_combo"),
                "language_combo": self.findChild(QComboBox, "language_combo"),
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
        
        # Language combo needs special handling to actually change language
        if self.ui_controls["language_combo"]:
            self.ui_controls["language_combo"].currentTextChanged.connect(self._on_language_changed)

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

            # 窗口大小模式
            window_size_mode = self.config_manager.get_config(
                "SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "default"
            )
            if self.ui_controls["window_size_combo"]:
                # 映射配置值到显示文本（默认 = 50%）
                mode_to_text = {
                    "default": "默认",
                    "screen_75": "75%",
                    "screen_100": "100%",
                }
                combo = self.ui_controls["window_size_combo"]
                combo.setCurrentText(mode_to_text.get(window_size_mode, "默认"))

            # 语言设置
            language = self.config_manager.get_config("SYSTEM_OPTIONS.LANGUAGE", "zh_CN")
            if self.ui_controls["language_combo"]:
                lang_map = {"zh_CN": "简体中文", "en_US": "English", "ru_RU": "Русский"}
                self.ui_controls["language_combo"].setCurrentText(lang_map.get(language, "简体中文"))

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

    def _on_language_changed(self, display_text: str):
        """Handle language combo change - actually switch language."""
        text_to_lang = {"简体中文": "zh_CN", "English": "en_US", "Русский": "ru_RU"}
        lang_code = text_to_lang.get(display_text, "zh_CN")
        
        # Actually change the language
        lang_manager = LanguageManager.get_instance()
        lang_manager.set_language(lang_code)
        
        # Manually retranslate all UI strings
        self._retranslate_ui(lang_code)
        
        self.logger.info(f"Language changed to: {lang_code}")

    def _retranslate_ui(self, lang_code: str):
        """Manually retranslate all UI strings."""
        if lang_code not in UI_TRANSLATIONS:
            lang_code = "zh_CN"
        
        translations = UI_TRANSLATIONS[lang_code]
        
        # Update all label texts
        self.findChild(QLabel, "label_client_id").setText(translations["client_id"])
        self.findChild(QLabel, "label_device_id").setText(translations["device_id"])
        self.findChild(QLabel, "label_ota_url").setText(translations["ota_url"])
        self.findChild(QLabel, "label_websocket_url").setText(translations["websocket_url"])
        self.findChild(QLabel, "label_websocket_token").setText(translations["websocket_token"])
        self.findChild(QLabel, "label_authorization_url").setText(translations["authorization_url"])
        self.findChild(QLabel, "label_activation_version").setText(translations["activation_version"])
        self.findChild(QLabel, "label_aec_enabled").setText(translations["aec_enabled"])
        self.findChild(QCheckBox, "aec_enabled_check").setText(translations["aec_enable"])
        self.findChild(QLabel, "label_window_size").setText(translations["window_size"])
        self.findChild(QLabel, "label_language").setText(translations["language"])
        
        # Update MQTT group title and labels
        self.findChild(QGroupBox, "mqtt_group").setTitle(translations["mqtt_config"])
        self.findChild(QLabel, "label_mqtt_endpoint").setText(translations["mqtt_endpoint"])
        self.findChild(QLabel, "label_mqtt_client_id").setText(translations["mqtt_client_id"])
        self.findChild(QLabel, "label_mqtt_username").setText(translations["mqtt_username"])
        self.findChild(QLabel, "label_mqtt_password").setText(translations["mqtt_password"])
        self.findChild(QLabel, "label_mqtt_publish_topic").setText(translations["mqtt_publish_topic"])
        self.findChild(QLabel, "label_mqtt_subscribe_topic").setText(translations["mqtt_subscribe_topic"])
        
        # Update window size combo items
        window_size_combo = self.findChild(QComboBox, "window_size_combo")
        if window_size_combo:
            window_size_combo.setItemText(0, translations["window_default"])
            window_size_combo.setItemText(1, "75%")
            window_size_combo.setItemText(2, "100%")

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
            # 客户端ID和设备ID
            client_id = self._get_text_value("client_id_edit")
            if client_id:
                config_data["SYSTEM_OPTIONS.CLIENT_ID"] = client_id

            device_id = self._get_text_value("device_id_edit")
            if device_id:
                config_data["SYSTEM_OPTIONS.DEVICE_ID"] = device_id

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

            # 窗口大小模式
            if self.ui_controls["window_size_combo"]:
                # 映射显示文本到配置值（默认 = 50%）
                text_to_mode = {
                    "默认": "default",
                    "75%": "screen_75",
                    "100%": "screen_100",
                }
                window_size_text = self.ui_controls["window_size_combo"].currentText()
                window_size_mode = text_to_mode.get(window_size_text, "default")
                config_data["SYSTEM_OPTIONS.WINDOW_SIZE_MODE"] = window_size_mode

            # 语言设置
            if self.ui_controls["language_combo"]:
                text_to_lang = {"简体中文": "zh_CN", "English": "en_US", "Русский": "ru_RU"}
                lang_text = self.ui_controls["language_combo"].currentText()
                config_data["SYSTEM_OPTIONS.LANGUAGE"] = text_to_lang.get(lang_text, "zh_CN")

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
