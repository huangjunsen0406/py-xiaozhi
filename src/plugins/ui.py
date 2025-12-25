"""UI 插件.

管理 CLI/GUI 显示界面。
"""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import AbortReason, DeviceState
from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class UIPlugin(Plugin):
    """UI 插件 - 管理 CLI/GUI 显示"""

    name = "ui"
    priority = 60  # UI 需要在其他插件完成后初始化

    STATE_TEXT_MAP = {
        DeviceState.IDLE: "待命",
        DeviceState.LISTENING: "聆听中...",
        DeviceState.SPEAKING: "说话中...",
    }

    def __init__(self, mode: Optional[str] = None) -> None:
        super().__init__()
        self.mode = (mode or "cli").lower()
        self.display = None
        self._is_gui = False
        self.is_first = True

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self.display = self._create_display()

    def _create_display(self):
        """
        根据模式创建 display 实例，并注入 EventBus.
        """
        if self.mode == "gui":
            from src.views.main import GuiMain

            self._is_gui = True
            return GuiMain(event_bus=self._ctx.event_bus)
        else:
            from src.views.main import CliMain

            self._is_gui = False
            return CliMain(event_bus=self._ctx.event_bus)

    async def start(self) -> None:
        if not self.display:
            return

        # 订阅音乐事件
        from src.core.event_bus import Events

        self._ctx.event_bus.on(Events.MUSIC_STATE_CHANGED, self._on_music_state_changed)
        self._ctx.event_bus.on(Events.MUSIC_LYRICS_UPDATE, self._on_music_lyrics_update)
        logger.info("UIPlugin 已订阅音乐事件")

        # 订阅用户操作事件（从 View 发出）
        self._ctx.event_bus.on(Events.UI_BUTTON_PRESS, self._press)
        self._ctx.event_bus.on(Events.UI_BUTTON_RELEASE, self._release)
        self._ctx.event_bus.on(Events.UI_AUTO_TOGGLE, self._auto_toggle)
        self._ctx.event_bus.on(Events.UI_ABORT_REQUEST, self._abort)
        self._ctx.event_bus.on(Events.UI_SEND_TEXT, self._send_text_from_event)
        self._ctx.event_bus.on(Events.UI_QUIT_REQUEST, self._request_shutdown)
        logger.info("UIPlugin 已订阅 UI 用户操作事件")

        self._cmd.spawn(self.display.start(), name=f"ui:{self.mode}:start")

    async def on_incoming_json(self, message) -> None:
        if not isinstance(message, dict):
            return

        from src.core.event_bus import Events
        from src.views.events import UIEmotionUpdate, UITextUpdate

        msg_type = message.get("type")

        if msg_type in ("tts", "stt"):
            if text := message.get("text"):
                await self._ctx.event_bus.emit(Events.UI_UPDATE_TEXT, UITextUpdate(text=text))
        elif msg_type == "llm":
            if emotion := message.get("emotion"):
                await self._ctx.event_bus.emit(
                    Events.UI_UPDATE_EMOTION, UIEmotionUpdate(emotion=emotion)
                )

    async def on_device_state_changed(self, state) -> None:
        if self.is_first:
            self.is_first = False
            return

        from src.core.event_bus import Events
        from src.views.events import UIEmotionUpdate, UIStatusUpdate

        # 更新表情为 neutral
        await self._ctx.event_bus.emit(Events.UI_UPDATE_EMOTION, UIEmotionUpdate(emotion="neutral"))

        # 更新状态文本
        if status_text := self.STATE_TEXT_MAP.get(state):
            await self._ctx.event_bus.emit(
                Events.UI_UPDATE_STATUS, UIStatusUpdate(status=status_text, connected=True)
            )

    async def shutdown(self) -> None:
        if self.display:
            # 取消订阅所有事件
            try:
                from src.core.event_bus import Events

                # 取消订阅音乐事件
                self._ctx.event_bus.off(
                    Events.MUSIC_STATE_CHANGED, self._on_music_state_changed
                )
                self._ctx.event_bus.off(
                    Events.MUSIC_LYRICS_UPDATE, self._on_music_lyrics_update
                )

                # 取消订阅 UI 用户操作事件
                self._ctx.event_bus.off(Events.UI_BUTTON_PRESS, self._press)
                self._ctx.event_bus.off(Events.UI_BUTTON_RELEASE, self._release)
                self._ctx.event_bus.off(Events.UI_AUTO_TOGGLE, self._auto_toggle)
                self._ctx.event_bus.off(Events.UI_ABORT_REQUEST, self._abort)
                self._ctx.event_bus.off(Events.UI_SEND_TEXT, self._send_text_from_event)
                self._ctx.event_bus.off(Events.UI_QUIT_REQUEST, self._request_shutdown)

                logger.info("UIPlugin 已取消订阅所有事件")
            except Exception as e:
                logger.warning(f"取消订阅事件失败: {e}")

            await self.display.close()
            self.display = None

    # ===== 回调函数 =====

    async def _request_shutdown(self):
        """
        请求应用关闭.
        """
        self._cmd.request_shutdown()

    async def _send_text_from_event(self, data):
        """
        从事件数据中提取文本并发送.
        """
        from src.views.events import UISendTextRequest

        if isinstance(data, UISendTextRequest):
            text = data.text
        elif isinstance(data, dict):
            text = data.get("text", "")
        elif isinstance(data, str):
            text = data
        else:
            logger.warning(f"无效的发送文本数据: {type(data)}")
            return

        await self._send_text(text)

    async def _send_text(self, text: str):
        """
        发送文本到服务端.
        """
        if self._ctx.is_speaking():
            await self._cmd.abort_speaking(None)
        if await self._cmd.connect_protocol():
            await self._cmd.send_wake_word_detected(text)

    async def _press(self):
        """
        手动模式：按下开始录音.
        """
        await self._cmd.connect_protocol()
        from src.constants.constants import ListeningMode

        await self._cmd.start_listening(ListeningMode.MANUAL)

    async def _release(self):
        """
        手动模式：释放停止录音.
        """
        await self._cmd.stop_listening()

    async def _auto_toggle(self):
        """
        自动模式切换.
        """
        await self._cmd.connect_protocol()
        from src.constants.constants import ListeningMode

        mode = (
            ListeningMode.REALTIME
            if self._ctx.get_config().get_config("AEC_OPTIONS.ENABLED", True)
            else ListeningMode.AUTO_STOP
        )
        await self._cmd.start_listening(mode)

    async def _abort(self):
        """
        中断对话.
        """
        await self._cmd.abort_speaking(AbortReason.USER_INTERRUPTION)

    # ===== 音乐事件处理器 =====

    async def _on_music_state_changed(self, data):
        """处理音乐状态变化事件.

        Args:
            data: MusicStateData 实例
        """
        try:
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicStateData
            from src.views.events import UITextUpdate

            if not isinstance(data, MusicStateData):
                logger.warning(f"收到非法的音乐状态数据: {type(data)}")
                return

            state_text_map = {
                "playing": f"正在播放: {data.song}",
                "paused": f"已暂停: {data.song}",
                "stopped": f"已停止: {data.song}",
                "completed": f"播放完成: {data.song}",
            }

            if text := state_text_map.get(data.state):
                await self._ctx.event_bus.emit(Events.UI_UPDATE_TEXT, UITextUpdate(text=text))
                logger.debug(f"UI 更新音乐状态: {data.state}")
        except Exception as e:
            logger.error(f"处理音乐状态变化失败: {e}", exc_info=True)

    async def _on_music_lyrics_update(self, data):
        """处理歌词更新事件.

        Args:
            data: MusicLyricsData 实例
        """
        try:
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicLyricsData
            from src.views.events import UITextUpdate

            if not isinstance(data, MusicLyricsData):
                logger.warning(f"收到非法的歌词数据: {type(data)}")
                return

            await self._ctx.event_bus.emit(Events.UI_UPDATE_TEXT, UITextUpdate(text=data.text))
        except Exception as e:
            logger.error(f"处理歌词更新失败: {e}", exc_info=True)
