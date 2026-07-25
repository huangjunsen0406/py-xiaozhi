"""把状态/协议消息画到界面上."""

from typing import TYPE_CHECKING, Optional

from src.constants.constants import DeviceState
from src.logging import get_logger

if TYPE_CHECKING:
    from src.ui.shared.viewport import ViewPort

logger = get_logger()


class UiPresenter:
    """写界面：对话、音乐、状态、表情、按钮等."""

    STATE_TEXT_MAP = {
        DeviceState.IDLE: "待命",
        DeviceState.LISTENING: "聆听中...",
        DeviceState.SPEAKING: "说话中...",
    }

    MUSIC_STATE_TEXT = {
        "playing": "正在播放: {song}",
        "paused": "已暂停: {song}",
        "stopped": "已停止: {song}",
        "completed": "播放完成: {song}",
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

    def set_music_line(self, text: str) -> None:
        if self._vp:
            self._vp.set_music_line(text)

    def set_emotion(self, emotion: str) -> None:
        if self._vp:
            self._vp.set_emotion(emotion)

    def set_status(self, status: str, connected: bool = True) -> None:
        if self._vp:
            self._vp.set_status(status, connected)

    def set_button_text(self, text: str) -> None:
        if not self._vp:
            return
        setter = getattr(self._vp, "set_button_text", None)
        if callable(setter):
            setter(text)

    def set_auto_mode(self, auto_mode: bool) -> None:
        if self._vp:
            self._vp.set_auto_mode(auto_mode)

    def show_device_state(self, state) -> None:
        if status_text := self.STATE_TEXT_MAP.get(state):
            self.set_emotion("neutral")
            self.set_status(status_text, connected=True)

    def show_network_error(self) -> None:
        self.set_status("未连接", connected=False)

    def show_music_state(self, data) -> None:
        try:
            from src.mcp.tools.music.events import MusicStateData

            if not isinstance(data, MusicStateData):
                logger.warning(f"收到非法的音乐状态数据: {type(data)}")
                return

            template = self.MUSIC_STATE_TEXT.get(data.state)
            if not template:
                return
            text = template.format(song=data.song)
            self.set_music_line(text)
            logger.debug(f"UI 更新音乐状态: {data.state}")
        except Exception as e:
            logger.error(f"处理音乐状态变化失败: {e}", exc_info=True)

    def show_music_lyrics(self, data) -> None:
        try:
            from src.mcp.tools.music.events import MusicLyricsData

            if not isinstance(data, MusicLyricsData):
                logger.warning(f"收到非法的歌词数据: {type(data)}")
                return
            self.set_music_line(data.text)
        except Exception as e:
            logger.error(f"处理歌词更新失败: {e}", exc_info=True)

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
