from collections import deque

import numpy as np

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

try:
    # 直接使用已安装的pyaec库
    from pyaec import Aec

    AEC_AVAILABLE = True
    logger.info("使用已安装的pyaec库")
except Exception as e:
    logger.warning(f"pyaec库不可用: {e}")
    logger.info("请安装pyaec: pip install pyaec")
    AEC_AVAILABLE = False
    Aec = None


class AECProcessor:
    """
    声学回声消除处理器.
    """

    def __init__(self, enabled: bool = True):
        """初始化AEC处理器.

        Args:
            enabled: 是否启用AEC功能
        """
        # 获取配置管理器
        self.config = ConfigManager.get_instance()

        # 从配置读取AEC设置
        aec_enabled = self.config.get_config("AEC_OPTIONS.ENABLED", True)
        self.enabled = enabled and aec_enabled and AEC_AVAILABLE

        self.aec = None

        # 从配置读取缓冲区设置
        buffer_max_length = self.config.get_config("AEC_OPTIONS.BUFFER_MAX_LENGTH", 200)
        self._reference_buffer = deque(maxlen=buffer_max_length)

        self._initialized = False

        # 注意：延迟补偿功能暂未实现，AudioCodec的立即处理已经减少了延迟
        # self._frame_delay = self.config.get_config("AEC_OPTIONS.FRAME_DELAY", 3)

        self._stats = {
            "processed_frames": 0,
            "reference_frames": 0,
            "buffer_underruns": 0,
        }

        if not AEC_AVAILABLE:
            logger.warning("pyaec不可用，AEC功能已禁用")
            self.enabled = False
        elif not aec_enabled:
            logger.info("AEC功能已在配置中禁用")
        elif not enabled:
            logger.info("AEC功能已手动禁用")

    async def initialize(self):
        """
        初始化AEC实例.
        """
        if not self.enabled:
            return

        try:
            # 从配置读取滤波器长度比例
            filter_length_ratio = self.config.get_config(
                "AEC_OPTIONS.FILTER_LENGTH_RATIO", 0.6
            )
            filter_length = int(AudioConfig.INPUT_SAMPLE_RATE * filter_length_ratio)

            # 从配置读取预处理设置
            enable_preprocess = self.config.get_config(
                "AEC_OPTIONS.ENABLE_PREPROCESS", True
            )

            # 创建AEC实例
            self.aec = Aec(
                frame_size=AudioConfig.INPUT_FRAME_SIZE,
                filter_length=filter_length,
                sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                enable_preprocess=enable_preprocess,
            )

            self._initialized = True

            logger.info(
                f"AEC处理器初始化成功 [帧大小: {AudioConfig.INPUT_FRAME_SIZE}, "
                f"滤波器长度: {filter_length} (比例: {filter_length_ratio}), "
                f"采样率: {AudioConfig.INPUT_SAMPLE_RATE}Hz, 预处理: {enable_preprocess}]"
            )

        except Exception as e:
            logger.error(f"AEC处理器初始化失败: {e}")
            self.enabled = False
            self._initialized = False

    def add_reference_audio(self, audio_data: np.ndarray):
        """添加参考音频信号.

        Args:
            audio_data: 音频数据，已重采样至16kHz且格式化为正确帧大小的参考信号
        """
        if not self.enabled or not self._initialized:
            return

        try:
            # AudioCodec已确保数据格式和帧大小正确，直接使用
            self._reference_buffer.append(audio_data.copy())
            self._stats["reference_frames"] += 1

            # 调试信息
            if self._stats["reference_frames"] % 100 == 0:  # 每100帧记录一次
                logger.debug(
                    f"AEC参考信号: 缓冲区={len(self._reference_buffer)}, "
                    f"总帧数={self._stats['reference_frames']}"
                )

        except Exception as e:
            logger.warning(f"添加参考音频失败: {e}")

    def process_audio(self, input_audio: np.ndarray) -> np.ndarray:
        """处理音频信号，应用回声消除.

        Args:
            input_audio: 输入音频信号(麦克风录音)，已确保格式和帧大小正确

        Returns:
            处理后的音频信号，如果AEC未启用则返回原始信号
        """
        if not self.enabled or not self._initialized or self.aec is None:
            return input_audio

        try:
            # 获取参考信号
            if len(self._reference_buffer) > 0:
                reference_audio = self._reference_buffer.popleft()
            else:
                # 如果没有参考信号，使用静音，记录缓冲区不足
                reference_audio = np.zeros(AudioConfig.INPUT_FRAME_SIZE, dtype=np.int16)
                self._stats["buffer_underruns"] += 1

            # AEC处理，回声消除和噪声抑制
            processed_audio = self.aec.cancel_echo(input_audio, reference_audio)

            # 转换回numpy数组
            if isinstance(processed_audio, list):
                processed_audio = np.array(processed_audio, dtype=np.int16)
            elif not isinstance(processed_audio, np.ndarray):
                processed_audio = np.array(processed_audio, dtype=np.int16)

            self._stats["processed_frames"] += 1

            # 定期输出统计信息
            if self._stats["processed_frames"] % 500 == 0:
                underrun_rate = (
                    self._stats["buffer_underruns"]
                    / self._stats["processed_frames"]
                    * 100
                )
                logger.debug(
                    f"AEC统计: 处理帧={self._stats['processed_frames']}, "
                    f"参考帧={self._stats['reference_frames']}, "
                    f"缓冲区不足率={underrun_rate:.1f}%"
                )

            return processed_audio

        except Exception as e:
            logger.warning(f"AEC处理失败，返回原始音频: {e}")
            return input_audio

    def clear_reference_buffer(self):
        """
        清空参考信号缓冲区.
        """
        if self._reference_buffer:
            cleared_count = len(self._reference_buffer)
            self._reference_buffer.clear()
            logger.debug(f"AEC参考信号缓冲区已清空，丢弃 {cleared_count} 帧")

        # 重置统计信息
        self._stats = {
            "processed_frames": 0,
            "reference_frames": 0,
            "buffer_underruns": 0,
        }

    def is_available(self) -> bool:
        """检查AEC功能是否可用.

        Returns:
            bool: AEC是否可用
        """
        return self.enabled and self._initialized and self.aec is not None

    async def close(self):
        """
        关闭AEC处理器，释放资源.
        """
        if self.aec is not None:
            try:
                self.aec = None
                self._initialized = False
                logger.info("AEC处理器已关闭")
            except Exception as e:
                logger.warning(f"关闭AEC处理器时出错: {e}")

        self.clear_reference_buffer()

    def __del__(self):
        """
        析构函数.
        """
        if self._initialized:
            logger.warning("AEC处理器被销毁但未正确关闭，请确保调用close()方法")
