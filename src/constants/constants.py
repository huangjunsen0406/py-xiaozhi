import platform

from src.utils.config_manager import ConfigManager

config = ConfigManager.get_instance()


class ListeningMode:
    """监听模式."""

    ALWAYS_ON = "always_on"
    AUTO_STOP = "auto_stop"
    MANUAL = "manual"


class AbortReason:
    """中止原因."""

    NONE = "none"
    WAKE_WORD_DETECTED = "wake_word_detected"
    USER_INTERRUPTION = "user_interruption"


class DeviceState:
    """设备状态."""

    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    SPEAKING = "speaking"


class EventType:
    """事件类型."""

    SCHEDULE_EVENT = "schedule_event"
    AUDIO_INPUT_READY_EVENT = "audio_input_ready_event"
    AUDIO_OUTPUT_READY_EVENT = "audio_output_ready_event"


def is_official_server(ws_addr: str) -> bool:
    """判断是否为小智官方的服务器地址.

    Args:
        ws_addr (str): WebSocket 地址

    Returns:
        bool: 是否为小智官方的服务器地址
    """
    return "api.tenclass.net" in ws_addr


def get_frame_duration() -> int:
    """获取设备的帧长度（优化版：避免独立PyAudio实例创建）

    返回:
        int: 帧长度(毫秒)
    """
    try:
        # 检查是否为官方服务器
        ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        if not is_official_server(ota_url):
            return 60

        system = platform.system()

        if system == "Windows":
            # Windows通常支持较小的缓冲区
            return 20
        elif system == "Linux":
            # Linux可能需要稍大的缓冲区以减少延迟(如果发现不行改为60)
            return 60
        elif system == "Darwin":  # macOS
            # macOS通常有良好的音频性能
            return 20
        else:
            # 其他系统使用保守值
            return 60

    except Exception:
        return 20  # 如果获取失败，返回默认值20ms


class AudioConfig:
    """音频配置类."""
    # 固定配置
    INPUT_SAMPLE_RATE = 16000  # 输入采样率16kHz
    # 输出采样率：官方服务器使用24kHz，其他使用16kHz
    _ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
    OUTPUT_SAMPLE_RATE = 24000 if is_official_server(_ota_url) else 16000
    CHANNELS = 1

    # 动态获取帧长度
    FRAME_DURATION = get_frame_duration()

    # 根据不同采样率计算帧大小
    INPUT_FRAME_SIZE = int(INPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
    # Linux系统使用固定帧大小以减少PCM打印，其他系统动态计算
    OUTPUT_FRAME_SIZE = int(OUTPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
