import json
import uuid
from typing import Any, Dict

from src.utils.logging_config import get_logger
from src.utils.resource_finder import resource_finder

logger = get_logger(__name__)


class ConfigManager:
    """配置管理器 - 单例模式"""

    _instance = None

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
            "USE_WAKE_WORD": True,
            "MODEL_PATH": "models",
            "NUM_THREADS": 4,
            "PROVIDER": "cpu",
            "MAX_ACTIVE_PATHS": 2,
            "KEYWORDS_SCORE": 1.8,
            "KEYWORDS_THRESHOLD": 0.2,
            "NUM_TRAILING_BLANKS": 1,
        },
        "CAMERA": {
            "camera_index": 0,
            "frame_width": 640,
            "frame_height": 480,
            "fps": 30,
            "Local_VL_url": "https://open.bigmodel.cn/api/paas/v4/",
            "VLapi_key": "",
            "models": "glm-4v-plus",
        },
        "SHORTCUTS": {
            "ENABLED": True,
            "MANUAL_PRESS": {"modifier": "ctrl", "key": "j", "description": "按住说话"},
            "AUTO_TOGGLE": {"modifier": "ctrl", "key": "k", "description": "自动对话"},
            "ABORT": {"modifier": "ctrl", "key": "q", "description": "中断对话"},
            "MODE_TOGGLE": {"modifier": "ctrl", "key": "m", "description": "切换模式"},
            "WINDOW_TOGGLE": {
                "modifier": "ctrl",
                "key": "w",
                "description": "显示/隐藏窗口",
            },
        },
        "AEC_OPTIONS": {
            "ENABLED": False,
            "BUFFER_MAX_LENGTH": 200,
            "FRAME_DELAY": 3,
            "FILTER_LENGTH_RATIO": 0.4,
            "ENABLE_PREPROCESS": True,
        },
        "AUDIO_DEVICES": {
            "input_device_id": None,
            "input_device_name": None,
            "output_device_id": None,
            "output_device_name": None,
            "input_sample_rate": None,
            "output_sample_rate": None,
        },
    }

    def __new__(cls):
        """
        确保单例模式.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """
        初始化配置管理器.
        """
        if self._initialized:
            return
        self._initialized = True

        # 初始化配置文件路径
        self._init_config_paths()

        # 确保必要的目录存在
        self._ensure_required_directories()

        # 加载配置
        self._config = self._load_config()

    def _init_config_paths(self):
        """
        初始化配置文件路径.
        """
        # 使用resource_finder查找或创建配置目录
        self.config_dir = resource_finder.find_config_dir()
        if not self.config_dir:
            # 如果找不到配置目录，在项目根目录下创建
            project_root = resource_finder.get_project_root()
            self.config_dir = project_root / "config"
            self.config_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建配置目录: {self.config_dir.absolute()}")

        self.config_file = self.config_dir / "config.json"

        # 记录配置文件路径
        logger.info(f"配置目录: {self.config_dir.absolute()}")
        logger.info(f"配置文件: {self.config_file.absolute()}")

    def _ensure_required_directories(self):
        """
        确保必要的目录存在.
        """
        project_root = resource_finder.get_project_root()

        # 创建 models 目录
        models_dir = project_root / "models"
        if not models_dir.exists():
            models_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建模型目录: {models_dir.absolute()}")

        # 创建 cache 目录
        cache_dir = project_root / "cache"
        if not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建缓存目录: {cache_dir.absolute()}")

    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建.
        """
        try:
            # 首先尝试使用resource_finder查找配置文件
            config_file_path = resource_finder.find_file("config/config.json")

            if config_file_path:
                logger.debug(f"使用resource_finder找到配置文件: {config_file_path}")
                config = json.loads(config_file_path.read_text(encoding="utf-8"))
                return self._merge_configs(self.DEFAULT_CONFIG, config)

            # 如果resource_finder没找到，尝试使用实例变量中的路径
            if self.config_file.exists():
                logger.debug(f"使用实例路径找到配置文件: {self.config_file}")
                config = json.loads(self.config_file.read_text(encoding="utf-8"))
                return self._merge_configs(self.DEFAULT_CONFIG, config)
            else:
                # 创建默认配置文件
                logger.info("配置文件不存在，创建默认配置")
                self._save_config(self.DEFAULT_CONFIG)
                return self.DEFAULT_CONFIG.copy()

        except Exception as e:
            logger.error(f"配置加载错误: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: dict) -> bool:
        """
        保存配置到文件.
        """
        try:
            # 确保配置目录存在
            self.config_dir.mkdir(parents=True, exist_ok=True)

            # 保存配置文件
            self.config_file.write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            logger.debug(f"配置已保存到: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"配置保存错误: {e}")
            return False

    @staticmethod
    def _merge_configs(default: dict, custom: dict) -> dict:
        """
        递归合并配置字典.
        """
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
        path: 点分隔的配置路径，如 "SYSTEM_OPTIONS.NETWORK.MQTT_INFO"
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
        path: 点分隔的配置路径，如 "SYSTEM_OPTIONS.NETWORK.MQTT_INFO"
        """
        try:
            current = self._config
            *parts, last = path.split(".")
            for part in parts:
                current = current.setdefault(part, {})
            current[last] = value
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"配置更新错误 {path}: {e}")
            return False

    def reload_config(self) -> bool:
        """
        重新加载配置文件.
        """
        try:
            self._config = self._load_config()
            logger.info("配置文件已重新加载")
            return True
        except Exception as e:
            logger.error(f"配置重新加载失败: {e}")
            return False

    def generate_uuid(self) -> str:
        """
        生成 UUID v4.
        """
        return str(uuid.uuid4())

    def initialize_client_id(self):
        """
        确保存在客户端ID.
        """
        if not self.get_config("SYSTEM_OPTIONS.CLIENT_ID"):
            client_id = self.generate_uuid()
            success = self.update_config("SYSTEM_OPTIONS.CLIENT_ID", client_id)
            if success:
                logger.info(f"已生成新的客户端ID: {client_id}")
            else:
                logger.error("保存新的客户端ID失败")

    def initialize_device_id_from_fingerprint(self, device_fingerprint):
        """
        从设备指纹初始化设备ID.
        """
        if not self.get_config("SYSTEM_OPTIONS.DEVICE_ID"):
            try:
                # 从efuse.json获取MAC地址作为DEVICE_ID
                mac_address = device_fingerprint.get_mac_address_from_efuse()
                if mac_address:
                    success = self.update_config(
                        "SYSTEM_OPTIONS.DEVICE_ID", mac_address
                    )
                    if success:
                        logger.info(f"从efuse.json获取DEVICE_ID: {mac_address}")
                    else:
                        logger.error("保存DEVICE_ID失败")
                else:
                    logger.error("无法从efuse.json获取MAC地址")
                    # 备用方案：从设备指纹直接获取
                    fingerprint = device_fingerprint.generate_fingerprint()
                    mac_from_fingerprint = fingerprint.get("mac_address")
                    if mac_from_fingerprint:
                        success = self.update_config(
                            "SYSTEM_OPTIONS.DEVICE_ID", mac_from_fingerprint
                        )
                        if success:
                            logger.info(
                                f"使用指纹中的MAC地址作为DEVICE_ID: "
                                f"{mac_from_fingerprint}"
                            )
                        else:
                            logger.error("保存备用DEVICE_ID失败")
            except Exception as e:
                logger.error(f"初始化DEVICE_ID时出错: {e}")

    @classmethod
    def get_instance(cls):
        """
        获取配置管理器实例.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
