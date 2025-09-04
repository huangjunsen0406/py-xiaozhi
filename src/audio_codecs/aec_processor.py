import platform
from collections import deque
from typing import Any, Dict, Optional

import numpy as np
import sounddevice as sd

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AECProcessor:
    """
    音频回声消除处理器
    专门用于处理参考信号（扬声器输出）和麦克风输入的AEC
    """
    
    def __init__(self):
        # 平台信息
        self._platform = platform.system().lower()
        self._is_macos = self._platform == 'darwin'
        self._is_linux = self._platform == 'linux'
        self._is_windows = self._platform == 'windows'
        
        # WebRTC APM 实例（仅 macOS 使用）
        self.apm = None
        self.apm_config = None
        self.capture_config = None
        self.render_config = None
        
        # 参考信号流（仅 macOS 使用）
        self.reference_stream = None
        self.reference_device_id = None
        self.reference_sample_rate = None
        
        # 缓冲区
        self._reference_buffer = deque()
        self._webrtc_frame_size = 160  # WebRTC标准：16kHz, 10ms = 160 samples
        self._system_frame_size = AudioConfig.INPUT_FRAME_SIZE  # 系统配置的帧大小
        
        # 状态标志
        self._is_initialized = False
        self._is_closing = False
        
    async def initialize(self):
        """初始化AEC处理器"""
        try:
            if self._is_windows or self._is_linux:
                # Windows 和 Linux 平台使用系统级AEC，无需额外处理
                logger.info(f"{self._platform.capitalize()} 平台使用系统级回声消除，AEC处理器已启用")
                self._is_initialized = True
                return
            elif self._is_macos:
                # macOS 平台使用 WebRTC + BlackHole
                await self._initialize_apm()
                await self._initialize_reference_capture()
            else:
                logger.warning(f"当前平台 {self._platform} 暂不支持AEC功能")
                self._is_initialized = True
                return
            
            self._is_initialized = True
            logger.info("AEC处理器初始化完成")
            
        except Exception as e:
            logger.error(f"AEC处理器初始化失败: {e}")
            await self.close()
            raise
    
    async def _initialize_apm(self):
        """初始化WebRTC音频处理模块（仅macOS）"""
        if not self._is_macos:
            logger.warning("非macOS平台调用了_initialize_apm，这不应该发生")
            return
            
        try:
            # 延迟导入，仅在macOS需要时加载本地库
            from libs.webrtc_apm import WebRTCAudioProcessing, create_default_config

            self.apm = WebRTCAudioProcessing()
            
            # 创建配置
            self.apm_config = create_default_config()
            
            # 启用回声消除
            self.apm_config.echo.enabled = True
            self.apm_config.echo.mobile_mode = False
            self.apm_config.echo.enforce_high_pass_filtering = True
            
            # 启用噪声抑制
            self.apm_config.noise_suppress.enabled = True
            self.apm_config.noise_suppress.noise_level = 2  # HIGH
            
            # 启用高通滤波器
            self.apm_config.high_pass.enabled = True
            self.apm_config.high_pass.apply_in_full_band = True
            
            # 应用配置
            result = self.apm.apply_config(self.apm_config)
            if result != 0:
                raise RuntimeError(f"WebRTC APM配置失败，错误码: {result}")
            
            # 创建流配置
            sample_rate = AudioConfig.INPUT_SAMPLE_RATE  # 16kHz
            channels = AudioConfig.CHANNELS  # 1
            
            self.capture_config = self.apm.create_stream_config(sample_rate, channels)
            self.render_config = self.apm.create_stream_config(sample_rate, channels)
            
            # 设置流延迟
            self.apm.set_stream_delay_ms(40)  # 50ms延迟
            
            logger.info("WebRTC APM初始化完成")
            
        except Exception as e:
            logger.error(f"WebRTC APM初始化失败: {e}")
            raise
    
    async def _initialize_reference_capture(self):
        """初始化参考信号捕获（仅macOS）"""
        if not self._is_macos:
            return
        
        try:
            # 查找BlackHole 2ch设备
            reference_device = self._find_blackhole_device()
            if reference_device is None:
                logger.warning("未找到BlackHole 2ch设备，参考信号捕获不可用")
                return
            
            self.reference_device_id = reference_device['id']
            self.reference_sample_rate = int(reference_device['default_samplerate'])
            
            # 创建参考信号输入流（固定使用10ms帧，匹配WebRTC标准）
            webrtc_frame_duration = 0.01  # 10ms，WebRTC标准帧长度
            reference_frame_size = int(self.reference_sample_rate * webrtc_frame_duration)
            
            self.reference_stream = sd.InputStream(
                device=self.reference_device_id,
                samplerate=self.reference_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=reference_frame_size,
                callback=self._reference_callback,
                finished_callback=self._reference_finished_callback,
                latency='low'
            )
            
            self.reference_stream.start()
            
            logger.info(f"参考信号捕获已启动: [{self.reference_device_id}] {reference_device['name']}")
            
        except Exception as e:
            logger.error(f"参考信号捕获初始化失败: {e}")
            # 不抛出异常，允许AEC在没有参考信号的情况下工作
    
    def _find_blackhole_device(self) -> Optional[Dict[str, Any]]:
        """查找BlackHole 2ch虚拟设备"""
        try:
            devices = sd.query_devices()
            for i, device in enumerate(devices):
                device_name = device['name'].lower()
                # 查找BlackHole 2ch设备
                if 'blackhole' in device_name and '2ch' in device_name:
                    # 确保是输入设备
                    if device['max_input_channels'] >= 1:
                        device_info = dict(device)
                        device_info['id'] = i
                        logger.info(f"找到BlackHole设备: [{i}] {device['name']}")
                        return device_info
            
            # 如果没找到具体的BlackHole 2ch，尝试查找任何BlackHole设备
            for i, device in enumerate(devices):
                device_name = device['name'].lower()
                if 'blackhole' in device_name and device['max_input_channels'] >= 1:
                    device_info = dict(device)
                    device_info['id'] = i
                    logger.info(f"找到BlackHole设备: [{i}] {device['name']}")
                    return device_info
            
            return None
            
        except Exception as e:
            logger.error(f"查找BlackHole设备失败: {e}")
            return None
    
    def _reference_callback(self, indata, frames, time_info, status):
        """参考信号回调"""
        # frames, time_info用于sounddevice回调，此处不使用但需要保留签名
        _ = frames, time_info
        
        if status and "overflow" not in str(status).lower():
            logger.warning(f"参考信号流状态: {status}")
        
        if self._is_closing:
            return
        
        try:
            audio_data = indata.copy().flatten()
            
            # 重采样到16kHz（如果需要）
            if self.reference_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
                # 简单的降采样处理（实际应用中应使用更好的重采样器）
                ratio = AudioConfig.INPUT_SAMPLE_RATE / self.reference_sample_rate
                target_length = int(len(audio_data) * ratio)
                audio_data = np.interp(
                    np.linspace(0, len(audio_data) - 1, target_length),
                    np.arange(len(audio_data)),
                    audio_data
                ).astype(np.int16)
            
            # 添加到参考缓冲区
            self._reference_buffer.extend(audio_data)
            
            # 保持缓冲区大小合理
            max_buffer_size = self._webrtc_frame_size * 20  # 保持约200ms的数据
            while len(self._reference_buffer) > max_buffer_size:
                self._reference_buffer.popleft()
                
        except Exception as e:
            logger.error(f"参考信号回调错误: {e}")
    
    def _reference_finished_callback(self):
        """参考信号流结束回调"""
        logger.info("参考信号流已结束")
    
    def process_audio(self, capture_audio: np.ndarray) -> np.ndarray:
        """
        处理音频帧，应用AEC
        支持10ms/20ms/40ms/60ms等不同帧长度，通过分割处理实现
        
        Args:
            capture_audio: 麦克风采集的音频数据 (16kHz, int16)
            
        Returns:
            处理后的音频数据
        """
        if not self._is_initialized:
            return capture_audio
        
        # Windows 和 Linux 平台直接返回原始音频（系统级处理）
        if self._is_windows or self._is_linux:
            return capture_audio
        
        # macOS 平台使用 WebRTC AEC 处理
        if not self._is_macos or self.apm is None:
            return capture_audio
        
        try:
            # 检查输入帧大小是否为WebRTC帧大小的整数倍
            if len(capture_audio) % self._webrtc_frame_size != 0:
                logger.warning(f"音频帧大小不是WebRTC帧的整数倍: {len(capture_audio)}, WebRTC帧: {self._webrtc_frame_size}")
                return capture_audio
            
            # 计算需要分割的块数
            num_chunks = len(capture_audio) // self._webrtc_frame_size
            
            if num_chunks == 1:
                # 10ms帧，直接处理
                return self._process_single_aec_frame(capture_audio)
            else:
                # 20ms/40ms/60ms帧，分割处理
                return self._process_chunked_aec_frames(capture_audio, num_chunks)
            
        except Exception as e:
            logger.error(f"AEC处理失败: {e}")
            return capture_audio
    
    def _process_single_aec_frame(self, capture_audio: np.ndarray) -> np.ndarray:
        """处理单个10ms WebRTC帧（仅macOS）"""
        if not self._is_macos:
            return capture_audio
            
        try:
            # 仅在macOS导入ctypes
            import ctypes
            
            # 获取参考信号
            reference_audio = self._get_reference_frame(self._webrtc_frame_size)
            
            # 创建ctypes缓冲区
            capture_buffer = (ctypes.c_short * self._webrtc_frame_size)(*capture_audio)
            reference_buffer = (ctypes.c_short * self._webrtc_frame_size)(*reference_audio)
            
            processed_capture = (ctypes.c_short * self._webrtc_frame_size)()
            processed_reference = (ctypes.c_short * self._webrtc_frame_size)()
            
            # 首先处理参考信号（render stream）
            render_result = self.apm.process_reverse_stream(
                reference_buffer, self.render_config, self.render_config, processed_reference
            )
            
            if render_result != 0:
                logger.warning(f"参考信号处理失败，错误码: {render_result}")
            
            # 然后处理采集信号（capture stream）
            capture_result = self.apm.process_stream(
                capture_buffer, self.capture_config, self.capture_config, processed_capture
            )
            
            if capture_result != 0:
                logger.warning(f"采集信号处理失败，错误码: {capture_result}")
                return capture_audio
            
            # 转换回numpy数组
            return np.array(processed_capture, dtype=np.int16)
            
        except Exception as e:
            logger.error(f"AEC帧处理失败: {e}")
            return capture_audio
    
    def _process_chunked_aec_frames(self, capture_audio: np.ndarray, num_chunks: int) -> np.ndarray:
        """分割处理大帧（20ms/40ms/60ms等）"""
        processed_chunks = []
        
        for i in range(num_chunks):
            # 提取当前10ms块
            start_idx = i * self._webrtc_frame_size
            end_idx = (i + 1) * self._webrtc_frame_size
            chunk = capture_audio[start_idx:end_idx]
            
            # 处理这个10ms块
            processed_chunk = self._process_single_aec_frame(chunk)
            processed_chunks.append(processed_chunk)
        
        # 将所有处理后的块重新组合
        return np.concatenate(processed_chunks)
    
    def _get_reference_frame(self, frame_size: int) -> np.ndarray:
        """获取指定大小的参考信号帧"""
        # 如果没有参考信号或缓冲区不足，返回静音
        if len(self._reference_buffer) < frame_size:
            return np.zeros(frame_size, dtype=np.int16)
        
        # 从缓冲区提取一帧
        frame_data = []
        for _ in range(frame_size):
            frame_data.append(self._reference_buffer.popleft())
        
        return np.array(frame_data, dtype=np.int16)
    
    def is_reference_available(self) -> bool:
        """检查参考信号是否可用"""
        if self._is_windows or self._is_linux:
            # Windows 和 Linux 使用系统级AEC，总是可用
            return self._is_initialized
        
        # macOS 需要检查参考信号流
        return (self.reference_stream is not None and 
                self.reference_stream.active and 
                len(self._reference_buffer) >= self._webrtc_frame_size)
    
    def get_status(self) -> Dict[str, Any]:
        """获取AEC处理器状态"""
        status = {
            'initialized': self._is_initialized,
            'platform': self._platform,
            'reference_available': self.is_reference_available(),
        }
        
        if self._is_windows:
            status.update({
                'aec_type': 'system_level',
                'description': 'Windows 系统底层回声消除'
            })
        elif self._is_linux:
            status.update({
                'aec_type': 'system_level',
                'description': 'Linux 系统级回声消除（PulseAudio）'
            })
        elif self._is_macos:
            status.update({
                'aec_type': 'webrtc_blackhole',
                'description': 'WebRTC + BlackHole 参考信号',
                'reference_device_id': self.reference_device_id,
                'reference_buffer_size': len(self._reference_buffer),
                'webrtc_apm_active': self.apm is not None
            })
        else:
            status.update({
                'aec_type': 'unsupported',
                'description': f'平台 {self._platform} 暂不支持AEC'
            })
        
        return status
    
    async def close(self):
        """关闭AEC处理器"""
        if self._is_closing:
            return
        
        self._is_closing = True
        logger.info("开始关闭AEC处理器...")
        
        try:
            # 仅在 macOS 平台清理 WebRTC 相关资源
            if self._is_macos:
                # 停止参考信号流
                if self.reference_stream:
                    try:
                        self.reference_stream.stop()
                        self.reference_stream.close()
                    except Exception as e:
                        logger.warning(f"关闭参考信号流失败: {e}")
                    finally:
                        self.reference_stream = None
                
                # 清理WebRTC APM
                if self.apm:
                    try:
                        if self.capture_config:
                            self.apm.destroy_stream_config(self.capture_config)
                        if self.render_config:
                            self.apm.destroy_stream_config(self.render_config)
                    except Exception as e:
                        logger.warning(f"清理APM配置失败: {e}")
                    finally:
                        self.capture_config = None
                        self.render_config = None
                        self.apm = None
            
            # 清理缓冲区
            self._reference_buffer.clear()
            
            self._is_initialized = False
            logger.info("AEC处理器已关闭")
            
        except Exception as e:
            logger.error(f"关闭AEC处理器时发生错误: {e}")