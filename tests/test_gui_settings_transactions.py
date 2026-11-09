"""Settings transactions through real Qt objects, without a GUI or devices."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

pytest.importorskip("PySide6.QtCore")

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.ui.gui.models.settings_model import SettingsModel
from src.ui.gui.settings_controller import SettingsController
from src.ui.shared.bridge.event_bridge import EventBridge
from src.utils.config_manager import ConfigManager


@pytest.fixture
def devices(monkeypatch):
    """Inject the device-service boundary; never import discovery backends."""
    service = SimpleNamespace(audio=Mock(), cameras=Mock())
    monkeypatch.setattr(SettingsModel, "_load_audio_devices", service.audio)
    monkeypatch.setattr(SettingsModel, "_load_cameras", service.cameras)
    monkeypatch.setattr(SettingsModel, "_update_wake_word_preview", lambda self: None)
    return service


def observe(model):
    signals = SimpleNamespace(saved=[], errors=[], status=[])
    model.configSaved.connect(lambda: signals.saved.append(True))
    model.errorOccurred.connect(signals.errors.append)
    model.statusMessage.connect(signals.status.append)
    return signals


@pytest.mark.parametrize("mqtt", [None, "invalid", [], 17])
def test_public_mqtt_property_promotes_non_object_nodes(mqtt):
    config = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"MQTT_INFO": mqtt}}}
    )
    model = SettingsModel(config_manager=config)
    assert model.metaObject().indexOfProperty("mqttEndpoint") >= 0
    model.mqttEndpoint = "mqtt.invalid"
    model.mqttUsername = "draft-user"
    assert model.mqttEndpoint == "mqtt.invalid"
    assert model.mqttUsername == "draft-user"
    assert config.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO") == mqtt
    assert model.save() is True
    assert config.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint") == "mqtt.invalid"


def test_save_has_public_qt_boolean_return():
    model = SettingsModel(config_manager=ConfigManager.from_dict())
    meta = model.metaObject()
    method = meta.method(meta.indexOfMethod("save()"))
    assert method.typeName() == "bool"


def test_open_cancel_reopen_discards_draft_and_refreshes_snapshot(devices):
    config = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"DEVICE_ID": "committed"}})
    bridge = EventBridge(EventBus())
    tasks = SimpleNamespace(spawn=lambda coro, **kwargs: coro.close())
    controller = SettingsController(EventBus(), tasks, bridge, config_manager=config)
    model = controller.ensure_model()
    shown = []
    bridge.showSettingsWindow.connect(lambda: shown.append(model.deviceId))

    bridge.onOpenSettings()
    assert shown == ["committed"]
    model.deviceId = "cancelled-edit"
    model._wake_word = "cancelled-word"
    model.discard()
    assert model.deviceId == "committed"
    assert model.wakeWord != "cancelled-word"
    assert devices.audio.call_count == 1
    assert devices.cameras.call_count == 1

    config.update_config("SYSTEM_OPTIONS.DEVICE_ID", "runtime-updated")
    bridge.onOpenSettings()
    assert shown == ["committed", "runtime-updated"]
    model.frameDuration = 40
    assert model.save() is True
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "runtime-updated"
    assert config.get_config("AUDIO_DEVICES.frame_duration") == 40
    assert devices.audio.call_count == 2


def test_reopening_without_cancel_refreshes_before_showing(devices):
    config = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"DEVICE_ID": "committed"}})
    bridge = EventBridge(EventBus())
    controller = SettingsController(EventBus(), Mock(), bridge, config)
    model = controller.ensure_model()
    shown = []
    bridge.showSettingsWindow.connect(lambda: shown.append(model.deviceId))
    bridge.onOpenSettings()
    model.deviceId = "stale-draft"
    bridge.onOpenSettings()
    assert shown == ["committed", "committed"]
    assert devices.audio.call_count == 2
    assert devices.cameras.call_count == 2


def test_file_draft_uses_runtime_snapshot_and_discard_does_not_scan(devices, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    model = SettingsModel(config_manager=config)
    # An independent writer has changed the injected runtime without persisting yet.
    config.update_config("SYSTEM_OPTIONS.DEVICE_ID", "runtime-change", save=False)
    model.deviceId = "cancelled"
    model.discard()
    assert model.deviceId == "runtime-change"
    assert not devices.audio.called and not devices.cameras.called
    model.frameDuration = 40
    assert model.save() is True
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "runtime-change"


@pytest.mark.parametrize("reload_error", [False, RuntimeError("injected reload failure")])
def test_apply_failure_retains_draft_and_suppresses_hot_reload(
    monkeypatch, tmp_path, reload_error
):
    config = ConfigManager(config_file=tmp_path / "config.json")
    model = SettingsModel(config_manager=config)
    signals = observe(model)
    model.deviceId = "on-disk-only"
    model._set_value("MCP_TOOLS.DISABLED", ["music_player.stop"])
    before = config.get_config("SYSTEM_OPTIONS.DEVICE_ID")
    reload = Mock()
    if isinstance(reload_error, Exception):
        reload.side_effect = reload_error
    else:
        reload.return_value = reload_error
    monkeypatch.setattr(config, "reload_config", reload)

    assert model.save() is False
    assert json.loads(config.config_file.read_text())["SYSTEM_OPTIONS"]["DEVICE_ID"] == "on-disk-only"
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == before
    assert model.deviceId == "on-disk-only"
    assert not signals.saved
    assert "已写入" in signals.errors[-1] and "运行时" in signals.errors[-1]
    assert not any("配置已保存" in status for status in signals.status)

    monkeypatch.setattr(config, "reload_config", ConfigManager.reload_config.__get__(config))
    assert model.save() is True
    assert signals.saved == [True]
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "on-disk-only"


def test_real_reload_read_failure_keeps_draft_and_suppresses_success(
    monkeypatch, tmp_path
):
    config = ConfigManager(config_file=tmp_path / "config.json")
    model = SettingsModel(config_manager=config)
    signals = observe(model)
    before = config.get_config("")
    model.deviceId = "disk-only"
    model._set_value("MCP_TOOLS.DISABLED", ["music_player.stop"])
    original_read = Path.read_text

    def failed_read(path, *args, **kwargs):
        if path == config.config_file:
            raise OSError("injected read failure")
        return original_read(path, *args, **kwargs)

    with monkeypatch.context() as read_patch:
        read_patch.setattr(Path, "read_text", failed_read)
        assert model.save() is False

    assert config.get_config("") == before
    assert model.deviceId == "disk-only"
    assert json.loads(config.config_file.read_text())["SYSTEM_OPTIONS"]["DEVICE_ID"] == "disk-only"
    assert not signals.saved
    assert "已写入" in signals.errors[-1] and "运行时" in signals.errors[-1]
    assert model.save() is True
    assert signals.saved == [True]


def test_atomic_replace_failure_keeps_previous_config_and_draft(monkeypatch, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    before = config.config_file.read_bytes()
    model = SettingsModel(config_manager=config)
    signals = observe(model)
    model.deviceId = "not-committed"
    monkeypatch.setattr(
        "src.utils.config_manager.os.replace",
        Mock(side_effect=PermissionError("injected read-only directory")),
    )
    assert model.save() is False
    assert config.config_file.read_bytes() == before
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") != "not-committed"
    assert model.deviceId == "not-committed"
    assert signals.errors and not signals.saved
    assert not any("配置已保存" in status for status in signals.status)


def test_memory_commit_failure_is_false_and_keeps_draft(monkeypatch):
    config = ConfigManager.from_dict()
    model = SettingsModel(config_manager=config)
    signals = observe(model)
    model.deviceId = "draft"
    monkeypatch.setattr(config, "commit_draft", lambda draft: "配置草稿提交失败")
    assert model.save() is False
    assert model.deviceId == "draft"
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") != "draft"
    assert signals.errors and not signals.saved


def test_success_emits_config_changed_only_after_runtime_applies(monkeypatch, tmp_path):
    bus = EventBus()
    config = ConfigManager(config_file=tmp_path / "config.json")
    scheduled = []

    def spawn(coro, *, name):
        scheduled.append((name, config.get_config("SYSTEM_OPTIONS.DEVICE_ID")))
        coro.close()

    controller = SettingsController(bus, SimpleNamespace(spawn=spawn), EventBridge(bus), config)
    model = controller.ensure_model()
    model.deviceId = "applied"
    reload = config.reload_config
    monkeypatch.setattr(config, "reload_config", lambda **kwargs: False)
    assert model.save() is False
    assert scheduled == []
    monkeypatch.setattr(config, "reload_config", reload)
    assert model.save() is True
    assert scheduled == [("ui:apply_settings", "applied")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL": "wss://changed.example"},
        {"SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint": "mqtt.example:8883"},
        {"SYSTEM_OPTIONS.DEVICE_ID": "new-device"},
        {
            "AUDIO_DEVICES.frame_duration": 40,
            "MCP_TOOLS.DISABLED": ["music_player.stop"],
        },
    ],
)
async def test_gui_save_reloads_before_reconnecting_and_noop_save_skips_reconnect(
    changes,
):
    config = ConfigManager.from_dict({"AUDIO_DEVICES": {"frame_duration": 20}})
    audio = AudioConfig.from_config(config)
    bus, tasks = EventBus(), TaskManager()
    tasks.initialize()
    controller = SettingsController(bus, tasks, EventBridge(bus), config)
    model = controller.ensure_model()
    events = []
    reconnected = asyncio.Event()
    reloaded = asyncio.Event()

    async def reload():
        await asyncio.sleep(0)
        audio.reload(config)
        events.append(("reload", audio.FRAME_DURATION))
        reloaded.set()

    def reconnect():
        events.append(("reconnect", audio.FRAME_DURATION))
        reconnected.set()

    bus.on(Events.CONFIG_CHANGED, reload)
    bus.on(Events.PROTOCOL_RECONNECT_REQUEST, reconnect)
    try:
        for path, value in changes.items():
            model._set_value(path, value)
        assert model.save()
        await asyncio.wait_for(reconnected.wait(), 1)
        expected_frame = changes.get("AUDIO_DEVICES.frame_duration", 20)
        assert events == [("reload", expected_frame), ("reconnect", expected_frame)]
        events.clear()
        reloaded.clear()
        assert model.save()
        await asyncio.wait_for(reloaded.wait(), 1)
        await asyncio.sleep(0)
        assert events == [("reload", expected_frame)]
    finally:
        controller.close()
        await tasks.cancel_all()


def test_wake_word_save_propagates_commit_failure(monkeypatch, tmp_path):
    config = ConfigManager.from_dict()
    model = SettingsModel(config_manager=config)
    signals = observe(model)
    monkeypatch.setattr(
        "src.ui.gui.models.settings.wake_word.convert_wake_word",
        lambda word: ("TEST @test", "en", "fake-model"),
    )
    monkeypatch.setattr("src.utils.resource_finder.get_keywords_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "commit_draft", lambda draft: "配置草稿提交失败")
    model._wake_word = "test"
    assert model.saveWakeWord() is False
    assert signals.errors and not signals.saved
    assert not any("唤醒词已保存" in status for status in signals.status)
    assert not (tmp_path / "en_keywords.txt").exists()


@pytest.mark.parametrize("word", ["", "cannot-convert"])
def test_wake_word_validation_errors_are_visible(monkeypatch, word):
    model = SettingsModel(config_manager=ConfigManager.from_dict())
    signals = observe(model)
    monkeypatch.setattr(
        "src.ui.gui.models.settings.wake_word.convert_wake_word",
        Mock(side_effect=ValueError("injected conversion failure")),
    )
    model._wake_word = word
    assert model.saveWakeWord() is False
    assert signals.errors and not signals.saved
    assert not signals.status


def test_qml_save_close_error_and_cancel_bindings():
    root = Path(__file__).resolve().parents[1] / "src/ui/gui/qml"
    settings = (root / "windows/SettingsWindow.qml").read_text()
    assert "if (settingsModel.save())" in settings
    assert "function onErrorOccurred(msg)" in settings
    assert "function onStatusReset()" in settings
    assert "if (!statusText.isError)" in settings
    assert "wrapMode: Text.Wrap" in settings
    assert "onClosing: settingsModel.discard()" in settings
    main = (root / "windows/MainWindow.qml").read_text()
    assert "eventBridge.onOpenSettings()" in main
    entry = (root / "main.qml").read_text()
    assert "function onShowSettingsWindow()" in entry
    assert "eventBridge.onOpenSettings()" not in entry
