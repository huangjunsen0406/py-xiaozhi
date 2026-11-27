"""AudioDeviceManager 声道数裁剪与配置保存测试."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.audio_device import AudioDeviceManager
from src.utils.config_manager import ConfigManager


@pytest.mark.parametrize(
    ("reported_channels", "expected_channels"),
    [
        (1, 1),
        (2, 2),
        (6, 2),
        (128, 2),
    ],
)
def test_output_channels_clamped_to_stereo(
    reported_channels: int, expected_channels: int
) -> None:
    """ALSA 默认设备上报 128 声道等多声道时，输出声道数应裁剪到 1~2 声道。"""
    cfg = ConfigManager.from_dict({})
    manager = AudioDeviceManager(cfg)

    fake_input = {
        "index": 0,
        "name": "default",
        "sample_rate": 48000,
        "channels": 32,
    }
    fake_output = {
        "index": 1,
        "name": "default",
        "sample_rate": 48000,
        "channels": reported_channels,
    }

    with patch(
        "src.utils.audio_device.select_audio_device",
        side_effect=lambda kind: fake_input if kind == "input" else fake_output,
    ):
        device_cfg = manager.load_or_detect_devices()

    assert device_cfg.input_channels == 1
    assert device_cfg.output_channels == expected_channels
    assert cfg.get_config("AUDIO_DEVICES.output_channels") == expected_channels


def test_stale_128_output_channels_in_config_gets_repaired() -> None:
    """旧配置中已保存 output_channels=128 时，启动加载应自动修正为 2。"""
    cfg = ConfigManager.from_dict(
        {
            "AUDIO_DEVICES": {
                "input_device_name": "default",
                "output_device_name": "default",
                "output_channels": 128,
            }
        }
    )
    manager = AudioDeviceManager(cfg)

    fake_input = {
        "index": 0,
        "name": "default",
        "sample_rate": 48000,
        "channels": 32,
    }
    fake_output = {
        "index": 1,
        "name": "default",
        "sample_rate": 48000,
        "channels": 128,
    }

    with patch(
        "src.utils.audio_device.find_device_by_name",
        side_effect=lambda kind, _name: fake_input if kind == "input" else fake_output,
    ):
        device_cfg = manager.load_or_detect_devices()

    assert device_cfg.output_channels == 2
    assert cfg.get_config("AUDIO_DEVICES.output_channels") == 2
