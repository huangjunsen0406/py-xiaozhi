"""主界面 ViewPort 写路径：状态 / 对话 / 音乐 / 表情."""

from src.ui.gui.services import EmotionService
from src.ui.gui.models import MainModel


class MainWindowController:
    """把 ViewPort 的 set_* 落到 MainModel + EmotionService."""

    def __init__(
        self,
        main_model: MainModel | None = None,
        emotion_service: EmotionService | None = None,
    ) -> None:
        self._main_model = main_model or MainModel()
        self._emotion_service = emotion_service or EmotionService()

    @property
    def main_model(self) -> MainModel:
        return self._main_model

    @property
    def emotion_service(self) -> EmotionService:
        return self._emotion_service

    def set_neutral_emotion(self) -> None:
        url = self._emotion_service.get_emotion_url("neutral")
        self._main_model.set_emotion_url(url)

    def set_chat_text(self, text: str) -> None:
        self._main_model.set_chat_text(text)

    def set_music_line(self, text: str) -> None:
        self._main_model.set_music_line(text)

    def set_emotion(self, emotion: str) -> None:
        url = self._emotion_service.get_emotion_url(emotion)
        self._main_model.set_emotion_url(url)

    def set_status(self, status: str, connected: bool = True) -> None:
        self._main_model.set_status(status, connected)

    def set_button_text(self, text: str) -> None:
        self._main_model.set_button_text(text)

    def set_auto_mode(self, auto_mode: bool) -> None:
        self._main_model.set_auto_mode(auto_mode)

    def is_auto_mode(self) -> bool:
        return bool(self._main_model._auto_mode)
