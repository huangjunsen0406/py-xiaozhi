"""协议管理器.

封装通信协议操作，通过事件总线转发消息。
音频数据走直连通道以减少延迟和避免 EventBus 背压问题。
"""

import asyncio
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from src.constants.constants import ListeningMode
from src.core.event_bus import EventBus, Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.protocols.protocol import Protocol

logger = get_logger()

# 音频回调类型
AudioCallback = Callable[[bytes], Awaitable[None]]


class ProtocolTransport:
    """负责协议创建与连接管理."""

    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._protocol: Optional["Protocol"] = None
        self._connect_lock = asyncio.Lock()
        self._incoming_audio_handler: Optional[AudioCallback] = None

    @property
    def protocol(self) -> Optional["Protocol"]:
        return self._protocol

    def set_protocol(self, protocol_type: str) -> None:
        logger.debug(f"设置协议类型: {protocol_type}")

        if protocol_type == "mqtt":
            from src.protocols.mqtt_protocol import MqttProtocol

            self._protocol = MqttProtocol(asyncio.get_running_loop())
        else:
            from src.protocols.websocket_protocol import WebsocketProtocol

            self._protocol = WebsocketProtocol()

        self._setup_callbacks()

    def set_audio_handler(self, handler: Optional[AudioCallback]) -> None:
        self._incoming_audio_handler = handler

    def _setup_callbacks(self) -> None:
        if not self._protocol:
            return

        self._protocol.on_network_error(self._on_network_error)
        self._protocol.on_incoming_json(self._on_incoming_json)
        self._protocol.on_incoming_audio(self._on_incoming_audio)
        self._protocol.on_audio_channel_opened(self._on_audio_channel_opened)
        self._protocol.on_audio_channel_closed(self._on_audio_channel_closed)

    async def _on_network_error(self, error_message: str = None) -> None:
        if error_message:
            logger.error(f"网络错误: {error_message}")
        await self._event_bus.emit(Events.NETWORK_ERROR, error_message)

    def _on_incoming_json(self, json_data: dict) -> None:
        asyncio.create_task(self._event_bus.emit(Events.INCOMING_JSON, json_data))

    def _on_incoming_audio(self, data: bytes) -> None:
        if self._incoming_audio_handler:
            try:
                asyncio.create_task(self._incoming_audio_handler(data))
            except Exception as exc:
                logger.warning(f"分发音频数据失败: {exc}")
        else:
            asyncio.create_task(self._event_bus.emit(Events.INCOMING_AUDIO, data))

    async def _on_audio_channel_opened(self) -> None:
        logger.info("协议通道已打开")
        await self._event_bus.emit(Events.AUDIO_CHANNEL_OPENED)
        await self._event_bus.emit(Events.PROTOCOL_CONNECTED, self._protocol)

    async def _on_audio_channel_closed(self) -> None:
        logger.info("协议通道已关闭")
        await self._event_bus.emit(Events.AUDIO_CHANNEL_CLOSED)
        await self._event_bus.emit(Events.PROTOCOL_DISCONNECTED)

    def is_audio_channel_opened(self) -> bool:
        try:
            return bool(self._protocol and self._protocol.is_audio_channel_opened())
        except Exception:
            logger.debug("检查音频通道状态时发生异常", exc_info=True)
            return False

    async def connect(self, timeout: float = 12.0) -> bool:
        if self.is_audio_channel_opened():
            return True

        if not self._protocol:
            logger.error("协议未初始化")
            return False

        async with self._connect_lock:
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
        if self._protocol:
            try:
                await self._protocol.close_audio_channel()
            except Exception as e:
                logger.error(f"关闭协议失败: {e}")


class ProtocolGateway:
    """负责消息发送的网关."""

    def __init__(self, transport: ProtocolTransport):
        self._transport = transport

    async def send_audio(self, data: bytes) -> None:
        protocol = self._transport.protocol
        if protocol and self._transport.is_audio_channel_opened():
            await protocol.send_audio(data)
        else:
            logger.debug("音频通道未打开，跳过发送音频数据")

    async def send_text(self, text: str) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_text(text)

    async def send_start_listening(self, mode: ListeningMode) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_start_listening(mode)

    async def send_stop_listening(self) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_stop_listening()

    async def send_abort_speaking(self, reason: str = None) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_abort_speaking(reason)

    async def send_wake_word_detected(self, wake_word: str) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_wake_word_detected(wake_word)

    async def send_iot_descriptors(self, descriptors) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_iot_descriptors(descriptors)

    async def send_iot_states(self, states) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_iot_states(states)

    async def send_mcp_message(self, payload) -> None:
        protocol = self._transport.protocol
        if protocol:
            await protocol.send_mcp_message(payload)


class ProtocolManager:
    """对外暴露统一接口，内部组合 Transport + Gateway."""

    def __init__(self, event_bus: EventBus):
        self._transport = ProtocolTransport(event_bus)
        self._gateway = ProtocolGateway(self._transport)

    @property
    def protocol(self) -> Optional["Protocol"]:
        return self._transport.protocol

    def set_protocol(self, protocol_type: str) -> None:
        self._transport.set_protocol(protocol_type)

    def set_audio_handler(self, handler: Optional[AudioCallback]) -> None:
        self._transport.set_audio_handler(handler)

    def is_audio_channel_opened(self) -> bool:
        return self._transport.is_audio_channel_opened()

    async def connect(self, timeout: float = 12.0) -> bool:
        return await self._transport.connect(timeout)

    async def disconnect(self) -> None:
        await self._transport.disconnect()

    async def send_audio(self, data: bytes) -> None:
        await self._gateway.send_audio(data)

    async def send_text(self, text: str) -> None:
        await self._gateway.send_text(text)

    async def send_start_listening(self, mode: ListeningMode) -> None:
        await self._gateway.send_start_listening(mode)

    async def send_stop_listening(self) -> None:
        await self._gateway.send_stop_listening()

    async def send_abort_speaking(self, reason: str = None) -> None:
        await self._gateway.send_abort_speaking(reason)

    async def send_wake_word_detected(self, wake_word: str) -> None:
        await self._gateway.send_wake_word_detected(wake_word)

    async def send_iot_descriptors(self, descriptors) -> None:
        await self._gateway.send_iot_descriptors(descriptors)

    async def send_iot_states(self, states) -> None:
        await self._gateway.send_iot_states(states)

    async def send_mcp_message(self, payload) -> None:
        await self._gateway.send_mcp_message(payload)
