"""配置常量模块 - 存放所有配置相关的常量"""
from pathlib import Path

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "SYSTEM_OPTIONS": {
        "CLIENT_ID": None,
        "DEVICE_ID": None,
        "NETWORK": {
            "OTA_VERSION_URL": "https://api.tenclass.net/xiaozhi/ota/",
            "WEBSOCKET_URL": "wss://api.tenclass.net/xiaozhi/v1/",
            "WEBSOCKET_ACCESS_TOKEN": "test-token",
            "MQTT_INFO": None,
            "ACTIVATION_VERSION": "v1"  # 可选值: v1, v2
        }
    },
    "WAKE_WORD_OPTIONS": {
        "USE_WAKE_WORD": False,
        "MODEL_PATH": "models/vosk-model-small-cn-0.22",
        "WAKE_WORDS": [
            "小智",
            "小美"
        ]
    },
    "TEMPERATURE_SENSOR_MQTT_INFO": {
        "endpoint": "你的Mqtt连接地址",
        "port": 1883,
        "username": "admin",
        "password": "123456",
        "publish_topic": "sensors/temperature/command",
        "subscribe_topic": "sensors/temperature/device_001/state"
    },
    "CAMERA": {
        "camera_index": 0,
        "frame_width": 640,
        "frame_height": 480,
        "fps": 30,
        "Loacl_VL_url": "https://open.bigmodel.cn/api/paas/v4/",
        "VLapi_key": "你自己的key",
        "models": "glm-4v-plus"
    }
} 