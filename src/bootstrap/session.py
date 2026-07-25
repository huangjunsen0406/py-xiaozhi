"""会话控制：听/说状态机与协议发送.

与 UI 侧 SessionActions（按钮文案/模式）分离：这里只负责 connect /
listen / abort / TTS 回环等应用级会话逻辑。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import Events
from src.logging import get_logger

if TYPE_CHECKING:
    from src.core.event_bus import EventBus
    from src.core.protocol_manager import ProtocolManager
    from src.core.state_manager import StateManager
    from src.plugins.manager import PluginManager

logger = get_logger()


class ConversationSession:
    """应用级会话控制器."""

    def __init__(
        self,
        state: "StateManager",
        protocol: "ProtocolManager",
        plugins: "PluginManager",
        event_bus: Optional["EventBus"] = None,
    ) -> None:
        self.state = state
        self.protocol = protocol
        self.plugins = plugins
        self._event_bus = event_bus
        self._aborted = False
        # MCP 工具配置重连等：通道打开后保持 IDLE，不自动进入聆听
        self._keep_idle_on_channel_open = False

    # -------------------------
    # 事件订阅
    # -------------------------
    def bind_events(self, event_bus: "EventBus") -> None:
        """订阅协议/状态相关事件（可重复调用，以最后一次为准）."""
        self._event_bus = event_bus
        event_bus.on(Events.AUDIO_CHANNEL_OPENED, self._on_audio_channel_opened)
        event_bus.on(Events.AUDIO_CHANNEL_CLOSED, self._on_audio_channel_closed)
        event_bus.on(Events.INCOMING_JSON, self._on_incoming_json)
        # 注意：INCOMING_AUDIO 走直连通道，不再通过 EventBus
        event_bus.on(Events.NETWORK_ERROR, self._on_network_error)
        event_bus.on(Events.DEVICE_STATE_CHANGED, self._on_device_state_changed)
        event_bus.on(
            Events.PROTOCOL_RECONNECT_REQUEST, self._on_protocol_reconnect_request
        )

    # -------------------------
    # 事件处理器
    # -------------------------
    async def _on_audio_channel_opened(self, _=None) -> None:
        if self._keep_idle_on_channel_open:
            self._keep_idle_on_channel_open = False
            self.state.set_keep_listening(False)
            await self.state.set_device_state(DeviceState.IDLE)
            logger.info("协议通道已打开（配置重连）：保持空闲，不进入聆听")
            return
        await self.state.set_device_state(DeviceState.LISTENING)

    async def _on_audio_channel_closed(self, _=None) -> None:
        await self.state.set_device_state(DeviceState.IDLE)

    async def _on_network_error(self, error_message: str = None) -> None:
        """网络错误：停止持续监听并复位设备状态到 IDLE."""
        self.state.set_keep_listening(False)
        try:
            if not self.state.is_idle():
                await self.state.set_device_state(DeviceState.IDLE)
        except Exception as e:
            logger.error(f"网络错误后复位设备状态失败: {e}", exc_info=True)

    async def _on_device_state_changed(self, data: dict) -> None:
        new_state = data.get("new_state")
        if new_state:
            await self.plugins.notify_device_state_changed(new_state)
            if new_state == DeviceState.LISTENING:
                self._aborted = False

    async def _on_incoming_json(self, json_data: dict) -> None:
        try:
            msg_type = json_data.get("type") if isinstance(json_data, dict) else None
            logger.info(f"收到JSON消息: type={msg_type}")

            if msg_type == "tts":
                state = json_data.get("state")
                if state == "start":
                    await self._handle_tts_start()
                elif state == "stop":
                    await self._handle_tts_stop()

            await self.plugins.notify_incoming_json(json_data)

        except Exception as e:
            logger.error(f"处理 JSON 消息失败: {e}", exc_info=True)

    async def _handle_tts_start(self) -> None:
        if (
            self.state.keep_listening
            and self.state.listening_mode == ListeningMode.REALTIME
        ):
            await self.state.set_device_state(DeviceState.LISTENING)
        else:
            await self.state.set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self) -> None:
        # 还要继续听的话，尽量先发 listen，再清队列、改状态
        if not self.state.keep_listening:
            await self.state.set_device_state(DeviceState.IDLE)
            return

        # realtime 一般还在 listen 里，不用再发一遍
        if self.state.listening_mode != ListeningMode.REALTIME:
            if self.protocol.is_audio_channel_opened():
                try:
                    await self.protocol.send_start_listening(self.state.listening_mode)
                except Exception as e:
                    logger.warning(
                        f"TTS 结束后重新 listen 失败: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning("TTS 结束但协议通道已关闭，跳过重新 listen")

        try:
            audio_plugin = self.plugins.get_plugin("audio")
            if audio_plugin and audio_plugin.codec:
                await audio_plugin.codec.clear_audio_queue()
        except Exception as e:
            logger.warning(f"清空音频队列失败: {e}", exc_info=True)

        await self.state.set_device_state(DeviceState.LISTENING)

    # -------------------------
    # 操作方法
    # -------------------------
    async def connect_protocol(self) -> bool:
        if self.protocol.is_audio_channel_opened():
            return True

        opened = await self.protocol.connect()
        if opened:
            await self.plugins.notify_protocol_connected(self.protocol.protocol)
        return opened

    async def _on_protocol_reconnect_request(self, _=None) -> None:
        """设置保存后 MCP 工具列表变更：已连接则断开并重连，便于服务端重新 list.

        仅刷新协议/工具视图，不恢复聆听会话（避免保存设置后进入「聆听中」）。
        """
        try:
            if not self.protocol.is_audio_channel_opened():
                logger.info("MCP 工具配置已更新（当前未连接，下次连接生效）")
                return
            logger.info("MCP 工具配置已更新，正在重连协议…")
            # 打断进行中的听/说语义，避免重连后沿用 keep_listening
            self.state.set_keep_listening(False)
            self._aborted = False
            self._keep_idle_on_channel_open = True
            try:
                await self.protocol.disconnect()
                ok = await self.connect_protocol()
            except Exception:
                self._keep_idle_on_channel_open = False
                raise
            if ok:
                # 双保险：若 OPENED 回调顺序异常，仍拉回空闲
                if not self.state.is_idle():
                    await self.state.set_device_state(DeviceState.IDLE)
                logger.info("协议重连成功（新 tools/list 将在握手时生效，保持空闲）")
            else:
                self._keep_idle_on_channel_open = False
                logger.warning("协议重连失败，请手动重新连接")
        except Exception as e:
            self._keep_idle_on_channel_open = False
            logger.error(f"协议重连失败: {e}", exc_info=True)

    async def start_listening(self, mode: ListeningMode) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        self.state.set_listening_mode(mode)
        self.state.set_keep_listening(mode != ListeningMode.MANUAL)
        await self.protocol.send_start_listening(mode)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def stop_listening(self) -> None:
        self.state.set_keep_listening(False)
        await self.protocol.send_stop_listening()
        await self.state.set_device_state(DeviceState.IDLE)

    async def start_listening_manual(self) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        self.state.set_keep_listening(False)

        if self.state.is_speaking():
            logger.info("说话中发送打断")
            await self.protocol.send_abort_speaking(None)
            await self.state.set_device_state(DeviceState.IDLE)

        await self.protocol.send_start_listening(ListeningMode.MANUAL)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def stop_listening_manual(self) -> None:
        await self.protocol.send_stop_listening()
        await self.state.set_device_state(DeviceState.IDLE)

    async def start_auto_conversation(self) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        mode = (
            ListeningMode.REALTIME
            if self.state.aec_enabled
            else ListeningMode.AUTO_STOP
        )
        self.state.set_listening_mode(mode)
        self.state.set_keep_listening(True)

        await self.protocol.send_start_listening(mode)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def abort_speaking(self, reason: str) -> None:
        # 自动对话还在持续听时，打断后回到 listening，别停在 idle
        if self._aborted:
            logger.debug(f"已经中止，忽略重复请求: {reason}")
            return

        logger.info(f"中止语音输出: {reason}")
        self._aborted = True
        self.state.set_aborted(True)
        try:
            if self.protocol.is_audio_channel_opened():
                await self.protocol.send_abort_speaking(reason)
        except Exception as e:
            logger.warning(f"发送 abort 失败: {e}", exc_info=True)

        if self.state.keep_listening:
            if self.state.listening_mode != ListeningMode.REALTIME:
                if self.protocol.is_audio_channel_opened():
                    try:
                        await self.protocol.send_start_listening(
                            self.state.listening_mode
                        )
                    except Exception as e:
                        logger.warning(
                            f"打断后重新 listen 失败: {e}",
                            exc_info=True,
                        )
            await self.state.set_device_state(DeviceState.LISTENING)
            self._aborted = False
            self.state.set_aborted(False)
            logger.debug("打断后已恢复持续监听")
        else:
            await self.state.set_device_state(DeviceState.IDLE)
