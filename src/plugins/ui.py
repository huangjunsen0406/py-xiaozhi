"""UI 插件.

管理 CLI/GUI 显示界面。通过 ViewManager facade 更新 UI，不触达 main_model 私有字段。
"""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import AbortReason, DeviceState
from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.core.task_manager import TaskManager

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

    def __init__(
        self,
        mode: Optional[str] = None,
        task_manager: Optional["TaskManager"] = None,
    ) -> None:
        super().__init__()
        self.mode = (mode or "cli").lower()
        self._task_manager = task_manager
        self.view_manager = None
        self.is_first = True
        self._manual_recording = False  # 手动录音状态

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self._create_view_manager()

    def _create_view_manager(self):
        """创建 ViewManager 实例（注入容器 TaskManager）."""
        if self.mode == "gui":
            from src.ui.gui import ViewManager

            self.view_manager = ViewManager(
                event_bus=self._ctx.event_bus,
                task_manager=self._task_manager,
            )
        elif self.mode == "gpio":
            # GPIO 模式：仅支持 Linux（树莓派）
            from src.ui.gpio import GPIOViewManager

            self.view_manager = GPIOViewManager(
                event_bus=self._ctx.event_bus,
                task_manager=self._task_manager,
            )
            logger.info("GPIO 模式，使用 GPIOViewManager")
        else:
            # CLI 模式使用 CLIViewManager
            from src.ui.cli import CLIViewManager

            self.view_manager = CLIViewManager(
                event_bus=self._ctx.event_bus,
                task_manager=self._task_manager,
            )
            logger.info("CLI 模式，使用 CLIViewManager")

    def _view_set_tts_text(self, text: str) -> None:
        if self.view_manager:
            self.view_manager.set_tts_text(text)

    def _view_set_emotion(self, emotion: str) -> None:
        if self.view_manager:
            self.view_manager.set_emotion(emotion)

    def _view_set_status(self, status: str, connected: bool = True) -> None:
        if self.view_manager:
            self.view_manager.set_status(status, connected)

    def _view_set_button_text(self, text: str) -> None:
        if not self.view_manager:
            return
        # CLI/GPIO 可能无按钮文案 API
        setter = getattr(self.view_manager, "set_button_text", None)
        if callable(setter):
            setter(text)

    def _view_toggle_auto_mode(self) -> bool:
        """切换自动模式，返回切换后是否为自动."""
        if not self.view_manager:
            return False
        if hasattr(self.view_manager, "toggle_auto_mode"):
            result = self.view_manager.toggle_auto_mode()
            if isinstance(result, bool):
                return result
        if hasattr(self.view_manager, "is_auto_mode"):
            return bool(self.view_manager.is_auto_mode())
        # 兼容旧 CLI：读 _auto_mode
        return bool(getattr(self.view_manager, "_auto_mode", False))

    async def start(self) -> None:
        # 订阅事件
        from src.core.event_bus import Events

        self._ctx.event_bus.on(Events.NETWORK_ERROR, self._on_network_error)
        self._ctx.event_bus.on(Events.MUSIC_STATE_CHANGED, self._on_music_state_changed)
        self._ctx.event_bus.on(Events.MUSIC_LYRICS_UPDATE, self._on_music_lyrics_update)
        logger.info("UIPlugin 已订阅音乐事件")

        # 订阅用户操作事件（从 View 发出）
        self._ctx.event_bus.on(Events.UI_BUTTON_PRESS, self._press)
        self._ctx.event_bus.on(Events.UI_BUTTON_RELEASE, self._release)
        self._ctx.event_bus.on(Events.UI_MANUAL_TOGGLE, self._manual_toggle)
        self._ctx.event_bus.on(Events.UI_AUTO_TOGGLE, self._auto_toggle)
        self._ctx.event_bus.on(Events.UI_AUTO_START, self._auto_start)
        self._ctx.event_bus.on(Events.UI_ABORT_REQUEST, self._abort)
        self._ctx.event_bus.on(Events.UI_SEND_TEXT, self._send_text_from_event)
        self._ctx.event_bus.on(Events.UI_QUIT_REQUEST, self._request_shutdown)
        logger.info("UIPlugin 已订阅 UI 用户操作事件")

        # 启动 ViewManager
        if self.view_manager:
            self._cmd.spawn(
                self.view_manager.start(mode=self.mode),
                name=f"ui:{self.mode}:start",
            )

    async def on_incoming_json(self, message) -> None:
        if not isinstance(message, dict):
            return

        msg_type = message.get("type")

        if msg_type in ("tts", "stt"):
            if text := message.get("text"):
                self._view_set_tts_text(text)
        elif msg_type == "llm":
            if emotion := message.get("emotion"):
                self._view_set_emotion(emotion)

    async def on_device_state_changed(self, state) -> None:
        if self.is_first:
            self.is_first = False
            return

        if not self.view_manager:
            return

        # 如果状态不是 LISTENING，重置手动录音标志
        if state != DeviceState.LISTENING and self._manual_recording:
            self._manual_recording = False
            self._view_set_button_text("按住后说话")

        # 更新状态文本
        if status_text := self.STATE_TEXT_MAP.get(state):
            self._view_set_emotion("neutral")
            self._view_set_status(status_text, connected=True)

    async def _on_network_error(self, error_message: str = None) -> None:
        """处理网络错误事件，更新 UI 状态."""
        self._view_set_status("未连接", connected=False)

    def register_resources(self, pool) -> None:
        view_manager = self.view_manager
        if view_manager:
            pool.register("ui.view_manager", view_manager.close)

    # ===== 回调函数 =====

    async def _request_shutdown(self):
        """请求应用关闭."""
        self._cmd.request_shutdown()

    async def _send_text_from_event(self, data):
        """从事件数据中提取文本并发送."""
        if hasattr(data, "text"):
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
        """发送文本到服务端."""
        if self._ctx.is_speaking():
            await self._cmd.abort_speaking(None)
        if await self._cmd.connect_protocol():
            await self._cmd.send_wake_word_detected(text)

    async def _press(self):
        """手动模式：按下开始录音."""
        await self._cmd.connect_protocol()
        from src.constants.constants import ListeningMode

        await self._cmd.start_listening(ListeningMode.MANUAL)

    async def _release(self):
        """手动模式：释放停止录音."""
        await self._cmd.stop_listening()

    async def _manual_toggle(self):
        """手动模式：切换录音状态（点击开始/停止）."""

        if not self._manual_recording:
            # 开始录音
            self._manual_recording = True
            logger.debug("手动模式：开始录音")
            self._view_set_button_text("发送")

            await self._cmd.connect_protocol()
            from src.constants.constants import ListeningMode
            await self._cmd.start_listening(ListeningMode.MANUAL)
        else:
            # 停止录音并发送
            self._manual_recording = False
            logger.debug("手动模式：停止录音并发送")
            self._view_set_button_text("按住后说话")

            await self._cmd.stop_listening()

    async def _auto_toggle(self):
        """自动模式切换.

        只切换模式状态，不自动开始监听。
        用户需要再次点击"开始对话"按钮才会开始监听。
        """
        if not self.view_manager:
            return

        new_auto = self._view_toggle_auto_mode()
        logger.debug(f"模式切换: {'自动' if new_auto else '手动'}")

    async def _auto_start(self):
        """自动模式开始监听.

        在自动模式下，用户点击"开始对话"按钮时调用。
        """
        await self._cmd.connect_protocol()
        from src.constants.constants import ListeningMode

        mode = (
            ListeningMode.REALTIME
            if self._ctx.get_config().get_config("AEC_OPTIONS.ENABLED", True)
            else ListeningMode.AUTO_STOP
        )
        await self._cmd.start_listening(mode)
        logger.debug("自动模式开始监听")

    async def _abort(self):
        """中断对话."""
        await self._cmd.abort_speaking(AbortReason.USER_INTERRUPTION)

    # ===== 音乐事件处理器 =====

    async def _on_music_state_changed(self, data):
        """处理音乐状态变化事件."""
        try:
            from src.mcp.tools.music.events import MusicStateData

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
                self._view_set_tts_text(text)
                logger.debug(f"UI 更新音乐状态: {data.state}")
        except Exception as e:
            logger.error(f"处理音乐状态变化失败: {e}", exc_info=True)

    async def _on_music_lyrics_update(self, data):
        """处理歌词更新事件."""
        try:
            from src.mcp.tools.music.events import MusicLyricsData

            if not isinstance(data, MusicLyricsData):
                logger.warning(f"收到非法的歌词数据: {type(data)}")
                return

            self._view_set_tts_text(data.text)
        except Exception as e:
            logger.error(f"处理歌词更新失败: {e}", exc_info=True)
