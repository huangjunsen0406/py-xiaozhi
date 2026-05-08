from collections import deque
from typing import Optional

import numpy as np
import soxr

from src.logging import get_logger
from src.utils.audio_utils import downmix_to_mono, upmix_mono_to_channels

logger = get_logger()


class AudioConverter:
    """音频格式转换器

    负责采样率转换和声道转换，内部维护缓冲区以凑够目标帧大小。
    """

    def __init__(self):
        """初始化转换器"""
        self.input_resampler = None
        self.output_resampler = None
        self._input_buffer = deque()
        self._output_buffer = deque()
        self.needs_input_downmix = False
        self.needs_output_upmix = False
        self.input_channels = 1
        self.output_channels = 1

    def setup_input_converter(
        self, from_rate: int, to_rate: int, from_channels: int, to_channels: int = 1
    ):
        """配置输入转换链（设备 → 协议）

        Args:
            from_rate: 设备采样率
            to_rate: 协议采样率（通常16kHz）
            from_channels: 设备声道数
            to_channels: 协议声道数（通常1）
        """
        self.input_channels = from_channels
        self.needs_input_downmix = from_channels > to_channels

        if self.needs_input_downmix:
            logger.info(f"输入声道下混: {from_channels}ch → {to_channels}ch")

        if from_rate != to_rate:
            self.input_resampler = soxr.ResampleStream(
                from_rate,
                to_rate,
                num_channels=to_channels,  # 下混后的声道数
                dtype="float32",
                quality="QQ",  # 快速质量（适合实时处理）
            )
            logger.info(f"输入重采样: {from_rate}Hz → {to_rate}Hz")

    def setup_output_converter(
        self, from_rate: int, to_rate: int, from_channels: int = 1, to_channels: int = 2
    ):
        """配置输出转换链（协议 → 设备）

        Args:
            from_rate: 协议采样率（通常24kHz）
            to_rate: 设备采样率
            from_channels: 协议声道数（通常1）
            to_channels: 设备声道数
        """
        self.output_channels = to_channels
        self.needs_output_upmix = to_channels > from_channels

        if from_rate != to_rate:
            self.output_resampler = soxr.ResampleStream(
                from_rate,
                to_rate,
                num_channels=from_channels,  # 上混前的声道数
                dtype="float32",
                quality="QQ",
            )
            logger.info(f"输出重采样: {from_rate}Hz → {to_rate}Hz")

        if self.needs_output_upmix:
            logger.info(f"输出声道上混: {from_channels}ch → {to_channels}ch")

    def convert_input(
        self, audio: np.ndarray, target_size: int
    ) -> Optional[np.ndarray]:
        """输入转换：多声道/高采样率 → 单声道/16kHz

        Args:
            audio: float32 音频数据
            target_size: 目标样本数

        Returns:
            转换后的 float32 数据，或 None（数据不足）
        """
        # 1. 下混（使用 audio_utils）
        if self.needs_input_downmix:
            audio = downmix_to_mono(audio, keepdims=False)
        else:
            audio = audio.flatten()

        # 2. 重采样
        if self.input_resampler:
            resampled = self.input_resampler.resample_chunk(audio, last=False)
            if len(resampled) > 0:
                self._input_buffer.extend(resampled)

            # 累积到目标大小
            if len(self._input_buffer) < target_size:
                return None

            # 取出一帧
            frame_data = [self._input_buffer.popleft() for _ in range(target_size)]
            return np.array(frame_data, dtype=np.float32)

        return audio

    def convert_output(
        self, audio: np.ndarray, target_frames: int
    ) -> Optional[np.ndarray]:
        """输出转换：单声道/24kHz → 多声道/高采样率

        Args:
            audio: float32 音频数据
            target_frames: 目标帧数

        Returns:
            转换后的 float32 数据
        """
        # 1. 重采样
        if self.output_resampler:
            resampled = self.output_resampler.resample_chunk(audio, last=False)
            if len(resampled) > 0:
                self._output_buffer.extend(resampled)

            # 取出目标帧数
            if len(self._output_buffer) < target_frames:
                return None

            frame_data = [self._output_buffer.popleft() for _ in range(target_frames)]
            audio = np.array(frame_data, dtype=np.float32)

        # 2. 上混（使用 audio_utils）
        if self.needs_output_upmix:
            audio = upmix_mono_to_channels(audio, self.output_channels)
        else:
            audio = audio.reshape(-1, 1)

        return audio

    def clear_buffers(self):
        """清空缓冲区"""
        self._input_buffer.clear()
        self._output_buffer.clear()
        logger.debug("音频转换器缓冲区已清空")

    def close(self):
        """释放 soxr 重采样器，防止 nanobind C++ 对象泄漏."""
        self.clear_buffers()
        self.input_resampler = None
        self.output_resampler = None
