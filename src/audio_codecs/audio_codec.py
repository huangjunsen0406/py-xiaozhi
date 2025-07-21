import asyncio
import gc
import time
from collections import deque
from typing import Optional

import numpy as np
import opuslib
import sounddevice as sd
import soxr

from src.audio_processing.aec_processor import AECProcessor
from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioCodec:
    """
    音频编解码器，负责录音编码和播放解码
    主要功能：
    1. 录音：麦克风 -> 重采样16kHz -> AEC处理 -> Opus编码 -> 发送
    2. 播放：接收 -> Opus解码24kHz -> 播放队列 -> 扬声器
    3. AEC：播放信号重采样16kHz作为参考信号，消除回声
    """

    def __init__(self):
        # 获取配置管理器
        self.config = ConfigManager.get_instance()

        # Opus编解码器：录音16kHz编码，播放24kHz解码
        self.opus_encoder = None
        self.opus_decoder = None

        # 设备采样率信息
        self.device_input_sample_rate = None
        self.device_output_sample_rate = None

        # 重采样器：统一采样率
        self.input_resampler = None  # 设备采样率 -> 16kHz
        self.aec_reference_resampler = None  # 24kHz -> 16kHz(AEC用)

        # 重采样缓冲区
        self._resample_input_buffer = deque()
        self._aec_reference_buffer = deque()

        self._device_input_frame_size = None
        self._is_closing = False

        # 音频流对象
        self.input_stream = None  # 录音流
        self.output_stream = None  # 播放流

        # 队列：唤醒词检测和播放缓冲
        self._wakeword_buffer = asyncio.Queue(maxsize=100)
        self._output_buffer = asyncio.Queue(maxsize=500)

        # 实时编码回调（直接发送，不走队列）
        self._encoded_audio_callback = None

        # AEC回声消除处理器 - 从配置读取启用状态
        self.aec_processor = AECProcessor()

    async def initialize(self):
        """
        初始化音频设备.
        """
        try:
            input_device_info = sd.query_devices(sd.default.device[0])
            output_device_info = sd.query_devices(sd.default.device[1])
            self.device_input_sample_rate = int(input_device_info["default_samplerate"])
            self.device_output_sample_rate = int(
                output_device_info["default_samplerate"]
            )
            frame_duration_sec = AudioConfig.FRAME_DURATION / 1000
            self._device_input_frame_size = int(
                self.device_input_sample_rate * frame_duration_sec
            )

            logger.info(
                f"输入采样率: {self.device_input_sample_rate}Hz, 输出: {self.device_output_sample_rate}Hz"
            )
            await self._create_resamplers()
            sd.default.samplerate = None
            sd.default.channels = AudioConfig.CHANNELS
            sd.default.dtype = np.int16
            await self._create_streams()
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                opuslib.APPLICATION_AUDIO,
            )
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE, AudioConfig.CHANNELS
            )
            await self.aec_processor.initialize()
            if self.aec_processor.is_available():
                logger.info("AEC初始化成功")
            else:
                logger.warning("AEC初始化失败")
            logger.info("音频初始化完成")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    async def _create_resamplers(self):
        """
        创建重采样器 输入：设备采样率 -> 16kHz（录音用） AEC参考：24kHz -> 16kHz（参考信号与录音采样率一致）
        """
        if self.device_input_sample_rate != AudioConfig.INPUT_SAMPLE_RATE:
            self.input_resampler = soxr.ResampleStream(
                self.device_input_sample_rate,
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                dtype="int16",
                quality="QQ",
            )
            logger.info(f"输入重采样: {self.device_input_sample_rate}Hz -> 16kHz")

        self.aec_reference_resampler = soxr.ResampleStream(
            AudioConfig.OUTPUT_SAMPLE_RATE,
            16000,  # 固定使用16kHz
            AudioConfig.CHANNELS,
            dtype="int16",
            quality="QQ",
        )
        logger.info(f"AEC参考重采样: {AudioConfig.OUTPUT_SAMPLE_RATE}Hz -> 16kHz")

    async def _create_streams(self):
        """
        创建音频流.
        """
        try:
            self.input_stream = sd.InputStream(
                samplerate=self.device_input_sample_rate,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=self._device_input_frame_size,
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency="low",
            )

            self.output_stream = sd.OutputStream(
                samplerate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=AudioConfig.OUTPUT_FRAME_SIZE,
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency="low",
            )

            self.input_stream.start()
            self.output_stream.start()

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """
        录音回调，硬件驱动调用 处理流程：原始音频 -> 重采样 -> AEC -> 编码发送 + 唤醒词检测.
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            audio_data = indata.copy().flatten()

            # 重采样到16kHz（如果设备不是16kHz）
            if self.input_resampler is not None:
                audio_data = self._process_input_resampling(audio_data)
                if audio_data is None:
                    return

            # AEC回声消除处理
            if len(audio_data) == AudioConfig.INPUT_FRAME_SIZE:
                try:
                    audio_data = self.aec_processor.process_audio(audio_data)
                except Exception as e:
                    logger.warning(f"AEC处理失败: {e}")

            # 实时编码并发送（不走队列，减少延迟）
            if (
                self._encoded_audio_callback
                and len(audio_data) == AudioConfig.INPUT_FRAME_SIZE
            ):
                try:
                    pcm_data = audio_data.astype(np.int16).tobytes()
                    encoded_data = self.opus_encoder.encode(
                        pcm_data, AudioConfig.INPUT_FRAME_SIZE
                    )

                    if encoded_data:
                        self._encoded_audio_callback(encoded_data)

                except Exception as e:
                    logger.warning(f"实时录音编码失败: {e}")

            # 同时提供给唤醒词检测（走队列）
            self._put_audio_data_safe(self._wakeword_buffer, audio_data.copy())

        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _process_input_resampling(self, audio_data):
        """
        输入重采样.
        """
        try:
            resampled_data = self.input_resampler.resample_chunk(audio_data, last=False)
            if len(resampled_data) > 0:
                self._resample_input_buffer.extend(resampled_data.astype(np.int16))

            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._resample_input_buffer) < expected_frame_size:
                return None

            frame_data = []
            for _ in range(expected_frame_size):
                frame_data.append(self._resample_input_buffer.popleft())

            return np.array(frame_data, dtype=np.int16)

        except Exception as e:
            logger.error(f"输入重采样失败: {e}")
            return None

    def _process_aec_reference_immediate(self, audio_data):
        """
        立即处理AEC参考信号 将24kHz播放数据重采样为16kHz，立即提供给AEC作为参考 这样可以减少延迟，提高回声消除效果.
        """
        try:
            # 24kHz -> 16kHz重采样
            resampled_data = self.aec_reference_resampler.resample_chunk(
                audio_data, last=False
            )
            if len(resampled_data) > 0:
                self._aec_reference_buffer.extend(resampled_data.astype(np.int16))

            # 组帧并提供给AEC处理器
            expected_frame_size = AudioConfig.INPUT_FRAME_SIZE
            if len(self._aec_reference_buffer) >= expected_frame_size:
                reference_frame = []
                for _ in range(expected_frame_size):
                    reference_frame.append(self._aec_reference_buffer.popleft())

                reference_array = np.array(reference_frame, dtype=np.int16)

                try:
                    self.aec_processor.add_reference_audio(reference_array)
                except Exception as e:
                    logger.debug(f"添加AEC参考信号失败: {e}")

        except Exception as e:
            logger.warning(f"AEC参考信号处理失败: {e}")

    def _put_audio_data_safe(self, queue, audio_data):
        """
        安全入队，队列满时丢弃最旧数据.
        """
        try:
            queue.put_nowait(audio_data)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(audio_data)
            except asyncio.QueueEmpty:
                queue.put_nowait(audio_data)

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """
        播放回调，硬件驱动调用 从播放队列取数据输出到扬声器.
        """
        if status:
            if "underflow" not in str(status).lower():
                logger.warning(f"输出流状态: {status}")

        try:
            try:
                # 从播放队列获取音频数据
                audio_data = self._output_buffer.get_nowait()

                if len(audio_data) >= frames:
                    output_frames = audio_data[:frames]
                    outdata[:] = output_frames.reshape(-1, AudioConfig.CHANNELS)
                else:
                    output_frames = audio_data
                    outdata[: len(audio_data)] = audio_data.reshape(
                        -1, AudioConfig.CHANNELS
                    )
                    outdata[len(audio_data) :] = 0

            except asyncio.QueueEmpty:
                # 无数据时输出静音
                outdata.fill(0)

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0)

    def _input_finished_callback(self):
        """
        输入流结束.
        """
        logger.info("输入流已结束")

    def _output_finished_callback(self):
        """
        输出流结束.
        """
        logger.info("输出流已结束")

    async def reinitialize_stream(self, is_input=True):
        """
        重建音频流.
        """
        if self._is_closing:
            return False if is_input else None

        try:
            if is_input:
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
                if self.output_stream:
                    self.output_stream.stop()
                    self.output_stream.close()

                self.output_stream = sd.OutputStream(
                    samplerate=AudioConfig.OUTPUT_SAMPLE_RATE,
                    channels=AudioConfig.CHANNELS,
                    dtype=np.int16,
                    blocksize=AudioConfig.OUTPUT_FRAME_SIZE,
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
        """
        获取唤醒词音频数据.
        """
        try:
            if self._wakeword_buffer.empty():
                return None

            audio_data = self._wakeword_buffer.get_nowait()

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
        设置编码回调.
        """
        self._encoded_audio_callback = callback

        if callback:
            logger.info("启用实时编码")
        else:
            logger.info("禁用编码回调")

    async def write_audio(self, opus_data: bytes):
        """
        解码音频并播放 网络接收的Opus数据 -> 解码24kHz -> AEC参考信号 + 播放队列.
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

            # 立即处理AEC参考信号（减少延迟）
            self._process_aec_reference_immediate(audio_array.copy())

            # 放入播放队列
            self._put_audio_data_safe(self._output_buffer, audio_array)

        except opuslib.OpusError as e:
            logger.warning(f"Opus解码失败，丢弃此帧: {e}")
        except Exception as e:
            logger.warning(f"音频写入失败，丢弃此帧: {e}")

    async def wait_for_audio_complete(self, timeout=10.0):
        """
        等待播放完成.
        """
        start = time.time()

        while not self._output_buffer.empty() and time.time() - start < timeout:
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.3)

        if not self._output_buffer.empty():
            output_remaining = self._output_buffer.qsize()
            logger.warning(f"音频播放超时，剩余队列 - 输出: {output_remaining} 帧")

    async def clear_audio_queue(self):
        """
        清空音频队列.
        """
        cleared_count = 0

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

        if self._resample_input_buffer:
            cleared_count += len(self._resample_input_buffer)
            self._resample_input_buffer.clear()

        if self._aec_reference_buffer:
            cleared_count += len(self._aec_reference_buffer)
            self._aec_reference_buffer.clear()

        try:
            self.aec_processor.clear_reference_buffer()
        except Exception as e:
            logger.debug(f"重置AEC处理器失败: {e}")

        await asyncio.sleep(0.01)

        if cleared_count > 0:
            logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")

        if cleared_count > 100:
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
        清理重采样器.
        """
        if resampler:
            try:
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
            await self.clear_audio_queue()

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

            await self._cleanup_resampler(self.input_resampler, "输入")
            await self._cleanup_resampler(self.aec_reference_resampler, "AEC参考")
            self.input_resampler = None
            self.aec_reference_resampler = None

            self._resample_input_buffer.clear()
            self._aec_reference_buffer.clear()

            self.opus_encoder = None
            self.opus_decoder = None

            try:
                await self.aec_processor.close()
            except Exception as e:
                logger.warning(f"关闭AEC处理器失败: {e}")

            gc.collect()

            logger.info("音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭音频编解码器过程中发生错误: {e}")

    def __del__(self):
        """
        析构函数.
        """
        if not self._is_closing:
            logger.warning("AudioCodec未正确关闭，请调用close()")
