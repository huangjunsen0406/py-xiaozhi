"""协议管理器.

封装通信协议操作，通过事件总线转发消息。
音频数据走直连通道（有界队列 + 单 consumer），避免 per-frame create_task 堆积。
"""

import asyncio
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Coroutine, Optional

from src.constants.constants import ListeningMode
from src.core.event_bus import EventBus, Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.task_manager import TaskManager
    from src.protocols.protocol import Protocol

logger = get_logger()

# 音频回调类型
AudioCallback = Callable[[bytes], Awaitable[None]]

# 入站音频有界队列：满时丢弃最旧帧，防止 event loop 被任务淹没
_INCOMING_AUDIO_QUEUE_SIZE = 64


class ProtocolManager:
    """拥有协议连接、发送门控与有界入站音频队列。"""

    def __init__(
        self,
        event_bus: EventBus,
        task_manager: Optional["TaskManager"] = None,
        *,
        config=None,
        audio_config=None,
    ):
        from src.constants.constants import AudioConfig
        from src.utils.config_manager import ConfigManager

        self.config = config if config is not None else ConfigManager.from_dict()
        self.audio_config = (
            audio_config
            if audio_config is not None
            else AudioConfig.from_config(self.config)
        )
        self._event_bus = event_bus
        self._task_manager = task_manager
        self._protocol: Optional["Protocol"] = None
        self._connect_lock = asyncio.Lock()
        self._shutdown = False
        self._open_generation = 0
        self._incoming_audio_handler: Optional[AudioCallback] = None

        # 有界音频队列 + 单 consumer（替代 per-packet create_task）
        self._audio_queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue(
            maxsize=_INCOMING_AUDIO_QUEUE_SIZE
        )
        self._audio_consumer_task: Optional[asyncio.Task] = None
        self._audio_consumer_running = False
        self._accepting_incoming_audio = True

    def set_task_manager(self, task_manager: "TaskManager") -> None:
        """注入 TaskManager（容器初始化后可再绑定）."""
        self._task_manager = task_manager

    @property
    def protocol(self) -> Optional["Protocol"]:
        return self._protocol

    def set_protocol(self, protocol_type: str) -> None:
        logger.debug(f"设置协议类型: {protocol_type}")

        if protocol_type == "mqtt":
            from src.protocols.mqtt_protocol import MqttProtocol

            self._protocol = MqttProtocol(
                asyncio.get_running_loop(),
                config=self.config,
                audio_config=self.audio_config,
            )
        else:
            from src.protocols.websocket_protocol import WebsocketProtocol

            self._protocol = WebsocketProtocol(
                config=self.config, audio_config=self.audio_config
            )

        self._setup_callbacks()
        self._ensure_audio_consumer()

    def set_audio_handler(self, handler: Optional[AudioCallback]) -> None:
        self._incoming_audio_handler = handler
        self._ensure_audio_consumer()

    def set_idle_checker(self, checker: Callable[[], bool]) -> None:
        if self._protocol:
            self._protocol.set_idle_checker(checker)

    def _setup_callbacks(self) -> None:
        if not self._protocol:
            return

        self._protocol.on_network_error(self._on_network_error)
        self._protocol.on_incoming_json(self._on_incoming_json)
        self._protocol.on_incoming_audio(self._on_incoming_audio)
        self._protocol.on_audio_channel_opened(self._on_audio_channel_opened)
        self._protocol.on_audio_channel_closed(self._on_audio_channel_closed)

    def _spawn(self, coro: Coroutine[Any, Any, Any], name: str) -> None:
        """接管原生协程，优先交给 TaskManager；否则本地创建任务并记录异常."""
        if self._task_manager is not None:
            # spawn 接管协程，包括拒绝或创建失败时的关闭。
            self._task_manager.spawn(coro, name=name)
            return

        try:
            task = asyncio.create_task(coro, name=name)

            def _on_done(t: asyncio.Task) -> None:
                if t.cancelled():
                    return
                exc = t.exception()
                if exc:
                    logger.error(f"任务 {name} 异常结束: {exc}", exc_info=exc)

            task.add_done_callback(_on_done)
        except Exception as e:
            logger.error(f"创建任务失败 {name}: {e}", exc_info=True)
            if asyncio.iscoroutine(coro):
                coro.close()

    def _ensure_audio_consumer(self) -> None:
        """确保入站音频 consumer 在运行（幂等）."""
        if self._audio_consumer_running:
            return
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        self._audio_consumer_running = True
        if self._task_manager is not None:
            self._audio_consumer_task = self._task_manager.spawn(
                self._audio_consumer_loop(), name="protocol:audio_consumer"
            )
        else:
            self._audio_consumer_task = asyncio.create_task(
                self._audio_consumer_loop(), name="protocol:audio_consumer"
            )

        if self._audio_consumer_task is None:
            self._audio_consumer_running = False
            return

        def _on_done(t: asyncio.Task) -> None:
            self._audio_consumer_running = False
            self._audio_consumer_task = None
            if t.cancelled():
                return
            # TaskManager.spawn 已记录异常；本地 create_task 时补日志
            if self._task_manager is None:
                exc = t.exception()
                if exc:
                    logger.error(f"音频 consumer 异常结束: {exc}", exc_info=exc)

        self._audio_consumer_task.add_done_callback(_on_done)

    async def _audio_consumer_loop(self) -> None:
        """单消费者串行处理入站音频，避免 per-frame 任务爆炸."""
        while True:
            data = await self._audio_queue.get()
            try:
                if data is None:
                    return
                if self._incoming_audio_handler:
                    await self._incoming_audio_handler(data)
                else:
                    await self._event_bus.emit(Events.INCOMING_AUDIO, data)
            except Exception as e:
                logger.error(f"处理入站音频失败: {e}", exc_info=True)
            finally:
                self._audio_queue.task_done()

    def discard_incoming_audio(self) -> None:
        """Cancel queued/late downlink until the next TTS start control frame."""
        self._accepting_incoming_audio = False
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
            self._audio_queue.task_done()

    async def wait_for_incoming_audio(self) -> None:
        """Wait for already received Opus frames to reach the playback FIFO."""
        await self._audio_queue.join()

    def _enqueue_audio(self, data: bytes) -> None:
        """有界入队：满则丢最旧帧再放入最新帧."""
        if not self._accepting_incoming_audio:
            return
        try:
            self._audio_queue.put_nowait(data)
            return
        except asyncio.QueueFull:
            pass

        # 丢弃最旧
        try:
            self._audio_queue.get_nowait()
            self._audio_queue.task_done()
        except asyncio.QueueEmpty:
            pass
        try:
            self._audio_queue.put_nowait(data)
        except asyncio.QueueFull:
            logger.warning("入站音频队列仍满，丢弃当前帧")

    async def _stop_audio_consumer(self) -> None:
        """Cancel on shutdown; a concurrent queue clear cannot erase cancellation."""
        task = self._audio_consumer_task
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._audio_consumer_task = None
        self._audio_consumer_running = False
        while not self._audio_queue.empty():
            self._audio_queue.get_nowait()
            self._audio_queue.task_done()

    async def _on_network_error(self, error_message: str = None) -> None:
        self.discard_incoming_audio()
        if error_message:
            logger.error(f"网络错误: {error_message}")
        await self._event_bus.emit(Events.NETWORK_ERROR, error_message)

    def _on_incoming_json(self, json_data: dict) -> None:
        # Open the gate synchronously: binary may arrive before the async
        # session handler has had a chance to process this start message.
        if json_data.get("type") == "tts" and json_data.get("state") == "start":
            self._accepting_incoming_audio = True
        self._spawn(
            self._event_bus.emit(Events.INCOMING_JSON, json_data),
            name="protocol:incoming_json",
        )

    def _on_incoming_audio(self, data: bytes) -> None:
        try:
            self._ensure_audio_consumer()
            self._enqueue_audio(data)
        except Exception as exc:
            logger.warning(f"分发音频数据失败: {exc}", exc_info=True)

    async def _on_audio_channel_opened(self) -> None:
        logger.info("协议通道已打开")
        await self._event_bus.emit(Events.AUDIO_CHANNEL_OPENED)
        await self._event_bus.emit(Events.PROTOCOL_CONNECTED, self._protocol)

    async def _on_audio_channel_closed(self) -> None:
        self.discard_incoming_audio()
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
        if self._shutdown:
            return False
        generation = self._open_generation
        if self.is_audio_channel_opened():
            return True

        if not self._protocol:
            logger.error("协议未初始化")
            return False

        async with self._connect_lock:
            if self._shutdown or generation != self._open_generation:
                return False
            if self.is_audio_channel_opened():
                return True

            # Only the lock owner owns this attempt. Cancellation while waiting
            # for the lock must not close another caller's successful session.
            protocol = self._protocol
            opened = False
            try:
                opened = await asyncio.wait_for(
                    protocol.open_audio_channel(),
                    timeout=timeout,
                )
                if self._shutdown or generation != self._open_generation:
                    opened = False
                if not opened:
                    logger.error("协议连接失败")
                    return False

                logger.info("协议连接已建立")
                return True

            except asyncio.TimeoutError:
                logger.error("协议连接超时")
                return False
            except Exception as e:
                logger.error(f"协议连接异常: {e}", exc_info=True)
                return False
            finally:
                if not opened:
                    try:
                        # Roll back the audio session only; MQTT may retain its
                        # established broker connection across failed opens.
                        await protocol.close_audio_channel()
                    except Exception:
                        logger.exception("清理未完成的协议音频会话失败")

    async def start(self) -> bool:
        """启动协议的常驻控制链路（若该协议需要）。"""
        if self._shutdown or not self._protocol:
            logger.error("协议未初始化或已关闭")
            return False
        try:
            return bool(await self._protocol.start())
        except Exception as e:
            logger.error(f"启动协议控制链路失败: {e}", exc_info=True)
            return False

    async def disconnect(self) -> None:
        """结束当前音频会话，但允许协议复用其控制连接."""
        self._open_generation += 1
        self.discard_incoming_audio()
        if self._protocol:
            try:
                await self._protocol.close_audio_channel()
            except Exception as e:
                logger.error(f"关闭协议失败: {e}", exc_info=True)
        await self._stop_audio_consumer()

    async def shutdown(self) -> None:
        """彻底关闭协议及其后台资源（应用退出路径）."""
        self._shutdown = True
        self._open_generation += 1
        self.discard_incoming_audio()
        if self._protocol:
            try:
                await self._protocol.shutdown()
            except Exception as e:
                logger.error(f"彻底关闭协议失败: {e}", exc_info=True)
        await self._stop_audio_consumer()

    async def send_audio(self, data: bytes) -> bool:
        protocol = self._protocol
        if protocol and self.is_audio_channel_opened():
            return bool(await protocol.send_audio(data))
        else:
            logger.debug("音频通道未打开，跳过发送音频数据")
        return False

    async def send_text(self, text: str) -> bool:
        protocol = self._protocol
        if protocol:
            return bool(await protocol.send_text(text))
        return False

    async def send_start_listening(self, mode: ListeningMode) -> bool:
        protocol = self._protocol
        if protocol and self.is_audio_channel_opened():
            return bool(await protocol.send_start_listening(mode))
        else:
            logger.warning("音频通道未打开，跳过 send_start_listening")
        return False

    async def send_stop_listening(self) -> bool:
        protocol = self._protocol
        if protocol and self.is_audio_channel_opened():
            return bool(await protocol.send_stop_listening())
        else:
            logger.debug("音频通道未打开，跳过 send_stop_listening")
        return False

    async def send_abort_speaking(self, reason: str = None) -> bool:
        protocol = self._protocol
        if protocol:
            return bool(await protocol.send_abort_speaking(reason))
        return False

    async def send_wake_word_detected(self, wake_word: str) -> bool:
        protocol = self._protocol
        if protocol and self.is_audio_channel_opened():
            return bool(await protocol.send_wake_word_detected(wake_word))
        else:
            logger.warning("音频通道未打开，跳过 send_wake_word_detected")
        return False

    async def send_mcp_message(self, payload) -> bool:
        protocol = self._protocol
        if protocol:
            return await protocol.send_mcp_message(payload)
        return False
