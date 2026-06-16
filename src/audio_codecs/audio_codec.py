import threading
from typing import Callable, List, Optional, Protocol

import numpy as np

from src.audio_codecs.audio_buffer import AudioBuffer
from src.audio_codecs.audio_converter import AudioConverter
from src.audio_codecs.opus_codec import OpusCodec, parse_opus_toc
from src.audio_codecs.stream_manager import AudioStreamManager
from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.audio_device import AudioDeviceManager, DeviceConfig
from src.utils.config_manager import ConfigManager

logger = get_logger()


class AudioListener(Protocol):
    """音频监听器协议"""

    def on_audio_data(self, audio_data: np.ndarray) -> None:
        """接收音频数据

        Args:
            audio_data: float32 音频数据
        """
        ...


class AudioCodec:
    """音频编解码器 - 协调器模式

    组合各个组件，协调数据流

    数据流：
    - 输入：设备(float32) → 下混+重采样(float32) → Opus编码(float32→bytes) → 网络
    - 输出：网络 → Opus解码(bytes→float32) → 重采样+上混(float32) → 设备(float32)
    """

    def __init__(self):
        """初始化音频编解码器"""
        # 刷新协议配置（支持 Settings UI 修改后生效）
        AudioConfig.reload()

        # 组件（依赖注入）
        self.device_manager = AudioDeviceManager(ConfigManager.get_instance())
        self.opus_codec = OpusCodec(
            input_sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
            output_sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
            channels=AudioConfig.CHANNELS,
        )
        self.converter = AudioConverter()
        self.stream_manager = None
        self.output_buffer = AudioBuffer(maxsize=500)

        # 监听器（线程安全）
        self._encoded_callback: Optional[Callable] = None
        self._audio_listeners: List[AudioListener] = []
        self._listeners_lock = threading.Lock()

        # 设备配置（初始化后填充）
        self.device_config: Optional[DeviceConfig] = None

        # 状态标记
        self._is_closing = False
        self._closed = False
        self._server_opus_logged = False

    async def initialize(self):
        """初始化所有组件

        流程：
        1. 加载/检测设备
        2. 刷新协议配置 + 初始化 Opus
        3. 配置格式转换管线
        4. 创建音频流
        5. 启动音频流
        """
        try:
            # 1. 加载/检测设备
            self.device_config = self.device_manager.load_or_detect_devices()

            # 2. 刷新协议配置并初始化 Opus
            AudioConfig.reload()
            self.opus_codec.close()
            self.opus_codec = OpusCodec(
                input_sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                output_sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            self.opus_codec.initialize()

            # 3. 配置格式转换管线
            self._configure_pipeline()

            # 4. 创建音频流
            self.stream_manager = AudioStreamManager(self.device_config)
            self.stream_manager.create_streams(
                input_callback=self._input_callback,
                output_callback=self._output_callback,
            )

            # 5. 启动音频流
            self.stream_manager.start()

            logger.info("AudioCodec 初始化完成")

        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            await self.close()
            raise

    def _input_callback(self, indata, frames, time_info, status):
        """输入回调：设备 → 编码 → 发送

        数据流：多声道/高采样率 → 下混 → 重采样 → Opus编码 → 网络

        Args:
            indata: float32 音频数据，shape (frames, channels)
            frames: 帧数
            time_info: 时间信息
            status: 状态标志
        """
        if status and "overflow" not in str(status).lower():
            logger.warning(f"输入流状态: {status}")

        if self._is_closing:
            return

        try:
            # 1. 格式转换（下混 + 重采样）
            # 保留 indata 的 (frames, channels) 形状，让 downmix_to_mono 正确下混
            audio_converted = self.converter.convert_input(
                indata, AudioConfig.INPUT_FRAME_SIZE
            )
            if audio_converted is None:
                return  # 数据不足，等待下一帧

            # 2. Opus 编码（float32 输入）
            if self._encoded_callback:
                try:
                    opus_data = self.opus_codec.encode(
                        audio_converted, AudioConfig.INPUT_FRAME_SIZE
                    )
                    self._encoded_callback(opus_data)
                except Exception as e:
                    logger.warning(f"编码失败: {e}")

            # 3. 通知监听器（线程安全）
            with self._listeners_lock:
                for listener in self._audio_listeners:
                    try:
                        listener.on_audio_data(audio_converted.copy())
                    except Exception as e:
                        logger.warning(f"监听器处理失败: {e}")

        except Exception as e:
            logger.error(f"输入回调错误: {e}")

    def _output_callback(self, outdata, frames, time_info, status):
        """输出回调：解码 → 转换 → 播放

        数据流：队列 → 重采样 → 上混 → 设备

        循环从队列取 chunk 喂给 convert_output，直到 resampler
        内部缓冲区凑够 frames 或队列耗尽。解决采样率非整除
        （如 16kHz→44100Hz）或服务器帧时长不匹配时的卡顿问题。

        Args:
            outdata: float32 输出缓冲区，shape (frames, channels)
            frames: 帧数
            time_info: 时间信息
            status: 状态标志
        """
        if status:
            logger.warning(f"输出流状态: {status}")

        try:
            audio_converted = None

            while audio_converted is None:
                audio_data = self.output_buffer.get_nowait()
                if audio_data is None:
                    break
                audio_converted = self.converter.convert_output(audio_data, frames)

            if audio_converted is None:
                audio_converted = self.converter.drain_output_buffer(frames)

            if audio_converted is None or len(audio_converted) < frames:
                outdata.fill(0.0)
                if audio_converted is not None and len(audio_converted) > 0:
                    outdata[: len(audio_converted)] = audio_converted
            else:
                outdata[:] = audio_converted[:frames]

        except Exception as e:
            logger.error(f"输出回调错误: {e}")
            outdata.fill(0.0)

    def _configure_pipeline(self):
        """配置格式转换管线（设备 ↔ 协议）。

        根据设备原生参数和协议要求参数，设置输入/输出转换链。
        输入：设备(f32, device_rate, device_ch) → 协议(f32, 16kHz, 1ch)
        输出：协议(f32, opus_out_rate, 1ch) → 设备(f32, device_rate, device_ch)
        """
        self.converter.setup_input_converter(
            from_rate=self.device_config.input_sample_rate,
            to_rate=AudioConfig.INPUT_SAMPLE_RATE,
            from_channels=self.device_config.input_channels,
            to_channels=1,
        )
        self.converter.setup_output_converter(
            from_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
            to_rate=self.device_config.output_sample_rate,
            from_channels=1,
            to_channels=self.device_config.output_channels,
        )

    # === 对外接口（保持兼容） ===

    def set_encoded_callback(self, callback: Callable[[bytes], None]):
        """设置编码回调

        Args:
            callback: 回调函数，接收 Opus 编码数据
        """
        self._encoded_callback = callback
        if callback:
            logger.info("已设置编码音频回调")
        else:
            logger.info("已清除编码音频回调")

    def add_audio_listener(self, listener: AudioListener):
        """添加音频监听器（线程安全）

        Args:
            listener: 实现 AudioListener 协议的监听器对象
        """
        with self._listeners_lock:
            if listener not in self._audio_listeners:
                self._audio_listeners.append(listener)
                logger.info(f"已添加音频监听器: {listener.__class__.__name__}")

    def remove_audio_listener(self, listener: AudioListener):
        """移除音频监听器（线程安全）

        Args:
            listener: 要移除的监听器对象
        """
        with self._listeners_lock:
            if listener in self._audio_listeners:
                self._audio_listeners.remove(listener)
                logger.info(f"已移除音频监听器: {listener.__class__.__name__}")

    async def write_audio(self, opus_data: bytes):
        """解码并播放音频（Opus → 扬声器）

        自动从 Opus TOC 字节检测帧时长，无需依赖客户端配置。

        Args:
            opus_data: Opus 编码数据
        """
        try:
            toc_info = parse_opus_toc(opus_data)
            if toc_info is None:
                return

            if not self._server_opus_logged:
                self._server_opus_logged = True
                logger.info(
                    f"服务端 Opus 参数: "
                    f"{toc_info['mode']} {toc_info['bandwidth_hz']} | "
                    f"帧时长 {toc_info['duration_ms']}ms "
                    f"({toc_info['frame_ms']}ms×{toc_info['num_frames']})"
                )

            frame_size = int(
                AudioConfig.OUTPUT_SAMPLE_RATE * toc_info["duration_ms"] / 1000
            )
            audio_float32 = self.opus_codec.decode(opus_data, frame_size)

            await self.output_buffer.put(audio_float32, replace_oldest=True)

        except Exception as e:
            logger.warning(f"音频写入失败: {e}")

    async def write_pcm_direct(self, pcm_float32: np.ndarray):
        """直接写入 float32 PCM（供 MusicPlayer 使用）

        Args:
            pcm_float32: float32 PCM 数据
        """
        # replace_oldest=True：输出队列满时丢弃旧帧而非阻塞，
        # 防止播放回路卡死在 put() 导致 decoder 超时刷屏
        await self.output_buffer.put(pcm_float32, replace_oldest=True)

    async def clear_audio_queue(self):
        """清空音频队列"""
        self._server_opus_logged = False
        self.converter.clear_output_buffer()
        count = await self.output_buffer.clear()
        if count > 0:
            logger.info(f"清空音频队列，丢弃 {count} 帧")

    async def reinitialize_stream(self, is_input: bool = True):
        """重建音频流（支持热插拔）

        Args:
            is_input: True=输入流, False=输出流

        Returns:
            bool: 是否成功
        """
        if not self.stream_manager:
            return False

        if is_input:
            return self.stream_manager.reinitialize_stream(
                is_input=True, input_callback=self._input_callback
            )
        else:
            return self.stream_manager.reinitialize_stream(
                is_input=False, output_callback=self._output_callback
            )

    async def reload_devices(self):
        """热重载音频设备配置

        流程：
        1. 停止当前音频流
        2. 重新加载设备配置 + 协议配置
        3. 重建格式转换器 + Opus 编解码器
        4. 重新创建并启动音频流

        Returns:
            bool: 是否成功
        """
        logger.info("AudioCodec: 开始热重载音频设备...")

        try:
            # 1. 停止当前流
            if self.stream_manager:
                self.stream_manager.stop()
                logger.debug("AudioCodec: 已停止当前音频流")

            # 2. 重新加载设备配置
            self.device_manager.config.reload_config()
            self.device_config = self.device_manager.load_or_detect_devices()
            logger.info(f"AudioCodec: 新设备配置 - 输入ID: {self.device_config.input_device_id}, 输出ID: {self.device_config.output_device_id}")

            # 3. 刷新协议配置并重建 Opus 编解码器
            AudioConfig.reload()
            self.opus_codec.close()
            self.opus_codec = OpusCodec(
                input_sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                output_sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            self.opus_codec.initialize()

            # 4. 重建格式转换器
            self.converter.clear_buffers()
            self._configure_pipeline()

            # 5. 重新创建音频流
            self.stream_manager = AudioStreamManager(self.device_config)
            self.stream_manager.create_streams(
                input_callback=self._input_callback,
                output_callback=self._output_callback,
            )

            # 6. 启动音频流
            self.stream_manager.start()

            logger.info("AudioCodec: 音频设备热重载完成")
            return True

        except Exception as e:
            logger.error(f"AudioCodec: 热重载音频设备失败: {e}", exc_info=True)
            return False

    async def close(self):
        """关闭音频编解码器"""
        self._is_closing = True

        try:
            # 1. 停止音频流
            if self.stream_manager:
                self.stream_manager.stop()

            # 2. 清空队列
            await self.clear_audio_queue()

            # 3. 释放转换器（含 soxr 重采样器）
            self.converter.close()

            # 4. 释放 Opus
            self.opus_codec.close()

            # 5. 清理监听器
            with self._listeners_lock:
                self._audio_listeners.clear()

            logger.info("AudioCodec 已关闭")
            self._closed = True

        except Exception as e:
            logger.error(f"关闭音频编解码器失败: {e}")
        finally:
            self._is_closing = False

    def __del__(self):
        """析构函数 - 执行同步清理"""
        # 如果已正确关闭或正在关闭，跳过
        if getattr(self, "_closed", False) or getattr(self, "_is_closing", False):
            return

        logger.warning("AudioCodec 未正确关闭，执行紧急清理（建议使用 async close()）")

        try:
            # 1. 停止音频流（同步）
            if self.stream_manager:
                self.stream_manager.stop()

            # 2. 清空队列（同步版本）
            if self.output_buffer:
                count = self.output_buffer.clear_sync()
                if count > 0:
                    logger.debug(f"析构函数清空了 {count} 帧音频")

            # 3. 释放转换器（同步，含 soxr 重采样器）
            if self.converter:
                self.converter.close()

            # 4. 释放 Opus（同步）
            if self.opus_codec:
                self.opus_codec.close()

            # 5. 清理监听器（同步）
            try:
                with self._listeners_lock:
                    self._audio_listeners.clear()
            except Exception as e:
                logger.warning(f"清理音频监听器失败（锁可能已损坏）: {e}")

            logger.debug("AudioCodec 析构清理完成")

        except Exception as e:
            logger.error(f"析构函数清理失败: {e}")
