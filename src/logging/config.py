"""
日志配置模块.

提供日志系统的配置管理，支持：
- 环境感知（dev/test/prod）
- 配置文件和环境变量
- 动态日志级别调整
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Environment(Enum):
    """运行环境枚举."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


@dataclass
class LoggingConfig:
    """日志配置数据类."""

    # 基础配置
    level: str = "INFO"
    format_type: str = "colored"  # colored, json, simple

    # 文件配置
    log_dir: Path | None = None
    log_file: str = "app.log"
    error_log_file: str = "error.log"

    # 轮转配置
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 30
    rotation_when: str = "midnight"  # midnight, H, D, W0-W6
    rotation_interval: int = 1

    # 功能开关
    enable_console: bool = True
    enable_file: bool = True
    enable_error_file: bool = True
    enable_json_file: bool = False
    enable_async: bool = False
    enable_sensitive_filter: bool = True

    # 敏感信息配置
    sensitive_patterns: list[str] = field(
        default_factory=lambda: [
            "password",
            "passwd",
            "secret",
            "token",
            "api_key",
            "apikey",
            "access_token",
            "refresh_token",
            "authorization",
            "credential",
            "private_key",
        ]
    )

    # 第三方日志级别控制
    third_party_levels: dict[str, str] = field(
        default_factory=lambda: {
            "urllib3": "WARNING",
            "websockets": "WARNING",
            "asyncio": "WARNING",
            "paho": "WARNING",
            "PIL": "WARNING",
            "matplotlib": "WARNING",
        }
    )


class LoggingConfigManager:
    """日志配置管理器."""

    _instance: "LoggingConfigManager | None" = None
    _config: LoggingConfig | None = None

    def __new__(cls) -> "LoggingConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._config is None:
            self._config = self._load_config()

    @classmethod
    def get_instance(cls) -> "LoggingConfigManager":
        """获取配置管理器单例."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load_config(self) -> LoggingConfig:
        """加载日志配置."""
        config = LoggingConfig()

        # 尝试从 ConfigManager 加载配置
        try:
            from src.utils.config_manager import ConfigManager

            cfg_manager = ConfigManager.get_instance()
            logging_cfg = cfg_manager.get_config("LOGGING", {})

            if logging_cfg:
                config.level = logging_cfg.get("LEVEL", config.level)
                config.format_type = logging_cfg.get("FORMAT_TYPE", config.format_type)
                config.enable_console = logging_cfg.get(
                    "ENABLE_CONSOLE", config.enable_console
                )
                config.enable_file = logging_cfg.get("ENABLE_FILE", config.enable_file)
                config.enable_error_file = logging_cfg.get(
                    "ENABLE_ERROR_FILE", config.enable_error_file
                )
                config.enable_json_file = logging_cfg.get(
                    "ENABLE_JSON_FILE", config.enable_json_file
                )
                config.enable_async = logging_cfg.get(
                    "ENABLE_ASYNC", config.enable_async
                )
                config.enable_sensitive_filter = logging_cfg.get(
                    "ENABLE_SENSITIVE_FILTER", config.enable_sensitive_filter
                )
                config.max_bytes = logging_cfg.get("MAX_BYTES", config.max_bytes)
                config.backup_count = logging_cfg.get(
                    "BACKUP_COUNT", config.backup_count
                )
                config.rotation_when = logging_cfg.get(
                    "ROTATION_WHEN", config.rotation_when
                )
                third_party = logging_cfg.get("THIRD_PARTY_LEVELS")
                if third_party:
                    config.third_party_levels.update(third_party)
        except Exception:
            # ConfigManager 未初始化时使用默认配置
            pass

        # 从环境变量加载（优先级更高）
        config.level = os.environ.get("LOG_LEVEL", config.level).upper()
        config.format_type = os.environ.get("LOG_FORMAT", config.format_type)

        # 根据环境自动调整
        env = self._get_environment()
        if env == Environment.DEVELOPMENT:
            config.level = os.environ.get("LOG_LEVEL", "DEBUG")
        elif env == Environment.PRODUCTION:
            config.level = os.environ.get("LOG_LEVEL", "INFO")
            config.enable_json_file = True
            config.enable_async = True

        # 设置日志目录
        if config.log_dir is None:
            config.log_dir = self._get_default_log_dir()

        return config

    def _get_environment(self) -> Environment:
        """获取当前运行环境."""
        env_str = os.environ.get("APP_ENV", "development").lower()
        env_map = {
            "dev": Environment.DEVELOPMENT,
            "development": Environment.DEVELOPMENT,
            "test": Environment.TESTING,
            "testing": Environment.TESTING,
            "prod": Environment.PRODUCTION,
            "production": Environment.PRODUCTION,
        }
        return env_map.get(env_str, Environment.DEVELOPMENT)

    def _get_default_log_dir(self) -> Path:
        """获取默认日志目录."""
        # 尝试从项目根目录获取
        try:
            from src.utils.resource_finder import get_app_root

            return get_app_root() / "logs"
        except ImportError:
            return Path.cwd() / "logs"

    @property
    def config(self) -> LoggingConfig:
        """获取当前配置."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def update_config(self, **kwargs: Any) -> None:
        """动态更新配置."""
        if self._config is None:
            self._config = self._load_config()

        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)

    def get_level_for_logger(self, name: str) -> str:
        """获取特定logger的日志级别."""
        if self._config is None:
            return "INFO"

        # 检查是否是第三方库
        for prefix, level in self._config.third_party_levels.items():
            if name.startswith(prefix):
                return level

        return self._config.level

    def reload(self) -> None:
        """重新加载配置."""
        self._config = self._load_config()
