#!/usr/bin/env python3
"""
四阶段初始化流程测试脚本 展示设备身份准备、配置管理、OTA配置获取三个阶段的协调工作 激活流程由用户自己实现.
"""

import json
from pathlib import Path

from src.constants.system import InitializationStage
from src.core.ota import Ota
from src.utils.config_manager import ConfigManager
from src.utils.device_fingerprint import DeviceFingerprint
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class SystemInitializer:
    """系统初始化器 - 协调四个阶段"""

    def __init__(self):
        self.device_fingerprint = None
        self.config_manager = None
        self.ota = None
        self.current_stage = None

    async def run_initialization(self):
        """
        运行完整的初始化流程.
        """
        logger.info("开始系统初始化流程")

        try:
            # 第一阶段：设备身份准备
            await self.stage_1_device_fingerprint()

            # 第二阶段：配置管理初始化
            await self.stage_2_config_management()

            # 第三阶段：OTA获取配置
            await self.stage_3_ota_config()

            # 第四阶段：激活流程（由用户实现）
            self.stage_4_activation_ready()

            logger.info("系统初始化流程完成，准备进入激活阶段")
            return True

        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            return False

    async def stage_1_device_fingerprint(self):
        """
        第一阶段：设备身份准备.
        """
        self.current_stage = InitializationStage.DEVICE_FINGERPRINT
        logger.info(f"开始{self.current_stage.value}")

        # 初始化设备指纹
        self.device_fingerprint = DeviceFingerprint.get_instance()

        # 确保设备身份信息完整
        (
            serial_number,
            hmac_key,
            is_activated,
        ) = self.device_fingerprint.ensure_device_identity()

        # 获取MAC地址并确保小写格式
        mac_address = self.device_fingerprint.get_mac_address_from_efuse()

        logger.info(f"设备序列号: {serial_number}")
        logger.info(f"MAC地址: {mac_address}")
        logger.info(f"HMAC密钥: {hmac_key[:8] if hmac_key else None}...")
        logger.info(f"激活状态: {'已激活' if is_activated else '未激活'}")

        # 验证efuse.json文件是否完整
        efuse_file = Path("config/efuse.json")
        if efuse_file.exists():
            logger.info(f"efuse.json文件位置: {efuse_file.absolute()}")
            with open(efuse_file, "r", encoding="utf-8") as f:
                efuse_data = json.load(f)
            logger.debug(
                f"efuse.json内容: "
                f"{json.dumps(efuse_data, indent=2, ensure_ascii=False)}"
            )
        else:
            logger.warning("efuse.json文件不存在")

        logger.info(f"完成{self.current_stage.value}")

    async def stage_2_config_management(self):
        """
        第二阶段：配置管理初始化.
        """
        self.current_stage = InitializationStage.CONFIG_MANAGEMENT
        logger.info(f"开始{self.current_stage.value}")

        # 初始化配置管理器
        self.config_manager = ConfigManager.get_instance()

        # 确保CLIENT_ID存在
        self.config_manager.initialize_client_id()

        # 从设备指纹初始化DEVICE_ID
        self.config_manager.initialize_device_id_from_fingerprint(
            self.device_fingerprint
        )

        # 验证关键配置
        client_id = self.config_manager.get_config("SYSTEM_OPTIONS.CLIENT_ID")
        device_id = self.config_manager.get_config("SYSTEM_OPTIONS.DEVICE_ID")

        logger.info(f"客户端ID: {client_id}")
        logger.info(f"设备ID: {device_id}")

        logger.info(f"完成{self.current_stage.value}")

    async def stage_3_ota_config(self):
        """
        第三阶段：OTA获取配置.
        """
        self.current_stage = InitializationStage.OTA_CONFIG
        logger.info(f"开始{self.current_stage.value}")

        # 初始化OTA
        self.ota = await Ota.get_instance()

        # 获取并更新配置
        try:
            config_result = await self.ota.fetch_and_update_config()

            logger.info("OTA配置获取结果:")
            mqtt_status = "已获取" if config_result["mqtt_config"] else "未获取"
            logger.info(f"- MQTT配置: {mqtt_status}")

            ws_status = "已获取" if config_result["websocket_config"] else "未获取"
            logger.info(f"- WebSocket配置: {ws_status}")

            # 显示获取到的配置信息摘要
            response_data = config_result["response_data"]
            # 详细配置信息仅在调试模式下显示
            logger.debug(
                f"OTA响应数据: {json.dumps(response_data, indent=2, ensure_ascii=False)}"
            )

            if "websocket" in response_data:
                ws_info = response_data["websocket"]
                logger.info(f"WebSocket URL: {ws_info.get('url', 'N/A')}")
            # 检查是否有激活信息
            if "activation" in response_data:
                logger.info("检测到激活信息，设备需要激活")
                self.activation_data = response_data["activation"]
            else:
                logger.info("未检测到激活信息，设备可能已激活")
                self.activation_data = None

        except Exception as e:
            logger.error(f"OTA配置获取失败: {e}")
            raise

        logger.info(f"完成{self.current_stage.value}")

    def stage_4_activation_ready(self):
        """
        第四阶段：激活流程准备就绪.
        """
        self.current_stage = InitializationStage.ACTIVATION
        logger.info(f"准备{self.current_stage.value}")

        # 检查激活状态
        is_activated = self.device_fingerprint.is_activated()

        if is_activated:
            logger.info("设备已激活，无需再次激活")
        else:
            logger.info("设备未激活，需要进行激活流程")

            if hasattr(self, "activation_data") and self.activation_data:
                logger.debug("激活数据已准备就绪:")
                challenge = self.activation_data.get("challenge", "N/A")
                logger.debug(f"- 挑战码: {challenge}")

                code = self.activation_data.get("code", "N/A")
                logger.debug(f"- 验证码: {code}")

                message = self.activation_data.get("message", "N/A")
                logger.debug(f"- 消息: {message}")

                logger.info("所有前置条件已满足，可以开始激活流程")
            else:
                logger.warning("未获取到激活数据，可能需要重新获取OTA配置")

        logger.info(f"{self.current_stage.value}准备完成")

    def get_activation_data(self):
        """
        获取激活数据（供激活模块使用）
        """
        return getattr(self, "activation_data", None)

    def get_device_fingerprint(self):
        """
        获取设备指纹实例.
        """
        return self.device_fingerprint

    def get_config_manager(self):
        """
        获取配置管理器实例.
        """
        return self.config_manager
