import logging
import queue
import numpy as np
import pyaudio
import opuslib
from src.constants.constants import AudioConfig
import time
import sys
import threading

logger = logging.getLogger("AudioCodec")


class AudioCodec:
    """音频编解码器类，处理音频的录制和播放"""

    def __init__(self):
        """初始化音频编解码器"""
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        self.opus_encoder = None
        self.opus_decoder = None
        self.audio_decode_queue = queue.Queue()
        self._is_closing = False  # 添加关闭状态标志
        self._is_input_paused = False  # 添加输入流暂停状态标志
        self._input_paused_lock = threading.Lock()  # 添加线程锁
        self._stream_lock = threading.Lock()  # 添加流操作锁

        self._initialize_audio()

    def _initialize_audio(self):
        """初始化音频设备和编解码器"""
        try:
            self.audio = pyaudio.PyAudio()

            # 自动选择默认输入/输出设备
            input_device_index = self._get_default_or_first_available_device(
                is_input=True
            )
            output_device_index = self._get_default_or_first_available_device(
                is_input=False
            )

            # 初始化音频输入流 - 使用16kHz采样率
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AudioConfig.CHANNELS,
                rate=AudioConfig.INPUT_SAMPLE_RATE,  # 使用16kHz
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=AudioConfig.INPUT_FRAME_SIZE
            )

            # 初始化音频输出流 - 使用24kHz采样率
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AudioConfig.CHANNELS,
                rate=AudioConfig.OUTPUT_SAMPLE_RATE,  # 使用24kHz
                output=True,
                output_device_index=output_device_index,
                frames_per_buffer=AudioConfig.OUTPUT_FRAME_SIZE
            )

            # 初始化Opus编码器 - 使用16kHz（与输入匹配）
            self.opus_encoder = opuslib.Encoder(
                fs=AudioConfig.INPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
                application=AudioConfig.OPUS_APPLICATION
            )

            # 初始化Opus解码器 - 使用24kHz（与输出匹配）
            self.opus_decoder = opuslib.Decoder(
                fs=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS
            )

            logger.info("音频设备和编解码器初始化成功")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            raise

    def _get_default_or_first_available_device(self, is_input=True):
        """获取默认设备或第一个可用的输入/输出设备"""
        try:
            if is_input:
                default_device = self.audio.get_default_input_device_info()
            else:
                default_device = self.audio.get_default_output_device_info()
            device_info = (
                f"使用默认设备: {default_device['name']} "
                f"(Index: {default_device['index']})"
            )
            logger.info(device_info)
            return int(default_device["index"])
        except Exception:
            logger.warning("未找到默认设备，正在查找第一个可用的设备...")

        # 遍历所有设备，寻找第一个可用的输入/输出设备
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if is_input and device_info["maxInputChannels"] > 0:
                logger.info(f"找到可用的麦克风: {device_info['name']} (Index: {i})")
                return i
            if not is_input and device_info["maxOutputChannels"] > 0:
                logger.info(f"找到可用的扬声器: {device_info['name']} (Index: {i})")
                return i

        logger.error("未找到可用的音频设备")
        raise RuntimeError("没有可用的音频设备")

    def pause_input(self):
        """暂停输入流但不关闭它"""
        with self._input_paused_lock:
            self._is_input_paused = True
        logger.info("音频输入已暂停")

    def resume_input(self):
        """恢复输入流"""
        with self._input_paused_lock:
            self._is_input_paused = False
        logger.info("音频输入已恢复")

    def is_input_paused(self):
        """检查输入流是否暂停"""
        with self._input_paused_lock:
            return self._is_input_paused

    def read_audio(self):
        """读取音频输入数据并编码"""
        if self.is_input_paused():
            return None
        
        try:
            with self._stream_lock:
                if not self.input_stream or not self.input_stream.is_active():
                    try:
                        if self.input_stream:
                            try:
                                self.input_stream.start_stream()
                                logger.info("重新启动了音频输入流")
                            except Exception as e:
                                logger.warning(f"无法重新启动音频输入流: {e}")
                                self._reinitialize_input_stream()
                        else:
                            self._reinitialize_input_stream()
                    except Exception as e:
                        logger.error(f"无法初始化音频输入流: {e}")
                        return None

                # 检查是否有数据可读
                available = self.input_stream.get_read_available()
                if available <= 0:
                    return None

                # 如果缓冲区累积了太多数据，清空一部分以避免延迟
                # 降低阈值，以避免在大帧长度下清除太多数据
                if available > AudioConfig.INPUT_FRAME_SIZE * 2:
                    # 降低清除量，保留更多最近的数据
                    to_skip = available - (AudioConfig.INPUT_FRAME_SIZE * 1.5)
                    if to_skip > 0:
                        self.input_stream.read(
                            int(to_skip),
                            exception_on_overflow=False
                        )
                
                # 读取音频数据
                try:
                    data = self.input_stream.read(
                        AudioConfig.INPUT_FRAME_SIZE,
                        exception_on_overflow=False
                    )
                except OSError as e:
                    if "Input overflowed" in str(e):
                        logger.warning("输入缓冲区溢出，尝试恢复")
                        self._reinitialize_input_stream()
                    else:
                        logger.error(f"读取音频数据时出错: {e}")
                    return None
                
                if not data:
                    return None

                # 检查音频数据是否有效
                if len(data) != AudioConfig.INPUT_FRAME_SIZE * 2:  # 16位采样，每个采样2字节
                    logger.warning(
                        f"音频数据大小异常: {len(data)} bytes, "
                        f"预期: {AudioConfig.INPUT_FRAME_SIZE * 2} bytes"
                    )
                    return None
                
                # 编码音频数据
                try:
                    return self.opus_encoder.encode(
                        data,
                        AudioConfig.INPUT_FRAME_SIZE
                    )
                except Exception as e:
                    logger.error(f"编码音频数据时出错: {e}")
                    return None
            
        except Exception as e:
            logger.error(f"读取音频输入时出错: {e}")
            return None

    def write_audio(self, opus_data):
        """将编码的音频数据添加到播放队列"""
        self.audio_decode_queue.put(opus_data)

    def play_audio(self):
        """处理并播放队列中的音频数据"""
        try:
            if self.audio_decode_queue.empty():
                return None

            # 批量处理多个音频包以减少处理延迟
            batch_size = min(10, self.audio_decode_queue.qsize())
            buffer = bytearray()
            
            # 从队列中获取数据并解码
            for _ in range(batch_size):
                try:
                    opus_data = self.audio_decode_queue.get_nowait()
                    # 解码为24kHz的PCM数据
                    pcm_data = self.opus_decoder.decode(
                        opus_data, 
                        AudioConfig.OUTPUT_FRAME_SIZE,
                        decode_fec=False
                    )
                    buffer.extend(pcm_data)
                except queue.Empty:
                    break
                except Exception as e:
                    logger.error(f"解码音频数据时出错: {e}")

            # 只有在有数据时才处理和播放
            if len(buffer) > 0:
                # 转换为numpy数组
                pcm_array = np.frombuffer(buffer, dtype=np.int16)
                
                # 使用锁保护输出流操作
                with self._stream_lock:
                    if self.output_stream and self.output_stream.is_active():
                        try:
                            self.output_stream.write(pcm_array.tobytes())
                        except OSError as e:
                            error_msg = str(e)
                            if ("Stream closed" in error_msg or 
                                "Internal PortAudio error" in error_msg):
                                logger.error("播放音频时出错: 流已关闭")
                                self._reinitialize_output_stream()
                            else:
                                logger.error("播放音频时出错")
                    else:
                        self._reinitialize_output_stream()
                        if self.output_stream and self.output_stream.is_active():
                            try:
                                self.output_stream.write(pcm_array.tobytes())
                            except Exception:
                                logger.error("重新初始化后播放音频时出错")
                                
        except Exception:
            logger.error("播放音频时出错")
            self._reinitialize_output_stream()

    def has_pending_audio(self):
        """检查是否还有待播放的音频数据"""
        return not self.audio_decode_queue.empty()

    def wait_for_audio_complete(self, timeout=5.0):
        # 等待音频队列清空
        attempt = 0
        max_attempts = 15
        while not self.audio_decode_queue.empty() and attempt < max_attempts:
            time.sleep(0.1)
            attempt += 1

        # 在关闭前清空任何剩余数据
        while not self.audio_decode_queue.empty():
            try:
                self.audio_decode_queue.get_nowait()
            except queue.Empty:
                break

    def clear_audio_queue(self):
        """清空音频队列"""
        while not self.audio_decode_queue.empty():
            try:
                self.audio_decode_queue.get_nowait()
            except queue.Empty:
                break

    def start_streams(self):
        """启动音频流"""
        if not self.input_stream.is_active():
            self.input_stream.start_stream()
        if not self.output_stream.is_active():
            self.output_stream.start_stream()

    def stop_streams(self):
        """停止音频流"""
        if self.input_stream and self.input_stream.is_active():
            self.input_stream.stop_stream()
        if self.output_stream and self.output_stream.is_active():
            self.output_stream.stop_stream()

    def _reinitialize_output_stream(self):
        """重新初始化音频输出流"""
        if self._is_closing:  # 如果正在关闭，不要重新初始化
            return

        try:
            if self.output_stream:
                try:
                    if self.output_stream.is_active():
                        self.output_stream.stop_stream()
                    self.output_stream.close()
                except Exception:  # 忽略关闭时的错误
                    pass

            # 在特定平台上添加延迟
            if sys.platform in ('darwin', 'linux'):
                time.sleep(0.1)

            input_device = self._get_default_or_first_available_device(
                is_input=True
            )
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AudioConfig.CHANNELS,
                rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                output=True,
                output_device_index=input_device,
                frames_per_buffer=AudioConfig.OUTPUT_FRAME_SIZE
            )
            logger.info("音频输出流重新初始化成功")
        except Exception as e:
            logger.error(f"重新初始化音频输出流失败: {e}")
            raise

    def _reinitialize_input_stream(self):
        """重新初始化音频输入流"""
        if self._is_closing:  # 如果正在关闭，不要重新初始化
            return

        try:
            if self.input_stream:
                try:
                    if self.input_stream.is_active():
                        # 在关闭前清空缓冲区
                        while self.input_stream.get_read_available() > 0:
                            self.input_stream.read(
                                AudioConfig.INPUT_FRAME_SIZE,
                                exception_on_overflow=False
                            )
                        self.input_stream.stop_stream()
                    self.input_stream.close()
                except Exception:  # 忽略关闭时的错误
                    pass

            # 在特定平台上添加短暂延迟
            if sys.platform in ('darwin', 'linux'):
                time.sleep(0.1)

            input_device_index = self._get_default_or_first_available_device(is_input=True)
            self.input_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AudioConfig.CHANNELS,
                rate=AudioConfig.INPUT_SAMPLE_RATE,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=AudioConfig.INPUT_FRAME_SIZE
            )
            logger.info("音频输入流重新初始化成功")
        except Exception as e:
            logger.error(f"重新初始化音频输入流失败: {e}")
            raise

    def get_shared_input_stream(self):
        """获取可共享的输入流，如果不可用则返回None"""
        with self._stream_lock:
            if not self.input_stream or not self.input_stream.is_active():
                try:
                    self._reinitialize_input_stream()
                except Exception as e:
                    logger.error(f"无法获取可共享的输入流: {e}")
                    return None
            return self.input_stream

    def close(self):
        """关闭音频编解码器，确保资源正确释放"""
        if self._is_closing:  # 防止重复关闭
            return

        self._is_closing = True
        logger.info("开始关闭音频编解码器...")

        try:
            # 等待并清理剩余音频数据
            timeout = 2.0  # 设置超时，避免无限等待
            try:
                self.wait_for_audio_complete(timeout=timeout)
            except Exception as e:
                logger.warning(f"等待音频完成时出错: {e}")
            
            # 强制清空音频队列
            self.clear_audio_queue()

            with self._stream_lock:  # 使用锁确保线程安全
                # 关闭输入流
                if self.input_stream:
                    logger.debug("正在关闭输入流...")
                    try:
                        if self.input_stream.is_active():
                            self.input_stream.stop_stream()
                        self.input_stream.close()
                    except Exception as e:
                        logger.error(f"关闭输入流时出错: {e}")
                    finally:
                        self.input_stream = None

                # 关闭输出流
                if self.output_stream:
                    logger.debug("正在关闭输出流...")
                    try:
                        if self.output_stream.is_active():
                            self.output_stream.stop_stream()
                        self.output_stream.close()
                    except Exception as e:
                        logger.error(f"关闭输出流时出错: {e}")
                    finally:
                        self.output_stream = None

                # 关闭 PyAudio 实例
                if self.audio:
                    logger.debug("正在终止 PyAudio...")
                    try:
                        self.audio.terminate()
                    except Exception as e:
                        logger.error(f"终止 PyAudio 时出错: {e}")
                    finally:
                        self.audio = None

            # 清理编解码器
            self.opus_encoder = None
            self.opus_decoder = None

            logger.info("音频编解码器关闭完成")
        except Exception as e:
            logger.error(f"关闭音频编解码器时发生错误: {e}")
        finally:
            self._is_closing = False

    def __del__(self):
        """析构函数，确保资源被释放"""
        self.close()
