"""Translate UI gestures into conversation commands; retain presentation state only."""

from typing import TYPE_CHECKING

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.core.event_bus import Events

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.plugins.ui_presenter import UiPresenter


class SessionActions:
    def __init__(
        self, ctx: "PluginContext", cmd: "PluginCommands", presenter: "UiPresenter"
    ):
        self._ctx = ctx
        self._cmd = cmd
        self._ui = presenter
        self._manual_recording = False
        self._auto_mode = False
        self._auto_session_active = False
        self._bus = None
        self._subscriptions = []
        self._subscription_generation = 0

    @property
    def auto_mode(self) -> bool:
        return self._auto_mode

    @property
    def auto_session_active(self) -> bool:
        return self._auto_session_active

    @property
    def manual_recording(self) -> bool:
        return self._manual_recording

    def subscribe(self, bus) -> None:
        self.unsubscribe()
        self._bus = bus
        generation = self._subscription_generation
        for event, handler in (
            (Events.UI_BUTTON_PRESS, self.press),
            (Events.UI_BUTTON_RELEASE, self.release),
            (Events.UI_MANUAL_TOGGLE, self.manual_toggle),
            (Events.UI_AUTO_TOGGLE, self.auto_toggle),
            (Events.UI_AUTO_START, self.auto_session_toggle),
            (Events.UI_ABORT_REQUEST, self.abort),
            (Events.UI_SEND_TEXT, self.send_text_from_event),
            (Events.UI_QUIT_REQUEST, self.request_shutdown),
        ):

            async def dispatch(data=None, handler=handler):
                if self._bus is bus and generation == self._subscription_generation:
                    await handler(data)

            self._subscriptions.append((event, dispatch))
            bus.on(event, dispatch)

    def unsubscribe(self) -> None:
        self._subscription_generation += 1
        if self._bus is not None:
            for event, handler in self._subscriptions:
                self._bus.off(event, handler)
        self._subscriptions.clear()
        self._bus = None

    def on_device_state_changed(self, state) -> None:
        if state != DeviceState.LISTENING and self._manual_recording:
            self._manual_recording = False
            if not self._auto_mode:
                self._ui.set_button_text("按住后说话")
        if self._auto_mode:
            self._auto_session_active = state in (
                DeviceState.LISTENING,
                DeviceState.SPEAKING,
            )
            self._ui.set_button_text(
                "停止对话" if self._auto_session_active else "开始对话"
            )

    async def request_shutdown(self, _data=None) -> None:
        self._cmd.request_shutdown()

    async def send_text_from_event(self, data) -> None:
        if isinstance(data, str):
            text = data
        elif isinstance(data, dict):
            text = data.get("text", "")
        else:
            text = getattr(data, "text", "")
        await self.send_text(text)

    async def send_text(self, text: str) -> None:
        mode = ListeningMode.REALTIME if self._auto_mode else ListeningMode.MANUAL
        await self._cmd.send_user_text(text, mode)

    async def press(self, _data=None) -> None:
        await self._cmd.start_listening(ListeningMode.MANUAL)

    async def release(self, _data=None) -> None:
        await self._cmd.stop_listening()

    async def manual_toggle(self, _data=None) -> None:
        if not self._manual_recording:
            if await self._cmd.start_listening(ListeningMode.MANUAL):
                self._manual_recording = True
                self._ui.set_button_text("发送")
        else:
            await self._cmd.stop_listening()
            self._manual_recording = False
            self._ui.set_button_text("按住后说话")

    async def auto_toggle(self, _data=None) -> None:
        self._auto_mode = not self._auto_mode
        self._auto_session_active = False
        self._manual_recording = False
        self._ui.set_auto_mode(self._auto_mode)

    async def auto_session_toggle(self, _data=None) -> None:
        if (
            self._auto_session_active
            or self._ctx.is_listening()
            or self._ctx.is_speaking()
        ):
            await self._cmd.stop_listening()
            self._auto_session_active = False
            self._ui.set_button_text("开始对话")
        elif await self._cmd.start_auto_conversation():
            self._auto_session_active = True
            self._ui.set_button_text("停止对话")

    async def abort(self, _data=None) -> None:
        await self._cmd.abort_speaking(AbortReason.USER_INTERRUPTION)
