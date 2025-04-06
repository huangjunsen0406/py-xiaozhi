from src.utils.config_manager import ConfigManager
config = ConfigManager.get_instance()


class ListeningMode:
    """监听模式"""
    ALWAYS_ON = "always_on"
    AUTO_STOP = "auto_stop"
    MANUAL = "manual"

class AbortReason:
    """中止原因"""
    NONE = "none"
    WAKE_WORD_DETECTED = "wake_word_detected"
    USER_INTERRUPTION = "user_interruption"

class DeviceState:
    """设备状态"""
    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    SPEAKING = "speaking"

class EventType:
    """事件类型"""
    SCHEDULE_EVENT = "schedule_event"
    AUDIO_INPUT_READY_EVENT = "audio_input_ready_event"
    AUDIO_OUTPUT_READY_EVENT = "audio_output_ready_event"


def is_official_server(ws_addr: str) -> bool:
    """判断是否为小智官方的服务器地址

    Args:
        ws_addr (str): WebSocket 地址

    Returns:
        bool: 是否为小智官方的服务器地址
    """
    return "api.tenclass.net" in ws_addr

def get_frame_duration() -> int:
    """
    获取设备的帧长度

    返回:
        int: 帧长度(毫秒)
    """
    import pyaudio
    try:

        if not is_official_server(config.get_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL")):
            return 60
        p = pyaudio.PyAudio()
        # 获取默认输入设备信息
        device_info = p.get_default_input_device_info()
        # 一些设备会提供建议的缓冲区大小
        default_rate = device_info.get('defaultSampleRate', 48000)
        # 默认20ms的缓冲区
        suggested_buffer = device_info.get('defaultSampleRate', 0) / 50
        # 计算帧长度
        frame_duration = int(1000 * suggested_buffer / default_rate)
        # 确保帧长度在合理范围内 (10ms-50ms)
        frame_duration = max(10, min(50, frame_duration))
        p.terminate()
        return frame_duration
    except Exception:
        return 20  # 如果获取失败，返回默认值20ms

class AudioConfig:
    """音频配置类"""
    # 固定配置
    INPUT_SAMPLE_RATE = 16000  # 输入采样率16kHz
    OUTPUT_SAMPLE_RATE = 24000 if is_official_server(config.get_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL")) else 16000  # 输出采样率
    CHANNELS = 1

    # 动态获取帧长度
    FRAME_DURATION = get_frame_duration()

    # 根据不同采样率计算帧大小
    INPUT_FRAME_SIZE = int(INPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
    OUTPUT_FRAME_SIZE = int(OUTPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))

    # Opus编码配置
    OPUS_APPLICATION = 2049  # OPUS_APPLICATION_AUDIO
    OPUS_FRAME_SIZE = INPUT_FRAME_SIZE  # 使用输入采样率的帧大小
