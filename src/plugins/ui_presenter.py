"""把状态/协议消息画到界面上."""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import DeviceState
from src.logging import get_logger

if TYPE_CHECKING:
    from src.ui.shared.viewport import ViewPort

logger = get_logger()


class UiPresenter:
    """写界面：对话、媒体、状态、表情、按钮等."""

    STATE_TEXT_MAP = {
        DeviceState.IDLE: "待命",
        DeviceState.LISTENING: "聆听中...",
        DeviceState.SPEAKING: "说话中...",
        DeviceState.NOTIFYING: "通知播放中...",
    }

    MEDIA_STATE_TEXT = {
        "playing": "正在播放: {title}",
        "paused": "已暂停: {title}",
        "stopped": "",
        "completed": "播放完成: {title}",
        "error": "播放失败: {title}",
    }

    def __init__(self, viewport: Optional["ViewPort"] = None) -> None:
        self._vp = viewport

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
        if status_text := self.STATE_TEXT_MAP.get(state):
            self.set_emotion("neutral")
            self.set_status(status_text, connected=True)

    def show_network_error(self) -> None:
        self.set_status("未连接", connected=False)

    def show_media_state(self, data) -> None:
        try:
            from src.media.events import MediaStateData

            if not isinstance(data, MediaStateData):
                logger.warning(f"收到非法的媒体状态数据: {type(data)}")
                return

            template = self.MEDIA_STATE_TEXT.get(data.state)
            if template is None:
                return
            text = template.format(title=data.title) if template else ""
            self.set_media_line(text)
            logger.debug(f"UI 更新媒体状态: {data.state}")
        except Exception as e:
            logger.error(f"处理媒体状态变化失败: {e}", exc_info=True)

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
