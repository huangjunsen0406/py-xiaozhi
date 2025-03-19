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
    """音频配置类，支持动态更新"""
    # 初始默认配置
    SAMPLE_RATE = 16000
    CHANNELS = 1
    FRAME_DURATION = 60  # 单位为毫秒
    FRAME_SIZE = int(SAMPLE_RATE * (FRAME_DURATION / 1000))
    
    @classmethod
    def update_from_server(cls, audio_params):
        """根据服务器配置更新音频参数"""
        if not audio_params:
            return False
            
        updated = False

        # 更新采样率
        if 'sample_rate' in audio_params and audio_params['sample_rate'] != cls.SAMPLE_RATE:
            cls.SAMPLE_RATE = audio_params['sample_rate']
            updated = True
            
        # 更新声道数
        if 'channels' in audio_params and audio_params['channels'] != cls.CHANNELS:
            cls.CHANNELS = audio_params['channels']
            updated = True
            
        # 更新帧持续时间
        if 'frame_duration' in audio_params and audio_params['frame_duration'] != cls.FRAME_DURATION:
            cls.FRAME_DURATION = audio_params['frame_duration']
            updated = True
            
        # 重新计算帧大小
        if updated:
            cls.FRAME_SIZE = int(cls.SAMPLE_RATE * (cls.FRAME_DURATION / 1000))
            
        return updated
