"""音频设备管理器.

职责：
- 设备发现和选择
- 配置持久化（按设备名称，而非 ID）
- 设备信息查询
"""

from dataclasses import dataclass

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.audio_utils import find_device_by_name, select_audio_device
from src.utils.config_manager import ConfigManager

logger = get_logger()


@dataclass
class DeviceConfig:
    """设备配置数据类"""

    input_device_id: int
    output_device_id: int
    input_sample_rate: int
    output_sample_rate: int
    input_channels: int
    output_channels: int
    input_frame_size: int
    output_frame_size: int


class AudioDeviceManager:
    """音频设备管理器（无状态，纯逻辑）"""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    def load_or_detect_devices(self) -> DeviceConfig:
        """加载配置或自动检测设备（按名称匹配）

        Returns:
            DeviceConfig: 设备配置

        Raises:
            RuntimeError: 无法找到可用设备
        """
        audio_config = self.config.get_config("AUDIO_DEVICES", {}) or {}

        input_device_name = audio_config.get("input_device_name")
        output_device_name = audio_config.get("output_device_name")

        # 1. 尝试按名称查找设备
        input_info = None
        output_info = None

        if input_device_name:
            logger.info(f"尝试查找输入设备: {input_device_name}")
            input_info = find_device_by_name("input", input_device_name)
            if input_info:
                logger.info(f"✓ 找到输入设备: {input_info['name']} (ID: {input_info['index']})")
            else:
                logger.warning(f"✗ 未找到设备 '{input_device_name}'，将重新选择")

        if output_device_name:
            logger.info(f"尝试查找输出设备: {output_device_name}")
            output_info = find_device_by_name("output", output_device_name)
            if output_info:
                logger.info(f"✓ 找到输出设备: {output_info['name']} (ID: {output_info['index']})")
            else:
                logger.warning(f"✗ 未找到设备 '{output_device_name}'，将重新选择")

        # 2. 如果按名称查找失败，自动选择新设备
        if not input_info:
            logger.info("自动选择输入设备...")
            input_info = select_audio_device("input")
            if not input_info:
                raise RuntimeError("无法找到可用的输入设备")

        if not output_info:
            logger.info("自动选择输出设备...")
            output_info = select_audio_device("output")
            if not output_info:
                raise RuntimeError("无法找到可用的输出设备")

        # 3. 限制声道数
        input_channels = min(input_info["channels"], AudioConfig.MAX_INPUT_CHANNELS)
        output_channels = min(output_info["channels"], AudioConfig.MAX_OUTPUT_CHANNELS)

        device_input_sample_rate = input_info["sample_rate"]
        device_output_sample_rate = output_info["sample_rate"]

        logger.info(
            f"使用输入设备: {input_info['name']} | "
            f"{device_input_sample_rate}Hz {input_channels}ch"
        )
        logger.info(
            f"使用输出设备: {output_info['name']} | "
            f"{device_output_sample_rate}Hz {output_channels}ch"
        )

        # 4. 保存设备名称（而非 ID）到配置
        if (
            input_device_name != input_info["name"]
            or output_device_name != output_info["name"]
        ):
            self.config.update_config("AUDIO_DEVICES.input_device_name", input_info["name"])
            self.config.update_config("AUDIO_DEVICES.input_sample_rate", device_input_sample_rate)
            self.config.update_config("AUDIO_DEVICES.input_channels", input_channels)
            self.config.update_config("AUDIO_DEVICES.output_device_name", output_info["name"])
            self.config.update_config("AUDIO_DEVICES.output_sample_rate", device_output_sample_rate)
            self.config.update_config("AUDIO_DEVICES.output_channels", output_channels)
            logger.info("设备配置已保存")

        return DeviceConfig(
            input_device_id=input_info["index"],
            output_device_id=output_info["index"],
            input_sample_rate=device_input_sample_rate,
            output_sample_rate=device_output_sample_rate,
            input_channels=input_channels,
            output_channels=output_channels,
            input_frame_size=int(
                device_input_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
            ),
            output_frame_size=int(
                device_output_sample_rate * (AudioConfig.FRAME_DURATION / 1000)
            ),
        )
