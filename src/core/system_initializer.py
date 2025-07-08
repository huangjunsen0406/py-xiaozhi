#!/usr/bin/env python3
"""
四阶段初始化流程测试脚本 展示设备身份准备、配置管理、OTA配置获取三个阶段的协调工作 激活流程由用户自己实现.
"""

import asyncio
import json
from pathlib import Path
from typing import Dict

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
        self.activation_data = None
        self.activation_status = {
            "local_activated": False,  # 本地激活状态
            "server_activated": False,  # 服务器激活状态
            "status_consistent": True,  # 状态是否一致
        }

    async def run_initialization(self) -> Dict:
        """运行完整的初始化流程.

        Returns:
            Dict: 初始化结果，包含激活状态和是否需要激活界面
        """
        logger.info("开始系统初始化流程")

        try:
            # 第一阶段：设备身份准备
            await self.stage_1_device_fingerprint()

            # 第二阶段：配置管理初始化
            await self.stage_2_config_management()

            # 第三阶段：OTA获取配置
            await self.stage_3_ota_config()

            # 获取激活版本配置
            activation_version = self.config_manager.get_config(
                "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1"
            )

            logger.info(f"激活版本: {activation_version}")

            # 根据激活版本决定是否需要激活流程
            if activation_version == "v1":
                # v1协议：完成前三个阶段后直接返回成功
                logger.info("v1协议：前三个阶段完成，无需激活流程")
                return {
                    "success": True,
                    "local_activated": True,
                    "server_activated": True,
                    "status_consistent": True,
                    "need_activation_ui": False,
                    "status_message": "v1协议初始化完成",
                    "activation_version": activation_version,
                }
            else:
                # v2协议：需要分析激活状态
                logger.info("v2协议：分析激活状态")
                activation_result = self.analyze_activation_status()
                activation_result["activation_version"] = activation_version

                # 根据分析结果决定是否需要激活流程
                if activation_result["need_activation_ui"]:
                    logger.info("需要显示激活界面")
                else:
                    logger.info("无需显示激活界面，设备已激活")

                return activation_result

        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            return {"success": False, "error": str(e), "need_activation_ui": False}

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

        # 记录本地激活状态
        self.activation_status["local_activated"] = is_activated

        # 获取MAC地址并确保小写格式
        mac_address = self.device_fingerprint.get_mac_address_from_efuse()

        logger.info(f"设备序列号: {serial_number}")
        logger.info(f"MAC地址: {mac_address}")
        logger.info(f"HMAC密钥: {hmac_key[:8] if hmac_key else None}...")
        logger.info(f"本地激活状态: {'已激活' if is_activated else '未激活'}")

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
                # 服务器认为设备未激活
                self.activation_status["server_activated"] = False
            else:
                logger.info("未检测到激活信息，设备可能已激活")
                self.activation_data = None
                # 服务器认为设备已激活
                self.activation_status["server_activated"] = True

        except Exception as e:
            logger.error(f"OTA配置获取失败: {e}")
            raise

        logger.info(f"完成{self.current_stage.value}")

    def analyze_activation_status(self) -> Dict:
        """分析激活状态，决定后续流程.

        Returns:
            Dict: 分析结果，包含是否需要激活界面等信息
        """
        local_activated = self.activation_status["local_activated"]
        server_activated = self.activation_status["server_activated"]

        # 检查状态是否一致
        status_consistent = local_activated == server_activated
        self.activation_status["status_consistent"] = status_consistent

        result = {
            "success": True,
            "local_activated": local_activated,
            "server_activated": server_activated,
            "status_consistent": status_consistent,
            "need_activation_ui": False,
            "status_message": "",
        }

        # 情况1: 本地未激活，服务器返回激活数据 - 正常激活流程
        if not local_activated and not server_activated:
            result["need_activation_ui"] = True
            result["status_message"] = "设备需要激活"

        # 情况2: 本地已激活，服务器无激活数据 - 正常已激活状态
        elif local_activated and server_activated:
            result["need_activation_ui"] = False
            result["status_message"] = "设备已激活"

        # 情况3: 本地未激活，但服务器无激活数据 - 状态不一致，自动修复
        elif not local_activated and server_activated:
            logger.warning(
                "状态不一致: 本地未激活，但服务器认为已激活，自动修复本地状态"
            )
            # 自动更新本地状态为已激活
            self.device_fingerprint.set_activation_status(True)
            result["need_activation_ui"] = False
            result["status_message"] = "已自动修复激活状态"
            result["local_activated"] = True  # 更新结果中的状态

        # 情况4: 本地已激活，但服务器返回激活数据 - 状态不一致，尝试自动修复
        elif local_activated and not server_activated:
            logger.warning("状态不一致: 本地已激活，但服务器认为未激活，尝试自动修复")

            # 检查是否有激活数据
            if self.activation_data and isinstance(self.activation_data, dict):
                # 如果有激活码，则需要重新激活
                if "code" in self.activation_data:
                    logger.info("服务器返回了激活码，需要重新激活")
                    result["need_activation_ui"] = True
                    result["status_message"] = "激活状态不一致，需要重新激活"
                else:
                    # 没有激活码，可能是服务器状态未更新，尝试继续使用
                    logger.info("服务器未返回激活码，保持本地激活状态")
                    result["need_activation_ui"] = False
                    result["status_message"] = "保持本地激活状态"
            else:
                # 没有激活数据，可能是网络问题，保持本地状态
                logger.info("未获取到激活数据，保持本地激活状态")
                result["need_activation_ui"] = False
                result["status_message"] = "保持本地激活状态"
                # 强制更新状态一致性，避免重复激活
                result["status_consistent"] = True
                self.activation_status["status_consistent"] = True
                self.activation_status["server_activated"] = True

        return result

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

    def get_activation_status(self) -> Dict:
        """
        获取激活状态信息.
        """
        return self.activation_status

    async def handle_activation_process(self, mode: str = "gui") -> Dict:
        """处理激活流程，根据需要创建激活界面.

        Args:
            mode: 界面模式，"gui"或"cli"

        Returns:
            Dict: 激活结果
        """
        # 先运行初始化流程
        init_result = await self.run_initialization()

        # 如果不需要激活界面，直接返回结果
        if not init_result.get("need_activation_ui", False):
            return {
                "is_activated": True,
                "device_fingerprint": self.device_fingerprint,
                "config_manager": self.config_manager,
            }

        # 需要激活界面，根据模式创建
        if mode == "gui":
            return await self._run_gui_activation()
        else:
            return await self._run_cli_activation()

    async def _run_gui_activation(self) -> Dict:
        """运行GUI激活流程.

        Returns:
            Dict: 激活结果
        """
        try:
            from src.views.activation.activation_window import ActivationWindow

            # 创建激活窗口
            activation_window = ActivationWindow(self)

            # 创建Future来等待激活完成
            activation_future = asyncio.Future()

            # 设置激活完成回调
            def on_activation_completed(success: bool):
                if not activation_future.done():
                    activation_future.set_result(success)

            # 设置窗口关闭回调
            def on_window_closed():
                if not activation_future.done():
                    activation_future.set_result(False)

            # 连接信号
            activation_window.activation_completed.connect(on_activation_completed)
            activation_window.window_closed.connect(on_window_closed)

            # 显示激活窗口
            activation_window.show()

            # 等待激活完成
            activation_success = await activation_future

            # 关闭窗口
            activation_window.close()

            return {
                "is_activated": activation_success,
                "device_fingerprint": self.device_fingerprint,
                "config_manager": self.config_manager,
            }

        except Exception as e:
            logger.error(f"GUI激活流程异常: {e}", exc_info=True)
            return {"is_activated": False, "error": str(e)}

    async def _run_cli_activation(self) -> Dict:
        """运行CLI激活流程.

        Returns:
            Dict: 激活结果
        """
        try:
            from src.views.activation.cli_activation import CLIActivation

            # 创建CLI激活处理器
            cli_activation = CLIActivation(self)

            # 运行激活流程
            activation_success = await cli_activation.run_activation_process()

            return {
                "is_activated": activation_success,
                "device_fingerprint": self.device_fingerprint,
                "config_manager": self.config_manager,
            }

        except Exception as e:
            logger.error(f"CLI激活流程异常: {e}", exc_info=True)
            return {"is_activated": False, "error": str(e)}
