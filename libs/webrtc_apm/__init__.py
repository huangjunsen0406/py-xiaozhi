"""
WebRTC Audio Processing Module for Python
WebRTC音频处理模块Python包

提供工业级的实时音频处理功能：
- 回声消除 (Echo Cancellation)
- 噪声抑制 (Noise Suppression)
- 自动增益控制 (Automatic Gain Control)
- 高通滤波器 (High Pass Filter)
- 瞬态抑制 (Transient Suppression)

使用示例:
    from libs import webrtc_apm
    import numpy as np
    
    # 创建音频处理器
    processor = webrtc_apm.AudioProcessor(sample_rate=16000, channels=1)
    
    # 处理音频
    audio_data = np.random.randn(160).astype(np.float32)  # 10ms @ 16kHz
    processed = processor.process(audio_data)
    
    # 或者使用便捷函数
    processor = webrtc_apm.create_audio_processor(16000, 1)
    processed = processor.process(audio_data)
"""
import numpy as np

from .core import (
    WebRTCAudioProcessing,
    WebRTCConfig,
    StreamConfig,
    WebRTCAudioProcessingError
)

# 版本信息
__version__ = "1.0.0"
__author__ = "WebRTC APM Python Team"
__email__ = "webrtc-apm@example.com"
__description__ = "WebRTC Audio Processing Module Python Bindings"

# 导出的公共API
__all__ = [
    # 主要类
    'AudioProcessor',
    'Config',
    'WebRTCAudioProcessingError',
    
    # 便捷函数
    'create_audio_processor',
    'create_enhanced_audio_processor',
    
    # 内部类（高级用户）
    'WebRTCAudioProcessing',
    'WebRTCConfig',
    'StreamConfig',
]


class AudioProcessor:
    """简化的音频处理器接口
    
    这是一个用户友好的封装，隐藏了复杂的底层细节
    
    Args:
        sample_rate: 采样率，支持8000-48000 Hz
        channels: 通道数，通常为1（单声道）
        config: 可选的配置对象，如果不提供则使用增强配置
        
    Example:
        >>> processor = AudioProcessor(16000, 1)
        >>> audio_data = np.random.randn(160).astype(np.float32)
        >>> processed = processor.process(audio_data)
    """
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1, config: WebRTCConfig = None):
        self._apm = WebRTCAudioProcessing()
        self._config_id, self._config_handle = self._apm.create_stream_config(sample_rate, channels)
        self._sample_rate = sample_rate
        self._channels = channels
        
        # 应用配置
        if config is None:
            config = WebRTCConfig()
            # 启用增强功能
            config.echo_canceller_enabled = True
            config.noise_suppression_enabled = True
            config.noise_suppression_level = WebRTCConfig.NoiseSuppressionLevel.High
            config.gain_controller1_enabled = True
            config.high_pass_filter_enabled = True
            
        self._apm.apply_config(config)
        
        # 设置默认延迟
        self._apm.set_stream_delay_ms(50)
    
    def process(self, audio_data):
        """处理音频数据
        
        Args:
            audio_data: 输入音频数据，numpy数组，支持float32或int16格式
            
        Returns:
            处理后的音频数据，numpy数组，int16格式
            
        Example:
            >>> audio_data = np.random.randn(160).astype(np.float32)
            >>> processed = processor.process(audio_data)
        """
        return self._apm.process_stream(audio_data, self._config_id)
    
    def process_playback(self, audio_data):
        """处理播放音频（用于回声消除的参考信号）
        
        Args:
            audio_data: 播放音频数据，numpy数组
            
        Returns:
            处理后的播放音频数据
            
        Example:
            >>> # 先处理播放音频
            >>> processor.process_playback(playback_audio)
            >>> # 再处理采集音频，会自动应用回声消除
            >>> processed = processor.process(capture_audio)
        """
        return self._apm.process_reverse_stream(audio_data, self._config_id)
    
    def set_delay(self, delay_ms: int):
        """设置回声路径延迟
        
        Args:
            delay_ms: 延迟时间（毫秒），通常为0-500ms
            
        Example:
            >>> processor.set_delay(100)  # 设置100ms延迟
        """
        self._apm.set_stream_delay_ms(delay_ms)
    
    def update_config(self, config: WebRTCConfig):
        """更新音频处理配置
        
        Args:
            config: 新的配置对象
            
        Example:
            >>> config = Config()
            >>> config.echo_canceller = False
            >>> processor.update_config(config._get_internal_config())
        """
        self._apm.apply_config(config)
    
    @property
    def sample_rate(self):
        """获取采样率"""
        return self._sample_rate
    
    @property
    def channels(self):
        """获取通道数"""
        return self._channels
    
    def __enter__(self):
        """上下文管理器支持"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器清理"""
        # 资源会在__del__中自动清理
        pass
    
    def __del__(self):
        """析构函数"""
        # WebRTCAudioProcessing会自动清理资源
        pass


