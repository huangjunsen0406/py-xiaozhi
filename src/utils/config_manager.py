import json
import shutil
import uuid
from typing import Any, Dict

from src.logging import get_logger
from src.utils.resource_finder import (
    get_config_dir,
    get_user_cache_dir,
    get_user_data_dir,
)

logger = get_logger()


class ConfigManager:
    """
    配置管理器.
    """

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
            "MODEL_PATH": "models/zh",
            "NUM_THREADS": 5,
            "PROVIDER": "cpu",
            "MAX_ACTIVE_PATHS": 2,
            "KEYWORDS_SCORE": 1.8,
            "KEYWORDS_THRESHOLD": 0.2,
            "NUM_TRAILING_BLANKS": 1,
            "WAKE_WORD": "你好小智",
            "WAKE_WORD_LANG": "zh"
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
            "input_channels": None,
            "output_channels": None,
            "opus_output_sample_rate": 24000,  # Opus 解码采样率：24000(官方) 或 16000(第三方)
            "frame_duration": 20,  # 音频帧长度(ms)：20(低延迟) / 40(平衡) / 60(低CPU)
        },
        "LOGGING": {
            "LEVEL": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
            "FORMAT_TYPE": "colored",  # colored, json, simple
            "ENABLE_CONSOLE": True,
            "ENABLE_FILE": True,
            "ENABLE_ERROR_FILE": True,
            "ENABLE_JSON_FILE": False,
            "ENABLE_ASYNC": False,
            "ENABLE_SENSITIVE_FILTER": True,
            "MAX_BYTES": 10485760,  # 10MB
            "BACKUP_COUNT": 30,
            "ROTATION_WHEN": "midnight",  # midnight, H, D
            "THIRD_PARTY_LEVELS": {
                "urllib3": "WARNING",
                "websockets": "WARNING",
                "asyncio": "WARNING",
                "paho": "WARNING",
                "PIL": "WARNING",
            },
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

        配置文件存储到用户数据目录，打包后可写。
        首次运行时从安装目录迁移默认配置。
        """
        # 用户数据目录下的 config 子目录
        self.config_dir = get_user_data_dir() / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "config.json"

        # 如果用户目录没有配置文件，尝试从安装目录迁移
        if not self.config_file.exists():
            install_config = get_config_dir() / "config.json"
            if install_config.exists():
                try:
                    shutil.copy2(install_config, self.config_file)
                    logger.info(f"已从安装目录迁移配置: {install_config} -> {self.config_file}")
                except Exception as e:
                    logger.warning(f"迁移配置文件失败: {e}，将使用默认配置")

        # 记录配置文件路径
        logger.info(f"配置目录: {self.config_dir.absolute()}")
        logger.info(f"配置文件: {self.config_file.absolute()}")

    def _ensure_required_directories(self):
        """
        确保必要的目录存在.
        """
        # models 目录保留在安装目录（只读）
        # cache 目录使用用户缓存目录（可写）
        cache_dir = get_user_cache_dir()
        logger.debug(f"缓存目录: {cache_dir.absolute()}")

    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件，如果不存在则创建.
        """
        try:
            if self.config_file.exists():
                logger.debug(f"找到配置文件: {self.config_file}")
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

    @classmethod
    def get_instance(cls):
        """
        获取配置管理器实例.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
