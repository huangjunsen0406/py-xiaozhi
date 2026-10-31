"""Audio runtime configuration stays local across construction and hot reload."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.audio_codecs.audio_codec import AudioCodec
from src.audio_codecs.music_decoder import MusicDecoder
from src.audio_processing.wake_word_detect import WakeWordDetector
from src.constants.constants import AudioConfig
from src.mcp.tools.music.music_player import MusicPlayer
from src.notifications.notification_player import NotificationPlayer
from src.utils.audio_device import AudioDeviceManager, DeviceConfig
from src.utils.config_manager import ConfigManager


def config_for(rate=24000, duration=20):
    return ConfigManager.from_dict(
        {
            "AUDIO_DEVICES": {
                "opus_output_sample_rate": rate,
                "frame_duration": duration,
            },
            "WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False},
        }
    )


def test_audio_format_reload_changes_only_its_runtime():
    first_config = config_for(24000, 20)
    second_config = config_for(48000, 60)
    first = AudioConfig.from_config(first_config)
    second = AudioConfig.from_config(second_config)
    first_config.update_config("AUDIO_DEVICES.frame_duration", 40)
    first.reload(first_config)
    assert (first.FRAME_DURATION, first.INPUT_FRAME_SIZE) == (40, 640)
    assert (second.OUTPUT_SAMPLE_RATE, second.FRAME_DURATION) == (48000, 60)
    assert AudioConfig.FRAME_DURATION == 20


def test_default_components_do_not_read_process_config_or_create_user_paths(
    monkeypatch,
):
    import src.utils.config_manager as config_module
    import src.mcp.tools.music.cache as cache_module

    def forbidden(*args, **kwargs):
        raise AssertionError("process configuration or user directory accessed")

    monkeypatch.setattr(config_module, "get_config", forbidden)
    monkeypatch.setattr(ConfigManager, "_init_config_paths", forbidden)
    monkeypatch.setattr(cache_module, "get_music_cache_dir", forbidden)
    codec = AudioCodec()
    detector = WakeWordDetector()
    music = MusicPlayer()
    notify = NotificationPlayer()
    assert codec.config.config_file is None
    assert detector.config.config_file is None
    assert music.config["DEFAULT_BR"] == "320k"
    assert notify.audio_config is not codec.audio_config


@pytest.mark.asyncio
async def test_codec_hot_reload_uses_local_format_before_choosing_device_frames(
    monkeypatch,
):
    import src.audio_codecs.audio_codec as codec_module

    first_config = config_for(24000, 20)
    second_config = config_for(48000, 60)
    first_format = AudioConfig.from_config(first_config)
    first = AudioCodec(first_config, first_format)
    second = AudioCodec(second_config)
    device = DeviceConfig(0, 1, 48000, 48000, 1, 2, 960, 960)
    manager = SimpleNamespace(config=first_config)

    def detect():
        assert first.audio_config.FRAME_DURATION == 40
        return device

    manager.load_or_detect_devices = detect
    first.device_manager = manager
    first.stream_manager = Mock()
    monkeypatch.setattr(codec_module, "AudioStreamManager", Mock())
    monkeypatch.setattr(codec_module, "OpusCodec", Mock())
    monkeypatch.setattr(first, "_setup_aec", Mock())
    setup_output = Mock(wraps=first.converter.setup_output_converter)
    monkeypatch.setattr(first.converter, "setup_output_converter", setup_output)
    first_config.update_config("AUDIO_DEVICES.frame_duration", 40)
    first_config.update_config("AUDIO_DEVICES.opus_output_sample_rate", 16000)
    assert await first.reload_devices(reenumerate=False)
    assert first.audio_config is first_format
    setup_output.assert_called_once_with(
        from_rate=16000, to_rate=48000, from_channels=1, to_channels=2
    )
    assert first._mix_chunk == 320
    assert second.audio_config.OUTPUT_SAMPLE_RATE == 48000
    assert second.audio_config.FRAME_DURATION == 60
    await first.close()
    await second.close()


def test_device_frames_use_injected_audio_format(monkeypatch):
    import src.utils.audio_device as device_module

    def select(kind):
        return {"index": 0, "name": kind, "sample_rate": 48000, "channels": 2}

    monkeypatch.setattr(device_module, "select_audio_device", select)
    manager = AudioDeviceManager(config_for(), AudioConfig(FRAME_DURATION=60))
    devices = manager.load_or_detect_devices()
    assert devices.input_frame_size == devices.output_frame_size == 2880
    assert manager.config.config_file is None


def test_music_settings_and_decoders_follow_their_own_runtime():
    first = MusicPlayer(
        ConfigManager.from_dict({"MUSIC": {"DEFAULT_QUALITY": "128k"}})
    )
    second = MusicPlayer(
        ConfigManager.from_dict({"MUSIC": {"DEFAULT_QUALITY": "320k"}})
    )
    assert first.config["DEFAULT_BR"] == "128k"
    assert second.config["DEFAULT_BR"] == "320k"
    first._engine.audio_codec = SimpleNamespace(
        audio_config=AudioConfig(OUTPUT_SAMPLE_RATE=16000, FRAME_DURATION=40)
    )
    decoder = first._engine._make_decoder()
    assert (decoder.sample_rate, decoder.frame_duration) == (16000, 40)
    first._engine.audio_codec = SimpleNamespace(
        audio_config=AudioConfig(OUTPUT_SAMPLE_RATE=48000, FRAME_DURATION=60)
    )
    resumed = first._engine._make_decoder()
    assert (resumed.sample_rate, resumed.frame_duration) == (48000, 60)
    assert decoder.sample_rate == 16000


@pytest.mark.asyncio
async def test_disabled_wake_detector_uses_injected_configuration(monkeypatch):
    import src.utils.config_manager as config_module

    monkeypatch.setattr(
        config_module, "get_config", lambda: pytest.fail("global config accessed")
    )
    detector = WakeWordDetector(config_for())
    assert await detector.initialize() is False
    assert detector.enabled is False


def test_decoder_rejects_invalid_frame_duration():
    with pytest.raises(ValueError, match="frame_duration"):
        MusicDecoder(frame_duration=0)


@pytest.mark.asyncio
async def test_notification_uses_bound_codec_format_and_snapshots_progress_rate(
    monkeypatch,
):
    import src.notifications.notification_player as notification_module

    decoder = SimpleNamespace(
        start_decode=AsyncMock(return_value=True), stop=AsyncMock()
    )
    factory = Mock(return_value=decoder)
    monkeypatch.setattr(notification_module, "MusicDecoder", factory)
    player = NotificationPlayer(AudioConfig(OUTPUT_SAMPLE_RATE=24000))
    player._codec = SimpleNamespace(
        audio_config=AudioConfig(OUTPUT_SAMPLE_RATE=16000, FRAME_DURATION=40),
        set_notification_playback_callbacks=Mock(),
        clear_notification_queue=AsyncMock(),
    )
    monkeypatch.setattr(player, "_consume", AsyncMock())
    assert await player.start("https://example.com/notify.wav", [], AsyncMock())
    factory.assert_called_once_with(sample_rate=16000, channels=1, frame_duration=40)
    player._codec.audio_config.OUTPUT_SAMPLE_RATE = 48000
    assert player._playback_sample_rate == 16000
    await player.stop()


def test_music_cache_resolves_default_path_only_on_first_use(monkeypatch, tmp_path):
    import src.mcp.tools.music.cache as cache_module

    resolve = Mock(return_value=tmp_path / "cache")
    monkeypatch.setattr(cache_module, "get_music_cache_dir", resolve)
    player = MusicPlayer(ConfigManager.from_dict())
    resolve.assert_not_called()
    player.prepare_for_io()
    resolve.assert_called_once_with()
    assert player.cache_dir == tmp_path / "cache"
    assert player.temp_cache_dir.is_dir()
