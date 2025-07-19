#!/usr/bin/env python3
"""
WebRTC Audio Processing Module Python Wrapper (Enhanced)
基于Unity版本webrtc_apm动态库的增强Python封装

完全兼容Unity版本的配置结构体，提供工业级音频处理功能：
- 回声消除 (Echo Cancellation) 
- 噪声抑制 (Noise Suppression)
- 自动增益控制 (Automatic Gain Control)
- 高通滤波器 (High Pass Filter)
- 瞬态抑制 (Transient Suppression)
"""

import ctypes
import platform
import os
import numpy as np
from typing import Optional, Union, Tuple
from pathlib import Path
import struct
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebRTCAudioProcessingError(Exception):
    """WebRTC音频处理异常"""
    pass


class StreamConfig:
    """音频流配置
    
    用于配置音频流的基本参数，包括采样率、通道数等
    """
    def __init__(self, sample_rate: int, num_channels: int):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.samples_per_channel = sample_rate // 100  # 10ms frame
        
    def __repr__(self):
        return f"StreamConfig(sample_rate={self.sample_rate}, num_channels={self.num_channels})"


class WebRTCConfig:
    """WebRTC音频处理配置
    
    完全基于Unity版本的Config结构体，确保与C++代码的内存布局兼容
    """
    
    # 枚举定义
    class DownmixMethod:
        """下混方法"""
        AverageChannels = 0
        UseFirstChannel = 1

    class NoiseSuppressionLevel:
        """噪声抑制级别"""
        Low = 0
        Moderate = 1
        High = 2
        VeryHigh = 3
    
    class AGCMode:
        """AGC模式"""
        AdaptiveAnalog = 0
        AdaptiveDigital = 1
        FixedDigital = 2
    
    class ClippingPredictorMode:
        """裁剪预测模式"""
        ClippingEventPrediction = 0
        AdaptiveStepClippingPeakPrediction = 1
        FixedStepClippingPeakPrediction = 2

    def __init__(self):
        """初始化配置，使用与Unity C#版本相同的默认值"""
        # Pipeline配置
        self.maximum_internal_processing_rate = 48000
        self.multi_channel_render = False
        self.multi_channel_capture = False
        self.capture_downmix_method = self.DownmixMethod.AverageChannels
        
        # Pre-amplifier配置
        self.pre_amplifier_enabled = False
        self.pre_amplifier_fixed_gain_factor = 1.0
        
        # Capture level adjustment配置
        self.capture_level_adjustment_enabled = False
        self.capture_level_adjustment_pre_gain_factor = 1.0
        self.capture_level_adjustment_post_gain_factor = 1.0
        self.analog_mic_gain_emulation_enabled = False
        self.analog_mic_gain_emulation_initial_level = 255
        
        # High pass filter配置
        self.high_pass_filter_enabled = False
        self.high_pass_filter_apply_in_full_band = True
        
        # Echo canceller配置
        self.echo_canceller_enabled = False
        self.echo_canceller_mobile_mode = False
        self.echo_canceller_export_linear_aec_output = False
        self.echo_canceller_enforce_high_pass_filtering = True
        
        # Noise suppression配置
        self.noise_suppression_enabled = False
        self.noise_suppression_level = self.NoiseSuppressionLevel.Moderate
        self.noise_suppression_analyze_linear_aec_output = False
        
        # Transient suppression配置
        self.transient_suppression_enabled = False
        
        # Gain Controller 1配置
        self.gain_controller1_enabled = False
        self.gain_controller1_mode = self.AGCMode.AdaptiveAnalog
        self.gain_controller1_target_level_dbfs = 3
        self.gain_controller1_compression_gain_db = 9
        self.gain_controller1_enable_limiter = True
        
        # Analog gain controller配置
        self.analog_gain_controller_enabled = True
        self.analog_gain_controller_startup_min_volume = 0
        self.analog_gain_controller_clipped_level_min = 70
        self.analog_gain_controller_enable_digital_adaptive = True
        self.analog_gain_controller_clipped_level_step = 15
        self.analog_gain_controller_clipped_ratio_threshold = 0.1
        self.analog_gain_controller_clipped_wait_frames = 300
        
        # Clipping predictor配置
        self.clipping_predictor_enabled = False
        self.clipping_predictor_mode = self.ClippingPredictorMode.ClippingEventPrediction
        self.clipping_predictor_window_length = 5
        self.clipping_predictor_reference_window_length = 5
        self.clipping_predictor_reference_window_delay = 5
        self.clipping_predictor_clipping_threshold = -1.0
        self.clipping_predictor_crest_factor_margin = 3.0
        self.clipping_predictor_use_predicted_step = True
        
        # Gain Controller 2配置
        self.gain_controller2_enabled = False
        self.gain_controller2_input_volume_controller_enabled = False
        self.gain_controller2_adaptive_digital_enabled = False
        self.gain_controller2_adaptive_digital_headroom_db = 5.0
        self.gain_controller2_adaptive_digital_max_gain_db = 50.0
        self.gain_controller2_adaptive_digital_initial_gain_db = 15.0
        self.gain_controller2_adaptive_digital_max_gain_change_db_per_second = 6.0
        self.gain_controller2_adaptive_digital_max_output_noise_level_dbfs = -50.0
        self.gain_controller2_fixed_digital_gain_db = 0.0

    def to_bytes(self) -> bytes:
        """将配置转换为字节数据，确保与C++结构体布局完全匹配
        
        这个方法按照Unity C#版本的结构体定义来打包数据，
        确保在不同平台上的内存布局一致性。
        """
        try:
            # 使用struct.pack确保字节对齐和数据类型匹配
            # 格式字符串对应C++结构体的内存布局
            
            # Pipeline config (16 bytes) 
            pipeline_data = struct.pack('I??xxI', 
                self.maximum_internal_processing_rate,  # int (4 bytes)
                self.multi_channel_render,              # bool (1 byte)
                self.multi_channel_capture,             # bool (1 byte)
                # 2 bytes padding
                self.capture_downmix_method             # int (4 bytes)
            )
            
            # Pre-amplifier config (8 bytes)
            pre_amp_data = struct.pack('?xxxf',
                self.pre_amplifier_enabled,             # bool (1 byte)
                # 3 bytes padding
                self.pre_amplifier_fixed_gain_factor,   # float (4 bytes)
            )
            
            # Capture level adjustment config (20 bytes)
            level_adj_data = struct.pack('?xxxff?xxxI',
                self.capture_level_adjustment_enabled,      # bool (1 byte)
                # 3 bytes padding
                self.capture_level_adjustment_pre_gain_factor,  # float (4 bytes)
                self.capture_level_adjustment_post_gain_factor, # float (4 bytes)
                self.analog_mic_gain_emulation_enabled,     # bool (1 byte)
                # 3 bytes padding
                self.analog_mic_gain_emulation_initial_level # int (4 bytes)
            )
            
            # High pass filter config (8 bytes)
            hpf_data = struct.pack('??xxxxxx',
                self.high_pass_filter_enabled,          # bool (1 byte)
                self.high_pass_filter_apply_in_full_band, # bool (1 byte)
                # 6 bytes padding
            )
            
            # Echo canceller config (8 bytes)
            echo_data = struct.pack('????xxxx',
                self.echo_canceller_enabled,            # bool (1 byte)
                self.echo_canceller_mobile_mode,        # bool (1 byte)
                self.echo_canceller_export_linear_aec_output, # bool (1 byte)
                self.echo_canceller_enforce_high_pass_filtering, # bool (1 byte)
                # 4 bytes padding
            )
            
            # Noise suppression config (12 bytes)
            ns_data = struct.pack('?xxi?xxx',
                self.noise_suppression_enabled,         # bool (1 byte)
                # 1 byte padding
                # 2 bytes padding
                self.noise_suppression_level,           # int (4 bytes)
                self.noise_suppression_analyze_linear_aec_output, # bool (1 byte)
                # 3 bytes padding
            )
            
            # Transient suppression config (4 bytes)
            ts_data = struct.pack('?xxx',
                self.transient_suppression_enabled,     # bool (1 byte)
                # 3 bytes padding
            )
            
            # Gain Controller 1 config (20 bytes)
            gc1_data = struct.pack('?xxxiii?xxx',
                self.gain_controller1_enabled,          # bool (1 byte)
                # 3 bytes padding
                self.gain_controller1_mode,             # int (4 bytes)
                self.gain_controller1_target_level_dbfs, # int (4 bytes)
                self.gain_controller1_compression_gain_db, # int (4 bytes)
                self.gain_controller1_enable_limiter,   # bool (1 byte)
                # 3 bytes padding
            )
            
            # Analog gain controller (32 bytes)
            agc_data = struct.pack('?xxxii?xxxifi',
                self.analog_gain_controller_enabled,    # bool (1 byte)
                # 3 bytes padding
                self.analog_gain_controller_startup_min_volume, # int (4 bytes)
                self.analog_gain_controller_clipped_level_min,  # int (4 bytes)
                self.analog_gain_controller_enable_digital_adaptive, # bool (1 byte)
                # 3 bytes padding
                self.analog_gain_controller_clipped_level_step,     # int (4 bytes)
                self.analog_gain_controller_clipped_ratio_threshold, # float (4 bytes)
                self.analog_gain_controller_clipped_wait_frames,    # int (4 bytes)
            )
            
            # Clipping predictor (36 bytes)
            cp_data = struct.pack('?xxxiiiiiff?xxx',
                self.clipping_predictor_enabled,        # bool (1 byte)
                # 3 bytes padding
                self.clipping_predictor_mode,           # int (4 bytes)
                self.clipping_predictor_window_length,  # int (4 bytes)
                self.clipping_predictor_reference_window_length, # int (4 bytes)
                self.clipping_predictor_reference_window_delay,  # int (4 bytes)
                self.clipping_predictor_clipping_threshold,      # float (4 bytes)
                self.clipping_predictor_crest_factor_margin,     # float (4 bytes)
                self.clipping_predictor_use_predicted_step,      # bool (1 byte)
                # 3 bytes padding
            )
            
            # Gain Controller 2 config (44 bytes)
            gc2_data = struct.pack('??xx?xxxfffff',
                self.gain_controller2_enabled,          # bool (1 byte)
                self.gain_controller2_input_volume_controller_enabled, # bool (1 byte)
                # 2 bytes padding
                self.gain_controller2_adaptive_digital_enabled,         # bool (1 byte)
                # 3 bytes padding
                self.gain_controller2_adaptive_digital_headroom_db,     # float (4 bytes)
                self.gain_controller2_adaptive_digital_max_gain_db,     # float (4 bytes)
                self.gain_controller2_adaptive_digital_initial_gain_db, # float (4 bytes)
                self.gain_controller2_adaptive_digital_max_gain_change_db_per_second, # float (4 bytes)
                self.gain_controller2_adaptive_digital_max_output_noise_level_dbfs,   # float (4 bytes)
                self.gain_controller2_fixed_digital_gain_db,            # float (4 bytes)
            )
            
            # 组合所有数据
            config_data = (
                pipeline_data + pre_amp_data + level_adj_data +
                hpf_data + echo_data + ns_data + ts_data +
                gc1_data + agc_data + cp_data + gc2_data
            )
            
            logger.debug(f"配置数据长度: {len(config_data)} bytes")
            return config_data
            
        except struct.error as e:
            raise WebRTCAudioProcessingError(f"配置数据打包失败: {e}")

    def __repr__(self):
        enabled_features = []
        if self.echo_canceller_enabled:
            enabled_features.append("echo_canceller")
        if self.noise_suppression_enabled:
            enabled_features.append("noise_suppression")
        if self.gain_controller1_enabled:
            enabled_features.append("gain_controller1")
        if self.gain_controller2_enabled:
            enabled_features.append("gain_controller2")
        if self.high_pass_filter_enabled:
            enabled_features.append("high_pass_filter")
        
        features_str = ", ".join(enabled_features) if enabled_features else "none"
        return f"WebRTCConfig(enabled_features=[{features_str}])"


