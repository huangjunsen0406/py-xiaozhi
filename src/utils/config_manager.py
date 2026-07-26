import copy
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from src.logging import get_logger
from src.utils.resource_finder import (
    get_config_dir,
    get_user_data_dir,
)

logger = get_logger()

# 进程内权威配置：由 initialize_config() 创建，get_config() 读取；无懒单例
_current: "ConfigManager | None" = None


def initialize_config() -> "ConfigManager":
    """创建或返回已初始化的配置管理器（应用入口调用）."""
    global _current
    if _current is None:
        _current = ConfigManager()
        # 应用 PATHS 覆盖并迁移 cache/logs/music/keywords（config 目录不迁）
        try:
            from src.utils.resource_finder import apply_path_overrides_from_config

            apply_path_overrides_from_config(_current, migrate=True)
        except Exception as e:
            logger.warning("应用 PATHS 目录覆盖失败: %s", e, exc_info=True)
    return _current


def get_config() -> "ConfigManager":
    """获取已初始化的配置管理器.

    Raises:
        RuntimeError: 尚未 initialize_config()
    """
    if _current is None:
        raise RuntimeError(
            "ConfigManager 未初始化：请在入口调用 initialize_config()"
        )
    return _current


def reset_config() -> None:
    """丢弃进程配置（仅测试）."""
    global _current
    _current = None


