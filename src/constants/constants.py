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

class AudioConfig:
    """音频配置"""
    SAMPLE_RATE = 24000
    CHANNELS = 1
    FRAME_DURATION = 60  # ms
    FRAME_SIZE = int(SAMPLE_RATE * (FRAME_DURATION / 1000))
