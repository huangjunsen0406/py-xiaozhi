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
    """音频配置类"""
    # 固定配置
    INPUT_SAMPLE_RATE = 16000  # 输入采样率16kHz
    OUTPUT_SAMPLE_RATE = 24000  # 输出采样率24kHz
    CHANNELS = 1
    DEFAULT_FRAME_DURATION = 20  # 默认帧长度20ms
    
    @classmethod
    def _get_device_frame_duration(cls) -> int:
        """
        获取设备推荐的帧长度
        
        返回:
            int: 帧长度(毫秒)
        """
        import pyaudio
        try:
            p = pyaudio.PyAudio()
            # 获取默认输入设备信息
            device_info = p.get_default_input_device_info()
            # 获取设备默认缓冲区大小
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
            return cls.DEFAULT_FRAME_DURATION
    
    @classmethod
    @property
    def FRAME_DURATION(cls) -> int:
        """
        获取当前设备的帧长度
        
        返回:
            int: 帧长度(毫秒)
        """
        if not hasattr(cls, '_frame_duration'):
            cls._frame_duration = cls._get_device_frame_duration()
        return cls._frame_duration
    
    # 根据不同采样率计算帧大小
    @classmethod
    @property
    def INPUT_FRAME_SIZE(cls) -> int:
        """获取输入帧大小"""
        return int(cls.INPUT_SAMPLE_RATE * (cls.FRAME_DURATION / 1000))
    
    @classmethod
    @property
    def OUTPUT_FRAME_SIZE(cls) -> int:
        """获取输出帧大小"""
        return int(cls.OUTPUT_SAMPLE_RATE * (cls.FRAME_DURATION / 1000))
    
    @classmethod
    @property
    def OPUS_FRAME_SIZE(cls) -> int:
        """获取Opus帧大小"""
        return cls.INPUT_FRAME_SIZE
    
    # Opus编码配置
    OPUS_APPLICATION = 2049  # OPUS_APPLICATION_AUDIO
