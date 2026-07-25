"""主窗口 ViewModel."""

from PySide6.QtCore import Property, Signal

from src.ui.gui.models.base_model import BaseModel


class MainModel(BaseModel):
    """主窗口数据模型."""

    # 信号
    ttsTextChanged = Signal()
    musicLineChanged = Signal()
    emotionUrlChanged = Signal()
    statusTextChanged = Signal()
    connectedChanged = Signal()
    autoModeChanged = Signal()
    modeTextChanged = Signal()
    buttonTextChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts_text = ""
        self._music_line = ""
        self._emotion_url = ""
        self._status_text = ""
        self._connected = False
        self._auto_mode = False
        self._mode_text = "手动对话"
        self._button_text = "按住后说话"

    # ========== Properties ==========

    @Property(str, notify=ttsTextChanged)
    def ttsText(self) -> str:
        # 历史属性名还是 ttsText，实际是对话内容
        return self._tts_text

    @Property(str, notify=musicLineChanged)
    def musicLine(self) -> str:
        return self._music_line

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

    def set_music_line(self, text: str):
        if self._music_line != text:
            self._music_line = text
            self.musicLineChanged.emit()

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
            self._mode_text = "自动对话" if auto else "手动对话"
            self._button_text = "开始对话" if auto else "按住后说话"
            self.autoModeChanged.emit()
            self.modeTextChanged.emit()
            self.buttonTextChanged.emit()

    def set_button_text(self, text: str):
        if self._button_text != text:
            self._button_text = text
            self.buttonTextChanged.emit()
