"""UI 插件.

管理 CLI/GUI 显示界面。
"""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import AbortReason, DeviceState
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext


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
        根据模式创建 display 实例.
        """
        if self.mode == "gui":
            from src.views.main import GuiMain

            self._is_gui = True
            return GuiMain()
        else:
            from src.views.main import CliMain

            self._is_gui = False
            return CliMain()

    async def start(self) -> None:
        if not self.display:
            return

        await self._setup_callbacks()
        self._cmd.spawn(self.display.start(), name=f"ui:{self.mode}:start")

    async def _setup_callbacks(self) -> None:
        """
        设置 display 回调.
        """
        if self._is_gui:
            callbacks = {
                "press_callback": self._wrap_callback(self._press),
                "release_callback": self._wrap_callback(self._release),
                "auto_callback": self._wrap_callback(self._auto_toggle),
                "abort_callback": self._wrap_callback(self._abort),
                "send_text_callback": self._send_text,
                "quit_callback": self._request_shutdown,
            }
        else:
            callbacks = {
                "auto_callback": self._auto_toggle,
                "abort_callback": self._abort,
                "send_text_callback": self._send_text,
            }

        await self.display.set_callbacks(**callbacks)

    def _wrap_callback(self, coro_func):
        """
        包装协程函数为可调度的 lambda.
        """
        return lambda: self._cmd.spawn(coro_func(), name="ui:callback")

    async def on_incoming_json(self, message) -> None:
        if not self.display or not isinstance(message, dict):
            return

        msg_type = message.get("type")

        if msg_type in ("tts", "stt"):
            if text := message.get("text"):
                await self.display.update_text(text)
        elif msg_type == "llm":
            if emotion := message.get("emotion"):
                await self.display.update_emotion(emotion)

    async def on_device_state_changed(self, state) -> None:
        if not self.display:
            return

        if self.is_first:
            self.is_first = False
            return

        await self.display.update_emotion("neutral")
        if status_text := self.STATE_TEXT_MAP.get(state):
            await self.display.update_status(status_text, True)

    async def shutdown(self) -> None:
        if self.display:
            await self.display.close()
            self.display = None

    # ===== 回调函数 =====

    def _request_shutdown(self):
        """
        请求应用关闭.
        """
        self._cmd.request_shutdown()

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
