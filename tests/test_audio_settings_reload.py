"""Settings saves preserve media playback unless the audio pipeline actually needs rebuilding."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.media import media_player as media_module
from src.media.media_player import MediaPlayer
from src.plugins.audio import AudioPlugin
from src.utils.config_manager import ConfigManager


@pytest.fixture
async def audio_settings(monkeypatch):
    """Run the real plugin, bus and MediaPlayer with hardware/decoder boundaries faked."""
    import src.audio_codecs.audio_codec as codec_module

    monkeypatch.delenv("XIAOZHI_DISABLE_AUDIO", raising=False)
    config = ConfigManager.from_dict()
    bus = EventBus()
    timeline, published, states, decoders, reload_results = [], [], [], [], []
    audio_config = AudioConfig.from_config(config)
    player = MediaPlayer(config, audio_config=audio_config)
    player.attach(bus)

    class Track:
        def __init__(self, codec):
            self._codec = codec

        async def write_pcm(self, pcm):
            await self._codec.written.put(pcm)

        async def clear(self):
            return 0

    class Codec:
        def __init__(self, *, config, audio_config):
            self.config = config
            self.audio_config = audio_config
            self.aec_active = False
            self.initialize = AsyncMock()
            self.set_encoded_callback = Mock()
            self.set_encode_gate = Mock()
            self.stop_streams_for_enumeration = Mock()
            self.written = asyncio.Queue()
            self.reload_devices = AsyncMock(side_effect=self._reload)

        def get_background_track(self):
            return Track(self)

        async def _reload(self, *, reenumerate):
            # Detach must finish stopping the media session before hardware resets.
            assert player._codec is None
            assert not player.is_playing
            timeline.append(("reload", reenumerate))
            result = reload_results.pop(0) if reload_results else True
            if isinstance(result, BaseException):
                raise result
            if result:
                self.audio_config.reload(self.config)
            return result

    class Decoder:
        get_duration = AsyncMock(return_value=60)

        def __init__(self, **_kwargs):
            self.error = None
            self.completed_successfully = False
            self.stop = AsyncMock()
            decoders.append(self)

        def is_running(self):
            return True

        async def start_decode(self, _source, output_queue, *_args, **_kwargs):
            self.queue = output_queue
            return True

    async def codec_changed(codec=None):
        published.append(codec)
        timeline.append(("detach" if codec is None else "bind", codec))

    async def state_changed(data):
        states.append(data.state)

    monkeypatch.setattr(codec_module, "AudioCodec", Codec)
    monkeypatch.setattr(media_module, "AudioDecoder", Decoder)
    bus.on(Events.AUDIO_CODEC_CHANGED, codec_changed)
    bus.on(Events.MEDIA_STATE_CHANGED, state_changed)
    plugin = AudioPlugin()
    await plugin.setup(
        SimpleNamespace(
            event_bus=bus, audio_config=audio_config, get_config=lambda: config
        ),
        SimpleNamespace(),
    )
    codec = plugin.codec
    codec.initialize.assert_awaited_once()
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
    timeline.clear()
    published.clear()
    try:
        yield SimpleNamespace(
            config=config,
            bus=bus,
            plugin=plugin,
            codec=codec,
            player=player,
            timeline=timeline,
            published=published,
            states=states,
            decoders=decoders,
            reload_results=reload_results,
        )
    finally:
        await player.detach()
        await plugin.stop()


async def _start_media(runtime):
    res = await runtime.player.play_url(
        "https://example.test/settings.ogg", title="Settings regression"
    )
    assert res["status"] == "success"
    decoder = runtime.decoders[-1]
    await _feed_pcm(runtime, decoder)
    assert runtime.player.is_playing
    assert not runtime.player.paused
    return decoder


async def _feed_pcm(runtime, decoder):
    pcm = np.zeros(480, dtype=np.float32)
    await decoder.queue.put(pcm)
    delivered = await asyncio.wait_for(runtime.codec.written.get(), timeout=1)
    assert delivered is pcm


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "compact"),
        ("SHORTCUTS.MANUAL_PRESS.key", "p"),
        ("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "wss://example.test/new"),
        ("MCP_TOOLS.DISABLED", ["media.stop"]),
        ("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False),
        ("AEC_OPTIONS.MEDIA_PARALLEL", False),
        ("AUDIO_DEVICES.frame_duration", 20),
        ("AEC_OPTIONS.FRAME_DELAY", 3),
    ],
)
async def test_unrelated_or_unchanged_save_keeps_media_playing(
    audio_settings, path, value
):
    runtime = audio_settings
    decoder = await _start_media(runtime)
    consumer = runtime.player._playback_task
    assert runtime.config.update_config(path, value)

    await runtime.bus.emit(Events.CONFIG_CHANGED)

    runtime.codec.reload_devices.assert_not_awaited()
    assert runtime.published == []
    assert runtime.player._codec is runtime.codec
    assert runtime.player._playback_task is consumer
    assert not consumer.done()
    assert runtime.player.is_playing and not runtime.player.paused
    decoder.stop.assert_not_awaited()
    assert runtime.states == ["playing"]
    await _feed_pcm(runtime, decoder)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("AUDIO_DEVICES.input_device_name", "New microphone"),
        ("AUDIO_DEVICES.output_device_id", 5),
        ("AUDIO_DEVICES.input_sample_rate", 48000),
        ("AUDIO_DEVICES.output_channels", 2),
        ("AUDIO_DEVICES.opus_output_sample_rate", 16000),
        ("AUDIO_DEVICES.frame_duration", 40),
        ("AEC_OPTIONS.ENABLED", True),
        ("AEC_OPTIONS.FRAME_DELAY", 4),
        ("AEC_OPTIONS.ENABLE_PREPROCESS", False),
    ],
)
async def test_audio_change_detaches_then_reloads_then_rebinds(
    audio_settings, path, value
):
    runtime = audio_settings
    decoder = await _start_media(runtime)
    assert runtime.config.update_config(path, value)

    await runtime.bus.emit(Events.CONFIG_CHANGED)

    assert runtime.timeline == [
        ("detach", None),
        ("reload", True),
        ("bind", runtime.codec),
    ]
    runtime.codec.reload_devices.assert_awaited_once_with(reenumerate=True)
    decoder.stop.assert_awaited_once()
    assert not runtime.player.is_playing
    assert runtime.states == ["playing", "stopped"]
    assert runtime.player._codec is runtime.codec

    await runtime.bus.emit(Events.CONFIG_CHANGED)
    runtime.codec.reload_devices.assert_awaited_once()
    assert runtime.published == [None, runtime.codec]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, OSError("device unavailable")])
async def test_failed_reload_retries_even_when_settings_are_reverted(
    audio_settings, failure
):
    runtime = audio_settings
    await _start_media(runtime)
    runtime.reload_results.extend([failure, True])
    assert runtime.config.update_config("AUDIO_DEVICES.frame_duration", 40)

    await runtime.bus.emit(Events.CONFIG_CHANGED)
    assert runtime.published == [None]
    assert runtime.player._codec is None
    assert not runtime.player.is_playing

    assert runtime.config.update_config("AUDIO_DEVICES.frame_duration", 20)
    await runtime.bus.emit(Events.CONFIG_CHANGED)

    assert runtime.codec.reload_devices.await_count == 2
    assert runtime.published == [None, None, runtime.codec]
    assert runtime.player._codec is runtime.codec
    await _start_media(runtime)
    await runtime.bus.emit(Events.CONFIG_CHANGED)
    assert runtime.codec.reload_devices.await_count == 2
    assert runtime.player.is_playing


@pytest.mark.asyncio
@pytest.mark.parametrize("change_before_refresh", [False, True])
async def test_explicit_refresh_reloads_and_updates_baseline(
    audio_settings, monkeypatch, change_before_refresh
):
    from src.utils import audio_utils

    runtime = audio_settings
    await _start_media(runtime)
    if change_before_refresh:
        assert runtime.config.update_config("AUDIO_DEVICES.output_device_name", "USB")
    devices = {"input": [{"name": "Mic"}], "output": [{"name": "USB"}]}
    refresh = Mock()
    enumerate_devices = Mock(return_value=devices)
    monkeypatch.setattr(audio_utils, "refresh_portaudio_devices", refresh)
    monkeypatch.setattr(audio_utils, "list_audio_devices", enumerate_devices)
    completed = asyncio.get_running_loop().create_future()

    await runtime.bus.emit(Events.AUDIO_DEVICES_REFRESH_REQUEST, completed)

    assert completed.done() and completed.result() == devices
    assert runtime.timeline == [
        ("detach", None),
        ("reload", False),
        ("bind", runtime.codec),
    ]
    runtime.codec.stop_streams_for_enumeration.assert_called_once_with()
    refresh.assert_called_once_with(reinitialize=True)
    enumerate_devices.assert_called_once_with(include_virtual=True)
    runtime.codec.reload_devices.assert_awaited_once_with(reenumerate=False)
    assert runtime.player._codec is runtime.codec

    decoder = await _start_media(runtime)
    assert runtime.config.update_config("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "compact")
    await runtime.bus.emit(Events.CONFIG_CHANGED)

    runtime.codec.reload_devices.assert_awaited_once()
    assert runtime.published == [None, runtime.codec]
    assert runtime.player.is_playing
    decoder.stop.assert_not_awaited()
    await _feed_pcm(runtime, decoder)
