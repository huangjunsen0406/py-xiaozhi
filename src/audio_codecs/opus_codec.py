import numpy as np

# ============================================================
# Opus 库加载（必须在导入 opuslib 之前）
# ============================================================
from src.utils.opus_loader import setup_opus

setup_opus()

# 必须在 setup_opus() 之后导入
import opuslib  # noqa: E402

from src.constants.constants import AudioConfig  # noqa: E402
from src.logging import get_logger  # noqa: E402

logger = get_logger()


class OpusCodec:
    """Opus 编解码器

    使用 libopus 的 encode_float 和 decode_float 接口，
    """

    def __init__(
        self,
        input_sample_rate: int = AudioConfig.INPUT_SAMPLE_RATE,
        output_sample_rate: int = AudioConfig.OUTPUT_SAMPLE_RATE,
        channels: int = AudioConfig.CHANNELS,
    ):
        """初始化Opus编解码器

        Args:
            input_sample_rate: 输入采样率（编码）
            output_sample_rate: 输出采样率（解码）
            channels: 声道数
        """
        self.input_sample_rate = input_sample_rate
        self.output_sample_rate = output_sample_rate
        self.channels = channels
        self.encoder = None
        self.decoder = None

    def initialize(self):
        """创建编解码器

        Raises:
            Exception: 创建失败
        """
        try:
            # 输入编码器：16kHz单声道
            self.encoder = opuslib.Encoder(
                self.input_sample_rate,
                self.channels,
                opuslib.APPLICATION_VOIP,
            )

            # 输出解码器：24kHz单声道
            self.decoder = opuslib.Decoder(self.output_sample_rate, self.channels)

            logger.info(
                f"Opus编解码器创建成功 (float32模式) | "
                f"编码: {self.input_sample_rate}Hz | "
                f"解码: {self.output_sample_rate}Hz"
            )
        except Exception as e:
            logger.error(f"创建Opus编解码器失败: {e}")
            raise

    def encode(self, pcm_float32: np.ndarray, frame_size: int) -> bytes:
        """编码 float32 PCM → Opus

        Args:
            pcm_float32: float32 数组，范围 [-1.0, 1.0]
            frame_size: 样本数

        Returns:
            Opus 编码数据

        Raises:
            RuntimeError: 编码器未初始化
            Exception: 编码失败
        """
        if self.encoder is None:
            raise RuntimeError("编码器未初始化")

        # 转换为 bytes（float32 格式）
        pcm_bytes = pcm_float32.astype(np.float32).tobytes()

        # 使用 encode_float（libopus 原生支持）
        return self.encoder.encode_float(pcm_bytes, frame_size)

    def decode(self, opus_data: bytes, frame_size: int) -> np.ndarray:
        """解码 Opus → float32 PCM

        Args:
            opus_data: Opus 编码数据
            frame_size: 期望的样本数

        Returns:
            float32 数组，范围 [-1.0, 1.0]

        Raises:
            RuntimeError: 解码器未初始化
            Exception: 解码失败
        """
        if self.decoder is None:
            raise RuntimeError("解码器未初始化")

        # 使用 decode_float（libopus 原生支持）
        # 注意：channels 在创建 Decoder 时已指定，decode_float 不需要此参数
        pcm_bytes = self.decoder.decode_float(opus_data, frame_size, decode_fec=False)

        # 转换为 numpy 数组
        return np.frombuffer(pcm_bytes, dtype=np.float32)

    def close(self):
        """释放资源"""
        self.encoder = None
        self.decoder = None
        logger.debug("Opus编解码器已释放")
