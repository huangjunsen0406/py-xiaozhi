"""激活 HTTP 客户端."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Callable, Optional

import aiohttp

from src.logging import get_logger

if TYPE_CHECKING:
    from src.activation.identity import DeviceIdentity
    from src.utils.config_manager import ConfigManager

logger = get_logger()


class ActivationHttpClient:
    """向 OTA activate 端点轮询直到成功或超时."""

    def __init__(
        self,
        config_manager: "ConfigManager",
        identity: "DeviceIdentity",
    ) -> None:
        self._config = config_manager
        self._identity = identity

    async def activate(
        self,
        challenge: str,
        code: str,
        *,
        on_retry_announce: Optional[Callable[[str], None]] = None,
    ) -> bool:
        serial_number = self._identity.get_serial_number()
        if not serial_number:
            logger.error("无序列号，无法激活")
            return False

        hmac_signature = self._identity.generate_hmac_signature(challenge)
        if not hmac_signature:
            logger.error("无法生成HMAC签名")
            return False

        payload = {
            "Payload": {
                "algorithm": "hmac-sha256",
                "serial_number": serial_number,
                "challenge": challenge,
                "hmac": hmac_signature,
            }
        }

        ota_url = self._config.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        if not ota_url:
            logger.error("OTA URL未配置")
            return False

        activate_url = f"{ota_url.rstrip('/')}/activate"
        headers = {
            "Activation-Version": "2",
            "Device-Id": self._config.get_config("SYSTEM_OPTIONS.DEVICE_ID"),
            "Client-Id": self._config.get_config("SYSTEM_OPTIONS.CLIENT_ID"),
            "Content-Type": "application/json",
        }
        logger.info(f"激活URL: {activate_url}")

        max_retries = 60
        retry_interval = 5
        timeout = aiohttp.ClientTimeout(total=10)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(max_retries):
                try:
                    logger.info(f"激活尝试 {attempt + 1}/{max_retries}")
                    if attempt > 0 and on_retry_announce:
                        try:
                            on_retry_announce(code)
                        except Exception as e:
                            logger.warning(f"激活码播报失败: {e}", exc_info=True)

                    async with session.post(
                        activate_url, headers=headers, json=payload
                    ) as response:
                        logger.debug(f"激活响应: HTTP {response.status}")
                        if response.status == 200:
                            logger.info("设备激活成功!")
                            self._identity.set_activation_status(True)
                            return True
                        if response.status == 202:
                            logger.info("等待用户输入验证码...")
                            await asyncio.sleep(retry_interval)
                            continue
                        logger.warning(f"服务器返回 {response.status}，继续重试")
                        await asyncio.sleep(retry_interval)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"激活请求失败: {e}，重试中...", exc_info=True)
                    await asyncio.sleep(retry_interval)

        logger.error(f"激活失败，达到最大重试次数 ({max_retries})")
        return False