class WebRTCAudioProcessing:
    """WebRTC音频处理核心类
    
    基于Unity版本的C API封装，提供完整的音频处理功能链
    """
    
    def __init__(self, library_path: Optional[str] = None):
        """初始化WebRTC音频处理实例
        
        Args:
            library_path: 动态库路径，如果为None则自动检测
        """
        self._lib = None
        self._apm_handle = None
        self._stream_configs = {}  # 管理流配置的生命周期
        self._stream_config_counter = 0
        
        # 确定动态库路径
        if library_path:
            self._library_path = library_path
        else:
            self._library_path = self._get_library_path()
        
        # 加载动态库
        self._load_library(self._library_path)
        
        # 设置函数签名
        self._setup_function_signatures()
        
        # 创建APM实例
        self._create_apm_instance()
    
    def _get_library_path(self) -> str:
        """获取动态库路径"""
        # 使用相对于当前包的路径
        base_path = Path(__file__).parent
        
        system = platform.system()
        machine = platform.machine()
        
        if system == "Darwin":  # macOS
            if machine == "arm64":
                return str(base_path / "macos" / "arm64" / "libwebrtc_apm.dylib")
            else:
                return str(base_path / "macos" / "x64" / "libwebrtc_apm.dylib")
        elif system == "Linux":
            if machine == "aarch64":
                return str(base_path / "linux" / "arm64" / "libwebrtc_apm.so")
            else:
                return str(base_path / "linux" / "x64" / "libwebrtc_apm.so")
        elif system == "Windows":
            if machine == "AMD64":
                return str(base_path / "windows" / "x64" / "libwebrtc_apm.dll")
            else:
                return str(base_path / "windows" / "x86" / "libwebrtc_apm.dll")
        else:
            raise WebRTCAudioProcessingError(f"不支持的平台: {system}")

    def _load_library(self, library_path: str):
        """加载动态库"""
        if not os.path.exists(library_path):
            raise WebRTCAudioProcessingError(f"动态库文件不存在: {library_path}")
        
        try:
            self._lib = ctypes.CDLL(library_path)
            logger.info(f"成功加载动态库: {library_path}")
        except OSError as e:
            raise WebRTCAudioProcessingError(f"加载动态库失败: {e}")

    def _setup_function_signatures(self):
        """设置函数签名"""
        try:
            # WebRTC_APM_Create
            self._lib.WebRTC_APM_Create.argtypes = []
            self._lib.WebRTC_APM_Create.restype = ctypes.c_void_p
            
            # WebRTC_APM_Destroy
            self._lib.WebRTC_APM_Destroy.argtypes = [ctypes.c_void_p]
            self._lib.WebRTC_APM_Destroy.restype = None
            
            # WebRTC_APM_CreateStreamConfig
            self._lib.WebRTC_APM_CreateStreamConfig.argtypes = [ctypes.c_int, ctypes.c_int]
            self._lib.WebRTC_APM_CreateStreamConfig.restype = ctypes.c_void_p
            
            # WebRTC_APM_DestroyStreamConfig
            self._lib.WebRTC_APM_DestroyStreamConfig.argtypes = [ctypes.c_void_p]
            self._lib.WebRTC_APM_DestroyStreamConfig.restype = ctypes.c_void_p
            
            # WebRTC_APM_ApplyConfig
            self._lib.WebRTC_APM_ApplyConfig.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char)]
            self._lib.WebRTC_APM_ApplyConfig.restype = ctypes.c_int
            
            # WebRTC_APM_ProcessStream
            self._lib.WebRTC_APM_ProcessStream.argtypes = [
                ctypes.c_void_p,        # apm handle
                ctypes.POINTER(ctypes.c_short),  # src data
                ctypes.c_void_p,        # src config
                ctypes.c_void_p,        # dest config
                ctypes.POINTER(ctypes.c_short)   # dest data
            ]
            self._lib.WebRTC_APM_ProcessStream.restype = ctypes.c_int
            
            # WebRTC_APM_ProcessReverseStream
            self._lib.WebRTC_APM_ProcessReverseStream.argtypes = [
                ctypes.c_void_p,        # apm handle
                ctypes.POINTER(ctypes.c_short),  # src data
                ctypes.c_void_p,        # src config
                ctypes.c_void_p,        # dest config
                ctypes.POINTER(ctypes.c_short)   # dest data
            ]
            self._lib.WebRTC_APM_ProcessReverseStream.restype = ctypes.c_int
            
            # WebRTC_APM_SetStreamDelayMs
            self._lib.WebRTC_APM_SetStreamDelayMs.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self._lib.WebRTC_APM_SetStreamDelayMs.restype = None
            
            logger.info("函数签名设置完成")
            
        except AttributeError as e:
            raise WebRTCAudioProcessingError(f"函数签名设置失败，可能是动态库版本不匹配: {e}")

    def _create_apm_instance(self):
        """创建APM实例"""
        self._apm_handle = self._lib.WebRTC_APM_Create()
        if not self._apm_handle:
            raise WebRTCAudioProcessingError("APM实例创建失败")
        
        logger.info(f"APM实例创建成功: {hex(self._apm_handle)}")

    def create_stream_config(self, sample_rate: int, num_channels: int) -> Tuple[int, int]:
        """创建流配置
        
        Args:
            sample_rate: 采样率
            num_channels: 通道数
            
        Returns:
            (config_id, config_handle): 配置ID和句柄
        """
        try:
            config_handle = self._lib.WebRTC_APM_CreateStreamConfig(sample_rate, num_channels)
            if not config_handle:
                raise WebRTCAudioProcessingError("流配置创建失败")
            
            config_id = self._stream_config_counter
            self._stream_configs[config_id] = {
                'handle': config_handle,
                'sample_rate': sample_rate,
                'num_channels': num_channels
            }
            self._stream_config_counter += 1
            
            logger.info(f"流配置创建成功: ID={config_id}, 句柄={hex(config_handle)}")
            return config_id, config_handle
            
        except Exception as e:
            raise WebRTCAudioProcessingError(f"创建流配置失败: {e}")

    def destroy_stream_config(self, config_id: int):
        """销毁流配置
        
        Args:
            config_id: 配置ID
        """
        if config_id not in self._stream_configs:
            logger.warning(f"配置ID {config_id} 不存在")
            return
        
        try:
            config_handle = self._stream_configs[config_id]['handle']
            self._lib.WebRTC_APM_DestroyStreamConfig(config_handle)
            del self._stream_configs[config_id]
            logger.info(f"流配置销毁成功: ID={config_id}")
            
        except Exception as e:
            logger.error(f"销毁流配置失败: {e}")

    def apply_config(self, config: WebRTCConfig) -> bool:
        """应用配置
        
        Args:
            config: WebRTC配置对象
            
        Returns:
            是否成功应用配置
        """
        try:
            config_bytes = config.to_bytes()
            config_buffer = (ctypes.c_char * len(config_bytes)).from_buffer_copy(config_bytes)
            
            result = self._lib.WebRTC_APM_ApplyConfig(self._apm_handle, config_buffer)
            
            if result == 0:
                logger.info(f"应用配置: {config}")
                return True
            else:
                logger.error(f"应用配置失败: 错误码={result}")
                return False
                
        except Exception as e:
            logger.error(f"应用配置异常: {e}")
            return False

    def set_stream_delay_ms(self, delay_ms: int):
        """设置流延迟
        
        Args:
            delay_ms: 延迟时间（毫秒）
        """
        try:
            self._lib.WebRTC_APM_SetStreamDelayMs(self._apm_handle, delay_ms)
            logger.info(f"流延迟设置成功: {delay_ms}ms")
        except Exception as e:
            logger.error(f"设置流延迟失败: {e}")

    def process_stream(self, 
                      audio_data: np.ndarray,
                      src_config_id: int,
                      dest_config_id: Optional[int] = None) -> np.ndarray:
        """处理音频流（前向流处理）
        
        Args:
            audio_data: 输入音频数据
            src_config_id: 源配置ID
            dest_config_id: 目标配置ID，如果为None则使用源配置
            
        Returns:
            处理后的音频数据
        """
        if src_config_id not in self._stream_configs:
            raise WebRTCAudioProcessingError(f"源配置ID {src_config_id} 不存在")
        
        if dest_config_id is None:
            dest_config_id = src_config_id
        elif dest_config_id not in self._stream_configs:
            raise WebRTCAudioProcessingError(f"目标配置ID {dest_config_id} 不存在")
        
        try:
            # 获取配置信息
            src_config = self._stream_configs[src_config_id]
            dest_config = self._stream_configs[dest_config_id]
            
            # 数据格式转换
            if audio_data.dtype == np.float32:
                # float32 -> int16
                audio_int16 = (audio_data * 32767).astype(np.int16)
            elif audio_data.dtype == np.int16:
                audio_int16 = audio_data
            else:
                raise WebRTCAudioProcessingError(f"不支持的音频数据类型: {audio_data.dtype}")
            
            # 确保数据是连续的
            if not audio_int16.flags.c_contiguous:
                audio_int16 = np.ascontiguousarray(audio_int16)
            
            # 调整数据形状
            if audio_int16.ndim == 1:
                samples_per_channel = len(audio_int16) // src_config['num_channels']
                if src_config['num_channels'] > 1:
                    audio_int16 = audio_int16.reshape(samples_per_channel, src_config['num_channels'])
                else:
                    audio_int16 = audio_int16.reshape(-1, 1)
            
            # 创建输出缓冲区
            output_samples = audio_int16.shape[0]
            output_channels = dest_config['num_channels']
            output_data = np.zeros((output_samples, output_channels), dtype=np.int16)
            
            # 确保输出数据是连续的
            if not output_data.flags.c_contiguous:
                output_data = np.ascontiguousarray(output_data)
            
            # 调用C函数
            result = self._lib.WebRTC_APM_ProcessStream(
                self._apm_handle,
                audio_int16.ctypes.data_as(ctypes.POINTER(ctypes.c_short)),
                src_config['handle'],
                dest_config['handle'],
                output_data.ctypes.data_as(ctypes.POINTER(ctypes.c_short))
            )
            
            if result != 0:
                raise WebRTCAudioProcessingError(f"音频流处理失败: 错误码={result}")
            
            return output_data
            
        except Exception as e:
            raise WebRTCAudioProcessingError(f"处理音频流时发生错误: {e}")

    def process_reverse_stream(self,
                              audio_data: np.ndarray,
                              src_config_id: int,
                              dest_config_id: Optional[int] = None) -> np.ndarray:
        """处理反向音频流（播放音频处理，用于回声消除）
        
        Args:
            audio_data: 输入音频数据
            src_config_id: 源配置ID
            dest_config_id: 目标配置ID，如果为None则使用源配置
            
        Returns:
            处理后的音频数据
        """
        if src_config_id not in self._stream_configs:
            raise WebRTCAudioProcessingError(f"源配置ID {src_config_id} 不存在")
        
        if dest_config_id is None:
            dest_config_id = src_config_id
        elif dest_config_id not in self._stream_configs:
            raise WebRTCAudioProcessingError(f"目标配置ID {dest_config_id} 不存在")
        
        try:
            # 获取配置信息
            src_config = self._stream_configs[src_config_id]
            dest_config = self._stream_configs[dest_config_id]
            
            # 数据格式转换
            if audio_data.dtype == np.float32:
                # float32 -> int16
                audio_int16 = (audio_data * 32767).astype(np.int16)
            elif audio_data.dtype == np.int16:
                audio_int16 = audio_data
            else:
                raise WebRTCAudioProcessingError(f"不支持的音频数据类型: {audio_data.dtype}")
            
            # 确保数据是连续的
            if not audio_int16.flags.c_contiguous:
                audio_int16 = np.ascontiguousarray(audio_int16)
            
            # 调整数据形状
            if audio_int16.ndim == 1:
                samples_per_channel = len(audio_int16) // src_config['num_channels']
                if src_config['num_channels'] > 1:
                    audio_int16 = audio_int16.reshape(samples_per_channel, src_config['num_channels'])
                else:
                    audio_int16 = audio_int16.reshape(-1, 1)
            
            # 创建输出缓冲区
            output_samples = audio_int16.shape[0]
            output_channels = dest_config['num_channels']
            output_data = np.zeros((output_samples, output_channels), dtype=np.int16)
            
            # 确保输出数据是连续的
            if not output_data.flags.c_contiguous:
                output_data = np.ascontiguousarray(output_data)
            
            # 调用C函数
            result = self._lib.WebRTC_APM_ProcessReverseStream(
                self._apm_handle,
                audio_int16.ctypes.data_as(ctypes.POINTER(ctypes.c_short)),
                src_config['handle'],
                dest_config['handle'],
                output_data.ctypes.data_as(ctypes.POINTER(ctypes.c_short))
            )
            
            if result != 0:
                raise WebRTCAudioProcessingError(f"反向音频流处理失败: 错误码={result}")
            
            return output_data
            
        except Exception as e:
            raise WebRTCAudioProcessingError(f"处理反向音频流时发生错误: {e}")

    def __del__(self):
        """析构函数，清理资源"""
        self.cleanup()

    def cleanup(self):
        """清理资源"""
        try:
            # 销毁所有流配置
            for config_id in list(self._stream_configs.keys()):
                self.destroy_stream_config(config_id)
            
            # 销毁APM实例
            if self._apm_handle and self._lib:
                self._lib.WebRTC_APM_Destroy(self._apm_handle)
                logger.info("APM实例销毁成功")
                self._apm_handle = None
                
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}")

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.cleanup()