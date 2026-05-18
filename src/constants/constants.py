import platform
from enum import Enum

from src.utils.config_manager import ConfigManager

config = ConfigManager.get_instance()


class ListeningMode(str, Enum):
    """
    监听模式.
    """

    REALTIME = "realtime"
    AUTO_STOP = "auto_stop"
    MANUAL = "manual"


class AbortReason(str, Enum):
    """
    中止原因.
    """

    NONE = "none"
    WAKE_WORD_DETECTED = "wake_word_detected"
    USER_INTERRUPTION = "user_interruption"


class DeviceState(str, Enum):
    """
    设备状态.
    """

    IDLE = "idle"
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
    音频配置类 — 协议层参数，与设备层（DeviceConfig）独立。

    所有值通过 reload() 从 ConfigManager 动态加载，支持运行时热重载。
    """

    # 服务端协议固定值（不随配置变化）
    INPUT_SAMPLE_RATE = 16000  # 协议要求：输入 16kHz
    CHANNELS = 1  # 协议要求：单声道

    # 以下为动态值，reload() 时从配置重新读取
    OUTPUT_SAMPLE_RATE: int = 24000
    FRAME_DURATION: int = 20
    INPUT_FRAME_SIZE: int = 320

    @classmethod
    def reload(cls):
        """从 ConfigManager 重新加载协议音频参数，支持运行时热重载。

        Settings UI 修改 opus_output_sample_rate / frame_duration 后，
        调用此方法使新值在下次 initialize/reload_devices 时生效。
        """
        cls.OUTPUT_SAMPLE_RATE = config.get_config(
            "AUDIO_DEVICES.opus_output_sample_rate", 24000
        )
        cls.FRAME_DURATION = get_frame_duration()
        cls.INPUT_FRAME_SIZE = int(cls.INPUT_SAMPLE_RATE * (cls.FRAME_DURATION / 1000))


# 模块加载时初始化默认值
AudioConfig.reload()
