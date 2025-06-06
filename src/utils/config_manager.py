import json
import socket
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import requests

from src.utils.device_activator import DeviceActivator
from src.utils.device_fingerprint import get_device_fingerprint
from src.utils.logging_config import get_logger
from src.utils.resource_finder import find_config_dir, find_file, get_app_path

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()

    # 配置文件路径
    CONFIG_DIR = find_config_dir()
    if not CONFIG_DIR:
        # 如果找不到配置目录，则使用项目根目录下的 config 文件夹
        CONFIG_DIR = Path(get_app_path()) / "config"
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE = CONFIG_DIR / "config.json"

    # 记录配置文件路径
    logger.info(f"配置目录: {CONFIG_DIR.absolute()}")
    logger.info(f"配置文件: {CONFIG_FILE.absolute()}")
    CONFIG_FILE = CONFIG_DIR / "config.json" if CONFIG_DIR else None

    # 记录配置文件路径
    if CONFIG_DIR:
        logger.info(f"配置目录: {CONFIG_DIR.absolute()}")
        logger.info(f"配置文件: {CONFIG_FILE.absolute()}")
    else:
        logger.warning("未找到配置目录，将使用默认配置")

    # 默认配置
    DEFAULT_CONFIG = {
        "SYSTEM_OPTIONS": {
            "CLIENT_ID": None,
            "DEVICE_ID": None,
            "NETWORK": {
                "OTA_VERSION_URL": "https://api.tenclass.net/xiaozhi/ota/",
                "WEBSOCKET_URL": None,
                "WEBSOCKET_ACCESS_TOKEN": None,
                "MQTT_INFO": None,
                "ACTIVATION_VERSION": "v2",  # 可选值: v1, v2
                "AUTHORIZATION_URL": "https://xiaozhi.me/",
            },
        },
        "WAKE_WORD_OPTIONS": {
            "USE_WAKE_WORD": False,
            "MODEL_PATH": "models/vosk-model-small-cn-0.22",
            "WAKE_WORDS": ["小智", "小美"],
        },
        "TEMPERATURE_SENSOR_MQTT_INFO": {
            "endpoint": "你的Mqtt连接地址",
            "port": 1883,
            "username": "admin",
            "password": "123456",
            "publish_topic": "sensors/temperature/command",
            "subscribe_topic": "sensors/temperature/device_001/state",
        },
        "HOME_ASSISTANT": {"URL": "http://localhost:8123", "TOKEN": "", "DEVICES": []},
        "CAMERA": {
            "camera_index": 0,
            "frame_width": 640,
            "frame_height": 480,
            "fps": 30,
            "Loacl_VL_url": "https://open.bigmodel.cn/api/paas/v4/",
            "VLapi_key": "你自己的key",
            "models": "glm-4v-plus",
        },
    }

    def __new__(cls):
        """确保单例模式."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置管理器."""
        self.logger = logger
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.device_activator = None
        # 加载配置
        self._config = self._load_config()
        self.device_fingerprint = get_device_fingerprint()
        self.device_fingerprint._ensure_efuse_file()
        self._initialize_client_id()
        self._initialize_device_id()
        # self._initialize_mqtt_info()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，如果不存在则创建."""
        try:
            # 使用 resource_finder 查找配置文件
            config_file_path = find_file("config/config.json")
            if config_file_path and config_file_path.exists():
                config = json.loads(config_file_path.read_text(encoding="utf-8"))
                return self._merge_configs(self.DEFAULT_CONFIG, config)

            # 如果找不到配置文件，尝试使用类变量中的路径
            if self.CONFIG_FILE and self.CONFIG_FILE.exists():
                config = json.loads(self.CONFIG_FILE.read_text(encoding="utf-8"))
                return self._merge_configs(self.DEFAULT_CONFIG, config)
            else:
                # 创建默认配置
                if self.CONFIG_DIR:
                    self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                    self._save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict) -> bool:
        """保存配置到文件."""
        try:
            if self.CONFIG_DIR and self.CONFIG_FILE:
                self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                self.CONFIG_FILE.write_text(
                    json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                return True
            else:
                logger.error("配置目录或文件路径未找到，无法保存配置")
                return False
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    @staticmethod
    def _merge_configs(default: dict, custom: dict) -> dict:
        """递归合并配置字典."""
        result = default.copy()
        for key, value in custom.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = ConfigManager._merge_configs(result[key], value)
            else:
                result[key] = value
        return result

    def get_config(self, path: str, default: Any = None) -> Any:
        """
        通过路径获取配置值
        path: 点分隔的配置路径，如 "network.mqtt.host"
        """
        try:
            value = self._config
            for key in path.split("."):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def update_config(self, path: str, value: Any) -> bool:
        """
        更新特定配置项
        path: 点分隔的配置路径，如 "network.mqtt.host"
        """
        try:
            current = self._config
            *parts, last = path.split(".")
            for part in parts:
                current = current.setdefault(part, {})
            current[last] = value
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"Error updating config {path}: {e}")
            return False

    @classmethod
    def get_instance(cls):
        """获取配置管理器实例（线程安全）"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def generate_uuid(self) -> str:
        """生成 UUID v4."""
        # 方法1：使用 Python 的 uuid 模块
        return str(uuid.uuid4())

    def get_local_ip(self):
        try:
            # 创建一个临时 socket 连接来获取本机 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _initialize_client_id(self):
        """确保存在客户端ID."""
        if not self.get_config("SYSTEM_OPTIONS.CLIENT_ID"):
            client_id = self.generate_uuid()
            success = self.update_config("SYSTEM_OPTIONS.CLIENT_ID", client_id)
            if success:
                logger.info(f"Generated new CLIENT_ID: {client_id}")
            else:
                logger.error("Failed to save new CLIENT_ID")

    def _initialize_device_id(self):
        """确保存在设备ID."""
        if not self.get_config("SYSTEM_OPTIONS.DEVICE_ID"):
            try:
                device_hash = self.device_fingerprint.generate_fingerprint().get(
                    "mac_address"
                )
                success = self.update_config("SYSTEM_OPTIONS.DEVICE_ID", device_hash)
                if success:
                    logger.info(f"Generated new DEVICE_ID: {device_hash}")
                else:
                    logger.error("Failed to save new DEVICE_ID")
            except Exception as e:
                logger.error(f"Error generating DEVICE_ID: {e}")

    def _initialize_mqtt_info(self):
        """初始化MQTT信息 每次启动都重新获取最新的MQTT配置信息.

        Returns:
            dict: MQTT配置信息，获取失败则返回已保存的配置
        """
        try:
            # 尝试获取新的MQTT信息
            response_data = self._get_ota_version()

            self.handle_mqtt_json(response_data)

            # 获取激活版本设置
            activation_version_setting = self.get_config(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v2"
            )

            if "websocket" in response_data:
                websocket_info = response_data["websocket"]
                self.logger.info("检测到WebSocket配置信息")

                # 更新WebSocket URL
                if "url" in websocket_info:
                    self.update_config(
                        "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", websocket_info["url"]
                    )
                    self.logger.info(f"WebSocket URL已更新: {websocket_info['url']}")

                # 更新WebSocket Token
                if "token" in websocket_info:
                    token_value = websocket_info["token"] or "test-token"
                else:
                    token_value = "test-token"

                self.update_config(
                    "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", token_value
                )
                self.logger.info("WebSocket Token已更新")

            # 确定使用哪个版本的激活协议
            if activation_version_setting in ["v1", "1"]:
                activation_version = "1"
            else:
                activation_version = "2"
                time.sleep(1)
                self.handle_v2_register(response_data)

            self.logger.info(
                f"OTA请求使用激活版本: {activation_version} "
                f"(配置值: {activation_version_setting})"
            )

        except Exception as e:
            self.logger.error(f"初始化MQTT信息失败: {e}")
            # 发生错误时返回已保存的配置
            return self.get_config("MQTT_INFO")

    def handle_v2_register(self, response_data):
        # 初始化设备激活器 - 确保在网络配置前初始化
        self.device_activator = DeviceActivator(self)
        # 处理激活信息
        if "activation" in response_data:
            self.logger.info("检测到激活请求，开始设备激活流程")
            # 如果设备已经激活，但服务器仍然发送激活请求，可能需要重新激活
            if self.device_activator.is_activated():
                self.logger.warning("设备已激活，但服务器仍然请求激活，尝试重新激活")

            # 处理激活流程
            activation_success = self.device_activator.process_activation(
                response_data["activation"]
            )

            if not activation_success:
                self.logger.error("设备激活失败")
                # 如果是全新设备且激活失败，可能需要返回现有配置
                return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")
            else:
                self.logger.info("设备激活成功，重新获取配置")
                # 重新获取OTA响应，应该不再包含激活信息
                response_data = self._get_ota_version()
            # 处理WebSocket配置

    def handle_mqtt_json(self, response_data):
        # 确保"mqtt"信息存在
        if "mqtt" in response_data:
            self.logger.info("MQTT服务器信息已更新")
            mqtt_info = response_data["mqtt"]
            if mqtt_info:
                # 更新配置
                self.update_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO", mqtt_info)
                self.logger.info("MQTT信息已成功更新")
                return mqtt_info
            else:
                self.logger.warning("获取MQTT信息失败，使用已保存的配置")
                return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")

    def _get_ota_version(self):
        """获取OTA服务器的MQTT信息."""
        MAC_ADDR = self.get_config("SYSTEM_OPTIONS.DEVICE_ID")
        OTA_VERSION_URL = self.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")

        # 获取应用信息
        app_name = "xiaozhi"
        app_version = "1.6.0"  # 从payload中获取
        board_type = "lc-esp32-s3"  # 立创ESP32-S3开发板

        # 设置请求头
        headers = {
            "Activation-Version": app_version,
            "Device-Id": MAC_ADDR,
            "Client-Id": self.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
            "User-Agent": f"{board_type}/{app_name}-{app_version}",
            "Accept-Language": "zh-CN",  # 添加语言标识，与C++版本保持一致
        }

        # 构建设备信息payload
        payload = {
            "version": 2,
            "flash_size": 16777216,  # 闪存大小 (16MB)
            "psram_size": 8388608,  # 8MB PSRAM
            "minimum_free_heap_size": 7265024,  # 最小可用堆内存
            "mac_address": MAC_ADDR,  # 设备MAC地址
            "uuid": self.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "chip_model_name": "esp32s3",  # 芯片型号
            "chip_info": {
                "model": 9,  # ESP32-S3
                "cores": 2,
                "revision": 0,  # 芯片版本修订
                "features": 20,  # WiFi + BLE + PSRAM
            },
            "application": {
                "name": "xiaozhi",
                "version": "1.6.0",
                "compile_time": "2025-4-16T12:00:00Z",
                "idf_version": "v5.3.2",
            },
            "partition_table": [
                {
                    "label": "nvs",
                    "type": 1,
                    "subtype": 2,
                    "address": 36864,
                    "size": 24576,
                },
                {
                    "label": "otadata",
                    "type": 1,
                    "subtype": 0,
                    "address": 61440,
                    "size": 8192,
                },
                {
                    "label": "app0",
                    "type": 0,
                    "subtype": 0,
                    "address": 65536,
                    "size": 1966080,
                },
                {
                    "label": "app1",
                    "type": 0,
                    "subtype": 0,
                    "address": 2031616,
                    "size": 1966080,
                },
                {
                    "label": "spiffs",
                    "type": 1,
                    "subtype": 130,
                    "address": 3997696,
                    "size": 1966080,
                },
            ],
            "ota": {"label": "app0"},
            "board": {
                "type": "lc-esp32-s3",
                "name": "立创ESP32-S3开发板",
                "features": ["wifi", "ble", "psram", "octal_flash"],
                "ip": self.get_local_ip(),
                "mac": MAC_ADDR,
            },
        }

        try:
            # 发送请求到OTA服务器
            response = requests.post(
                OTA_VERSION_URL,
                headers=headers,
                json=payload,
                timeout=10,  # 设置超时时间，防止请求卡死
                proxies={"http": None, "https": None},  # 禁用代理
            )

            # 检查HTTP状态码
            if response.status_code != 200:
                self.logger.error(f"OTA服务器错误: HTTP {response.status_code}")
                raise ValueError(f"OTA服务器返回错误状态码: {response.status_code}")

            # 解析JSON数据
            response_data = response.json()
            # 调试信息：打印完整的OTA响应
            self.logger.debug(
                f"OTA服务器返回数据: "
                f"{json.dumps(response_data, indent=4, ensure_ascii=False)}"
            )

            print(json.dumps(response_data, indent=4, ensure_ascii=False))

            return response_data

        except requests.Timeout:
            self.logger.error("OTA请求超时，请检查网络或服务器状态")
            raise ValueError("OTA请求超时！请稍后重试。")

        except requests.RequestException as e:
            self.logger.error(f"OTA请求失败: {e}")
            raise ValueError("无法连接到OTA服务器，请检查网络连接！")

    def get_app_path(self) -> Path:
        """获取应用程序的基础路径（支持开发环境和打包环境）"""
        return get_app_path()
