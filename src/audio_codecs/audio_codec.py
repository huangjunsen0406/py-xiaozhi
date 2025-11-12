import asyncio
import gc
import time
from collections import deque
from typing import Callable, List, Optional, Protocol

import numpy as np
import opuslib
import sounddevice as sd
import soxr

from src.audio_codecs.aec_processor import AECProcessor
from src.constants.constants import AudioConfig
from src.utils.audio_utils import (
    downmix_to_mono,
    safe_queue_put,
    select_audio_device,
    upmix_mono_to_channels,
)
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioListener(Protocol):
    """音频监听器协议（用于唤醒词检测等）"""
    def on_audio_data(self, audio_data: np.ndarray) -> None:
        """接收音频数据的回调"""
        ...


class AudioCodec:
    """
    音频编解码器 - 音频格式适配器 + 编解码通道
    
    核心职责：
    1. 设备管理：设备选择、流创建、错误恢复
    2. 格式转换：采样率转换、声道转换、帧重组
    3. 编解码：PCM ↔ Opus
    4. 流控缓冲：防溢出、防卡顿
    
    设计原则：
    - 设备层：完全按照设备原生能力创建（采样率、声道数）
    - 转换层：自动适配设备格式与服务端协议
    - 解耦原则：通过回调和观察者模式解耦外部依赖
    
    转换流程：
    - 输入：设备原生 → 下混+重采样 → 16kHz单声道 → Opus编码 → 回调发送
    - 输出：接收Opus → 解码24kHz单声道 → 重采样+上混 → 设备原生播放
    """

    def __init__(
        self,
        audio_processor: Optional[AECProcessor] = None
    ):
        """
        初始化音频编解码器
        
        Args:
            audio_processor: 可选的音频处理器（AEC等），通过依赖注入解耦
        """
        # 获取配置管理器
        self.config = ConfigManager.get_instance()

        # Opus编解码器
        self.opus_encoder = None
        self.opus_decoder = None

        # 设备原生信息
        self.device_input_sample_rate = None
        self.device_output_sample_rate = None
        self.device_input_channels = None
        self.device_output_channels = None
        self.mic_device_id = None
        self.speaker_device_id = None

        # 重采样器（按需创建）
        self.input_resampler = None
        self.output_resampler = None

        # 重采样缓冲区
        self._resample_input_buffer = deque()
        self._resample_output_buffer = deque()

        # 转换标记
        self._need_input_downmix = False
        self._need_output_upmix = False

        # 设备帧大小
        self._device_input_frame_size = None
        self._device_output_frame_size = None

        # 音频流对象
        self.input_stream = None
        self.output_stream = None

        # 播放队列
        self._output_buffer = asyncio.Queue(maxsize=500)

        # 回调和监听器（解耦外部依赖）
        self._encoded_callback: Optional[Callable] = None
        self._audio_listeners: List[AudioListener] = []

        # 音频处理器（可选注入）
        self.audio_processor = audio_processor
        self._aec_enabled = False

        # 状态标记
        self._is_closing = False

    async def initialize(self):
        """
        初始化音频设备和编解码器
        
        策略：
        1. 首次运行：自动选择最佳设备，保存配置
        2. 后续运行：从配置加载设备信息
        3. 按设备原生能力创建流（采样率、声道数）
        4. 自动创建转换器（采样率、声道）
        """
        try:
            # 加载或初始化设备配置
            await self._load_device_config()
            
            # 创建Opus编解码器
            await self._create_opus_codecs()
            
            # 创建重采样器和转换标记
            await self._create_resamplers()
            
            # 创建音频流（使用设备原生格式）
            await self._create_streams()
            
            # 初始化AEC处理器（如果提供）
            if self.audio_processor:
                try:
                    await self.audio_processor.initialize()
                    self._aec_enabled = self.audio_processor._is_initialized
                    logger.info(f"AEC处理器已初始化: {'启用' if self._aec_enabled else '禁用'}")
                except Exception as e:
                    logger.warning(f"AEC处理器初始化失败: {e}")
                    self._aec_enabled = False
            
            logger.info("AudioCodec 初始化完成")
            
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _load_device_config(self):
        """加载或初始化设备配置"""
        audio_config = self.config.get_config("AUDIO_DEVICES", {}) or {}
        
        input_device_id = audio_config.get("input_device_id")
        output_device_id = audio_config.get("output_device_id")
        
        # 首次运行：自动选择设备
        if input_device_id is None or output_device_id is None:
            logger.info("首次运行，自动选择音频设备...")
            await self._auto_detect_devices()
            return
        
        # 从配置加载
        self.mic_device_id = input_device_id
        self.speaker_device_id = output_device_id
        self.device_input_sample_rate = audio_config.get("input_sample_rate", AudioConfig.INPUT_SAMPLE_RATE)
        self.device_output_sample_rate = audio_config.get("output_sample_rate", AudioConfig.OUTPUT_SAMPLE_RATE)
        self.device_input_channels = audio_config.get("input_channels", 1)
        self.device_output_channels = audio_config.get("output_channels", 1)
        
        # 计算设备帧大小
        self._device_input_frame_size = int(
            self.device_input_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
        )
        self._device_output_frame_size = int(
            self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
        )
        
        logger.info(
            f"加载设备配置 | 输入: {self.device_input_sample_rate}Hz {self.device_input_channels}ch | "
            f"输出: {self.device_output_sample_rate}Hz {self.device_output_channels}ch"
        )

    async def _auto_detect_devices(self):
        """自动检测并选择最佳设备"""
        # 使用智能设备选择
        in_info = select_audio_device("input", include_virtual=False)
        out_info = select_audio_device("output", include_virtual=False)
        
        if not in_info or not out_info:
            raise RuntimeError("无法找到可用的音频设备")
        
        # 限制声道数（避免100+声道设备性能浪费）
        raw_input_channels = in_info['channels']
        raw_output_channels = out_info['channels']
        
        self.device_input_channels = min(raw_input_channels, AudioConfig.MAX_INPUT_CHANNELS)
        self.device_output_channels = min(raw_output_channels, AudioConfig.MAX_OUTPUT_CHANNELS)
        
        # 记录设备信息
        self.mic_device_id = in_info['index']
        self.speaker_device_id = out_info['index']
        self.device_input_sample_rate = in_info['sample_rate']
        self.device_output_sample_rate = out_info['sample_rate']
        
        # 计算帧大小
        self._device_input_frame_size = int(
            self.device_input_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
        )
        self._device_output_frame_size = int(
            self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
        )
        
        # 日志输出
        if raw_input_channels > AudioConfig.MAX_INPUT_CHANNELS:
            logger.info(
                f"输入设备支持 {raw_input_channels} 声道，限制使用前 {self.device_input_channels} 声道"
            )
        if raw_output_channels > AudioConfig.MAX_OUTPUT_CHANNELS:
            logger.info(
                f"输出设备支持 {raw_output_channels} 声道，限制使用前 {self.device_output_channels} 声道"
            )
        
        logger.info(f"选择输入设备: {in_info['name']} ({self.device_input_sample_rate}Hz, {self.device_input_channels}ch)")
        logger.info(f"选择输出设备: {out_info['name']} ({self.device_output_sample_rate}Hz, {self.device_output_channels}ch)")
        
        # 保存配置（首次运行时保存）
        self.config.update_config("AUDIO_DEVICES.input_device_id", self.mic_device_id)
        self.config.update_config("AUDIO_DEVICES.input_device_name", in_info['name'])
        self.config.update_config("AUDIO_DEVICES.input_sample_rate", self.device_input_sample_rate)
        self.config.update_config("AUDIO_DEVICES.input_channels", self.device_input_channels)
        
        self.config.update_config("AUDIO_DEVICES.output_device_id", self.speaker_device_id)
        self.config.update_config("AUDIO_DEVICES.output_device_name", out_info['name'])
        self.config.update_config("AUDIO_DEVICES.output_sample_rate", self.device_output_sample_rate)
        self.config.update_config("AUDIO_DEVICES.output_channels", self.device_output_channels)

    async def _create_opus_codecs(self):
        """创建Opus编解码器"""
        try:
            # 输入编码器：16kHz单声道
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                opuslib.APPLICATION_VOIP
            )
            
            # 输出解码器：24kHz单声道
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS
            )
            
            logger.info("Opus编解码器创建成功")
        except Exception as e:
            logger.error(f"创建Opus编解码器失败: {e}")
            raise

    async def _create_resamplers(self):
        """
        根据设备与服务端的差异，按需创建重采样器和转换标记
        """
        # 输入转换器配置
        # 1. 声道下混标记
        self._need_input_downmix = (self.device_input_channels > 1)
        if self._need_input_downmix:
            logger.info(f"输入声道下混: {self.device_input_channels}ch → 1ch")

        # 2. 采样率重采样器
        if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
            self.input_resampler = soxr.ResampleStream(
                self.device_input_sample_rate,
                AudioConfig.INPUT_SAMPLE_RATE,
                num_channels=1,  # 重采样器处理单声道（下混后）
                dtype="int16",
                quality="QQ",    # 快速质量（低延迟）
            )
            logger.info(f"输入重采样: {self.device_input_sample_rate}Hz → 16kHz")

        # 输出转换器配置
        # 1. 采样率重采样器
        if self.device_output_sample_rate != AudioConfig.OUTPUT_SAMPLE_RATE:
            self.output_resampler = soxr.ResampleStream(
                AudioConfig.OUTPUT_SAMPLE_RATE,
                self.device_output_sample_rate,
                num_channels=1,  # 重采样器处理单声道（上混前）
                dtype="int16",
                quality="QQ",
            )
            logger.info(
                f"输出重采样: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz → "
                f"{self.device_output_sample_rate}Hz"
            )

        # 2. 声道上混标记
        self._need_output_upmix = (self.device_output_channels > 1)
        if self._need_output_upmix:
            logger.info(f"输出声道上混: 1ch → {self.device_output_channels}ch")

    async def _create_streams(self):
        """
        创建音频流（完全使用设备原生格式）
        """
        try:
            # 输入流：使用设备原生采样率和声道数
            self.input_stream = sd.InputStream(
                device=self.mic_device_id,
                samplerate=self.device_input_sample_rate,   # 设备原生采样率
                channels=self.device_input_channels,        # 设备原生声道数
                dtype=np.int16,
                blocksize=self._device_input_frame_size,    # 设备原生帧大小
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency="low",
            )

            # 输出流：使用设备原生采样率和声道数
            self.output_stream = sd.OutputStream(
                device=self.speaker_device_id,
                samplerate=self.device_output_sample_rate,  # 设备原生采样率
                channels=self.device_output_channels,       # 设备原生声道数
                dtype=np.int16,
                blocksize=self._device_output_frame_size,   # 设备原生帧大小
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency="low",
            )

            self.input_stream.start()
            self.output_stream.start()

            logger.info(
                f"音频流已启动 | 输入: {self.device_input_sample_rate}Hz {self.device_input_channels}ch | "
                f"输出: {self.device_output_sample_rate}Hz {self.device_output_channels}ch"
            )

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """
        输入回调：设备原生格式 → 服务端协议格式
        转换流程：多声道/高采样率 → 下混+重采样 → 16kHz单声道 → Opus编码
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            # 步骤1: 声道下混（立体声/多声道 → 单声道）
            if self._need_input_downmix:
                # indata shape: (frames, channels)
                audio_data = downmix_to_mono(indata, keepdims=False).astype(np.int16)
            else:
                audio_data = indata.flatten()  # 已经是单声道

            # 步骤2: 采样率转换（设备采样率 → 16kHz）
            if self.input_resampler is not None:
                audio_data = self._process_input_resampling(audio_data)
                if audio_data is None:  # 数据不足，等待下一帧
                    return

            # 步骤3: 验证帧大小
            if len(audio_data) != AudioConfig.INPUT_FRAME_SIZE:
                return

            # 步骤4: AEC处理（如果启用）
            if self._aec_enabled and self.audio_processor._is_macos:
                try:
                    audio_data = self.audio_processor.process_audio(audio_data)
                except Exception as e:
                    logger.warning(f"AEC处理失败，使用原始音频: {e}")

            # 步骤5: Opus编码并实时发送
            if self._encoded_callback:
                try:
                    pcm_data = audio_data.astype(np.int16).tobytes()
                    encoded_data = self.opus_encoder.encode(
                        pcm_data, AudioConfig.INPUT_FRAME_SIZE
                    )
                    if encoded_data:
                        self._encoded_callback(encoded_data)
                except Exception as e:
                    logger.warning(f"实时录音编码失败: {e}")

            # 步骤6: 通知音频监听器（解耦唤醒词检测）
            for listener in self._audio_listeners:
                try:
                    listener.on_audio_data(audio_data.copy())
                except Exception as e:
                    logger.warning(f"音频监听器处理失败: {e}")

        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _process_input_resampling(self, audio_data):
        """
        输入重采样处理：设备采样率 → 16kHz
        使用缓冲区累积数据，凑够一帧再返回
        """
        try:
            resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
            if len(resampled_data) > 0:
                self._resample_input_buffer.extend(resampled_data.astype(np.int16))

            # 累积到目标帧大小
            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._resample_input_buffer) < expected_frame_size:
                return None

            # 取出一帧
            frame_data = []
            for _ in range(expected_frame_size):
                frame_data.append(self._resample_input_buffer.popleft())

            return np.array(frame_data, dtype=np.int16)

        except Exception as e:
            logger.error(f"输入重采样失败: {e}")
            return None

    def _output_callback(self, outdata, frames, time_info, status):
        """
        输出回调：服务端协议格式 → 设备原生格式
        转换流程：24kHz单声道 → 重采样+上混 → 多声道/高采样率
        """
        if status:
            if "underflow" not in str(status).lower():
                logger.warning(f"输出流状态: {status}")

        try:
            # 获取解码后的24kHz单声道数据
            if self.output_resampler is not None:
                # 需要重采样：24kHz → 设备采样率
                self._output_callback_with_resample(outdata, frames)
            else:
                # 直接播放：24kHz
                self._output_callback_direct(outdata, frames)

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0)

    def _output_callback_direct(self, outdata, frames):
        """
        直接播放（设备支持24kHz时）

        处理流程:
        1. 从队列取出单声道数据 (OUTPUT_FRAME_SIZE个样本)
        2. 截取或填充到所需帧数
        3. 如需上混,复制到多声道;否则直接输出
        """
        try:
            # 从播放队列获取音频数据（单声道数据）
            audio_data = self._output_buffer.get_nowait()

            # audio_data 是单声道数据,长度通常 = OUTPUT_FRAME_SIZE
            # 截取或填充到所需帧数
            if len(audio_data) >= frames:
                mono_samples = audio_data[:frames]
            else:
                # 数据不足,填充静音
                mono_samples = np.zeros(frames, dtype=np.int16)
                mono_samples[:len(audio_data)] = audio_data

            # 声道处理
            if self._need_output_upmix:
                # 单声道 → 多声道（复制到所有声道）
                multi_channel = upmix_mono_to_channels(mono_samples, self.device_output_channels)
                outdata[:] = multi_channel
            else:
                # 单声道输出
                outdata[:, 0] = mono_samples

        except asyncio.QueueEmpty:
            # 无数据时输出静音
            outdata.fill(0)

    def _output_callback_with_resample(self, outdata, frames):
        """
        重采样播放（24kHz → 设备采样率）

        处理流程:
        1. 从队列取出24kHz单声道数据
        2. 重采样到设备采样率（仍为单声道）
        3. 累积到缓冲区,凑够所需帧数
        4. 如需上混,复制到多声道;否则直接输出
        """
        try:
            # 持续处理24kHz单声道数据进行重采样
            # 注意: 缓冲区保存的是单声道数据,所以比较 frames 而非 frames*channels
            while len(self._resample_output_buffer) < frames:
                try:
                    audio_data = self._output_buffer.get_nowait()
                    # 24kHz单声道 → 设备采样率单声道重采样
                    resampled_data = self.output_resampler.resample_chunk(
                        audio_data, last=False
                    )
                    if len(resampled_data) > 0:
                        self._resample_output_buffer.extend(
                            resampled_data.astype(np.int16)
                        )
                except asyncio.QueueEmpty:
                    break

            # 取出所需帧数的单声道数据
            if len(self._resample_output_buffer) >= frames:
                frame_data = []
                for _ in range(frames):
                    frame_data.append(self._resample_output_buffer.popleft())
                mono_data = np.array(frame_data, dtype=np.int16)

                # 声道处理
                if self._need_output_upmix:
                    # 单声道 → 多声道（复制到所有声道）
                    multi_channel = upmix_mono_to_channels(mono_data, self.device_output_channels)
                    outdata[:] = multi_channel
                else:
                    # 单声道输出
                    outdata[:, 0] = mono_data
            else:
                # 数据不足时输出静音
                outdata.fill(0)

        except Exception as e:
            logger.warning(f"重采样输出失败: {e}")
            outdata.fill(0)

    def _input_finished_callback(self):
        """输入流结束回调"""
        logger.info("输入流已结束")

    def _output_finished_callback(self):
        """输出流结束回调"""
        logger.info("输出流已结束")

    # ============= 对外接口方法 =============

    def set_encoded_callback(self, callback: Callable[[bytes], None]):
        """
        设置编码音频回调（解耦网络层）
        
        Args:
            callback: 编码后数据的回调函数，接收 bytes 类型的 Opus 数据
        
        示例:
            def network_send(opus_data: bytes):
                await websocket.send(opus_data)
            
            audio_codec.set_encoded_callback(network_send)
        """
        self._encoded_callback = callback
        
        if callback:
            logger.info("已设置编码音频回调")
        else:
            logger.info("已清除编码音频回调")

    def add_audio_listener(self, listener: AudioListener):
        """
        添加音频监听器（解耦唤醒词检测等功能）
        
        Args:
            listener: 实现 AudioListener 协议的监听器对象
        
        示例:
            wake_word_detector = WakeWordDetector()  # 实现了 on_audio_data 方法
            audio_codec.add_audio_listener(wake_word_detector)
        """
        if listener not in self._audio_listeners:
            self._audio_listeners.append(listener)
            logger.info(f"已添加音频监听器: {listener.__class__.__name__}")

    def remove_audio_listener(self, listener: AudioListener):
        """
        移除音频监听器
        
        Args:
            listener: 要移除的监听器对象
        """
        if listener in self._audio_listeners:
            self._audio_listeners.remove(listener)
            logger.info(f"已移除音频监听器: {listener.__class__.__name__}")

    async def write_audio(self, opus_data: bytes):
        """
        解码并播放音频（服务端 Opus 数据 → 扬声器）
        
        Args:
            opus_data: 服务端返回的 Opus 编码数据
        
        流程:
            Opus解码 → 24kHz单声道PCM → 播放队列 → 输出回调处理
        """
        try:
            # Opus解码为24kHz PCM数据
            pcm_data = self.opus_decoder.decode(
                opus_data, AudioConfig.OUTPUT_FRAME_SIZE
            )
            
            audio_array = np.frombuffer(pcm_data, dtype=np.int16)
            
            expected_length = AudioConfig.OUTPUT_FRAME_SIZE * AudioConfig.CHANNELS
            if len(audio_array) != expected_length:
                logger.warning(
                    f"解码音频长度异常: {len(audio_array)}, 期望: {expected_length}"
                )
                return
            
            # 放入播放队列（使用工具函数安全入队）
            if not safe_queue_put(self._output_buffer, audio_array, replace_oldest=True):
                logger.warning("播放队列已满，丢弃音频帧")
        
        except opuslib.OpusError as e:
            logger.warning(f"Opus解码失败，丢弃此帧: {e}")
        except Exception as e:
            logger.warning(f"音频写入失败，丢弃此帧: {e}")

    async def start(self):
        """启动音频流"""
        try:
            if self.input_stream and not self.input_stream.active:
                try:
                    self.input_stream.start()
                except Exception as e:
                    logger.warning(f"启动输入流时出错: {e}")
                    await self.reinitialize_stream(is_input=True)
            
            if self.output_stream and not self.output_stream.active:
                try:
                    self.output_stream.start()
                except Exception as e:
                    logger.warning(f"启动输出流时出错: {e}")
                    await self.reinitialize_stream(is_input=False)
            
            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")

    async def stop(self):
        """停止音频流"""
        try:
            if self.input_stream and self.input_stream.active:
                self.input_stream.stop()
        except Exception as e:
            logger.warning(f"停止输入流失败: {e}")
        
        try:
            if self.output_stream and self.output_stream.active:
                self.output_stream.stop()
        except Exception as e:
            logger.warning(f"停止输出流失败: {e}")

    async def reinitialize_stream(self, is_input: bool = True):
        """
        重建音频流（处理设备错误/断开）
        
        Args:
            is_input: True=重建输入流, False=重建输出流
        
        使用场景:
            - 设备热插拔
            - 驱动错误恢复
            - 系统休眠唤醒
        """
        if self._is_closing:
            return False if is_input else None
        
        try:
            if is_input:
                if self.input_stream:
                    self.input_stream.stop()
                    self.input_stream.close()
                
                self.input_stream = sd.InputStream(
                    device=self.mic_device_id,
                    samplerate=self.device_input_sample_rate,
                    channels=self.device_input_channels,
                    dtype=np.int16,
                    blocksize=self._device_input_frame_size,
                    callback=self._input_callback,
                    finished_callback=self._input_finished_callback,
                    latency="low",
                )
                self.input_stream.start()
                logger.info("输入流重新初始化成功")
                return True
            else:
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()
                
                self.output_stream = sd.OutputStream(
                    device=self.speaker_device_id,
                    samplerate=self.device_output_sample_rate,
                    channels=self.device_output_channels,
                    dtype=np.int16,
                    blocksize=self._device_output_frame_size,
                    callback=self._output_callback,
                    finished_callback=self._output_finished_callback,
                    latency="low",
                )
                self.output_stream.start()
                logger.info("输出流重新初始化成功")
                return None
        except Exception as e:
            stream_type = "输入" if is_input else "输出"
            logger.error(f"{stream_type}流重建失败: {e}")
            if is_input:
                return False
            else:
                raise

    async def clear_audio_queue(self):
        """
        清空音频队列
        
        使用场景:
            - 用户中断播放
            - 唤醒词触发时打断旧音频
            - 错误恢复时清空脏数据
        """
        cleared_count = 0
        
        # 清空播放队列
        while not self._output_buffer.empty():
            try:
                self._output_buffer.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        # 清空重采样缓冲区
        if self._resample_input_buffer:
            cleared_count += len(self._resample_input_buffer)
            self._resample_input_buffer.clear()
        
        if self._resample_output_buffer:
            cleared_count += len(self._resample_output_buffer)
            self._resample_output_buffer.clear()
        
        if cleared_count > 0:
            logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")
        
        if cleared_count > 100:
            gc.collect()
            logger.debug("执行垃圾回收以释放内存")

    async def wait_for_audio_complete(self, timeout: float = 10.0):
        """
        等待播放完成
        
        Args:
            timeout: 超时时间（秒）
        
        使用场景:
            - TTS播放完成后再继续对话
            - 确保音频完整播放后关闭流
        """
        start = time.time()
        
        while not self._output_buffer.empty() and time.time() - start < timeout:
            await asyncio.sleep(0.05)
        
        await asyncio.sleep(0.3)
        
        if not self._output_buffer.empty():
            output_remaining = self._output_buffer.qsize()
            logger.warning(f"音频播放超时，剩余队列: {output_remaining} 帧")

    def is_active(self) -> bool:
        """检查音频流是否活跃"""
        input_active = self.input_stream and self.input_stream.active
        output_active = self.output_stream and self.output_stream.active
        return input_active or output_active

    def get_buffer_status(self) -> dict:
        """获取缓冲区状态"""
        return {
            "output_queue_size": self._output_buffer.qsize(),
            "input_resample_buffer": len(self._resample_input_buffer),
            "output_resample_buffer": len(self._resample_output_buffer),
        }

    # ============= AEC 控制方法（可选）=============

    def is_aec_enabled(self) -> bool:
        """检查AEC是否启用"""
        return self._aec_enabled

    def get_aec_status(self) -> dict:
        """获取AEC状态信息"""
        if not self._aec_enabled or not self.audio_processor:
            return {"enabled": False, "reason": "AEC未启用或初始化失败"}
        
        try:
            return {"enabled": True, **self.audio_processor.get_status()}
        except Exception as e:
            return {"enabled": False, "reason": f"获取状态失败: {e}"}

    def toggle_aec(self, enabled: bool) -> bool:
        """
        切换AEC启用状态
        
        Args:
            enabled: 是否启用AEC
        
        Returns:
            实际的AEC状态
        """
        if not self.audio_processor:
            logger.warning("AEC处理器未初始化，无法切换状态")
            return False
        
        self._aec_enabled = enabled and self.audio_processor._is_initialized
        
        if enabled and not self._aec_enabled:
            logger.warning("无法启用AEC，处理器未正确初始化")
        
        logger.info(f"AEC状态: {'启用' if self._aec_enabled else '禁用'}")
        return self._aec_enabled

    # ============= 资源清理 =============

    async def _cleanup_resampler(self, resampler, name: str):
        """清理重采样器资源"""
        if not resampler:
            return
        
        try:
            # 刷新缓冲区
            if hasattr(resampler, "resample_chunk"):
                empty_array = np.array([], dtype=np.int16)
                resampler.resample_chunk(empty_array, last=True)
        except Exception as e:
            logger.debug(f"刷新{name}重采样器缓冲区失败: {e}")
        
        try:
            # 尝试显式关闭
            if hasattr(resampler, "close"):
                resampler.close()
                logger.debug(f"{name}重采样器已关闭")
        except Exception as e:
            logger.debug(f"关闭{name}重采样器失败: {e}")

    def _stop_stream_sync(self, stream, name: str):
        """同步停止单个音频流"""
        if not stream:
            return
        try:
            if stream.active:
                stream.stop()
            stream.close()
        except Exception as e:
            logger.warning(f"关闭{name}流失败: {e}")

    async def close(self):
        """
        关闭音频编解码器并释放所有资源
        
        清理顺序:
        1. 设置关闭标志，停止音频流
        2. 清空回调和监听器引用
        3. 清空队列和缓冲区
        4. 关闭AEC处理器
        5. 清理重采样器
        6. 释放编解码器
        7. 执行垃圾回收
        """
        if self._is_closing:
            return
        
        self._is_closing = True
        logger.info("开始关闭音频编解码器...")
        
        try:
            # 1. 停止音频流
            self._stop_stream_sync(self.input_stream, "输入")
            self._stop_stream_sync(self.output_stream, "输出")
            self.input_stream = None
            self.output_stream = None
            
            # 等待回调完全停止
            await asyncio.sleep(0.05)
            
            # 2. 清空回调和监听器
            self._encoded_callback = None
            self._audio_listeners.clear()
            
            # 3. 清空队列和缓冲区
            await self.clear_audio_queue()
            
            # 4. 关闭AEC处理器
            if self.audio_processor:
                try:
                    await self.audio_processor.close()
                except Exception as e:
                    logger.warning(f"关闭AEC处理器失败: {e}")
                finally:
                    self.audio_processor = None
            
            # 5. 清理重采样器
            await self._cleanup_resampler(self.input_resampler, "输入")
            await self._cleanup_resampler(self.output_resampler, "输出")
            self.input_resampler = None
            self.output_resampler = None
            
            # 6. 释放编解码器
            self.opus_encoder = None
            self.opus_decoder = None
            
            # 7. 垃圾回收
            gc.collect()
            
            logger.info("音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭音频编解码器过程中发生错误: {e}", exc_info=True)
        finally:
            self._is_closing = True

    def __del__(self):
        """析构函数 - 检查资源是否正确释放"""
        if not self._is_closing:
            logger.warning("AudioCodec未正确关闭，请调用 close() 方法")

