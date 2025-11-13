import asyncio
from typing import Any


class Plugin:
    """
    最小插件基类：提供异步生命周期钩子。按需覆写。
    """

    name: str = "plugin"
    priority: int = 50  # 优先级，数值越小越优先（范围: 1-100）

    def __init__(self) -> None:
        self._started = False

    async def setup(self, app: Any) -> None:
        """
        插件准备阶段（在应用 run 早期调用）。
        """
        await asyncio.sleep(0)

    async def start(self) -> None:
        """
        插件启动（通常在协议连接建立后调用）。
        """
        self._started = True
        await asyncio.sleep(0)

    async def on_protocol_connected(self, protocol: Any) -> None:
        """
        协议通道建立后的通知。
        """
        await asyncio.sleep(0)

    async def on_incoming_json(self, message: Any) -> None:
        """
        收到JSON消息时的通知。
        """
        await asyncio.sleep(0)

    async def on_incoming_audio(self, data: bytes) -> None:
        """
        收到音频数据时的通知。
        """
        await asyncio.sleep(0)

    async def on_device_state_changed(self, state: Any) -> None:
        """
        设备状态变更通知（由应用广播）。
        """
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """
        插件停止（在应用 shutdown 前调用）。
        """
        self._started = False
        await asyncio.sleep(0)

    async def shutdown(self) -> None:
        """
        插件最终清理（在应用 shutdown 过程中调用）。
        """
        await asyncio.sleep(0)
