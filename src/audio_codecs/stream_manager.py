"""音频流管理器.

职责：sounddevice 流创建、生命周期管理
"""

from typing import Callable

import numpy as np
import sounddevice as sd

from src.logging import get_logger
from src.utils.audio_device import DeviceConfig
from src.utils.audio_utils import ALSAErrorSuppressor

logger = get_logger()


class AudioStreamManager:
    """音频流管理器（sounddevice 封装）

    负责创建和管理音频输入/输出流的生命周期。
    """

    def __init__(self, device_config: DeviceConfig):
        """初始化流管理器

        Args:
            device_config: 设备配置
        """
        self.device_config = device_config
        self.input_stream = None
        self.output_stream = None

    def create_streams(
        self, input_callback: Callable, output_callback: Callable
    ) -> None:
        """创建双工音频流

        Args:
            input_callback: 输入回调函数
            output_callback: 输出回调函数

        Raises:
            Exception: 创建流失败
        """
        try:
            # 使用 ALSAErrorSuppressor 抑制 Linux 上的 ALSA 警告
            with ALSAErrorSuppressor():
                # 输入流
                self.input_stream = sd.InputStream(
                    device=self.device_config.input_device_id,
                    samplerate=self.device_config.input_sample_rate,
                    channels=self.device_config.input_channels,
                    dtype=np.float32,  # 统一 float32
                    blocksize=self.device_config.input_frame_size,
                    callback=input_callback,
                    latency="low",
                )

                # 输出流
                self.output_stream = sd.OutputStream(
                    device=self.device_config.output_device_id,
                    samplerate=self.device_config.output_sample_rate,
                    channels=self.device_config.output_channels,
                    dtype=np.float32,  # 统一 float32
                    blocksize=self.device_config.output_frame_size,
                    callback=output_callback,
                    latency="low",
                )

            logger.info(
                f"音频流已创建 | "
                f"输入: {self.device_config.input_sample_rate}Hz "
                f"{self.device_config.input_channels}ch | "
                f"输出: {self.device_config.output_sample_rate}Hz "
                f"{self.device_config.output_channels}ch"
            )
        except Exception as e:
            logger.error(f"创建音频流失败: {e}")
            raise

    def start(self) -> None:
        """启动音频流

        Raises:
            Exception: 启动失败
        """
        try:
            if self.input_stream:
                self.input_stream.start()
            if self.output_stream:
                self.output_stream.start()
            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")
            raise

    def stop(self) -> None:
        """停止音频流，幂等可重复调用"""
        if getattr(self, '_stopped', False):
            return
        self._stopped = True

        try:
            if self.input_stream:
                self.input_stream.stop()
                self.input_stream.close()
                self.input_stream = None

            if self.output_stream:
                self.output_stream.stop()
                self.output_stream.close()
                self.output_stream = None

            logger.info("音频流已停止")
        except Exception as e:
            logger.error(f"停止音频流失败: {e}")

    def reinitialize_stream(
        self,
        is_input: bool,
        input_callback: Callable = None,
        output_callback: Callable = None,
    ) -> bool:
        """重建音频流（支持热插拔）

        Args:
            is_input: True=输入流, False=输出流
            input_callback: 输入回调函数（仅重建输入流时需要）
            output_callback: 输出回调函数（仅重建输出流时需要）

        Returns:
            bool: 是否成功
        """
        try:
            # 使用 ALSAErrorSuppressor 抑制 Linux 上的 ALSA 警告
            with ALSAErrorSuppressor():
                if is_input and input_callback:
                    # 重建输入流
                    if self.input_stream:
                        self.input_stream.stop()
                        self.input_stream.close()

                    self.input_stream = sd.InputStream(
                        device=self.device_config.input_device_id,
                        samplerate=self.device_config.input_sample_rate,
                        channels=self.device_config.input_channels,
                        dtype=np.float32,
                        blocksize=self.device_config.input_frame_size,
                        callback=input_callback,
                        latency="low",
                    )
                    self.input_stream.start()
                    logger.info("输入流重新初始化成功")
                    return True

                elif not is_input and output_callback:
                    # 重建输出流
                    if self.output_stream:
                        self.output_stream.stop()
                        self.output_stream.close()

                    self.output_stream = sd.OutputStream(
                        device=self.device_config.output_device_id,
                        samplerate=self.device_config.output_sample_rate,
                        channels=self.device_config.output_channels,
                        dtype=np.float32,
                        blocksize=self.device_config.output_frame_size,
                        callback=output_callback,
                        latency="low",
                    )
                    self.output_stream.start()
                    logger.info("输出流重新初始化成功")
                    return True

            return False

        except Exception as e:
            stream_type = "输入" if is_input else "输出"
            logger.error(f"{stream_type}流重建失败: {e}")
            return False