class ConfigManager:
    """
    配置管理器（普通实例；进程权威由 initialize_config/get_config 持有）.
    """

    # 当前 schema 版本；加载时 migrate_config() 会升到此版本
    CONFIG_VERSION = 1

    # 默认配置（完整产品 schema；加载时 deepcopy，禁止与实例共享嵌套对象）
    DEFAULT_CONFIG = {
        "CONFIG_VERSION": 1,
        "SYSTEM_OPTIONS": {
            "CLIENT_ID": None,
            "DEVICE_ID": None,
            "WINDOW_SIZE_MODE": "default",
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
            "WAKE_WORD_LANG": "zh",
        },
        "CAMERA": {
            "camera_index": 0,
            # 设备路径优先于 index，如 "/dev/video0"（树莓派 USB/V4L2）
            "device": "",
            # auto | opencv | picamera2；auto 先 OpenCV，失败再试 CSI(picamera2)
            "backend": "auto",
            "frame_width": 640,
            "frame_height": 480,
            "fps": 30,
            # 打开后丢弃的预热帧数（USB/Pi 前几帧常无效）
            "warm_up_frames": 5,
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
            # AEC 在位时 TTS 不暂停音乐，混音闪避并行播放（引擎旁路则自动回退暂停）
            "MUSIC_PARALLEL": True,
            "BUFFER_MAX_LENGTH": 200,
            "FRAME_DELAY": 3,
            "FILTER_LENGTH_RATIO": 0.4,
            "ENABLE_PREPROCESS": True,
        },
        # 可写目录覆盖（config 仍固定在用户数据/config；null=默认）
        # 环境变量优先：XIAOZHI_CACHE_DIR / XIAOZHI_LOG_DIR /
        # XIAOZHI_MUSIC_CACHE_DIR / XIAOZHI_KEYWORDS_DIR / XIAOZHI_DATA_DIR
        # 更改 CACHE/LOG/MUSIC/KEYWORDS 后启动时会从旧目录复制到新目录（不删旧）
        "PATHS": {
            "CACHE_DIR": None,
            "LOG_DIR": None,
            "MUSIC_CACHE_DIR": None,
            "KEYWORDS_DIR": None,
        },
        # 外挂 MCP 插件（用户目录 mcp_plugins，自带 lib/）
        "MCP_PLUGINS": {
            "ENABLED": True,
            "DIR": None,  # null = {用户数据}/mcp_plugins
            "ENABLED_IDS": [],  # 空 = 按插件 enabled_by_default
            "DISABLED_IDS": [],
            "ALLOW_HOST_GET": ["config_readonly", "logger"],
            # 严格校验（默认关，避免示例包无 platforms/abi 时无法加载）
            "ENFORCE_PREFIX": False,
            "REQUIRE_PYTHON_ABI": False,
            "REQUIRE_PLATFORMS": False,
        },
        # MCP 工具暴露（黑名单：不出现在 tools/list，call 亦拒绝）
        "MCP_TOOLS": {
            "DISABLED": [],  # 如 ["music_player.stop", "self.application.launch"]
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
        # 音乐 API（空字符串=运行时用内置默认 URL）
        "MUSIC": {
            "SEARCH_URL": "",
            "URL_API": "",
            "URL_API_KEY": "",
            "LYRICS_URL": "",
            "DEFAULT_PLATFORM": "kw",
            "DEFAULT_QUALITY": "320k",
        },
    }

    def __init__(self):
        """初始化配置管理器（直接构造；应用请用 initialize_config）."""
        self._init_config_paths()
        self._config = self._load_config()

    def _init_config_paths(self):
        """
        初始化配置文件路径.

        配置文件存储到用户数据目录，打包后可写。
        首次运行时从安装目录迁移默认配置。
        """
        self.config_dir = get_user_data_dir() / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config_file = self.config_dir / "config.json"

        # 如果用户目录没有配置文件，尝试从安装目录迁移
        if not self.config_file.exists():
            install_config = get_config_dir() / "config.json"
            if install_config.exists():
                try:
                    # 先校验 JSON，避免把损坏的安装配置拷进来
                    json.loads(install_config.read_text(encoding="utf-8"))
                    shutil.copy2(install_config, self.config_file)
                    logger.info(
                        f"已从安装目录迁移配置: {install_config} -> {self.config_file}"
                    )
                except Exception as e:
                    logger.warning(
                        f"迁移配置文件失败: {e}，将使用默认配置", exc_info=True
                    )

        logger.info(f"配置目录: {self.config_dir.absolute()}")
        logger.info(f"配置文件: {self.config_file.absolute()}")

    def _default_config_copy(self) -> Dict[str, Any]:
        """深拷贝默认配置，避免实例与类属性共享嵌套 dict/list."""
        return copy.deepcopy(self.DEFAULT_CONFIG)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件；不存在则创建；损坏则备份后回退默认."""
        try:
            if self.config_file.exists():
                logger.debug(f"找到配置文件: {self.config_file}")
                try:
                    raw = self.config_file.read_text(encoding="utf-8")
                    config = json.loads(raw)
                except Exception as e:
                    backup = self._backup_corrupt_config(e)
                    logger.error(
                        "配置文件损坏，已备份%s并回退默认: %s",
                        f"至 {backup}" if backup else "",
                        e,
                        exc_info=True,
                    )
                    defaults = self._default_config_copy()
                    self._save_config(defaults)
                    return defaults

                if not isinstance(config, dict):
                    backup = self._backup_corrupt_config(
                        TypeError(f"根节点须为 object，实际为 {type(config).__name__}")
                    )
                    logger.error(
                        "配置文件根节点无效，已备份%s并回退默认",
                        f"至 {backup}" if backup else "",
                    )
                    defaults = self._default_config_copy()
                    self._save_config(defaults)
                    return defaults

                merged = self._merge_configs(self._default_config_copy(), config)
                # 版本以「磁盘文件」为准；merge 会带上默认 CONFIG_VERSION 导致误判已迁移
                try:
                    file_ver = int(config.get("CONFIG_VERSION", 0) or 0)
                except (TypeError, ValueError):
                    file_ver = 0
                return self._migrate_config(merged, from_version=file_ver)

            logger.info("配置文件不存在，创建默认配置")
            defaults = self._default_config_copy()
            self._save_config(defaults)
            return defaults

        except Exception as e:
            logger.error(f"配置加载错误: {e}", exc_info=True)
            return self._default_config_copy()

    def _migrate_config(
        self, config: Dict[str, Any], *, from_version: int | None = None
    ) -> Dict[str, Any]:
        """按 CONFIG_VERSION 做向前迁移；必要时写回磁盘.

        from_version: 磁盘文件中的版本（merge 前）。若省略则读 config 内字段
        （此时若已 merge 默认值，可能已经是最新版，迁移会被跳过）。

        约定：
        - 缺省 / 非法版本视为 0
        - 每步只做可逆性要求低的补丁（改名、补段、规范化）
        - 升到 CONFIG_VERSION 后写回，避免下次重复迁移
        """
        if from_version is not None:
            ver = int(from_version)
        else:
            try:
                raw_ver = config.get("CONFIG_VERSION", 0)
                try:
                    ver = int(raw_ver)
                except (TypeError, ValueError):
                    ver = 0
            except Exception:
                ver = 0

        original = ver
        # --- 迁移步骤（按版本递增追加）---
        if ver < 1:
            # v1: 引入版本号；补齐 MCP_TOOLS；规范化 subscribe_topic 字符串 "null"
            config.setdefault("MCP_TOOLS", {"DISABLED": []})
            if not isinstance(config.get("MCP_TOOLS"), dict):
                config["MCP_TOOLS"] = {"DISABLED": []}
            config["MCP_TOOLS"].setdefault("DISABLED", [])

            try:
                net = config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {})
                mqtt = net.get("MQTT_INFO")
                if isinstance(mqtt, dict) and mqtt.get("subscribe_topic") == "null":
                    mqtt["subscribe_topic"] = None
            except Exception:
                pass
            ver = 1

        # 将来：if ver < 2: ...; ver = 2

        if ver != original or config.get("CONFIG_VERSION") != self.CONFIG_VERSION:
            config["CONFIG_VERSION"] = self.CONFIG_VERSION
            if self._save_config(config):
                logger.info(
                    "配置已迁移: v%s -> v%s", original, self.CONFIG_VERSION
                )
            else:
                logger.warning(
                    "配置迁移后写回失败（内存已是 v%s）", self.CONFIG_VERSION
                )
        else:
            config["CONFIG_VERSION"] = self.CONFIG_VERSION
        return config

    def _backup_corrupt_config(self, error: Exception) -> str | None:
        """将损坏的 config.json 备份为 .corrupt-时间戳，返回备份路径."""
        try:
            if not self.config_file.exists():
                return None
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self.config_file.with_name(f"config.json.corrupt-{ts}")
            # 避免极端情况下重名
            n = 0
            while backup.exists():
                n += 1
                backup = self.config_file.with_name(f"config.json.corrupt-{ts}-{n}")
            shutil.copy2(self.config_file, backup)
            logger.warning("已备份损坏配置: %s (%s)", backup, error)
            return str(backup)
        except Exception as e:
            logger.error("备份损坏配置失败: %s", e, exc_info=True)
            return None

    def _save_config(self, config: dict) -> bool:
        """原子写入配置文件（临时文件 + rename 防写入中断损坏）."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)

            tmp_file = self.config_file.with_suffix(".tmp")
            tmp_file.write_text(
                json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            os.replace(tmp_file, self.config_file)
            logger.debug(f"配置已保存到: {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"配置保存错误: {e}", exc_info=True)
            return False

    @staticmethod
    def _merge_configs(default: dict, custom: dict) -> dict:
        """递归合并配置：default 为底，custom 覆盖；两边均为 dict 时深合并.

        注意：调用方应传入已 deepcopy 的 default，避免污染类级 DEFAULT_CONFIG。
        """
        result = default  # 已是独立副本时原地合并即可
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

    def update_config(self, path: str, value: Any, *, save: bool = True) -> bool:
        """
        更新特定配置项
        path: 点分隔的配置路径，如 "SYSTEM_OPTIONS.NETWORK.MQTT_INFO"
        save: 是否立即落盘；批量更新时传 False，最后再 save_config()/update_configs

        中间节点若为 None/非 dict，会提升为 dict 再写入（兼容 MQTT_INFO: null 等默认）。
        """
        try:
            current: Any = self._config
            *parts, last = path.split(".")
            for part in parts:
                if not isinstance(current, dict):
                    raise TypeError(
                        f"配置路径前缀不是对象，无法写入 {path}（当前节点类型 {type(current).__name__}）"
                    )
                existing = current.get(part, None)
                if not isinstance(existing, dict):
                    # 键缺失、或值为 None/标量：建空对象以便继续下钻
                    existing = {}
                    current[part] = existing
                current = existing
            if not isinstance(current, dict):
                raise TypeError(f"配置路径无法写入: {path}")
            current[last] = value
            if not save:
                return True
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"配置更新错误 {path}: {e}", exc_info=True)
            return False

    def update_configs(self, updates: Dict[str, Any]) -> bool:
        """批量更新多个配置路径，只写盘一次.

        Args:
            updates: path -> value，例如
                {"SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL": "wss://..."}
        """
        if not updates:
            return True
        try:
            for path, value in updates.items():
                if not self.update_config(path, value, save=False):
                    return False
            return self._save_config(self._config)
        except Exception as e:
            logger.error(f"批量配置更新错误: {e}", exc_info=True)
            return False

    def save_config(self) -> bool:
        """将当前内存配置落盘."""
        return self._save_config(self._config)

    def reload_config(self, *, apply_paths: bool = True) -> bool:
        """重新加载配置文件.

        apply_paths: 是否重新应用 PATHS 覆盖（不迁移目录）。
        PATHS 目录迁移仅在 initialize_config 时执行。
        """
        try:
            self._config = self._load_config()
            if apply_paths:
                try:
                    from src.utils.resource_finder import apply_path_overrides_from_config

                    apply_path_overrides_from_config(self, migrate=False)
                except Exception as e:
                    logger.warning(
                        "reload 后应用 PATHS 失败: %s", e, exc_info=True
                    )
            logger.info("配置文件已重新加载")
            return True
        except Exception as e:
            logger.error(f"配置重新加载失败: {e}", exc_info=True)
            return False

    def generate_uuid(self) -> str:
        """生成 UUID v4."""
        return str(uuid.uuid4())

    def initialize_client_id(self):
        """确保存在客户端ID."""
        if not self.get_config("SYSTEM_OPTIONS.CLIENT_ID"):
            client_id = self.generate_uuid()
            success = self.update_config("SYSTEM_OPTIONS.CLIENT_ID", client_id)
            if success:
                logger.info(f"已生成新的客户端ID: {client_id}")
            else:
                logger.error("保存新的客户端ID失败")
