"""SettingsModel keeps injected configurations isolated from user paths."""

import pytest

pytest.importorskip("PySide6.QtCore")

from src.ui.gui.models.settings_model import SettingsModel
from src.utils.config_manager import ConfigManager


def test_memory_settings_load_save_without_user_paths(monkeypatch):
    import src.utils.resource_finder as resource_finder

    def forbidden(*_args, **_kwargs):
        raise AssertionError("memory settings accessed a user path")

    monkeypatch.setattr(resource_finder, "get_user_data_dir", forbidden)
    config = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"DEVICE_ID": "isolated-device"}}
    )
    model = SettingsModel(config_manager=config)
    assert config.config_file is None
    assert model._get_value("SYSTEM_OPTIONS.DEVICE_ID") == "isolated-device"

    model._set_value("SYSTEM_OPTIONS.DEVICE_ID", "updated-device")
    model.save()

    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "updated-device"
    assert config.config_file is None
    model._set_value("SYSTEM_OPTIONS.DEVICE_ID", "unsaved-device")
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "updated-device"
    model._load_config()
    assert model._get_value("SYSTEM_OPTIONS.DEVICE_ID") == "updated-device"


def test_independent_memory_settings_snapshots_do_not_share_nested_data():
    first_config = ConfigManager.from_dict({"AUDIO_DEVICES": {"frame_duration": 20}})
    second_config = ConfigManager.from_dict({"AUDIO_DEVICES": {"frame_duration": 60}})
    first = SettingsModel(config_manager=first_config)
    second = SettingsModel(config_manager=second_config)

    first._set_value("AUDIO_DEVICES.frame_duration", 40)
    assert first._get_value("AUDIO_DEVICES.frame_duration") == 40
    assert second._get_value("AUDIO_DEVICES.frame_duration") == 60
    assert first_config.get_config("AUDIO_DEVICES.frame_duration") == 20


def test_file_settings_save_uses_own_path_without_applying_global_overrides(
    monkeypatch, tmp_path
):
    from unittest.mock import Mock

    config = ConfigManager(config_file=tmp_path / "independent.json")
    reload_config = Mock(wraps=config.reload_config)
    monkeypatch.setattr(config, "reload_config", reload_config)
    model = SettingsModel(config_manager=config)
    model._set_value("SYSTEM_OPTIONS.DEVICE_ID", "file-device")
    model.save()
    reload_config.assert_called_once_with(apply_paths=False, strict=True)
    assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "file-device"
    assert not config.config_file.with_suffix(".tmp").exists()


def test_tui_settings_use_only_supplied_config(monkeypatch):
    from src.ui.tui.settings_data import load_setting_values, save_settings
    import src.utils.config_manager as config_module

    monkeypatch.setattr(
        config_module,
        "get_config",
        lambda: (_ for _ in ()).throw(AssertionError("global lookup")),
    )
    first = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"DEVICE_ID": "first"}})
    second = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"DEVICE_ID": "second"}})
    assert load_setting_values(first)["SYSTEM_OPTIONS.DEVICE_ID"] == "first"
    assert save_settings({"SYSTEM_OPTIONS.DEVICE_ID": "changed"}, first)[0]
    assert first.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "changed"
    assert second.get_config("SYSTEM_OPTIONS.DEVICE_ID") == "second"
