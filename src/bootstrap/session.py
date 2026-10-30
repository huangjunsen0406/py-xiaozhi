"""会话控制：听/说状态机与协议发送.

与 UI 侧 SessionActions（按钮文案/模式）分离：这里只负责 connect /
listen / abort / TTS 回环等应用级会话逻辑。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Protocol

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.core.event_bus import Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.protocol_manager import ProtocolManager
    from src.core.state_manager import StateManager
    from src.notifications.notification_player import NotificationPlayer
    from src.utils.config_manager import ConfigManager

logger = get_logger()


class SessionAudio(Protocol):
    @property
    def aec_active(self) -> bool: ...

    async def clear_audio_queue(self) -> None: ...


class ConversationSession:
    """应用级会话控制器."""

    def __init__(
        self,
        state: StateManager,
        protocol: ProtocolManager,
        audio: SessionAudio | None = None,
        event_bus: EventBus | None = None,
        notification_player: NotificationPlayer | None = None,
        config: ConfigManager | None = None,
    ) -> None:
        self.state = state
        self.protocol = protocol
        self.audio = audio
        self.config = config
        self._event_bus = event_bus
        self.audio_generation = 0
        self._listen_start_generation: int | None = None
        self._tts_active = False
        self._tts_generation = 0
        self._notification_player = notification_player
        self._notification_generation = 0
        self._notification_lock = asyncio.Lock()
        self._tts_message_lock = asyncio.Lock()

    def is_speaking(self) -> bool:
        return self._tts_active or self.state.is_speaking()

    def _reset_tts(self) -> None:
        self.audio_generation += 1
        self._tts_generation += 1
        self._tts_active = False

    def set_audio(self, audio: SessionAudio | None) -> None:
        self.audio = audio
        self.audio_generation += 1

    def set_notification_player(self, player: NotificationPlayer | None) -> None:
        """由容器注入 notify 播放服务。"""
        self._notification_player = player

    # -------------------------
    # 事件订阅
    # -------------------------
    def bind_events(self, event_bus: EventBus) -> None:
        self.unbind_events()
        self._event_bus = event_bus
        event_bus.on(Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed)
        event_bus.on(Events.AUDIO_CHANNEL_CLOSED, self._on_audio_channel_closed)
        event_bus.on(Events.INCOMING_JSON, self._on_incoming_json)
        event_bus.on(Events.NETWORK_ERROR, self._on_network_error)
        event_bus.on(
            Events.PROTOCOL_RECONNECT_REQUEST, self._on_protocol_reconnect_request
        )

    def unbind_events(self) -> None:
        if self._event_bus is None:
            return
        for event, handler in (
            (Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed),
            (Events.AUDIO_CHANNEL_CLOSED, self._on_audio_channel_closed),
            (Events.INCOMING_JSON, self._on_incoming_json),
            (Events.NETWORK_ERROR, self._on_network_error),
            (Events.PROTOCOL_RECONNECT_REQUEST, self._on_protocol_reconnect_request),
        ):
            self._event_bus.off(event, handler)

    # -------------------------
    # 事件处理器
    # -------------------------
    async def _on_audio_codec_changed(self, audio: SessionAudio | None = None) -> None:
        self.set_audio(audio)

    async def _on_audio_channel_closed(self, _=None) -> None:
        self._reset_tts()
        self.state.set_keep_listening(False)
        await self._cancel_notification()
        await self.state.set_device_state(DeviceState.IDLE)

    async def _on_network_error(self, error_message: str = None) -> None:
        """网络错误：停止持续监听并复位设备状态到 IDLE."""
        self._reset_tts()
        self.state.set_keep_listening(False)
        await self._cancel_notification()
        try:
            if not self.state.is_idle():
                await self.state.set_device_state(DeviceState.IDLE)
        except Exception as e:
            logger.error(f"网络错误后复位设备状态失败: {e}", exc_info=True)

    async def _on_incoming_json(self, json_data: dict) -> None:
        if isinstance(json_data, dict) and json_data.get("type") == "tts":
            async with self._tts_message_lock:
                await self._dispatch_message(json_data)
        else:
            await self._dispatch_message(json_data)

    async def _dispatch_message(self, json_data: dict) -> None:
        try:
            msg_type = json_data.get("type") if isinstance(json_data, dict) else None
            logger.info(f"收到JSON消息: type={msg_type}")

            if msg_type == "tts":
                state = json_data.get("state")
                if state == "start":
                    await self._handle_tts_start()
                elif state == "stop":
                    await self._handle_tts_stop()
            elif msg_type == "notify":
                await self._handle_notify(json_data)

            if self._event_bus is not None:
                await self._event_bus.emit_sequential(Events.SESSION_MESSAGE, json_data)

        except Exception as e:
            logger.error(f"处理 JSON 消息失败: {e}", exc_info=True)

    async def sync_audio_state(self, *, update_protocol: bool = True) -> bool:
        """同步实际 AEC 状态，返回本次检查时是否允许上传音频。"""
        active = bool(self.audio and self.audio.aec_active)
        self.state.set_aec_enabled(active)
        capture_allowed = self.state.should_capture_audio() and (
            active or not self._tts_active
        )
        if active or self.state.listening_mode != ListeningMode.REALTIME:
            return capture_allowed

        self.state.set_listening_mode(ListeningMode.AUTO_STOP)
        generation = self._tts_generation
        if self._tts_active:
            # 必须先关闭上行门闩，再 await 网络操作。
            await self.state.set_device_state(DeviceState.SPEAKING)
        if generation != self._tts_generation:
            return False
        logger.warning("AEC 不可用，实时对话已降级为自动停止监听")
        if (
            update_protocol
            and self.state.keep_listening
            and self.protocol.is_audio_channel_opened()
        ):
            generation = self.audio_generation
            try:
                if self._tts_active:
                    await self.protocol.send_stop_listening()
                elif not await self.protocol.send_start_listening(
                    ListeningMode.AUTO_STOP
                ):
                    return await self._fail_listening(generation)
            except Exception as e:
                logger.warning("同步半双工监听模式失败: %s", e, exc_info=True)
                if not self._tts_active:
                    return await self._fail_listening(generation)
                return False
        return capture_allowed

    async def _handle_tts_start(self) -> None:
        self.audio_generation += 1
        self._tts_generation += 1
        generation = self._tts_generation
        self._tts_active = True
        await self._cancel_notification()
        if generation != self._tts_generation:
            return
        await self.sync_audio_state()
        if generation != self._tts_generation:
            return
        if (
            self.state.keep_listening
            and self.state.listening_mode == ListeningMode.REALTIME
        ):
            await self.state.set_device_state(DeviceState.LISTENING)
        else:
            await self.state.set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self) -> None:
        if not self._tts_active:
            return
        self._reset_tts()
        generation = self._tts_generation
        await self.sync_audio_state(update_protocol=False)
        # 还要继续听的话，尽量先发 listen，再清队列、改状态
        if not self.state.keep_listening:
            await self.state.set_device_state(DeviceState.IDLE)
            return

        # realtime 一般还在 listen 里，不用再发一遍。
        if self.state.listening_mode != ListeningMode.REALTIME:
            resumed = False
            if self.protocol.is_audio_channel_opened():
                try:
                    resumed = await self.protocol.send_start_listening(
                        self.state.listening_mode
                    )
                except Exception as e:
                    logger.warning(f"TTS 结束后重新 listen 失败: {e}", exc_info=True)
            else:
                logger.warning("TTS 结束但协议通道已关闭，跳过重新 listen")
            if generation != self._tts_generation:
                return
            if not resumed:
                await self._fail_listening(self.audio_generation)
                return

        if generation != self._tts_generation:
            return
        try:
            if self.audio:
                await self.audio.clear_audio_queue()
        except Exception as e:
            logger.warning(f"清空音频队列失败: {e}", exc_info=True)

        if generation == self._tts_generation:
            await self.state.set_device_state(DeviceState.LISTENING)

    async def _handle_notify(self, message: dict) -> None:
        """仅在空闲时接收服务端单向音频通知。"""
        player = self._notification_player
        if player is None:
            logger.debug("未配置 NotificationPlayer，忽略 notify")
            return

        from src.notifications.notification_player import parse_notification

        parsed = parse_notification(message)
        if parsed is None:
            logger.warning("忽略格式无效的 notify 消息")
            return
        audio_url, subtitles = parsed

        async with self._notification_lock:
            if not self.state.is_idle():
                logger.info("设备忙碌，忽略 notify")
                return

            generation = None
            try:
                await self.state.set_device_state(DeviceState.NOTIFYING)
                generation = await player.start(
                    audio_url,
                    subtitles,
                    self._on_notification_finished,
                )
            finally:
                if generation is None and self._is_notifying():
                    await self.state.set_device_state(DeviceState.IDLE)
            if generation is None:
                return
            self._notification_generation = generation
            logger.info("开始播放服务端通知: %s", audio_url)

    async def _on_notification_finished(self, generation: int, success: bool) -> None:
        async with self._notification_lock:
            if generation != self._notification_generation:
                return
            self._notification_generation = 0
            if self._is_notifying():
                await self.state.set_device_state(DeviceState.IDLE)
            logger.info("通知播放%s", "完成" if success else "失败")

    def _is_notifying(self) -> bool:
        return getattr(self.state, "device_state", None) == DeviceState.NOTIFYING

    async def _cancel_notification(self) -> None:
        """打断 notify；调用方随后可进入 listen / TTS / idle。"""
        player = self._notification_player
        if player is None:
            return
        async with self._notification_lock:
            if not player.is_active and not self._is_notifying():
                return
            self._notification_generation = 0
            await player.stop()
            if self._is_notifying():
                await self.state.set_device_state(DeviceState.IDLE)

    # -------------------------
    # 操作方法
    # -------------------------
    async def connect_protocol(self) -> bool:
        if self.protocol.is_audio_channel_opened():
            return True

        return await self.protocol.connect()

    async def _on_protocol_reconnect_request(self, _=None) -> None:
        """设置保存后 MCP 工具列表变更：已连接则断开并重连，便于服务端重新 list.

        仅刷新协议/工具视图，不恢复聆听会话（避免保存设置后进入「聆听中」）。
        """
        if not self.protocol.is_audio_channel_opened():
            return
        self._reset_tts()
        self.state.set_keep_listening(False)
        self.state.set_aborted(False)
        await self._cancel_notification()
        await self.protocol.disconnect()
        await self.state.set_device_state(DeviceState.IDLE)
        await self.connect_protocol()

    async def _fail_listening(self, generation: int) -> bool:
        if generation == self.audio_generation:
            self.state.set_keep_listening(False)
            self.state.set_aborted(False)
            await self.state.set_device_state(DeviceState.IDLE)
        return False

    async def start_listening(self, mode: ListeningMode) -> bool:
        was_speaking = self.is_speaking()
        self._reset_tts()
        generation = self.audio_generation
        self._listen_start_generation = generation
        try:
            self.state.set_aborted(True)
            await self._cancel_notification()
            if generation != self.audio_generation:
                return False
            opened = await self.connect_protocol()
            if generation != self.audio_generation:
                return False
            if not opened:
                return await self._fail_listening(generation)
            if was_speaking:
                aborted = await self.protocol.send_abort_speaking(None)
                if generation != self.audio_generation:
                    return False
                if self.audio:
                    await self.audio.clear_audio_queue()
                if not aborted:
                    return await self._fail_listening(generation)
            await self.sync_audio_state(update_protocol=False)
            if generation != self.audio_generation:
                return False
            if mode == ListeningMode.REALTIME and not self.state.aec_enabled:
                mode = ListeningMode.AUTO_STOP
            self.state.set_listening_mode(mode)
            self.state.set_keep_listening(mode != ListeningMode.MANUAL)
            sent = await self.protocol.send_start_listening(mode)
            if generation != self.audio_generation:
                return False
            if not sent:
                return await self._fail_listening(generation)
            self.state.set_aborted(False)
            await self.state.set_device_state(DeviceState.LISTENING)
            return generation == self.audio_generation
        finally:
            if self._listen_start_generation == generation:
                self._listen_start_generation = None

    async def stop_listening(self) -> None:
        was_speaking = self.is_speaking()
        self._reset_tts()
        self.state.set_keep_listening(False)
        self.state.set_aborted(False)
        await self.state.set_device_state(DeviceState.IDLE)
        await self._cancel_notification()
        try:
            await self.protocol.send_stop_listening()
        finally:
            if was_speaking:
                try:
                    await self.protocol.send_abort_speaking(
                        AbortReason.USER_INTERRUPTION
                    )
                finally:
                    if self.audio:
                        await self.audio.clear_audio_queue()

    async def start_listening_manual(self) -> bool:
        return await self.start_listening(ListeningMode.MANUAL)

    async def stop_listening_manual(self) -> None:
        await self.stop_listening()

    async def start_auto_conversation(self) -> bool:
        enabled = self.config is None or bool(
            self.config.get_config("AEC_OPTIONS.ENABLED", True)
        )
        mode = ListeningMode.REALTIME if enabled else ListeningMode.AUTO_STOP
        return await self.start_listening(mode)

    async def send_user_text(
        self, text: str, mode: ListeningMode = ListeningMode.MANUAL
    ) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        if self.is_speaking():
            generation = self.audio_generation
            await self.abort_speaking(AbortReason.USER_INTERRUPTION)
            if self.audio_generation != generation + 1:
                return False
        started_here = self.state.device_state not in (
            DeviceState.LISTENING,
            DeviceState.SPEAKING,
        )
        if started_here:
            started = (
                await self.start_auto_conversation()
                if mode == ListeningMode.REALTIME
                else await self.start_listening(mode)
            )
            if not started:
                return False
        generation = self.audio_generation
        sent = await self.protocol.send_wake_word_detected(text)
        if generation != self.audio_generation:
            return False
        if not sent and started_here:
            await self.stop_listening()
        return bool(sent)

    async def wake(self) -> None:
        if self.is_speaking():
            await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
        else:
            await self.start_auto_conversation()

    async def abort_speaking(self, reason: str) -> None:
        if self._listen_start_generation == self.audio_generation:
            # start_listening mutes capture with aborted=True while preparing;
            # a user cancellation here is not a duplicate speaking abort.
            await self.stop_listening()
            return
        if self._is_notifying():
            await self._cancel_notification()
            return
        # 自动对话还在持续听时，打断后回到 listening，别停在 idle
        if self.state.aborted:
            logger.debug(f"已经中止，忽略重复请求: {reason}")
            return

        logger.info(f"中止语音输出: {reason}")
        self._reset_tts()
        generation = self.audio_generation
        self.state.set_aborted(True)
        sent = False
        try:
            if self.protocol.is_audio_channel_opened():
                sent = await self.protocol.send_abort_speaking(reason)
        except Exception as e:
            logger.warning(f"发送 abort 失败: {e}", exc_info=True)
        if generation != self.audio_generation:
            return
        if self.audio:
            try:
                await self.audio.clear_audio_queue()
            except Exception as e:
                logger.warning(f"清空中止语音队列失败: {e}", exc_info=True)
        if generation != self.audio_generation:
            return
        if not sent:
            await self._fail_listening(generation)
            return

        if self.state.keep_listening:
            resumed = self.protocol.is_audio_channel_opened()
            if self.state.listening_mode != ListeningMode.REALTIME and resumed:
                try:
                    resumed = await self.protocol.send_start_listening(
                        self.state.listening_mode
                    )
                except Exception as e:
                    resumed = False
                    logger.warning(f"打断后重新 listen 失败: {e}", exc_info=True)
            if generation != self.audio_generation:
                return
            if not resumed:
                await self._fail_listening(generation)
                return
            await self.state.set_device_state(DeviceState.LISTENING)
            if generation == self.audio_generation:
                self.state.set_aborted(False)
                logger.debug("打断后已恢复持续监听")
        else:
            await self.state.set_device_state(DeviceState.IDLE)
