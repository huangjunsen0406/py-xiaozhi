import queue
import threading
import time
from typing import Optional

import numpy as np
import opuslib
import sounddevice as sd

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AudioCodec:
    """音频编解码器类，处理音频的录制和播放（SoundDevice版本）"""

    def __init__(self):
        self.opus_encoder = None
        self.opus_decoder = None
        # 设置队列最大大小，防止内存溢出（约10秒音频缓冲）
        max_queue_size = int(10 * 1000 / AudioConfig.FRAME_DURATION)
        self.audio_decode_queue = queue.Queue(maxsize=max_queue_size)

        # 状态管理
        self._is_closing = False
        self._is_input_paused = False
        self._input_paused_lock = threading.Lock()
        self._stream_lock = threading.Lock()

        # SoundDevice流对象
        self.input_stream = None
        self.output_stream = None

        # 音频缓冲区 - 增加大小以避免溢出
        self._input_buffer = queue.Queue(maxsize=300)  # 增加输入缓冲区
        self._output_buffer = queue.Queue(maxsize=200)  # 增加输出缓冲区

        self._initialize_audio()

    def _initialize_audio(self):
        """初始化音频设备和编解码器"""
        try:
            # 设置SoundDevice默认参数
            sd.default.samplerate = AudioConfig.INPUT_SAMPLE_RATE
            sd.default.channels = AudioConfig.CHANNELS
            sd.default.dtype = np.int16

            # 初始化流
            self._create_streams()

            # 编解码器初始化
            self.opus_encoder = opuslib.Encoder(
                AudioConfig.INPUT_SAMPLE_RATE,
                AudioConfig.CHANNELS,
                opuslib.APPLICATION_AUDIO,
            )
            self.opus_decoder = opuslib.Decoder(
                AudioConfig.OUTPUT_SAMPLE_RATE, AudioConfig.CHANNELS
            )

            logger.info("音频设备和编解码器初始化成功")
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            self.close()
            raise

    def _create_streams(self):
        """创建输入和输出流"""
        try:
            # 使用标准帧大小作为blocksize，确保数据完整性
            input_blocksize = AudioConfig.INPUT_FRAME_SIZE
            output_blocksize = AudioConfig.OUTPUT_FRAME_SIZE

            # 创建输入流（录音）
            self.input_stream = sd.InputStream(
                samplerate=AudioConfig.INPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=input_blocksize,
                callback=self._input_callback,
                finished_callback=self._input_finished_callback,
                latency='low'  # 设置低延迟模式
            )

            # 创建输出流（播放）
            self.output_stream = sd.OutputStream(
                samplerate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
                dtype=np.int16,
                blocksize=output_blocksize,
                callback=self._output_callback,
                finished_callback=self._output_finished_callback,
                latency='low'  # 设置低延迟模式
            )

            # 启动流
            self.input_stream.start()
            self.output_stream.start()

        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def _input_callback(self, indata: np.ndarray, frames: int, time_info, status):
        """输入流回调函数 - 简化版本，处理完整帧"""
        if status:
            # 只记录严重错误，忽略常见的overflow警告
            if 'overflow' not in str(status).lower():
                logger.warning(f"输入流状态: {status}")
        
        if self._is_closing or self.is_input_paused():
            return
        
        try:
            # 直接存储完整帧数据
            audio_data = indata.copy().flatten()
            
            # 非阻塞放入，如果满了就丢弃最旧的数据
            try:
                self._input_buffer.put_nowait(audio_data)
            except queue.Full:
                # 移除最旧的数据，添加新数据
                try:
                    self._input_buffer.get_nowait()
                    self._input_buffer.put_nowait(audio_data)
                except queue.Empty:
                    self._input_buffer.put_nowait(audio_data)
                    
        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _output_callback(self, outdata: np.ndarray, frames: int, time_info, status):
        """输出流回调函数 - 优化版本"""
        if status:
            # 只记录严重错误，忽略常见的underflow警告
            if 'underflow' not in str(status).lower():
                logger.warning(f"输出流状态: {status}")
        
        try:
            # 尝试获取音频数据
            try:
                audio_data = self._output_buffer.get_nowait()
                
                # 确保数据长度匹配
                if len(audio_data) >= frames:
                    outdata[:] = audio_data[:frames].reshape(-1, 1)
                else:
                    # 数据不足时，用现有数据填充，剩余部分静音
                    outdata[:len(audio_data)] = audio_data.reshape(-1, 1)
                    outdata[len(audio_data):] = 0
                    
            except queue.Empty:
                # 没有数据时输出静音
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

    def _reinitialize_stream(self, is_input=True):
        """重新初始化流"""
        if self._is_closing:
            return False if is_input else None

        try:
            with self._stream_lock:
                if is_input:
                    # 重建输入流
                    if self.input_stream:
                        self.input_stream.stop()
                        self.input_stream.close()
                    
                    input_blocksize = AudioConfig.INPUT_FRAME_SIZE
                    self.input_stream = sd.InputStream(
                        samplerate=AudioConfig.INPUT_SAMPLE_RATE,
                        channels=AudioConfig.CHANNELS,
                        dtype=np.int16,
                        blocksize=input_blocksize,
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
                    
                    output_blocksize = AudioConfig.OUTPUT_FRAME_SIZE
                    self.output_stream = sd.OutputStream(
                        samplerate=AudioConfig.OUTPUT_SAMPLE_RATE,
                        channels=AudioConfig.CHANNELS,
                        dtype=np.int16,
                        blocksize=output_blocksize,
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

    def pause_input(self):
        """暂停音频输入"""
        with self._input_paused_lock:
            self._is_input_paused = True
        logger.info("音频输入已暂停")

    def resume_input(self):
        """恢复音频输入"""
        with self._input_paused_lock:
            self._is_input_paused = False
        logger.info("音频输入已恢复")

    def is_input_paused(self):
        """检查输入是否已暂停"""
        with self._input_paused_lock:
            return self._is_input_paused

    def read_audio(self) -> Optional[bytes]:
        """读取音频数据并编码 - 简化为处理单个完整帧"""
        if self.is_input_paused():
            return None

        try:
            # 直接从缓冲区获取一个完整帧
            if not self._input_buffer.empty():
                audio_data = self._input_buffer.get_nowait()
                
                # 验证数据长度
                if len(audio_data) != AudioConfig.INPUT_FRAME_SIZE:
                    expected = AudioConfig.INPUT_FRAME_SIZE
                    actual = len(audio_data)
                    logger.warning(f"音频数据长度异常: {actual}, 期望: {expected}")
                    return None

                # 转换为bytes并编码
                pcm_data = audio_data.astype(np.int16).tobytes()
                return self.opus_encoder.encode(pcm_data, AudioConfig.INPUT_FRAME_SIZE)
                
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"音频读取失败: {e}")
        
        return None

    def play_audio(self):
        """播放音频（处理解码队列中的数据）"""
        try:
            if self.audio_decode_queue.empty():
                return

            # 逐个处理音频数据
            processed_count = 0
            max_process_per_call = 3  # 减少单次处理量

            while (
                not self.audio_decode_queue.empty()
                and processed_count < max_process_per_call
            ):
                try:
                    opus_data = self.audio_decode_queue.get_nowait()

                    # 解码音频数据
                    try:
                        pcm_data = self.opus_decoder.decode(
                            opus_data, AudioConfig.OUTPUT_FRAME_SIZE
                        )
                        
                        # 转换为NumPy数组
                        audio_array = np.frombuffer(pcm_data, dtype=np.int16)
                        
                        # 放入输出缓冲区（非阻塞）
                        try:
                            self._output_buffer.put_nowait(audio_array)
                        except queue.Full:
                            # 输出缓冲区满时，移除旧数据
                            try:
                                self._output_buffer.get_nowait()
                                self._output_buffer.put_nowait(audio_array)
                            except queue.Empty:
                                self._output_buffer.put_nowait(audio_array)
                            
                    except opuslib.OpusError as e:
                        logger.warning(f"音频解码失败，丢弃此帧: {e}")
                    except Exception as e:
                        logger.warning(f"音频处理失败，丢弃此帧: {e}")

                    processed_count += 1

                except queue.Empty:
                    break

        except Exception as e:
            logger.error(f"播放音频时发生未预期错误: {e}")

    def write_audio(self, opus_data: bytes):
        """将Opus数据写入播放队列"""
        try:
            self.audio_decode_queue.put_nowait(opus_data)
        except queue.Full:
            # 队列满时，移除最旧的数据，添加新数据
            try:
                self.audio_decode_queue.get_nowait()
                self.audio_decode_queue.put_nowait(opus_data)
            except queue.Empty:
                self.audio_decode_queue.put_nowait(opus_data)

    def get_queue_status(self):
        """获取队列状态信息"""
        queue_size = self.audio_decode_queue.qsize()
        max_size = self.audio_decode_queue.maxsize
        input_buffer_size = self._input_buffer.qsize()
        output_buffer_size = self._output_buffer.qsize()
        
        return {
            "current_size": queue_size,
            "max_size": max_size,
            "is_empty": queue_size == 0,
            "input_buffer_size": input_buffer_size,
            "output_buffer_size": output_buffer_size,
        }

    def wait_for_audio_complete(self, timeout=5.0):
        """等待音频播放完成"""
        start = time.time()
        while not self.audio_decode_queue.empty() and time.time() - start < timeout:
            time.sleep(0.1)

        if not self.audio_decode_queue.empty():
            remaining = self.audio_decode_queue.qsize()
            logger.warning(f"音频播放超时，剩余队列: {remaining} 帧")

    def clear_audio_queue(self):
        """清空音频队列"""
        with self._stream_lock:
            cleared_count = 0
            
            # 清空解码队列
            while not self.audio_decode_queue.empty():
                try:
                    self.audio_decode_queue.get_nowait()
                    cleared_count += 1
                except queue.Empty:
                    break
            
            # 清空输入缓冲区
            while not self._input_buffer.empty():
                try:
                    self._input_buffer.get_nowait()
                    cleared_count += 1
                except queue.Empty:
                    break
            
            # 清空输出缓冲区
            while not self._output_buffer.empty():
                try:
                    self._output_buffer.get_nowait()
                    cleared_count += 1
                except queue.Empty:
                    break
                    
            if cleared_count > 0:
                logger.info(f"清空音频队列，丢弃 {cleared_count} 帧音频数据")

    def stop_streams(self):
        """停止音频流"""
        with self._stream_lock:
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

    def close(self):
        """关闭音频编解码器"""
        if self._is_closing:
            return

        self._is_closing = True
        logger.info("开始关闭音频编解码器...")

        try:
            # 清空队列
            self.clear_audio_queue()

            # 关闭流
            with self._stream_lock:
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

            # 清理编解码器
            self.opus_encoder = None
            self.opus_decoder = None

            logger.info("音频资源已完全释放")
        except Exception as e:
            logger.error(f"关闭音频编解码器过程中发生错误: {e}")

    def __del__(self):
        """析构函数"""
        self.close()
