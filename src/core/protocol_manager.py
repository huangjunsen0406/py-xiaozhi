"""
协议管理器.

封装通信协议操作，通过事件总线转发消息。
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.constants.constants import ListeningMode
from src.core.event_bus import EventBus, Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.protocols.protocol import Protocol

logger = get_logger()


class ProtocolManager:
    """
    协议管理器.

    职责:
    - 创建和管理协议实例 (WebSocket/MQTT)
    - 设置协议回调，转发到事件总线
    - 提供协议操作的统一接口

    用法:
        pm = ProtocolManager(event_bus)
        pm.set_protocol("websocket")
        await pm.connect()
        await pm.send_audio(data)
    """

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._protocol: Optional["Protocol"] = None
        self._connect_lock = asyncio.Lock()

    @property
    def protocol(self) -> Optional["Protocol"]:
        """获取当前协议实例."""
        return self._protocol

    def set_protocol(self, protocol_type: str) -> None:
        """
        设置协议类型.

        Args:
            protocol_type: "websocket" 或 "mqtt"
        """
        logger.debug(f"设置协议类型: {protocol_type}")

        if protocol_type == "mqtt":
            from src.protocols.mqtt_protocol import MqttProtocol

            self._protocol = MqttProtocol(asyncio.get_running_loop())
        else:
            from src.protocols.websocket_protocol import WebsocketProtocol

            self._protocol = WebsocketProtocol()

        self._setup_callbacks()

    def _setup_callbacks(self) -> None:
        """设置协议回调，转发到事件总线."""
        if not self._protocol:
            return

        self._protocol.on_network_error(self._on_network_error)
        self._protocol.on_incoming_json(self._on_incoming_json)
        self._protocol.on_incoming_audio(self._on_incoming_audio)
        self._protocol.on_audio_channel_opened(self._on_audio_channel_opened)
        self._protocol.on_audio_channel_closed(self._on_audio_channel_closed)

    def _on_network_error(self, error_message: str = None) -> None:
        """网络错误回调."""
        if error_message:
            logger.error(f"网络错误: {error_message}")
        # 使用 spawn 或直接创建任务
        asyncio.create_task(
            self._event_bus.emit(Events.NETWORK_ERROR, error_message)
        )

    def _on_incoming_json(self, json_data: dict) -> None:
        """JSON 消息回调."""
        asyncio.create_task(
            self._event_bus.emit(Events.INCOMING_JSON, json_data)
        )

    def _on_incoming_audio(self, data: bytes) -> None:
        """音频数据回调."""
        asyncio.create_task(
            self._event_bus.emit(Events.INCOMING_AUDIO, data)
        )

    async def _on_audio_channel_opened(self) -> None:
        """音频通道打开回调."""
        logger.info("协议通道已打开")
        await self._event_bus.emit(Events.AUDIO_CHANNEL_OPENED)
        await self._event_bus.emit(Events.PROTOCOL_CONNECTED, self._protocol)

    async def _on_audio_channel_closed(self) -> None:
        """音频通道关闭回调."""
        logger.info("协议通道已关闭")
        await self._event_bus.emit(Events.AUDIO_CHANNEL_CLOSED)
        await self._event_bus.emit(Events.PROTOCOL_DISCONNECTED)

    # -------------------------
    # 协议操作
    # -------------------------
    def is_audio_channel_opened(self) -> bool:
        """检查音频通道是否已打开."""
        try:
            return bool(self._protocol and self._protocol.is_audio_channel_opened())
        except Exception:
            return False

    async def connect(self, timeout: float = 12.0) -> bool:
        """
        连接协议通道.

        Args:
            timeout: 连接超时时间（秒）

        Returns:
            是否连接成功
        """
        if self.is_audio_channel_opened():
            return True

        if not self._protocol:
            logger.error("协议未初始化")
            return False

        async with self._connect_lock:
            # 再次检查（双重检查锁定）
            if self.is_audio_channel_opened():
                return True

            try:
                opened = await asyncio.wait_for(
                    self._protocol.open_audio_channel(),
                    timeout=timeout,
                )
                if not opened:
                    logger.error("协议连接失败")
                    return False

                logger.info("协议连接已建立")
                return True

            except asyncio.TimeoutError:
                logger.error("协议连接超时")
                return False
            except Exception as e:
                logger.error(f"协议连接异常: {e}")
                return False

    async def disconnect(self) -> None:
        """断开协议连接."""
        if self._protocol:
            try:
                await self._protocol.close_audio_channel()
            except Exception as e:
                logger.error(f"关闭协议失败: {e}")

    # -------------------------
    # 发送操作
    # -------------------------
    async def send_audio(self, data: bytes) -> None:
        """发送音频数据."""
        if self._protocol and self.is_audio_channel_opened():
            await self._protocol.send_audio(data)

    async def send_text(self, text: str) -> None:
        """发送文本消息."""
        if self._protocol:
            await self._protocol.send_text(text)

    async def send_start_listening(self, mode: ListeningMode) -> None:
        """发送开始监听消息."""
        if self._protocol:
            await self._protocol.send_start_listening(mode)

    async def send_stop_listening(self) -> None:
        """发送停止监听消息."""
        if self._protocol:
            await self._protocol.send_stop_listening()

    async def send_abort_speaking(self, reason: str = None) -> None:
        """发送中止语音消息."""
        if self._protocol:
            await self._protocol.send_abort_speaking(reason)

    async def send_wake_word_detected(self, wake_word: str) -> None:
        """发送唤醒词检测消息."""
        if self._protocol:
            await self._protocol.send_wake_word_detected(wake_word)

    async def send_iot_descriptors(self, descriptors) -> None:
        """发送 IoT 描述符."""
        if self._protocol:
            await self._protocol.send_iot_descriptors(descriptors)

    async def send_iot_states(self, states) -> None:
        """发送 IoT 状态."""
        if self._protocol:
            await self._protocol.send_iot_states(states)

    async def send_mcp_message(self, payload) -> None:
        """发送 MCP 消息."""
        if self._protocol:
            await self._protocol.send_mcp_message(payload)
