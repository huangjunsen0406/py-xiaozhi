# 系统常量定义
from enum import Enum


class InitializationStage(Enum):
    """
    初始化阶段枚举.
    """

    DEVICE_FINGERPRINT = "第一阶段：设备身份准备"
    CONFIG_MANAGEMENT = "第二阶段：配置管理初始化"
    OTA_CONFIG = "第三阶段：OTA获取配置"
    ACTIVATION = "第四阶段：激活流程"


class SystemConstants:
    """
    系统常量.
    """

    # 应用信息
    APP_NAME = "py-xiaozhi"
    APP_VERSION = "2.0.0"
    BOARD_TYPE = "bread-compact-wifi"

    # 默认超时设置
    DEFAULT_TIMEOUT = 10
    ACTIVATION_MAX_RETRIES = 60
    ACTIVATION_RETRY_INTERVAL = 5

    # 文件名常量
    CONFIG_FILE = "config.json"
    EFUSE_FILE = "efuse.json"
