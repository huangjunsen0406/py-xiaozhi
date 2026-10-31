"""GUI writes retain model signals and QML context after removing thin routing."""

import pytest

pytest.importorskip("PySide6.QtCore")

from src.core.event_bus import EventBus
from src.core.task_manager import TaskManager
from src.ui.gui.manager import GuiViewManager
from src.ui.gui.qml_host import QmlAppHost
from src.ui.gui.services import EmotionService
from src.ui.gui.settings_controller import SettingsController
from src.utils.config_manager import ConfigManager


@pytest.mark.asyncio
async def test_gui_viewport_keeps_qml_models_and_signal_updates(monkeypatch):
    contexts = []
    monkeypatch.setattr(QmlAppHost, "create_engine", lambda self: None)
    monkeypatch.setattr(
        QmlAppHost, "inject_context", lambda self, data: contexts.append(data)
    )
    monkeypatch.setattr(QmlAppHost, "load_main", lambda self: None)
    monkeypatch.setattr(QmlAppHost, "show_root", lambda self, **kwargs: None)
    monkeypatch.setattr(GuiViewManager, "_setup_tray", lambda self: None)
    monkeypatch.setattr(SettingsController, "ensure_model", lambda self: None)
    monkeypatch.setattr(
        EmotionService, "get_emotion_url", lambda self, emotion: f"test://{emotion}"
    )
    tasks = TaskManager()
    tasks.initialize()
    view = GuiViewManager(EventBus(), tasks, ConfigManager.from_dict())
    model = view.main_model
    seen = []
    model.ttsTextChanged.connect(lambda: seen.append(("chat", model.ttsText)))
    model.musicLineChanged.connect(lambda: seen.append(("music", model.musicLine)))
    model.emotionUrlChanged.connect(lambda: seen.append(("emotion", model.emotionUrl)))
    model.connectedChanged.connect(lambda: seen.append(("connected", model.connected)))
    model.autoModeChanged.connect(lambda: seen.append(("auto", model.autoMode)))
    model.buttonTextChanged.connect(lambda: seen.append(("button", model.buttonText)))
    try:
        await view.start()
        assert contexts[0]["mainModel"] is model
        assert contexts[0]["settingsModel"] is None
        assert isinstance(contexts[0]["emotionService"], EmotionService)
        assert model.emotionUrl == "test://neutral"
        assert view.is_running
        view.set_chat_text("hello")
        view.set_music_line("lyrics")
        view.set_emotion("happy")
        view.set_status("connected", True)
        view.set_auto_mode(True)
        view.set_button_text("stop")
        assert model.ttsText == "hello" and model.musicLine == "lyrics"
        assert model.emotionUrl == "test://happy"
        assert model.statusText == "connected" and model.connected
        assert model.autoMode and model.buttonText == "stop"
        assert ("chat", "hello") in seen
        assert ("music", "lyrics") in seen
        assert ("emotion", "test://happy") in seen
        assert ("connected", True) in seen
        assert ("auto", True) in seen
        assert ("button", "stop") in seen
    finally:
        await view.close()
        await tasks.cancel_all()
    assert not view.is_running
