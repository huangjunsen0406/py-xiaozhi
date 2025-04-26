import json
import hashlib
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
import threading
import socket
import uuid
import sys

from src.utils.logging_config import get_logger
from src.utils.config_constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_CONFIG
from src.utils.device_activator import DeviceActivator

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()

    # 记录配置文件路径
    logger.info(f"配置目录: {CONFIG_DIR.absolute()}")
    logger.info(f"配置文件: {CONFIG_FILE.absolute()}")

    def __new__(cls):
        """确保单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化配置管理器"""
        self.logger = logger
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        # 加载配置
        self._config = self._load_config()
        self._initialize_client_id()
        self._initialize_device_id()

        # 初始化设备激活器 - 确保在网络配置前初始化
        self.device_activator = DeviceActivator(self)

        # 检查efuse.json是否存在，如果不存在则创建
        self._ensure_efuse_exists()

        # 初始化MQTT信息并处理激活流程
        self._initialize_mqtt_info()

    def _ensure_efuse_exists(self):
        """确保efuse.json文件存在并包含必要的配置"""
        efuse_file = Path(__file__).parent.parent.parent / "config" / "efuse.json"

        # 记录配置文件路径
        self.logger.info(f"efuse文件路径: {efuse_file.absolute()}")

        if not efuse_file.exists():
            # 使用设备指纹生成序列号
            from src.utils.device_fingerprint import get_device_fingerprint
            fingerprint = get_device_fingerprint()
            serial_number, source = fingerprint.generate_serial_number()

            # 使用硬件哈希生成HMAC密钥 (使用不同的哈希算法避免重复)
            hmac_key = fingerprint.generate_hardware_hash()

            self.logger.info(f"使用{source}生成序列号: {serial_number}")

            # 创建默认efuse数据
            default_data = {
                "serial_number": serial_number,
                "hmac_key": hmac_key,
                "activation_status": False
            }

            # 确保目录存在
            efuse_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                # 写入默认数据
                with open(efuse_file, 'w', encoding='utf-8') as f:
                    json.dump(default_data, f, indent=2, ensure_ascii=False)

                self.logger.info(f"已创建efuse配置文件: {efuse_file}")
                self.logger.info(f"生成序列号: {serial_number}")
                self.logger.info(f"生成HMAC密钥: {hmac_key[:8]}...")
                print(f"设备序列号: {serial_number}")
            except Exception as e:
                self.logger.error(f"创建efuse配置文件失败: {e}")
        else:
            self.logger.info(f"efuse配置文件已存在: {efuse_file}")

            # 验证文件内容是否完整
            try:
                with open(efuse_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 检查必要字段是否存在
                required_fields = ["serial_number", "hmac_key", "activation_status"]
                missing_fields = [
                    field for field in required_fields if field not in data
                ]

                if missing_fields:
                    self.logger.warning(f"efuse配置文件缺少字段: {missing_fields}")

                    # 添加缺失的字段
                    for field in missing_fields:
                        if field == "serial_number":
                            # 使用设备指纹生成序列号
                            from src.utils.device_fingerprint import get_device_fingerprint
                            fingerprint = get_device_fingerprint()
                            serial_number, source = fingerprint.generate_serial_number()
                            data[field] = serial_number
                            self.logger.info(
                                f"使用{source}生成序列号: {data[field]}"
                            )
                        elif field == "hmac_key":
                            # 使用设备指纹生成HMAC密钥
                            from src.utils.device_fingerprint import get_device_fingerprint
                            fingerprint = get_device_fingerprint()
                            data[field] = fingerprint.generate_hardware_hash()
                            self.logger.info(
                                f"使用硬件哈希生成HMAC密钥: {data[field][:8]}..."
                            )
                        else:
                            data[field] = False

                    # 重新写入修复后的数据
                    with open(efuse_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)

                    self.logger.info("已修复efuse配置文件")

                # 检查序列号和HMAC密钥是否为None，如果是，生成新值
                if data.get("serial_number") is None:
                    # 使用设备指纹生成序列号
                    from src.utils.device_fingerprint import get_device_fingerprint
                    fingerprint = get_device_fingerprint()
                    serial_number, source = fingerprint.generate_serial_number()
                    data["serial_number"] = serial_number
                    self.logger.info(
                        f"使用{source}生成序列号: {data['serial_number']}"
                    )
                    update_needed = True
                else:
                    self.logger.info(f"现有序列号: {data['serial_number']}")
                    update_needed = False

                if data.get("hmac_key") is None:
                    # 使用设备指纹生成HMAC密钥
                    from src.utils.device_fingerprint import get_device_fingerprint
                    fingerprint = get_device_fingerprint()
                    data["hmac_key"] = fingerprint.generate_hardware_hash()
                    self.logger.info(
                        f"使用硬件哈希生成HMAC密钥: {data['hmac_key'][:8]}..."
                    )
                    update_needed = True
                else:
                    self.logger.info("现有HMAC密钥已存在")

                # 如果更新了值，重新写入文件
                if update_needed:
                    with open(efuse_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    self.logger.info("已更新efuse配置文件")

                # 打印设备序列号
                print(f"设备序列号: {data['serial_number']}")

            except Exception as e:
                self.logger.error(f"验证efuse配置文件失败: {e}")

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，如果不存在则创建"""
        try:
            # 先尝试从当前工作目录加载
            config_file = Path("config/config.json")
            if config_file.exists():
                config = json.loads(config_file.read_text(encoding='utf-8'))
                return self._merge_configs(DEFAULT_CONFIG, config)

            # 再尝试从打包目录加载
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                config_file = Path(sys._MEIPASS) / "config" / "config.json"
                if config_file.exists():
                    config = json.loads(
                        config_file.read_text(encoding='utf-8')
                    )
                    return self._merge_configs(DEFAULT_CONFIG, config)

            # 最后尝试从开发环境目录加载
            if CONFIG_FILE.exists():
                config = json.loads(
                    CONFIG_FILE.read_text(encoding='utf-8')
                )
                return self._merge_configs(DEFAULT_CONFIG, config)
            else:
                # 创建默认配置
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                self._save_config(DEFAULT_CONFIG)
                return DEFAULT_CONFIG.copy()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict) -> bool:
        """保存配置到文件"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CONFIG_FILE.write_text(
                json.dumps(config, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            return True
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return False

    @staticmethod
    def _merge_configs(default: dict, custom: dict) -> dict:
        """递归合并配置字典"""
        result = default.copy()
        for key, value in custom.items():
            if (key in result and isinstance(result[key], dict)
                    and isinstance(value, dict)):
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
            for key in path.split('.'):
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
            *parts, last = path.split('.')
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

    def get_mac_address(self):
        """获取系统MAC地址作为设备ID"""
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        return ":".join([mac[i:i + 2] for i in range(0, 12, 2)])

    def generate_uuid(self) -> str:
        """生成 UUID v4"""
        return str(uuid.uuid4())

    def get_local_ip(self):
        """获取本地IP地址"""
        try:
            # 创建一个临时 socket 连接来获取本机 IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def _initialize_client_id(self):
        """确保存在客户端ID"""
        if not self.get_config("SYSTEM_OPTIONS.CLIENT_ID"):
            client_id = self.generate_uuid()
            success = self.update_config("SYSTEM_OPTIONS.CLIENT_ID", client_id)
            if success:
                logger.info(f"Generated new CLIENT_ID: {client_id}")
            else:
                logger.error("Failed to save new CLIENT_ID")

    def _initialize_device_id(self):
        """确保存在设备ID"""
        if not self.get_config("SYSTEM_OPTIONS.DEVICE_ID"):
            try:
                # 使用device_fingerprint获取主网卡MAC地址
                from src.utils.device_fingerprint import get_device_fingerprint
                fingerprint = get_device_fingerprint()
                primary_mac_info = fingerprint.get_primary_mac_address()
                
                if primary_mac_info:
                    device_hash, mac_type = primary_mac_info
                    self.logger.info(
                        f"使用{mac_type} MAC地址作为设备ID: {device_hash}"
                    )
                else:
                    # 备选方案：使用系统MAC地址
                    device_hash = self.get_mac_address()
                    self.logger.info(f"使用系统MAC地址作为设备ID: {device_hash}")
                
                success = self.update_config(
                    "SYSTEM_OPTIONS.DEVICE_ID", device_hash)
                if success:
                    logger.info(f"Generated new DEVICE_ID: {device_hash}")
                else:
                    logger.error("Failed to save new DEVICE_ID")
            except Exception as e:
                logger.error(f"Error generating DEVICE_ID: {e}")
                # 出错时仍使用旧方法
                device_hash = self.get_mac_address()
                self.update_config("SYSTEM_OPTIONS.DEVICE_ID", device_hash)
                logger.info(f"Fallback to system MAC as DEVICE_ID: {device_hash}")

    def _initialize_mqtt_info(self):
        """
        初始化MQTT信息和WebSocket信息
        每次启动都重新获取最新的服务配置信息

        Returns:
            dict: MQTT配置信息，获取失败则返回已保存的配置
        """
        try:
            # 尝试获取新的OTA信息
            ota_response = self._get_ota_response()

            if not ota_response:
                self.logger.warning("获取OTA信息失败，使用已保存的配置")
                return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")

            # 处理激活信息
            if ("activation" in ota_response and 
                self.get_config("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION") == "v2"):
                self.logger.info("检测到激活请求，开始设备激活流程")
                # 如果设备已经激活，但服务器仍然发送激活请求，可能需要重新激活
                if self.device_activator.is_activated():
                    self.logger.warning("设备已激活，但服务器仍然请求激活，尝试重新激活")

                # 处理激活流程
                activation_success = self.device_activator.process_activation(
                    ota_response["activation"])

                if not activation_success:
                    self.logger.error("设备激活失败")
                    # 如果是全新设备且激活失败，可能需要返回现有配置
                    return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")
                else:
                    self.logger.info("设备激活成功，重新获取配置")
                    # 重新获取OTA响应，应该不再包含激活信息
                    ota_response = self._get_ota_response()

            # 处理WebSocket配置
            if "websocket" in ota_response:
                websocket_info = ota_response["websocket"]
                self.logger.info("检测到WebSocket配置信息")

                # 更新WebSocket URL
                if "url" in websocket_info:
                    self.update_config(
                        "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL",
                        websocket_info["url"]
                    )
                    self.logger.info(f"WebSocket URL已更新: {websocket_info['url']}")

                # 更新WebSocket Token
                if "token" in websocket_info:
                    self.update_config(
                        "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN",
                        websocket_info["token"]
                    )
                    self.logger.info("WebSocket Token已更新")

                print("\nWebSocket配置信息:")
                print(f"URL: {self.get_config('SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL')}")
                print(f"Token: {self.get_config('SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN')[:10]}...")

            # 提取MQTT信息
            if "mqtt" in ota_response:
                mqtt_info = ota_response["mqtt"]
                # 更新配置
                self.update_config(
                    "SYSTEM_OPTIONS.NETWORK.MQTT_INFO", mqtt_info)
                self.logger.info("MQTT信息已成功更新")
                return mqtt_info
            else:
                self.logger.warning("OTA响应中没有MQTT信息")
                return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")

        except Exception as e:
            self.logger.error(f"初始化网络配置信息失败: {e}")
            # 发生错误时返回已保存的配置
            return self.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO")

    def _get_ota_response(self):
        """获取OTA服务器的完整响应"""
        MAC_ADDR = self.get_config("SYSTEM_OPTIONS.DEVICE_ID")
        OTA_VERSION_URL = self.get_config(
            "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")

        # 获取应用信息
        app_name = "xiaozhi"
        app_version = "1.6.0"  # 从payload中获取
        board_type = "lc-esp32-s3"  # 立创ESP32-S3开发板

        # 获取激活版本设置
        activation_version_setting = self.get_config(
            "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v2")

        # 确定使用哪个版本的激活协议
        if activation_version_setting in ["v1", "1"]:
            activation_version = "1"
        else:
            activation_version = "2"

        self.logger.info(
            f"OTA请求使用激活版本: {activation_version} "
            f"(配置值: {activation_version_setting})"
        )

        # 设置请求头
        headers = {
            "Activation-Version": activation_version,
            "Device-Id": MAC_ADDR,
            "Client-Id": self.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
            "User-Agent": f"{board_type}/{app_name}-{app_version}",
            "Accept-Language": "zh-CN"  # 添加语言标识，与C++版本保持一致
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
                "features": 20  # WiFi + BLE + PSRAM
            },
            "application": {
                "name": "xiaozhi",
                "version": "1.6.0",
                "compile_time": "2025-4-16T12:00:00Z",
                "idf_version": "v5.3.2"
            },
            "partition_table": [
                {
                    "label": "nvs",
                    "type": 1,
                    "subtype": 2,
                    "address": 36864,
                    "size": 24576
                },
                {
                    "label": "otadata",
                    "type": 1,
                    "subtype": 0,
                    "address": 61440,
                    "size": 8192
                },
                {
                    "label": "app0",
                    "type": 0,
                    "subtype": 0,
                    "address": 65536,
                    "size": 1966080
                },
                {
                    "label": "app1",
                    "type": 0,
                    "subtype": 0,
                    "address": 2031616,
                    "size": 1966080
                },
                {
                    "label": "spiffs",
                    "type": 1,
                    "subtype": 130,
                    "address": 3997696,
                    "size": 1966080
                }
            ],
            "ota": {
                "label": "app0"
            },
            "board": {
                "type": "lc-esp32-s3",
                "name": "立创ESP32-S3开发板",
                "features": ["wifi", "ble", "psram", "octal_flash"],
                "ip": self.get_local_ip(),
                "mac": MAC_ADDR
            }
        }

        try:
            # 发送请求到OTA服务器
            response = requests.post(
                OTA_VERSION_URL,
                headers=headers,
                json=payload,
                timeout=10,  # 设置超时时间，防止请求卡死
                proxies={'http': None, 'https': None}  # 禁用代理
            )

            # 检查HTTP状态码
            if response.status_code != 200:
                self.logger.error(f"OTA服务器错误: HTTP {response.status_code}")
                return None

            # 解析JSON数据
            response_data = response.json()

            # 保存OTA响应到文件
            try:
                log_dir = Path("logs")
                log_dir.mkdir(exist_ok=True)

                # 保存OTA请求
                with open(log_dir / "ota_request.json", "w", encoding="utf-8") as f:
                    request_data = {
                        "url": OTA_VERSION_URL,
                        "headers": headers,
                        "payload": payload
                    }
                    json.dump(request_data, f, indent=4, ensure_ascii=False)

                # 保存OTA响应
                with open(log_dir / "ota_response.json", "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=4, ensure_ascii=False)

                self.logger.info("OTA请求和响应已保存到logs目录")
            except Exception as e:
                self.logger.error(f"保存OTA日志失败: {e}")

            # 调试信息：打印完整的OTA响应
            self.logger.debug(
                f"OTA服务器返回数据: "
                f"{json.dumps(response_data, indent=4, ensure_ascii=False)}"
            )

            return response_data

        except requests.Timeout:
            self.logger.error("OTA请求超时，请检查网络或服务器状态")
            return None

        except requests.RequestException as e:
            self.logger.error(f"OTA请求失败: {e}")
            return None

        except Exception as e:
            self.logger.error(f"OTA请求处理过程中发生错误: {e}")
            return None


# 用于测试的函数
def setup_device_for_activation():
    """设置设备用于测试激活流程"""
    # 获取配置管理器实例
    config_manager = ConfigManager.get_instance()

    # 检查序列号和HMAC密钥
    if not config_manager.device_activator.has_serial_number():
        # 生成随机序列号
        serial_number = f"SN-{uuid.uuid4().hex[:16].upper()}"
        print(f"生成序列号: {serial_number}")

        # 烧录序列号
        if config_manager.device_activator.burn_serial_number(serial_number):
            print("序列号烧录成功")
        else:
            print("序列号烧录失败")
    else:
        sn = config_manager.device_activator.get_serial_number()
        print(f"设备已有序列号: {sn}")

    # 检查HMAC密钥
    if not config_manager.device_activator.get_hmac_key():
        # 生成随机HMAC密钥
        hmac_key = uuid.uuid4().hex
        print(f"生成HMAC密钥: {hmac_key}")

        # 烧录HMAC密钥
        if config_manager.device_activator.burn_hmac_key(hmac_key):
            print("HMAC密钥烧录成功")
        else:
            print("HMAC密钥烧录失败")
    else:
        print("设备已有HMAC密钥")