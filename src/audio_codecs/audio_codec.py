import asyncio
import gc
import time
from collections import deque
from typing import Optional

import numpy as np
import opuslib
import sounddevice as sd
import soxr

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioCodec:
    """
    音频编解码器类.
    """

    def __init__(self):
        self.opus_encoder = None
        self.opus_decoder = None

        # 设备默认采样率
        self.device_input_sample_rate = None
        self.device_output_sample_rate = None

        # 重采样器
        self.input_resampler = None
        self.output_resampler = None

        # 使用deque替代list，提升性能
        self._resample_input_buffer = deque()

        # 缓存计算结果
        self._device_input_frame_size = None
        self._device_output_frame_size = None

        # 状态管理
        self._is_closing = False

        # SoundDevice流对象
        self.input_stream = None
        self.output_stream = None

        # 音频缓冲区 - 只保留必要的队列
        self._wakeword_buffer = asyncio.Queue(maxsize=100)  # 唤醒词检测专用
        self._output_buffer = asyncio.Queue(maxsize=500)  # 播放专用
        
        # 实时编码回调机制
        self._encoded_audio_callback = None  # 编码后音频数据回调

    async def initialize(self):
        """
        初始化音频设备和编解码器.
        """
        try:
            # 获取设备默认采样率
            input_device_info = sd.query_devices(sd.default.device[0])
            output_device_info = sd.query_devices(sd.default.device[1])

            self.device_input_sample_rate = int(input_device_info["default_samplerate"])
            self.device_output_sample_rate = int(
                output_device_info["default_samplerate"]
            )

            # 缓存帧大小计算结果
            frame_duration_sec = AudioConfig.FRAME_DURATION / 1000
            self._device_input_frame_size = int(
                self.device_input_sample_rate * frame_duration_sec
            )
            self._device_output_frame_size = int(
                self.device_output_sample_rate * frame_duration_sec
            )

            logger.info(f"设备输入采样率: {self.device_input_sample_rate}Hz")
            logger.info(f"设备输出采样率: {self.device_output_sample_rate}Hz")

            # 创建重采样器
            await self._create_resamplers()

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
                AudioConfig.OUTPUT_SAMPLE_RATE, AudioConfig.CHANNELS  # 24kHz
            )

            logger.info("音频设备和编解码器初始化成功")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _create_resamplers(self):
        """
        创建重采样器.
        """
        if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
            self.input_resampler = soxr.ResampleStream(
                self.device_input_sample_rate,
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                dtype="int16",
                quality="QQ",
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
                dtype="int16",
                quality="QQ",
            )
            logger.info(
                f"✓ 创建输出重采样器: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz (Opus) -> "
                f"{self.device_output_sample_rate}Hz (设备) - 支持非24kHz设备"
            )
        else:
            logger.info(
                f"✓ 设备支持24kHz输出，无需重采样 (设备采样率: {self.device_output_sample_rate}Hz)"
            )

    async def _create_streams(self):
        """
        创建输入和输出流.
        """
        try:
            # 创建输入流（录音）
            self.input_stream = sd.InputStream(
                samplerate=self.device_input_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=self._device_input_frame_size,
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency="low",
            )

            # 创建输出流（播放）
            self.output_stream = sd.OutputStream(
                samplerate=self.device_output_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=self._device_output_frame_size,
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency="low",
            )

            # 启动流
            self.input_stream.start()
            self.output_stream.start()

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """
        输入流回调函数.
        实时处理：重采样 → Opus编码 → 回调传递，同时为唤醒词检测提供数据.
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            audio_data = indata.copy().flatten()

            # 如果需要重采样，先进行重采样
            if self.input_resampler is not None:
                audio_data = self._process_input_resampling(audio_data)
                if audio_data is None:
                    return

            # ✅ 新方案：实时编码录音数据
            if self._encoded_audio_callback and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE:
                try:
                    # 转换为bytes并编码
                    pcm_data = audio_data.astype(np.int16).tobytes()
                    encoded_data = self.opus_encoder.encode(pcm_data, AudioConfig.INPUT_FRAME_SIZE)
                    
                    # 通过回调立即传递编码数据（非阻塞）
                    if encoded_data:
                        self._encoded_audio_callback(encoded_data)
                        
                except Exception as e:
                    logger.warning(f"实时录音编码失败: {e}")

            # 唤醒词检测队列（独立处理）
            self._put_audio_data_safe(self._wakeword_buffer, audio_data.copy())

        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _process_input_resampling(self, audio_data):
        """
        处理输入重采样.
        """
        try:
            resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
            if len(resampled_data) > 0:
                # 添加重采样数据到缓冲区
                self._resample_input_buffer.extend(resampled_data.astype(np.int16))

            # 检查缓冲区是否有足够的数据组成完整帧
            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._resample_input_buffer) < expected_frame_size:
                return None  # 数据不足，等待更多数据

            # 取出一帧数据
            frame_data = []
            for _ in range(expected_frame_size):
                frame_data.append(self._resample_input_buffer.popleft())

            return np.array(frame_data, dtype=np.int16)

        except Exception as e:
            logger.error(f"输入重采样失败: {e}")
            return None

    def _put_audio_data_safe(self, queue, audio_data):
        """
        安全地将音频数据放入队列.
        """
        try:
            queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            # 移除最旧的数据
            try:
                queue.get_nowait()
                queue.put_nowait(audio_data)
            except asyncio.QueueEmpty:
                queue.put_nowait(audio_data)

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        输出流回调函数.
        从缓冲区取出24kHz音频数据，根据需要重采样到设备采样率后播放.
        """
        if status:
            if "underflow" not in str(status).lower():
                logger.warning(f"输出流状态: {status}")

        try:
            try:
                # 从输出缓冲区获取24kHz音频数据
                audio_data = self._output_buffer.get_nowait()

                # 如果设备采样率与24kHz不同，需要重采样
                if self.output_resampler is not None and len(audio_data) > 0:
                    audio_data = self._process_output_resampling(audio_data)
                    if audio_data is None:
                        outdata.fill(0)
                        return

                # 将音频数据写入输出缓冲区
                if len(audio_data) >= frames:
                    outdata[:] = audio_data[:frames].reshape(-1, AudioConfig.CHANNELS)
                else:
                    outdata[: len(audio_data)] = audio_data.reshape(-1, AudioConfig.CHANNELS)
                    outdata[len(audio_data) :] = 0

            except asyncio.QueueEmpty:
                # 没有音频数据时输出静音
                outdata.fill(0)

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0)

    def _process_output_resampling(self, audio_data):
        """
        处理输出重采样：从24kHz重采样到设备采样率.
        """
        try:
            # 确保输入数据格式正确
            if not isinstance(audio_data, np.ndarray):
                audio_data = np.array(audio_data, dtype=np.int16)
            
            # 进行重采样：24kHz -> 设备采样率
            resampled_data = self.output_resampler.resample_chunk(
                audio_data, last=False
            )
            
            if len(resampled_data) > 0:
                return resampled_data.astype(np.int16)
            else:
                # 重采样器可能还在累积数据，返回None等待更多数据
                return None
                
        except Exception as e:
            logger.error(f"输出重采样失败 ({AudioConfig.OUTPUT_SAMPLE_RATE}Hz -> {self.device_output_sample_rate}Hz): {e}")
            return None

    def _input_finished_callback(self):
        """
        输入流结束回调.
        """
        logger.info("输入流已结束")

    def _output_finished_callback(self):
        """
        输出流结束回调.
        """
        logger.info("输出流已结束")

    async def reinitialize_stream(self, is_input=True):
        """
        重新初始化流.
        """
        if self._is_closing:
            return False if is_input else None

        try:
            if is_input:
                # 重建输入流
                if self.input_stream:
                    self.input_stream.stop()
                    self.input_stream.close()

                self.input_stream = sd.InputStream(
                    samplerate=self.device_input_sample_rate,
                    channels=AudioConfig.CHANNELS,
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
                # 重建输出流
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()

                self.output_stream = sd.OutputStream(
                    samplerate=self.device_output_sample_rate,
                    channels=AudioConfig.CHANNELS,
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

    async def get_raw_audio_for_detection(self) -> Optional[bytes]:
        """为唤醒词检测获取原始音频数据.
        
        从专用的唤醒词检测队列获取数据，与录音编码完全独立，
        避免数据竞争，确保唤醒词检测的准确性。

        Returns:
            Optional[bytes]: PCM格式的音频数据，如果没有数据则返回None.
        """
        try:
            if self._wakeword_buffer.empty():
                return None

            audio_data = self._wakeword_buffer.get_nowait()

            # 转换为bytes格式
            if hasattr(audio_data, "tobytes"):
                return audio_data.tobytes()
            elif hasattr(audio_data, "astype"):
                return audio_data.astype("int16").tobytes()
            else:
                return audio_data

        except asyncio.QueueEmpty:
            return None
        except Exception as e:
            logger.error(f"获取唤醒词音频数据失败: {e}")
            return None

    def set_encoded_audio_callback(self, callback):
        """
        设置编码后音频数据的回调函数.
        
        启用实时编码模式：录音回调中直接编码并通过回调传递，
        消除轮询延迟，提升录音实时性。
        
        Args:
            callback: 回调函数，接收 (encoded_data: bytes) 参数
                     如果为None，则禁用实时编码
        """
        self._encoded_audio_callback = callback
        
        if callback:
            logger.info("✓ 启用实时录音编码模式 - 录音回调直接编码传递")
        else:
            logger.info("✓ 禁用录音编码回调")

    async def write_audio(self, opus_data: bytes):
        """
        将Opus数据直接解码并放入播放队列.
        解码输出为24kHz，将在播放回调中根据设备采样率进行重采样.
        """
        try:
            # Opus解码输出24kHz PCM数据
            pcm_data = self.opus_decoder.decode(
                opus_data, AudioConfig.OUTPUT_FRAME_SIZE
            )

            audio_array = np.frombuffer(pcm_data, dtype=np.int16)

            # 验证解码数据长度
            expected_length = AudioConfig.OUTPUT_FRAME_SIZE * AudioConfig.CHANNELS
            if len(audio_array) != expected_length:
                logger.warning(f"解码音频长度异常: {len(audio_array)}, 期望: {expected_length}")
                return

            # 直接放入输出缓冲区，重采样将在输出回调中处理
            self._put_audio_data_safe(self._output_buffer, audio_array)

        except opuslib.OpusError as e:
            logger.warning(f"Opus解码失败，丢弃此帧: {e}")
        except Exception as e:
            logger.warning(f"音频写入失败，丢弃此帧: {e}")

    async def wait_for_audio_complete(self, timeout=10.0):
        """
        等待音频播放完成.
        """
        start = time.time()
        
        # 1. 首先等待解码队列清空
        while not self._output_buffer.empty() and time.time() - start < timeout:
            await asyncio.sleep(0.05)
        
        # 2. 额外等待一小段时间，确保最后的音频数据被播放
        await asyncio.sleep(0.3)  # 300ms额外缓冲时间
        
        # 检查是否超时
        if not self._output_buffer.empty():
            output_remaining = self._output_buffer.qsize()
            logger.warning(
                f"音频播放超时，剩余队列 - 输出: {output_remaining} 帧"
            )

    async def clear_audio_queue(self):
        """
        清空音频队列.
        """
        cleared_count = 0

        # 清空所有队列
        queues_to_clear = [
            self._wakeword_buffer,
            self._output_buffer,
        ]

        for queue in queues_to_clear:
            while not queue.empty():
                try:
                    queue.get_nowait()
                    cleared_count += 1
                except asyncio.QueueEmpty:
                    break

        # 清空重采样缓冲区
        if self._resample_input_buffer:
            cleared_count += len(self._resample_input_buffer)
            self._resample_input_buffer.clear()

        # 额外等待一小段时间，确保正在处理的音频数据完成
        await asyncio.sleep(0.01)

        if cleared_count > 0:
            logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")

        # 定期执行垃圾回收以释放内存
        if cleared_count > 100:  # 清理了大量数据时
            gc.collect()
            logger.debug("执行垃圾回收以释放内存")

    async def start_streams(self):
        """
        启动音频流.
        """
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
        """
        停止音频流.
        """
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

    async def _cleanup_resampler(self, resampler, name):
        """
        清理重采样器的辅助方法.
        """
        if resampler:
            try:
                # 让重采样器处理完剩余数据
                if hasattr(resampler, "resample_chunk"):
                    empty_array = np.array([], dtype=np.int16)
                    resampler.resample_chunk(empty_array, last=True)
            except Exception as e:
                logger.warning(f"清理{name}重采样器失败: {e}")

    async def close(self):
        """
        关闭音频编解码器.
        """
        if self._is_closing:
            return

        self._is_closing = True
        logger.info("开始关闭音频编解码器...")

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
            await self._cleanup_resampler(self.input_resampler, "输入")
            await self._cleanup_resampler(self.output_resampler, "输出")

            self.input_resampler = None
            self.output_resampler = None

            # 清理重采样缓冲区
            self._resample_input_buffer.clear()

            # 清理编解码器
            self.opus_encoder = None
            self.opus_decoder = None

            gc.collect()  # 强制释放 nanobind 的 C++ 对象

            logger.info("音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭音频编解码器过程中发生错误: {e}")

    def __del__(self):
        """
        析构函数.
        """
        if not self._is_closing:
            # 在析构函数中不能使用asyncio.create_task，改为记录警告
            logger.warning("AudioCodec对象被销毁但未正确关闭，请确保调用close()方法")
