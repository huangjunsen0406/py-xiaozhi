import asyncio
import json
import socket
import ssl

import aiohttp

from src.constants.system import SystemConstants
from src.utils.config_manager import ConfigManager
from src.utils.device_fingerprint import DeviceFingerprint
from src.utils.logging_config import get_logger


class Ota:
    _instance = None
    _lock = asyncio.Lock()

    def __init__(self):
        self.logger = get_logger(__name__)
        self.config = ConfigManager.get_instance()
        self.device_fingerprint = DeviceFingerprint.get_instance()
        self.mac_addr = None
        self.ota_version_url = None
        self.local_ip = None
        self.system_info = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    instance = cls()
                    await instance.init()
                    cls._instance = instance
        return cls._instance

    async def init(self):
        """
        初始化OTA实例.
        """
        self.local_ip = await self.get_local_ip()
        # 从配置中获取设备ID（MAC地址）
        self.mac_addr = self.config.get_config("SYSTEM_OPTIONS.DEVICE_ID")
        # 获取OTA URL
        self.ota_version_url = self.config.get_config(
            "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL"
        )

    async def get_local_ip(self):
        """
        异步获取本机IP地址.
        """
        try:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._sync_get_ip)
        except Exception as e:
            self.logger.error(f"获取本机 IP 失败：{e}")
            return "127.0.0.1"

    def _sync_get_ip(self):
        """
        同步获取IP地址.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]

    def build_payload(self):
        """
        构建OTA请求的payload.
        """
        # 从efuse.json获取hmac_key作为elf_sha256
        hmac_key = self.device_fingerprint.get_hmac_key()
        elf_sha256 = hmac_key if hmac_key else "unknown"

        return {
            "application": {
                "version": SystemConstants.APP_VERSION,
                "elf_sha256": elf_sha256,
            },
            "board": {
                "type": SystemConstants.BOARD_TYPE,
                "name": SystemConstants.APP_NAME,
                "ip": self.local_ip,
                "mac": self.mac_addr,
            },
        }

    def build_headers(self):
        """
        构建OTA请求的headers.
        """
        app_version = SystemConstants.APP_VERSION
        board_type = SystemConstants.BOARD_TYPE
        app_name = SystemConstants.APP_NAME

        # 基础头部
        headers = {
            "Device-Id": self.mac_addr,
            "Client-Id": self.config.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
            "User-Agent": f"{board_type}/{app_name}-{app_version}",
            "Accept-Language": "zh-CN",
        }

        # 根据激活版本决定是否添加Activation-Version头部
        activation_version = self.config.get_config(
            "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v1"
        )

        # 只有v2协议才添加Activation-Version头部
        if activation_version == "v2":
            headers["Activation-Version"] = app_version
            self.logger.debug(f"v2协议：添加Activation-Version头部: {app_version}")
        else:
            self.logger.debug("v1协议：不添加Activation-Version头部")

        return headers

    async def get_ota_config(self):
        """
        获取OTA服务器的配置信息（MQTT、WebSocket等）
        """
        if not self.mac_addr:
            self.logger.error("设备ID(MAC地址)未配置")
            raise ValueError("设备ID未配置")

        if not self.ota_version_url:
            self.logger.error("OTA URL未配置")
            raise ValueError("OTA URL未配置")

        headers = self.build_headers()
        payload = self.build_payload()

        try:
            # 禁用SSL证书验证以支持自签名证书
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # 使用aiohttp异步发送请求
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(
                timeout=timeout, connector=connector
            ) as session:
                async with session.post(
                    self.ota_version_url, headers=headers, json=payload
                ) as response:
                    # 检查HTTP状态码
                    if response.status != 200:
                        self.logger.error(f"OTA服务器错误: HTTP {response.status}")
                        raise ValueError(f"OTA服务器返回错误状态码: {response.status}")

                    # 解析JSON数据
                    response_data = await response.json()

                    # 调试信息：打印完整的OTA响应
                    self.logger.debug(
                        f"OTA服务器返回数据: "
                        f"{json.dumps(response_data, indent=4, ensure_ascii=False)}"
                    )

                    return response_data

        except asyncio.TimeoutError:
            self.logger.error("OTA请求超时，请检查网络或服务器状态")
            raise ValueError("OTA请求超时！请稍后重试。")

        except aiohttp.ClientError as e:
            self.logger.error(f"OTA请求失败: {e}")
            raise ValueError("无法连接到OTA服务器，请检查网络连接！")

    async def update_mqtt_config(self, response_data):
        """
        更新MQTT配置信息.
        """
        if "mqtt" in response_data:
            self.logger.info("发现MQTT配置信息")
            mqtt_info = response_data["mqtt"]
            if mqtt_info:
                # 更新配置
                success = self.config.update_config(
                    "SYSTEM_OPTIONS.NETWORK.MQTT_INFO", mqtt_info
                )
                if success:
                    self.logger.info("MQTT配置已更新")
                    return mqtt_info
                else:
                    self.logger.error("MQTT配置更新失败")
            else:
                self.logger.warning("MQTT配置为空")
        else:
            self.logger.info("未发现MQTT配置信息")

        return None

    async def update_websocket_config(self, response_data):
        """
        更新WebSocket配置信息.
        """
        if "websocket" in response_data:
            self.logger.info("发现WebSocket配置信息")
            websocket_info = response_data["websocket"]

            # 更新WebSocket URL
            if "url" in websocket_info:
                self.config.update_config(
                    "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", websocket_info["url"]
                )
                self.logger.info(f"WebSocket URL已更新: {websocket_info['url']}")

            # 更新WebSocket Token
            token_value = websocket_info.get("token", "test-token") or "test-token"
            self.config.update_config(
                "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", token_value
            )
            self.logger.info("WebSocket Token已更新")

            return websocket_info
        else:
            self.logger.info("未发现WebSocket配置信息")

        return None

    async def fetch_and_update_config(self):
        """
        获取并更新所有配置信息.
        """
        try:
            # 获取OTA配置
            response_data = await self.get_ota_config()

            # 更新MQTT配置
            mqtt_config = await self.update_mqtt_config(response_data)

            # 更新WebSocket配置
            websocket_config = await self.update_websocket_config(response_data)

            # 返回完整的响应数据，供激活流程使用
            return {
                "response_data": response_data,
                "mqtt_config": mqtt_config,
                "websocket_config": websocket_config,
            }

        except Exception as e:
            self.logger.error(f"获取并更新配置失败: {e}")
            raise
