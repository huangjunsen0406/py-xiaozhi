import platform

from src.utils.config_manager import ConfigManager

config = ConfigManager.get_instance()


class ListeningMode:
    """
    监听模式.
    """

    REALTIME = "realtime"
    AUTO_STOP = "auto_stop"
    MANUAL = "manual"


class AbortReason:
    """
    中止原因.
    """

    NONE = "none"
    WAKE_WORD_DETECTED = "wake_word_detected"
    USER_INTERRUPTION = "user_interruption"


class DeviceState:
    """
    设备状态.
    """

    IDLE = "idle"
    CONNECTING = "connecting"
    LISTENING = "listening"
    SPEAKING = "speaking"


class EventType:
    """
    事件类型.
    """

    SCHEDULE_EVENT = "schedule_event"
    AUDIO_INPUT_READY_EVENT = "audio_input_ready_event"
    AUDIO_OUTPUT_READY_EVENT = "audio_output_ready_event"


def get_frame_duration() -> int:
    """获取设备的帧长度.

    优先从配置读取，无配置时根据设备架构自动检测。

    返回:
        int: 帧长度(毫秒)，支持 20/40/60
    """
    try:
        # 优先从配置读取
        configured = config.get_config("AUDIO_DEVICES.frame_duration")
        if configured in [20, 40, 60]:
            return configured

        # 无配置时自动检测（保持向后兼容）
        machine = platform.machine().lower()
        arm_archs = ["arm", "aarch64", "armv7l", "armv6l"]
        is_arm_device = any(arch in machine for arch in arm_archs)

        if is_arm_device:
            # ARM设备（如树莓派）使用较大帧长以减少CPU负载
            return 60
        else:
            # 其他设备（Windows/macOS/Linux x86）都有足够性能，使用低延迟
            return 20

    except Exception:
        # 如果获取失败，返回默认值20ms（适合大多数现代设备）
        return 20


class AudioConfig:
    """
    音频配置类.
    """

    # 固定配置
    INPUT_SAMPLE_RATE = 16000  # 输入采样率16kHz
    # 输出采样率：从配置读取，默认24kHz（官方服务器推荐值）
    OUTPUT_SAMPLE_RATE = config.get_config("AUDIO_DEVICES.opus_output_sample_rate", 24000)
    CHANNELS = 1  # 服务端协议要求：单声道

    # 设备声道限制（避免多声道设备性能浪费）
    MAX_INPUT_CHANNELS = 2  # 最多使用2个输入声道（立体声）
    MAX_OUTPUT_CHANNELS = 2  # 最多使用2个输出声道（立体声）

    # 动态获取帧长度
    FRAME_DURATION = get_frame_duration()

    # 根据不同采样率计算帧大小
    INPUT_FRAME_SIZE = int(INPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
    # Linux系统使用固定帧大小以减少PCM打印，其他系统动态计算
    OUTPUT_FRAME_SIZE = int(OUTPUT_SAMPLE_RATE * (FRAME_DURATION / 1000))