class Config:
    """简化的配置类
    
    提供用户友好的配置接口
    
    Example:
        >>> config = Config()
        >>> config.echo_canceller = True
        >>> config.noise_suppression = True
        >>> config.noise_level = 'high'
        >>> config.gain_control = True
    """
    
    def __init__(self):
        self._internal_config = WebRTCConfig()
    
    @property
    def echo_canceller(self):
        """回声消除开关"""
        return self._internal_config.echo_canceller_enabled
    
    @echo_canceller.setter
    def echo_canceller(self, value: bool):
        self._internal_config.echo_canceller_enabled = value
    
    @property
    def noise_suppression(self):
        """噪声抑制开关"""
        return self._internal_config.noise_suppression_enabled
    
    @noise_suppression.setter
    def noise_suppression(self, value: bool):
        self._internal_config.noise_suppression_enabled = value
    
    @property
    def noise_level(self):
        """噪声抑制级别"""
        levels = {0: 'low', 1: 'moderate', 2: 'high', 3: 'very_high'}
        return levels.get(self._internal_config.noise_suppression_level, 'high')
    
    @noise_level.setter
    def noise_level(self, value: str):
        levels = {'low': 0, 'moderate': 1, 'high': 2, 'very_high': 3}
        if value in levels:
            self._internal_config.noise_suppression_level = levels[value]
        else:
            raise ValueError(f"Invalid noise level: {value}. Must be one of: {list(levels.keys())}")
    
    @property
    def gain_control(self):
        """自动增益控制开关"""
        return self._internal_config.gain_controller1_enabled
    
    @gain_control.setter
    def gain_control(self, value: bool):
        self._internal_config.gain_controller1_enabled = value
    
    @property
    def high_pass_filter(self):
        """高通滤波器开关"""
        return self._internal_config.high_pass_filter_enabled
    
    @high_pass_filter.setter
    def high_pass_filter(self, value: bool):
        self._internal_config.high_pass_filter_enabled = value
    
    def _get_internal_config(self):
        """获取内部配置对象（内部使用）"""
        return self._internal_config
    
    @classmethod
    def default(cls):
        """创建默认配置"""
        return cls()
    
    @classmethod
    def enhanced(cls):
        """创建增强配置（推荐）"""
        config = cls()
        config.echo_canceller = True
        config.noise_suppression = True
        config.noise_level = 'high'
        config.gain_control = True
        config.high_pass_filter = True
        return config
    
    @classmethod
    def minimal(cls):
        """创建最小配置（仅基本功能）"""
        config = cls()
        config.echo_canceller = True
        config.noise_suppression = False
        config.gain_control = False
        config.high_pass_filter = False
        return config


def create_audio_processor(sample_rate: int = 16000, channels: int = 1, 
                          echo_canceller: bool = True, noise_suppression: bool = True,
                          gain_control: bool = True):
    """便捷函数：创建音频处理器
    
    Args:
        sample_rate: 采样率，默认16000 Hz
        channels: 通道数，默认1（单声道）
        echo_canceller: 是否启用回声消除，默认True
        noise_suppression: 是否启用噪声抑制，默认True
        gain_control: 是否启用自动增益控制，默认True
        
    Returns:
        AudioProcessor实例
        
    Example:
        >>> processor = create_audio_processor(16000, 1)
        >>> processed = processor.process(audio_data)
    """
    config = Config()
    config.echo_canceller = echo_canceller
    config.noise_suppression = noise_suppression
    config.gain_control = gain_control
    
    return AudioProcessor(sample_rate, channels, config._get_internal_config())


# 保持向后兼容性的别名  
def create_enhanced_audio_processor(sample_rate: int = 16000, channels: int = 1):
    """创建增强配置的音频处理器（向后兼容）
    
    Returns:
        (WebRTCAudioProcessing, config_id) - 底层接口
    """
    apm = WebRTCAudioProcessing()
    config_id, config_handle = apm.create_stream_config(sample_rate, channels)
    
    # 创建增强配置
    config = WebRTCConfig()
    config.echo_canceller_enabled = True
    config.noise_suppression_enabled = True
    config.noise_suppression_level = WebRTCConfig.NoiseSuppressionLevel.High
    config.gain_controller1_enabled = True
    config.high_pass_filter_enabled = True
    
    apm.apply_config(config)
    apm.set_stream_delay_ms(50)
    
    return apm, config_id