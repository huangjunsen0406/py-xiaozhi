import asyncio
import time
from typing import Optional

import numpy as np
import opuslib
import sounddevice as sd
import soxr

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioCodec:
    """异步音频编解码器类"""

    def __init__(self):
        self.opus_encoder = None
        self.opus_decoder = None
        
        # 设备默认采样率
        self.device_input_sample_rate = None
        self.device_output_sample_rate = None
        
        # 重采样器
        self.input_resampler = None
        self.output_resampler = None
        
        # 重采样缓冲区 - 用于处理不定长的重采样输出
        self._resample_input_buffer = []
        
        # 异步队列
        max_queue_size = int(10 * 1000 / AudioConfig.FRAME_DURATION)
        self.audio_decode_queue = asyncio.Queue(maxsize=max_queue_size)
        
        # 状态管理
        self._is_closing = False
        self._is_input_paused = False
        
        # SoundDevice流对象
        self.input_stream = None
        self.output_stream = None
        
        # 音频缓冲区
        self._input_buffer = asyncio.Queue(maxsize=300)
        self._output_buffer = asyncio.Queue(maxsize=200)
        
        # 专门为唤醒词检测器提供的缓冲区（不受暂停影响）
        self._wake_word_buffer = asyncio.Queue(maxsize=100)

    async def initialize(self):
        """初始化音频设备和编解码器"""
        try:
            # 获取设备默认采样率
            input_device_info = sd.query_devices(sd.default.device[0])
            output_device_info = sd.query_devices(sd.default.device[1])
            
            self.device_input_sample_rate = int(
                input_device_info['default_samplerate']
            )
            self.device_output_sample_rate = int(
                output_device_info['default_samplerate']
            )
            
            logger.info(f"设备输入采样率: {self.device_input_sample_rate}Hz")
            logger.info(f"设备输出采样率: {self.device_output_sample_rate}Hz")
            
            # 创建重采样器
            if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
                self.input_resampler = soxr.ResampleStream(
                    self.device_input_sample_rate,
                    AudioConfig.INPUT_SAMPLE_RATE,
                    AudioConfig.CHANNELS,
                    dtype='int16',
                    quality='QQ'
                )
                logger.info(
                    f"创建输入重采样器: {self.device_input_sample_rate}Hz -> "
                    f"{AudioConfig.INPUT_SAMPLE_RATE}Hz"
                )
            
            # 输出重采样器：从Opus解码的24kHz重采样到设备采样率
            if self.device_output_sample_rate != AudioConfig.OUTPUT_SAMPLE_RATE:
                self.output_resampler = soxr.ResampleStream(
                    AudioConfig.OUTPUT_SAMPLE_RATE,  # Opus输出24kHz
                    self.device_output_sample_rate,
                    AudioConfig.CHANNELS,
                    dtype='int16',
                    quality='QQ'
                )
                logger.info(
                    f"创建输出重采样器: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz -> "
                    f"{self.device_output_sample_rate}Hz"
                )

            # 设置SoundDevice使用设备默认采样率
            sd.default.samplerate = None  # 让设备使用默认采样率
            sd.default.channels = AudioConfig.CHANNELS
            sd.default.dtype = np.int16

            # 初始化流
            await self._create_streams()

            # 编解码器初始化 - 客户端-服务器架构
            # 编码器：16kHz发送给服务器
            # 解码器：24kHz从服务器接收
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,  # 16kHz
                AudioConfig.CHANNELS,
                opuslib.APPLICATION_AUDIO,
            )
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE,  # 24kHz
                AudioConfig.CHANNELS
            )

            logger.info("异步音频设备和编解码器初始化成功")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _create_streams(self):
        """创建输入和输出流"""
        try:
            # 计算设备采样率下的帧大小
            device_input_frame_size = int(self.device_input_sample_rate * (AudioConfig.FRAME_DURATION / 1000))
            device_output_frame_size = int(self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000))

            # 创建输入流（录音）
            self.input_stream = sd.InputStream(
                samplerate=self.device_input_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=device_input_frame_size,
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency='low'
            )

            # 创建输出流（播放）
            self.output_stream = sd.OutputStream(
                samplerate=self.device_output_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=device_output_frame_size,
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency='low'
            )

            # 启动流
            self.input_stream.start()
            self.output_stream.start()

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """输入流回调函数"""
        if status and 'overflow' not in str(status).lower():
            logger.warning(f"输入流状态: {status}")
        
        if self._is_closing:
            return
        
        try:
            audio_data = indata.copy().flatten()
            
            # 如果需要重采样，先进行重采样
            if self.input_resampler is not None:
                try:
                    resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
                    if len(resampled_data) > 0:
                        # 添加重采样数据到缓冲区
                        self._resample_input_buffer.extend(resampled_data.astype(np.int16))
                    
                    # 检查缓冲区是否有足够的数据组成完整帧
                    expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
                    if len(self._resample_input_buffer) < expected_frame_size:
                        return  # 数据不足，等待更多数据
                    
                    # 取出一帧数据
                    audio_data = np.array(self._resample_input_buffer[:expected_frame_size])
                    self._resample_input_buffer = self._resample_input_buffer[expected_frame_size:]
                    
                except Exception as e:
                    logger.error(f"输入重采样失败: {e}")
                    return
            
            # 始终填充唤醒词缓冲区（不受暂停状态影响）
            try:
                self._wake_word_buffer.put_nowait(audio_data)
            except asyncio.QueueFull:
                # 移除最旧的数据
                try:
                    self._wake_word_buffer.get_nowait()
                    self._wake_word_buffer.put_nowait(audio_data)
                except asyncio.QueueEmpty:
                    self._wake_word_buffer.put_nowait(audio_data)
            
            # 只有在未暂停时才填充正常的输入缓冲区
            if not self._is_input_paused:
                try:
                    self._input_buffer.put_nowait(audio_data)
                except asyncio.QueueFull:
                    # 移除最旧的数据
                    try:
                        self._input_buffer.get_nowait()
                        self._input_buffer.put_nowait(audio_data)
                    except asyncio.QueueEmpty:
                        self._input_buffer.put_nowait(audio_data)
                    
        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """输出流回调函数"""
        if status:
            if 'underflow' not in str(status).lower():
                logger.warning(f"输出流状态: {status}")
        
        try:
            try:
                audio_data = self._output_buffer.get_nowait()
                
                # 如果需要重采样到设备采样率
                if self.output_resampler is not None and len(audio_data) > 0:
                    try:
                        resampled_data = self.output_resampler.resample_chunk(audio_data, last=False)
                        if len(resampled_data) > 0:
                            audio_data = resampled_data.astype(np.int16)
                        else:
                            outdata.fill(0)
                            return
                    except Exception as e:
                        logger.error(f"输出重采样失败: {e}")
                        outdata.fill(0)
                        return
                
                if len(audio_data) >= frames:
                    outdata[:] = audio_data[:frames].reshape(-1, 1)
                else:
                    outdata[:len(audio_data)] = audio_data.reshape(-1, 1)
                    outdata[len(audio_data):] = 0
                    
            except asyncio.QueueEmpty:
                outdata.fill(0)
                
        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0)

    def _input_finished_callback(self):
        """输入流结束回调"""
        logger.info("输入流已结束")

    def _output_finished_callback(self):
        """输出流结束回调"""
        logger.info("输出流已结束")

    async def reinitialize_stream(self, is_input=True):
        """重新初始化流"""
        if self._is_closing:
            return False if is_input else None

        try:
            if is_input:
                # 重建输入流
                if self.input_stream:
                    self.input_stream.stop()
                    self.input_stream.close()
                
                device_input_frame_size = int(self.device_input_sample_rate * (AudioConfig.FRAME_DURATION / 1000))
                self.input_stream = sd.InputStream(
                    samplerate=self.device_input_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=device_input_frame_size,
                    callback=self._input_callback,
                    finished_callback=self._input_finished_callback,
                    latency='low'
                )
                self.input_stream.start()
                logger.info("输入流重新初始化成功")
                return True
            else:
                # 重建输出流
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()
                
                device_output_frame_size = int(self.device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000))
                self.output_stream = sd.OutputStream(
                    samplerate=self.device_output_sample_rate,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=device_output_frame_size,
                    callback=self._output_callback,
                    finished_callback=self._output_finished_callback,
                    latency='low'
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

    async def pause_input(self):
        """暂停音频输入"""
        self._is_input_paused = True
        # 暂停输入的同时清空输入缓冲区
        while not self._input_buffer.empty():
            try:
                self._input_buffer.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.info("音频输入已暂停并清空缓冲区")

    async def resume_input(self):
        """恢复音频输入"""
        self._is_input_paused = False
        logger.info("音频输入已恢复")

    def is_input_paused(self):
        """检查输入是否已暂停"""
        return self._is_input_paused

    async def read_audio(self) -> Optional[bytes]:
        """读取音频数据并编码"""
        if self.is_input_paused():
            return None

        try:
            # 直接处理单帧数据，避免浪费
            try:
                audio_data = self._input_buffer.get_nowait()
                
                # 严格验证数据长度
                if len(audio_data) != AudioConfig.INPUT_FRAME_SIZE:
                    expected = AudioConfig.INPUT_FRAME_SIZE
                    actual = len(audio_data)
                    logger.warning(f"音频数据长度异常: {actual}, 期望: {expected}")
                    return None

                # 转换为bytes并编码
                pcm_data = audio_data.astype(np.int16).tobytes()
                return self.opus_encoder.encode(pcm_data, AudioConfig.INPUT_FRAME_SIZE)
                
            except asyncio.QueueEmpty:
                return None
                
        except Exception as e:
            logger.error(f"音频读取失败: {e}")
        
        return None

    async def play_audio(self):
        """播放音频（处理解码队列中的数据）"""
        try:
            if self.audio_decode_queue.empty():
                return

            processed_count = 0
            max_process_per_call = 3

            while (
                not self.audio_decode_queue.empty()
                and processed_count < max_process_per_call
            ):
                try:
                    opus_data = self.audio_decode_queue.get_nowait()

                    try:
                        # Opus解码输出24kHz
                        pcm_data = self.opus_decoder.decode(
                            opus_data, AudioConfig.OUTPUT_FRAME_SIZE
                        )
                        
                        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                        
                        try:
                            self._output_buffer.put_nowait(audio_array)
                        except asyncio.QueueFull:
                            try:
                                self._output_buffer.get_nowait()
                                self._output_buffer.put_nowait(audio_array)
                            except asyncio.QueueEmpty:
                                self._output_buffer.put_nowait(audio_array)
                            
                    except opuslib.OpusError as e:
                        logger.warning(f"音频解码失败，丢弃此帧: {e}")
                    except Exception as e:
                        logger.warning(f"音频处理失败，丢弃此帧: {e}")

                    processed_count += 1

                except asyncio.QueueEmpty:
                    break

        except Exception as e:
            logger.error(f"播放音频时发生未预期错误: {e}")

    async def write_audio(self, opus_data: bytes):
        """将Opus数据写入播放队列"""
        try:
            self.audio_decode_queue.put_nowait(opus_data)
        except asyncio.QueueFull:
            try:
                self.audio_decode_queue.get_nowait()
                self.audio_decode_queue.put_nowait(opus_data)
            except asyncio.QueueEmpty:
                self.audio_decode_queue.put_nowait(opus_data)

    async def wait_for_audio_complete(self, timeout=5.0):
        """等待音频播放完成"""
        start = time.time()
        while not self.audio_decode_queue.empty() and time.time() - start < timeout:
            await asyncio.sleep(0.1)

        if not self.audio_decode_queue.empty():
            remaining = self.audio_decode_queue.qsize()
            logger.warning(f"音频播放超时，剩余队列: {remaining} 帧")

    async def clear_audio_queue(self):
        """清空音频队列"""
        cleared_count = 0
        
        # 清空解码队列
        while not self.audio_decode_queue.empty():
            try:
                self.audio_decode_queue.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        # 清空输入缓冲区
        while not self._input_buffer.empty():
            try:
                self._input_buffer.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        # 清空输出缓冲区
        while not self._output_buffer.empty():
            try:
                self._output_buffer.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        # 清空唤醒词缓冲区
        while not self._wake_word_buffer.empty():
            try:
                self._wake_word_buffer.get_nowait()
                cleared_count += 1
            except asyncio.QueueEmpty:
                break
        
        # 额外等待一小段时间，确保正在处理的音频数据完成
        await asyncio.sleep(0.01)
        
        # 再次清空可能新产生的数据
        extra_cleared = 0
        while not self._input_buffer.empty():
            try:
                self._input_buffer.get_nowait()
                extra_cleared += 1
            except asyncio.QueueEmpty:
                break
        
        # 再次清空唤醒词缓冲区
        while not self._wake_word_buffer.empty():
            try:
                self._wake_word_buffer.get_nowait()
                extra_cleared += 1
            except asyncio.QueueEmpty:
                break
        
        cleared_count += extra_cleared
                
        if cleared_count > 0:
            logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")

    async def start_streams(self):
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

    async def stop_streams(self):
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

    async def close(self):
        """关闭音频编解码器"""
        if self._is_closing:
            return

        self._is_closing = True
        logger.info("开始关闭异步音频编解码器...")

        try:
            # 清空队列
            await self.clear_audio_queue()

            # 关闭流
            if self.input_stream:
                try:
                    self.input_stream.stop()
                    self.input_stream.close()
                except Exception as e:
                    logger.warning(f"关闭输入流失败: {e}")
                finally:
                    self.input_stream = None

            if self.output_stream:
                try:
                    self.output_stream.stop()
                    self.output_stream.close()
                except Exception as e:
                    logger.warning(f"关闭输出流失败: {e}")
                finally:
                    self.output_stream = None

            # 清理重采样器
            if self.input_resampler:
                try:
                    # 让重采样器处理完剩余数据
                    if hasattr(self.input_resampler, 'resample_chunk'):
                        empty_array = np.array([], dtype=np.int16)
                        self.input_resampler.resample_chunk(empty_array, last=True)
                except Exception as e:
                    logger.warning(f"清理输入重采样器失败: {e}")
                finally:
                    self.input_resampler = None

            if self.output_resampler:
                try:
                    # 让重采样器处理完剩余数据
                    if hasattr(self.output_resampler, 'resample_chunk'):
                        empty_array = np.array([], dtype=np.int16)
                        self.output_resampler.resample_chunk(empty_array, last=True)
                except Exception as e:
                    logger.warning(f"清理输出重采样器失败: {e}")
                finally:
                    self.output_resampler = None

            # 清理重采样缓冲区
            self._resample_input_buffer.clear()

            # 清理编解码器
            self.opus_encoder = None
            self.opus_decoder = None

            logger.info("异步音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭异步音频编解码器过程中发生错误: {e}")

    def __del__(self):
        """析构函数"""
        if not self._is_closing:
            asyncio.create_task(self.close()) 