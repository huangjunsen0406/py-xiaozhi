"""主窗口 ViewModel."""

from PySide6.QtCore import Property, Signal

from .base_model import BaseModel


class MainModel(BaseModel):
    """主窗口数据模型."""

    # 信号
    ttsTextChanged = Signal()
    emotionUrlChanged = Signal()
    statusTextChanged = Signal()
    connectedChanged = Signal()
    autoModeChanged = Signal()
    modeTextChanged = Signal()
    buttonTextChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tts_text = ""
        self._emotion_url = ""
        self._status_text = ""
        self._connected = False
        self._auto_mode = False
        self._mode_text = "手动对话"
        self._button_text = "按住后说话"

    # ========== Properties ==========

    @Property(str, notify=ttsTextChanged)
    def ttsText(self) -> str:
        return self._tts_text

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

    def set_tts_text(self, text: str):
        if self._tts_text != text:
            self._tts_text = text
            self.ttsTextChanged.emit()

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

    def toggle_auto_mode(self):
        """切换自动/手动模式."""
        self.set_auto_mode(not self._auto_mode)

    # ========== 便捷方法 ==========

    def update_text(self, text: str):
        """更新 TTS 文本."""
        self.set_tts_text(text)

    def update_emotion(self, url: str):
        """更新表情 URL."""
        self.set_emotion_url(url)

    def update_status(self, status: str, connected: bool):
        """更新状态."""
        self.set_status(status, connected)

    def update_mode_text(self, text: str):
        """更新模式文本."""
        if self._mode_text != text:
            self._mode_text = text
            self.modeTextChanged.emit()

    def update_button_text(self, text: str):
        """更新按钮文本."""
        self.set_button_text(text)
