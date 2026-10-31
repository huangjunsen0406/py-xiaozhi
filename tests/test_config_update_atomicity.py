"""Fault injection and concurrent writes without touching user data or devices."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from src.activation.ota import OtaConfigClient
from src.utils.audio_device import AudioDeviceManager
from src.utils.config_manager import ConfigManager


@pytest.mark.parametrize("batch", [False, True])
@pytest.mark.parametrize("failure", ["replace", "serialize"])
def test_rejected_update_preserves_memory_disk_and_removes_temporary(
    tmp_path, monkeypatch, batch, failure
):
    config = ConfigManager(tmp_path / "config.json")
    before, disk = config.get_config(""), config.config_file.read_bytes()
    value = object() if failure == "serialize" else "new"
    if failure == "replace":
        monkeypatch.setattr(
            "src.utils.config_manager.os.replace", Mock(side_effect=OSError("denied"))
        )
    updates = {"SYSTEM_OPTIONS.DEVICE_ID": "must-not-apply", "EXTRA": value}
    if batch:
        assert not config.update_configs(updates)
    else:
        assert not config.update_config("SYSTEM_OPTIONS.DEVICE_ID", value)
    assert config.get_config("") == before
    assert config.config_file.read_bytes() == disk
    assert list(tmp_path.iterdir()) == [config.config_file]


def test_invalid_second_path_cannot_partially_apply(tmp_path):
    config = ConfigManager(tmp_path / "config.json")
    before, disk = config.get_config(""), config.config_file.read_bytes()
    assert not config.update_configs({"CUSTOM.valid": 1, "bad..path": 2})
    assert config.get_config("") == before
    assert config.config_file.read_bytes() == disk


def test_concurrent_updates_preserve_every_successful_write(tmp_path, monkeypatch):
    config = ConfigManager(tmp_path / "config.json")
    barrier = threading.Barrier(8)
    original_save = config._save_config
    active = 0
    maximum = 0

    def save(candidate):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        try:
            return original_save(candidate)
        finally:
            active -= 1

    monkeypatch.setattr(config, "_save_config", save)

    def update(index):
        barrier.wait(timeout=3)
        return config.update_configs({f"CUSTOM.worker_{index}": index})

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert all(pool.map(update, range(8)))
    expected = {f"worker_{index}": index for index in range(8)}
    assert maximum == 1
    assert config.get_config("CUSTOM") == expected
    assert json.loads(config.config_file.read_text())["CUSTOM"] == expected
    assert list(tmp_path.iterdir()) == [config.config_file]


@pytest.mark.parametrize("saved", [False, True])
def test_device_detection_submits_all_six_fields_once(monkeypatch, saved):
    config = ConfigManager.from_dict()
    batch = Mock(return_value=saved)
    monkeypatch.setattr(config, "update_configs", batch)
    monkeypatch.setattr(
        config, "update_config", Mock(side_effect=AssertionError("single write"))
    )
    devices = {
        "input": {"name": "mic", "index": 3, "sample_rate": 48000, "channels": 2},
        "output": {"name": "speaker", "index": 4, "sample_rate": 24000, "channels": 2},
    }
    monkeypatch.setattr("src.utils.audio_device.select_audio_device", devices.get)
    selected = AudioDeviceManager(config).load_or_detect_devices()
    assert selected.input_device_id == 3 and selected.output_device_id == 4
    batch.assert_called_once_with(
        {
            "AUDIO_DEVICES.input_device_name": "mic",
            "AUDIO_DEVICES.input_sample_rate": 48000,
            "AUDIO_DEVICES.input_channels": 1,
            "AUDIO_DEVICES.output_device_name": "speaker",
            "AUDIO_DEVICES.output_sample_rate": 24000,
            "AUDIO_DEVICES.output_channels": 2,
        }
    )


def test_ota_save_failure_keeps_config_and_activation_state(tmp_path, monkeypatch):
    config = ConfigManager(tmp_path / "config.json")
    client = OtaConfigClient(config, SimpleNamespace())
    client.activation_data = {"old": "challenge"}
    before = config.get_config("")
    monkeypatch.setattr(config, "_save_config", lambda candidate: False)
    with pytest.raises(OSError, match="OTA 配置保存失败"):
        client._process_ota_response({"websocket": {"url": "wss://invalid"}})
    assert config.get_config("") == before
    assert client.activation_data == {"old": "challenge"}
    assert client.server_activated is False


@pytest.mark.parametrize("failed_id", ["CLIENT_ID", "DEVICE_ID"])
def test_ota_initialization_rejects_unsaved_identity(tmp_path, monkeypatch, failed_id):
    config = ConfigManager(tmp_path / "config.json")
    if failed_id == "DEVICE_ID":
        assert config.update_config("SYSTEM_OPTIONS.CLIENT_ID", "existing-client")
    client = OtaConfigClient(
        config, SimpleNamespace(get_mac_address=lambda: "00:11:22:33:44:55")
    )
    before = config.get_config("")
    monkeypatch.setattr(config, "_save_config", lambda candidate: False)
    with pytest.raises(OSError, match=f"保存 {failed_id} 失败"):
        client.initialize_config()
    assert config.get_config("") == before
