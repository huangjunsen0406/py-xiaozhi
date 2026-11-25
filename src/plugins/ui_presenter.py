"""把状态/协议消息画到界面上."""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import DeviceState
from src.i18n import t
from src.logging import get_logger

if TYPE_CHECKING:
    from src.ui.shared.viewport import ViewPort

logger = get_logger()


class UiPresenter:
    """写界面：对话、媒体、状态、表情、按钮等."""

    STATE_TEXT_KEYS = {
        DeviceState.IDLE: "main.status.idle",
        DeviceState.LISTENING: "main.status.listening",
        DeviceState.SPEAKING: "main.status.speaking",
        DeviceState.NOTIFYING: "main.status.notifying",
    }

    MEDIA_STATE_KEYS = {
        "playing": "main.media.playing",
        "paused": "main.media.paused",
        "stopped": "",
        "completed": "main.media.completed",
        "error": "main.media.error",
    }

    def __init__(self, viewport: Optional["ViewPort"] = None) -> None:
        self._vp = viewport
        self._last_device_state = None
        self._last_network_error = False
        self._last_media_state = None

    def bind(self, viewport: Optional["ViewPort"]) -> None:
        self._vp = viewport

    @property
    def viewport(self) -> Optional["ViewPort"]:
        return self._vp

    def set_chat_text(self, text: str) -> None:
        if self._vp:
            self._vp.set_chat_text(text)

    def set_media_line(self, text: str) -> None:
        if self._vp:
            self._vp.set_media_line(text)

    def set_emotion(self, emotion: str) -> None:
        if self._vp:
            self._vp.set_emotion(emotion)

    def set_status(self, status: str, connected: bool = True) -> None:
        if self._vp:
            self._vp.set_status(status, connected)

    def set_button_text(self, text: str) -> None:
        if self._vp:
            self._vp.set_button_text(text)

    def set_auto_mode(self, auto_mode: bool) -> None:
        if self._vp:
            self._vp.set_auto_mode(auto_mode)

    def show_device_state(self, state) -> None:
        if key := self.STATE_TEXT_KEYS.get(state):
            self._last_device_state = state
            self._last_network_error = False
            self.set_emotion("neutral")
            self.set_status(t(key), connected=True)

    def show_network_error(self) -> None:
        self._last_network_error = True
        self.set_status(t("main.status.disconnected"), connected=False)

    def show_media_state(self, data) -> None:
        try:
            from src.media.events import MediaStateData

            if not isinstance(data, MediaStateData):
                logger.warning(f"收到非法的媒体状态数据: {type(data)}")
                return

            key = self.MEDIA_STATE_KEYS.get(data.state)
            if key is None:
                return
            self._last_media_state = data
            text = t(key, title=data.title) if key else ""
            self.set_media_line(text)
            logger.debug(f"UI 更新媒体状态: {data.state}")
        except Exception as e:
            logger.error(f"处理媒体状态变化失败: {e}", exc_info=True)

    def refresh_locale(self) -> None:
        """语言热切换后，将当前语义状态以新语言重推到界面."""
        if not self._vp:
            return
        if self._last_network_error:
            self.set_status(t("main.status.disconnected"), connected=False)
        elif self._last_device_state is not None:
            if key := self.STATE_TEXT_KEYS.get(self._last_device_state):
                self.set_status(t(key), connected=True)
        if self._last_media_state is not None:
            key = self.MEDIA_STATE_KEYS.get(self._last_media_state.state)
            if key:
                self.set_media_line(t(key, title=self._last_media_state.title))

    def show_media_subtitle(self, data) -> None:
        try:
            from src.media.events import MediaSubtitleData

            if not isinstance(data, MediaSubtitleData):
                logger.warning(f"收到非法的媒体副标题数据: {type(data)}")
                return
            self.set_media_line(data.text)
        except Exception as e:
            logger.error(f"处理媒体副标题更新失败: {e}", exc_info=True)

    def show_protocol_message(self, message) -> None:
        if not isinstance(message, dict):
            return
        msg_type = message.get("type")
        if msg_type in ("tts", "stt"):
            if text := message.get("text"):
                self.set_chat_text(text)
        elif msg_type == "llm":
            if emotion := message.get("emotion"):
                self.set_emotion(emotion)
