"""TUI settings contracts without Qt, devices, models, or real user directories."""

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import src.ui.tui.settings_data as settings
import src.utils.config_manager as config_module
import src.utils.resource_finder as resources
from src.utils.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def forbid_user_directories(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("TUI settings accessed real user directories or PATHS")

    monkeypatch.setattr(config_module, "get_user_data_dir", forbidden)
    monkeypatch.setattr(config_module, "get_config_dir", forbidden)
    monkeypatch.setattr(resources, "get_keywords_dir", forbidden)
    monkeypatch.setattr(resources, "apply_path_overrides_from_config", forbidden)


@pytest.fixture(params=["memory", "file"])
def config(request, tmp_path):
    if request.param == "memory":
        return ConfigManager.from_dict()
    return ConfigManager(config_file=tmp_path / "config.json")


@pytest.fixture
def keywords(monkeypatch, tmp_path):
    directory = tmp_path / "active-keywords"
    monkeypatch.setattr(resources, "get_keywords_dir", lambda: directory)
    converter = Mock(return_value=("TEST @test", "en", "models/en"))
    monkeypatch.setattr(settings, "preview_wake_word", converter)
    return SimpleNamespace(directory=directory, converter=converter)


def fields():
    return {
        field.path: field
        for _, section in settings.SETTING_SECTIONS
        for field in section
    }


def disk_bytes(config):
    return config.config_file.read_bytes() if config.config_file else None


def test_schema_preserves_existing_paths_and_gui_contracts():
    schema = fields()
    assert len(schema) == sum(len(section) for _, section in settings.SETTING_SECTIONS)
    assert schema["WAKE_WORD_OPTIONS.WAKE_WORD_LANG"].kind == "readonly"
    assert schema["SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN"].kind == "secret"
    assert schema["SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password"].kind == "secret"
    assert schema["MUSIC.URL_API_KEY"].kind == "secret"
    assert schema["CAMERA.VLapi_key"].kind == "secret"
    assert schema["MUSIC.DEFAULT_QUALITY"].choices == ("128k", "320k")
    assert schema["WAKE_WORD_OPTIONS.KEYWORDS_SCORE"].minimum == 0.5
    assert schema["AEC_OPTIONS.FRAME_DELAY"].maximum == 20
    assert not any("WINDOW_TOGGLE" in path for path in schema)
    assert {schema[path].effect for path in schema if path.startswith("PATHS.")} == {
        "restart"
    }
    assert all(
        field.effect in {"hot", "reconnect", "restart"} for field in schema.values()
    )
    assert all(isinstance(field.choices, tuple) for field in schema.values())
    assert {
        "AEC_OPTIONS." + name
        for name in ("ENABLED", "MUSIC_PARALLEL", "FRAME_DELAY", "ENABLE_PREPROCESS")
    } <= schema.keys()
    assert {
        "WAKE_WORD_OPTIONS." + name
        for name in ("NUM_THREADS", "KEYWORDS_SCORE", "KEYWORDS_THRESHOLD")
    } <= schema.keys()
    assert {
        "CAMERA." + name for name in ("fps", "Local_VL_url", "VLapi_key", "models")
    } <= schema.keys()
    assert {
        "SYSTEM_OPTIONS.NETWORK.MQTT_INFO." + name
        for name in (
            "endpoint",
            "client_id",
            "username",
            "password",
            "publish_topic",
            "subscribe_topic",
        )
    } <= schema.keys()


def test_all_default_fields_load_save_without_conversion_or_paths(config, monkeypatch):
    before = config.get_config("")
    converter = Mock(side_effect=AssertionError("ordinary save converted wake word"))
    monkeypatch.setattr(settings, "preview_wake_word", converter)
    values = settings.load_setting_values(config)
    assert all(isinstance(value, str) for value in values.values())
    assert values["AEC_OPTIONS.ENABLED"] == "false"
    assert values["SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint"] == ""
    assert values["AUDIO_DEVICES.opus_output_sample_rate"] == "24000"
    assert settings.save_settings(values, config)[0]
    assert config.get_config("") == before
    converter.assert_not_called()


def test_secret_whitespace_and_shortcut_normalization_round_trip(config):
    secrets = {
        path: "  preserved secret  "
        for path, field in fields().items()
        if field.kind == "secret"
    }
    shortcuts = {
        f"SHORTCUTS.{name}.key": "J"
        for name in ("MANUAL_PRESS", "AUTO_TOGGLE", "ABORT", "MODE_TOGGLE")
    }
    values = {**secrets, **shortcuts}
    ok, message = settings.save_settings(values, config)
    assert ok, message
    loaded = settings.load_setting_values(config)
    for path, secret in secrets.items():
        assert config.get_config(path) == secret
        assert loaded[path] == secret
    for path in shortcuts:
        assert config.get_config(path) == "j"
        assert loaded[path] == "j"
        assert values[path] == "J"


def test_loading_and_cancelling_only_changes_local_strings(config):
    before = config.get_config("")
    disk = disk_bytes(config)
    draft = settings.load_setting_values(config)
    draft["SYSTEM_OPTIONS.DEVICE_ID"] = "cancelled"
    draft["WAKE_WORD_OPTIONS.WAKE_WORD"] = "cancelled-word"
    assert config.get_config("") == before
    assert disk_bytes(config) == disk


def test_save_preserves_unknown_config_and_typed_values(config, monkeypatch):
    config.update_config("CUSTOM", {"nested": ["keep"]}, save=False)
    config.update_config("MCP_TOOLS.EXTRA", {"future": True}, save=False)
    config.update_config("AUDIO_DEVICES.future", 42, save=False)
    updates = {
        "AUDIO_DEVICES.frame_duration": "40",
        "AUDIO_DEVICES.opus_output_sample_rate": "16000",
        "AEC_OPTIONS.ENABLED": "true",
        "AEC_OPTIONS.FRAME_DELAY": "4",
        "WAKE_WORD_OPTIONS.KEYWORDS_SCORE": "2.5",
        "WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD": "0.35",
        "SHORTCUTS.ABORT.key": "p",
        "PATHS.CACHE_DIR": "/unused/cache",
        "UNKNOWN.INPUT": "ignored",
    }
    monkeypatch.setattr(
        config, "update_configs", Mock(side_effect=AssertionError("mutating API used"))
    )
    ok, message = settings.save_settings(
        updates,
        config,
        disabled_tools=["plugin.unknown", " plugin.unknown ", "future.tool"],
        device_updates={
            "AUDIO_DEVICES.input_device_id": 3,
            "AUDIO_DEVICES.input_device_name": "raw microphone",
        },
    )
    assert ok, message
    assert config.get_config("CUSTOM") == {"nested": ["keep"]}
    assert config.get_config("MCP_TOOLS.EXTRA") == {"future": True}
    assert config.get_config("AUDIO_DEVICES.future") == 42
    assert config.get_config("MCP_TOOLS.DISABLED") == ["plugin.unknown", "future.tool"]
    assert config.get_config("AUDIO_DEVICES.input_device_id") == 3
    assert config.get_config("AUDIO_DEVICES.input_device_name") == "raw microphone"
    assert type(config.get_config("AUDIO_DEVICES.frame_duration")) is int
    assert type(config.get_config("AUDIO_DEVICES.opus_output_sample_rate")) is int
    assert type(config.get_config("AEC_OPTIONS.FRAME_DELAY")) is int
    assert type(config.get_config("AEC_OPTIONS.ENABLED")) is bool
    assert type(config.get_config("WAKE_WORD_OPTIONS.KEYWORDS_SCORE")) is float
    assert config.get_config("UNKNOWN.INPUT") is None
    assert updates["AEC_OPTIONS.ENABLED"] == "true"
    if config.config_file:
        assert json.loads(config.config_file.read_text()) == config.get_config("")


@pytest.mark.parametrize(
    "path,value",
    [
        ("AEC_OPTIONS.ENABLED", "truthy"),
        ("AEC_OPTIONS.ENABLED", ""),
        ("AEC_OPTIONS.ENABLED", "2"),
        ("CAMERA.backend", "invalid"),
        ("SHORTCUTS.ABORT.modifier", "super"),
        ("SHORTCUTS.ABORT.key", ""),
        ("SHORTCUTS.AUTO_TOGGLE.key", "ab"),
        ("SHORTCUTS.MODE_TOGGLE.key", " "),
        ("AUDIO_DEVICES.opus_output_sample_rate", "48000"),
        ("AUDIO_DEVICES.frame_duration", "20.0"),
        ("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION", "v3"),
        ("MUSIC.DEFAULT_QUALITY", "flac"),
        ("AEC_OPTIONS.FRAME_DELAY", "-1"),
        ("AEC_OPTIONS.FRAME_DELAY", "21"),
        ("AEC_OPTIONS.FRAME_DELAY", "1.5"),
        ("CAMERA.frame_width", "0"),
        ("CAMERA.frame_height", "invalid"),
        ("CAMERA.fps", "121"),
        ("WAKE_WORD_OPTIONS.NUM_THREADS", "0"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", "nan"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", "inf"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", "-inf"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", "1e999"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", "0.1"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", "1.01"),
        ("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", ""),
    ],
)
def test_validation_failure_does_not_partially_update(
    config, keywords, monkeypatch, path, value
):
    before = config.get_config("")
    disk = disk_bytes(config)
    commit = Mock(wraps=config.commit_draft)
    monkeypatch.setattr(config, "commit_draft", commit)
    updates = {
        "SYSTEM_OPTIONS.DEVICE_ID": "must-not-apply",
        "WAKE_WORD_OPTIONS.WAKE_WORD": "new word",
        path: value,
    }
    ok, message = settings.save_settings(updates, config)
    assert not ok and message
    assert config.get_config("") == before
    assert disk_bytes(config) == disk
    assert not keywords.directory.exists()
    keywords.converter.assert_not_called()
    commit.assert_not_called()
    assert updates[path] == value


@pytest.mark.parametrize(
    "text,expected",
    [
        ("true", True),
        ("1", True),
        ("YES", True),
        (" on ", True),
        ("是", True),
        ("false", False),
        ("0", False),
        ("No", False),
        ("off", False),
        ("否", False),
    ],
)
def test_bool_accepts_only_known_spellings(text, expected):
    assert settings.parse_field_value(fields()["AEC_OPTIONS.ENABLED"], text) is expected


@pytest.mark.parametrize(
    "extras",
    [
        {"disabled_tools": "tool.name"},
        {"disabled_tools": ["valid", 17]},
        {"disabled_tools": [""]},
        {"disabled_tools": ["  "]},
        {"device_updates": []},
        {"device_updates": {"SYSTEM_OPTIONS.DEVICE_ID": "wrong"}},
        {"device_updates": {"AUDIO_DEVICES.input_channels": 2}},
        {"device_updates": {"AUDIO_DEVICES.input_device_id": True}},
        {"device_updates": {"AUDIO_DEVICES.output_device_id": "1"}},
        {"device_updates": {"AUDIO_DEVICES.output_device_id": -2}},
        {"device_updates": {"AUDIO_DEVICES.input_device_name": 7}},
    ],
)
def test_invalid_extras_cannot_apply_other_changes(config, keywords, extras):
    before = config.get_config("")
    disk = disk_bytes(config)
    ok, message = settings.save_settings(
        {
            "SYSTEM_OPTIONS.DEVICE_ID": "draft",
            "WAKE_WORD_OPTIONS.WAKE_WORD": "new word",
        },
        config,
        **extras,
    )
    assert not ok and message
    assert config.get_config("") == before
    assert disk_bytes(config) == disk
    keywords.converter.assert_not_called()


def test_device_updates_override_name_form_and_clear_disabled(config):
    config.update_config("MCP_TOOLS.DISABLED", ["old.tool"], save=False)
    assert settings.save_settings(
        {"AUDIO_DEVICES.input_device_name": "old-widget-name"},
        config,
        disabled_tools=[],
        device_updates={
            "AUDIO_DEVICES.input_device_id": -1,
            "AUDIO_DEVICES.input_device_name": "",
            "AUDIO_DEVICES.output_device_id": None,
            "AUDIO_DEVICES.output_device_name": None,
        },
    )[0]
    assert config.get_config("MCP_TOOLS.DISABLED") == []
    assert config.get_config("AUDIO_DEVICES.input_device_id") == -1
    assert config.get_config("AUDIO_DEVICES.input_device_name") in ("", None)
    assert config.get_config("AUDIO_DEVICES.output_device_id") is None


def test_language_is_derived_and_keywords_use_active_directory(
    config, keywords, tmp_path
):
    new_directory = tmp_path / "next-start-keywords"
    draft = {
        "WAKE_WORD_OPTIONS.WAKE_WORD": "test",
        "WAKE_WORD_OPTIONS.WAKE_WORD_LANG": "zh",
        "PATHS.KEYWORDS_DIR": str(new_directory),
    }
    ok, message = settings.save_settings(draft, config)
    assert ok, message
    keywords.converter.assert_called_once_with("test")
    assert config.get_config("WAKE_WORD_OPTIONS.WAKE_WORD_LANG") == "en"
    assert config.get_config("WAKE_WORD_OPTIONS.MODEL_PATH") == "models/en"
    assert config.get_config("PATHS.KEYWORDS_DIR") == str(new_directory)
    assert (keywords.directory / "en_keywords.txt").read_text() == "TEST @test\n"
    assert not new_directory.exists()
    assert list(keywords.directory.iterdir()) == [
        keywords.directory / "en_keywords.txt"
    ]


def test_readonly_language_does_not_apply_direct_edits(config, keywords):
    before = config.get_config("WAKE_WORD_OPTIONS.WAKE_WORD_LANG")
    assert settings.save_settings(
        {"WAKE_WORD_OPTIONS.WAKE_WORD_LANG": "en"}, config
    ) == (True, "无变更")
    assert config.get_config("WAKE_WORD_OPTIONS.WAKE_WORD_LANG") == before
    keywords.converter.assert_not_called()


@pytest.mark.parametrize("word", ["", "new word"])
def test_wake_conversion_failure_keeps_configuration(config, keywords, word):
    before = config.get_config("")
    disk = disk_bytes(config)
    keywords.converter.side_effect = ValueError("conversion failed")
    ok, message = settings.save_settings(
        {"WAKE_WORD_OPTIONS.WAKE_WORD": word, "SYSTEM_OPTIONS.DEVICE_ID": "draft"},
        config,
    )
    assert not ok and message
    assert config.get_config("") == before
    assert disk_bytes(config) == disk
    assert not keywords.directory.exists()


def test_keyword_atomic_replace_failure_prevents_commit(config, keywords, monkeypatch):
    keywords.directory.mkdir()
    target = keywords.directory / "en_keywords.txt"
    target.write_text("previous\n")
    before = config.get_config("")
    disk = disk_bytes(config)
    replace = settings.os.replace

    def fail_keyword_replace(source, destination):
        if Path(destination) == target:
            raise OSError("keyword write denied")
        return replace(source, destination)

    monkeypatch.setattr(settings.os, "replace", fail_keyword_replace)
    commit = Mock(wraps=config.commit_draft)
    monkeypatch.setattr(config, "commit_draft", commit)
    ok, message = settings.save_settings(
        {"WAKE_WORD_OPTIONS.WAKE_WORD": "test"}, config
    )
    assert not ok and "keyword write denied" in message
    assert config.get_config("") == before
    assert disk_bytes(config) == disk
    assert target.read_text() == "previous\n"
    assert list(keywords.directory.iterdir()) == [target]
    commit.assert_not_called()


def test_commit_failure_keeps_runtime_and_draft_but_keywords_may_exist(
    config, keywords, monkeypatch
):
    before = config.get_config("")
    values = {"WAKE_WORD_OPTIONS.WAKE_WORD": "test"}
    monkeypatch.setattr(
        config, "commit_draft", lambda draft: "configuration commit failed"
    )
    ok, message = settings.save_settings(values, config)
    assert (ok, message) == (False, "configuration commit failed")
    assert config.get_config("") == before
    assert values == {"WAKE_WORD_OPTIONS.WAKE_WORD": "test"}
    assert (keywords.directory / "en_keywords.txt").read_text() == "TEST @test\n"


def test_real_config_write_failure_preserves_runtime_and_disk(monkeypatch, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    before = config.get_config("")
    disk = disk_bytes(config)
    monkeypatch.setattr(
        config_module.os, "replace", Mock(side_effect=OSError("disk unavailable"))
    )
    values = {"SYSTEM_OPTIONS.DEVICE_ID": "draft"}
    ok, message = settings.save_settings(values, config)
    assert not ok and "保存配置失败" in message
    assert config.get_config("") == before
    assert disk_bytes(config) == disk
    assert values["SYSTEM_OPTIONS.DEVICE_ID"] == "draft"


def test_reload_failure_returns_error_preserves_new_disk_old_runtime(
    monkeypatch, tmp_path
):
    config = ConfigManager(config_file=tmp_path / "config.json")
    before = config.get_config("")
    monkeypatch.setattr(config, "reload_config", lambda **kwargs: False)
    values = {"SYSTEM_OPTIONS.DEVICE_ID": "disk-only"}
    ok, message = settings.save_settings(values, config)
    assert not ok and "已写入" in message and "运行时" in message
    assert config.get_config("") == before
    assert (
        json.loads(config.config_file.read_text())["SYSTEM_OPTIONS"]["DEVICE_ID"]
        == "disk-only"
    )
    assert values["SYSTEM_OPTIONS.DEVICE_ID"] == "disk-only"


def test_preview_delegates_to_converter_without_qt_or_writes(monkeypatch):
    convert = Mock(return_value=("LINE", "zh", "models/zh"))
    monkeypatch.setitem(
        sys.modules,
        "src.audio_processing.keyword_converters",
        SimpleNamespace(convert_wake_word=convert),
    )
    assert settings.preview_wake_word("  你好  ") == ("LINE", "zh", "models/zh")
    convert.assert_called_once_with("你好")


def test_import_and_ordinary_save_do_not_import_qt_textual_or_converters():
    code = """
import builtins
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.startswith(("PySide6", "textual", "src.ui.gui", "src.audio_processing.keyword_converters")):
        raise AssertionError("unexpected import: " + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from src.ui.tui.settings_data import load_setting_values, save_settings
from src.utils.config_manager import ConfigManager
config = ConfigManager.from_dict()
values = load_setting_values(config)
values["SYSTEM_OPTIONS.DEVICE_ID"] = "plain-python"
assert save_settings(values, config)[0]
assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "plain-python"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
