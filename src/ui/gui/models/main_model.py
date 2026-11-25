"""主窗口 ViewModel."""

from PySide6.QtCore import Property, Qt, Signal, Slot

from src.i18n import off_locale_changed, on_locale_changed, t
from src.ui.gui.models.base_model import BaseModel


class MainModel(BaseModel):
    """主窗口数据模型."""

    # 信号
    ttsTextChanged = Signal()
    mediaLineChanged = Signal()
    emotionUrlChanged = Signal()
    statusTextChanged = Signal()
    connectedChanged = Signal()
    autoModeChanged = Signal()
    modeTextChanged = Signal()
    buttonTextChanged = Signal()
    _localeChangeRequested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._closed = False
        self._tts_text = ""
        self._media_line = ""
        self._emotion_url = ""
        self._status_text = ""
        self._connected = False
        self._auto_mode = False
        self._mode_text = t("main.mode.manual")
        self._button_text = t("main.button.hold_to_talk")
        self._has_custom_button_text = False
        self._localeChangeRequested.connect(
            self._on_locale_changed_ui, Qt.ConnectionType.QueuedConnection
        )
        on_locale_changed(self._on_locale_changed)

    def _on_locale_changed(self, locale_code: str) -> None:
        if self._closed:
            return
        try:
            self._localeChangeRequested.emit(locale_code)
        except RuntimeError:
            pass

    @Slot(str)
    def _on_locale_changed_ui(self, _locale_code: str) -> None:
        if self._closed:
            return
        new_mode = t("main.mode.auto" if self._auto_mode else "main.mode.manual")
        if self._mode_text != new_mode:
            self._mode_text = new_mode
            self.modeTextChanged.emit()
        if not self._has_custom_button_text:
            new_btn = t(
                "main.button.start_chat"
                if self._auto_mode
                else "main.button.hold_to_talk"
            )
            if self._button_text != new_btn:
                self._button_text = new_btn
                self.buttonTextChanged.emit()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            off_locale_changed(self._on_locale_changed)

    # ========== Properties ==========

    @Property(str, notify=ttsTextChanged)
    def ttsText(self) -> str:
        # 历史属性名还是 ttsText，实际是对话内容
        return self._tts_text

    @Property(str, notify=mediaLineChanged)
    def mediaLine(self) -> str:
        return self._media_line

    @Property(str, notify=emotionUrlChanged)
    def emotionUrl(self) -> str:
        return self._emotion_url

    @Property(str, notify=statusTextChanged)
    def statusText(self) -> str:
        return self._status_text

    @Property(bool, notify=connectedChanged)
    def connected(self) -> bool:
        return self._connected

    @Property(bool, notify=autoModeChanged)
    def autoMode(self) -> bool:
        return self._auto_mode

    @Property(str, notify=modeTextChanged)
    def modeText(self) -> str:
        return self._mode_text

    @Property(str, notify=buttonTextChanged)
    def buttonText(self) -> str:
        return self._button_text

    # ========== Setters ==========

    def set_chat_text(self, text: str):
        if self._tts_text != text:
            self._tts_text = text
            self.ttsTextChanged.emit()

    def set_media_line(self, text: str):
        if self._media_line != text:
            self._media_line = text
            self.mediaLineChanged.emit()

    def set_emotion_url(self, url: str):
        if self._emotion_url != url:
            self._emotion_url = url
            self.emotionUrlChanged.emit()

    def set_status(self, status: str, connected: bool):
        status_changed = self._status_text != status
        connected_changed = self._connected != connected

        if status_changed:
            self._status_text = status
            self.statusTextChanged.emit()

        if connected_changed:
            self._connected = connected
            self.connectedChanged.emit()

    def set_auto_mode(self, auto: bool):
        # 默认按钮文案；对话进行中会再被 Session 改成「停止对话」
        if self._auto_mode != auto:
            self._auto_mode = auto
            self._has_custom_button_text = False
            self._mode_text = t("main.mode.auto" if auto else "main.mode.manual")
            self._button_text = t(
                "main.button.start_chat" if auto else "main.button.hold_to_talk"
            )
            self.autoModeChanged.emit()
            self.modeTextChanged.emit()
            self.buttonTextChanged.emit()

    def set_button_text(self, text: str):
        self._has_custom_button_text = True
        if self._button_text != text:
            self._button_text = text
            self.buttonTextChanged.emit()
