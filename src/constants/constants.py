import platform
from dataclasses import dataclass
from enum import Enum


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
    NOTIFYING = "notifying"


class EventType:
    """
    事件类型.
    """

    SCHEDULE_EVENT = "schedule_event"
    AUDIO_INPUT_READY_EVENT = "audio_input_ready_event"
    AUDIO_OUTPUT_READY_EVENT = "audio_output_ready_event"


def get_frame_duration(config=None) -> int:
    """Resolve frame duration from the supplied configuration only."""
    configured = (
        config.get_config("AUDIO_DEVICES.frame_duration")
        if config is not None
        else None
    )
    if configured in (20, 40, 60):
        return int(configured)
    machine = platform.machine().lower()
    return 60 if any(arch in machine for arch in ("arm", "aarch64")) else 20


@dataclass
class AudioConfig:
    """Protocol audio parameters owned by one runtime.

    Runtime components can share one instance so a device reload and the next
    protocol handshake use the same format. Independent runtimes create their
    own instance; no parameter is written to class or process state.
    """

    INPUT_SAMPLE_RATE: int = 16000
    CHANNELS: int = 1
    OUTPUT_SAMPLE_RATE: int = 24000
    FRAME_DURATION: int = 20

    @property
    def INPUT_FRAME_SIZE(self) -> int:
        return self.INPUT_SAMPLE_RATE * self.FRAME_DURATION // 1000

    @classmethod
    def from_config(cls, config=None) -> "AudioConfig":
        result = cls()
        result.reload(config)
        return result

    def reload(self, config=None) -> None:
        """Refresh only this runtime's parameters from an explicit config."""
        self.OUTPUT_SAMPLE_RATE = (
            config.get_config("AUDIO_DEVICES.opus_output_sample_rate", 24000)
            if config is not None
            else 24000
        )
        self.FRAME_DURATION = get_frame_duration(config)
