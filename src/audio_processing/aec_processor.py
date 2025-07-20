"""
声学回声消除(AEC)处理器模块.

基于pyaec库实现实时回声消除功能，用于消除扬声器播放音频在麦克风中产生的回声。
"""

import logging
from collections import deque
from typing import Optional

import numpy as np

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    # 直接使用已安装的pyaec库
    from pyaec import Aec
    AEC_AVAILABLE = True
    logger.info("使用已安装的pyaec库")
except Exception as e:
    logger.warning(f"pyaec库不可用: {e}")
    logger.info("请安装pyaec: pip install pyaec")
    AEC_AVAILABLE = False
    Aec = None


class AECProcessor:
    """
    声学回声消除处理器.
    
    使用pyaec库实现实时回声消除，需要同时提供录音信号和播放参考信号。
    参考pyaec示例代码进行优化配置。
    """

    def __init__(self, enabled: bool = True):
        """
        初始化AEC处理器.
        
        Args:
            enabled: 是否启用AEC功能
        """
        self.enabled = enabled and AEC_AVAILABLE
        self.aec = None
        # 参考pyaec示例，使用更大的缓冲区以确保时序对齐
        self._reference_buffer = deque(maxlen=200)  
        self._initialized = False
        # 根据实际测试调整延迟补偿
        self._frame_delay = 3  
        self._stats = {
            'processed_frames': 0,
            'reference_frames': 0,
            'buffer_underruns': 0
        }
        
        if not AEC_AVAILABLE:
            logger.warning("pyaec不可用，AEC功能已禁用")
            self.enabled = False
        elif not enabled:
            logger.info("AEC功能已手动禁用")

    async def initialize(self):
        """
        初始化AEC实例.
        参考pyaec示例优化滤波器长度配置。
        """
        if not self.enabled:
            return
            
        try:
            # 参考pyaec示例代码，优化滤波器长度
            # microphone.py使用了 int(sample_rate * 0.4) = 6400 (对于16kHz)
            # wav.py使用了更小的值 1600
            # 根据实际环境选择合适的滤波器长度
            filter_length = int(AudioConfig.INPUT_SAMPLE_RATE * 0.4)  # 0.4秒滤波器
            
            # 创建AEC实例，参考pyaec示例参数
            self.aec = Aec(
                frame_size=AudioConfig.INPUT_FRAME_SIZE,
                filter_length=filter_length,
                sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                enable_preprocess=True  # 启用预处理(降噪)
            )
            
            self._initialized = True
            logger.info(f"AEC处理器初始化成功 [帧大小: {AudioConfig.INPUT_FRAME_SIZE}, "
                       f"滤波器长度: {filter_length}, 采样率: {AudioConfig.INPUT_SAMPLE_RATE}Hz]")
                       
        except Exception as e:
            logger.error(f"AEC处理器初始化失败: {e}")
            self.enabled = False
            self._initialized = False

    def add_reference_audio(self, audio_data: np.ndarray):
        """
        添加参考音频信号(来自服务端解码的PCM数据).
        参考pyaec示例优化参考信号处理。
        
        Args:
            audio_data: 音频数据，来自服务端opus解码后的PCM，应为int16格式的numpy数组
        """
        if not self.enabled or not self._initialized:
            return
            
        try:
            # 确保数据格式正确
            if audio_data.dtype != np.int16:
                audio_data = audio_data.astype(np.int16)
            
            # 服务端解码的PCM数据应该已经是正确的采样率(24kHz)
            # 需要重采样到16kHz以匹配录音信号
            if len(audio_data) == AudioConfig.OUTPUT_FRAME_SIZE:
                # 从24kHz重采样到16kHz
                if AudioConfig.OUTPUT_SAMPLE_RATE != AudioConfig.INPUT_SAMPLE_RATE:
                    # 使用更准确的重采样方法
                    ratio = AudioConfig.INPUT_SAMPLE_RATE / AudioConfig.OUTPUT_SAMPLE_RATE
                    new_length = int(len(audio_data) * ratio)
                    
                    # 使用numpy的线性插值进行重采样
                    indices = np.linspace(0, len(audio_data) - 1, new_length)
                    audio_data = np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.int16)
            
            # 确保帧大小匹配录音帧大小
            if len(audio_data) >= AudioConfig.INPUT_FRAME_SIZE:
                reference_frame = audio_data[:AudioConfig.INPUT_FRAME_SIZE].copy()
            else:
                # 补零到正确大小
                reference_frame = np.zeros(AudioConfig.INPUT_FRAME_SIZE, dtype=np.int16)
                reference_frame[:len(audio_data)] = audio_data
            
            # 添加到参考信号缓冲区
            self._reference_buffer.append(reference_frame)
            self._stats['reference_frames'] += 1
            
            # 调试信息
            if self._stats['reference_frames'] % 100 == 0:  # 每100帧记录一次
                logger.debug(f"AEC参考信号: 缓冲区={len(self._reference_buffer)}, "
                           f"总帧数={self._stats['reference_frames']}")
                
        except Exception as e:
            logger.warning(f"添加参考音频失败: {e}")

    def process_audio(self, input_audio: np.ndarray) -> np.ndarray:
        """
        处理音频信号，应用回声消除.
        参考pyaec示例优化AEC处理逻辑。
        
        Args:
            input_audio: 输入音频信号(麦克风录音)
            
        Returns:
            处理后的音频信号，如果AEC未启用则返回原始信号
        """
        if not self.enabled or not self._initialized or self.aec is None:
            return input_audio
            
        try:
            # 确保输入数据格式正确
            if input_audio.dtype != np.int16:
                input_audio = input_audio.astype(np.int16)
                
            # 确保帧大小正确
            if len(input_audio) != AudioConfig.INPUT_FRAME_SIZE:
                if len(input_audio) > AudioConfig.INPUT_FRAME_SIZE:
                    input_audio = input_audio[:AudioConfig.INPUT_FRAME_SIZE]
                else:
                    padded_input = np.zeros(AudioConfig.INPUT_FRAME_SIZE, dtype=np.int16)
                    padded_input[:len(input_audio)] = input_audio
                    input_audio = padded_input
            
            # 获取参考信号
            if len(self._reference_buffer) > 0:
                reference_audio = self._reference_buffer.popleft()
            else:
                # 如果没有参考信号，使用静音，记录缓冲区不足
                reference_audio = np.zeros(AudioConfig.INPUT_FRAME_SIZE, dtype=np.int16)
                self._stats['buffer_underruns'] += 1
                
            # 应用AEC处理，参考pyaec示例的cancel_echo调用方式
            processed_audio = self.aec.cancel_echo(input_audio, reference_audio)
            
            # 转换回numpy数组
            if isinstance(processed_audio, list):
                processed_audio = np.array(processed_audio, dtype=np.int16)
            elif not isinstance(processed_audio, np.ndarray):
                processed_audio = np.array(processed_audio, dtype=np.int16)
            
            self._stats['processed_frames'] += 1
            
            # 定期输出统计信息
            if self._stats['processed_frames'] % 500 == 0:
                underrun_rate = self._stats['buffer_underruns'] / self._stats['processed_frames'] * 100
                logger.debug(f"AEC统计: 处理帧={self._stats['processed_frames']}, "
                           f"参考帧={self._stats['reference_frames']}, "
                           f"缓冲区不足率={underrun_rate:.1f}%")
                
            return processed_audio
            
        except Exception as e:
            logger.warning(f"AEC处理失败，返回原始音频: {e}")
            return input_audio

    def clear_reference_buffer(self):
        """
        清空参考信号缓冲区.
        """
        if self._reference_buffer:
            cleared_count = len(self._reference_buffer)
            self._reference_buffer.clear()
            logger.debug(f"AEC参考信号缓冲区已清空，丢弃 {cleared_count} 帧")
        
        # 重置统计信息
        self._stats = {
            'processed_frames': 0,
            'reference_frames': 0,
            'buffer_underruns': 0
        }

    def is_available(self) -> bool:
        """
        检查AEC功能是否可用.
        
        Returns:
            bool: AEC是否可用
        """
        return self.enabled and self._initialized and self.aec is not None

    async def close(self):
        """
        关闭AEC处理器，释放资源.
        """
        if self.aec is not None:
            try:
                # pyaec会在对象销毁时自动释放资源
                self.aec = None
                self._initialized = False
                logger.info("AEC处理器已关闭")
            except Exception as e:
                logger.warning(f"关闭AEC处理器时出错: {e}")
                
        self.clear_reference_buffer()

    def __del__(self):
        """
        析构函数.
        """
        if self._initialized:
            logger.warning("AEC处理器被销毁但未正确关闭，请确保调用close()方法")