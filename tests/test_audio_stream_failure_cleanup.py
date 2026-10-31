"""Audio stream failures clean every handle and remain retryable."""

import asyncio
import builtins
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.audio_codecs.audio_codec import AudioCodec
from src.audio_codecs.stream_manager import AudioStreamManager
from src.constants.constants import AudioConfig, DeviceState
from src.core.event_bus import EventBus, Events
from src.core.resource_pool import ResourcePool
from src.plugins.audio import AudioPlugin
from src.utils.audio_device import DeviceConfig
from src.utils.config_manager import ConfigManager


def device_config():
    return DeviceConfig(0, 1, 16000, 24000, 1, 1, 320, 480)


class Stream:
    def __init__(self, *, fail_stop=0, fail_close=0, fail_start=False):
        self.active = False
        self.closed = False
        self.fail_stop = fail_stop
        self.fail_close = fail_close
        self.fail_start = fail_start
        self.stop_calls = 0
        self.close_calls = 0

    def start(self):
        self.active = True
        if self.fail_start:
            raise OSError("start failed")

    def stop(self):
        self.stop_calls += 1
        if self.fail_stop:
            self.fail_stop -= 1
            raise OSError("stop failed")
        self.active = False

    def close(self):
        self.close_calls += 1
        if self.fail_close:
            self.fail_close -= 1
            raise OSError("close failed")
        self.closed = True
        self.active = False


@pytest.mark.asyncio
async def test_codec_close_attempts_every_stream_despite_input_stop_exception():
    codec = AudioCodec(ConfigManager.from_dict())
    manager = AudioStreamManager(device_config())
    first = Stream(fail_stop=1)
    second = Stream()
    first.start()
    second.start()
    manager.input_stream, manager.output_stream = first, second
    codec.stream_manager = manager
    await codec.close()
    assert first.closed and second.closed
    assert first.close_calls == second.close_calls == 1
    assert manager._stopped and not manager.is_active()
    assert codec._closed


@pytest.mark.asyncio
async def test_failed_handle_close_retains_dsp_and_retry_finishes_cleanup(monkeypatch):
    codec = AudioCodec(ConfigManager.from_dict())
    manager = AudioStreamManager(device_config())
    first = Stream(fail_stop=2, fail_close=1)
    second = Stream()
    first.start()
    second.start()
    manager.input_stream, manager.output_stream = first, second
    codec.stream_manager = manager
    converter_close = Mock(wraps=codec.converter.close)
    opus_close = Mock(wraps=codec.opus_codec.close)
    monkeypatch.setattr(codec.converter, "close", converter_close)
    monkeypatch.setattr(codec.opus_codec, "close", opus_close)
    await codec.close()
    assert first.active and not first.closed
    assert second.closed
    assert manager.input_stream is first
    assert not manager._stopped
    assert not codec._closed
    converter_close.assert_not_called()
    opus_close.assert_not_called()
    await codec.close()
    assert first.closed
    assert codec._closed and manager._stopped
    converter_close.assert_called_once()
    opus_close.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "phase", ["input_construct", "output_construct", "input_start", "output_start"]
)
async def test_reload_failure_rolls_back_partial_streams_through_event_bus(
    monkeypatch, phase
):
    import src.audio_codecs.stream_manager as stream_module

    config = ConfigManager.from_dict()
    codec = AudioCodec(config)
    codec.device_config = device_config()
    codec.device_manager = SimpleNamespace(
        config=config, load_or_detect_devices=device_config
    )
    old = AudioStreamManager(device_config())
    original_input, original_output = Stream(), Stream()
    original_input.start()
    original_output.start()
    old.input_stream, old.output_stream = original_input, original_output
    codec.stream_manager = old
    replacement_input = Stream(fail_start=phase == "input_start")
    replacement_output = Stream(fail_start=phase == "output_start")

    def input_stream(**kwargs):
        if phase == "input_construct":
            raise OSError("input constructor failed")
        return replacement_input

    monkeypatch.setattr(stream_module.sd, "InputStream", input_stream)

    def output(**kwargs):
        if phase == "output_construct":
            raise OSError("output constructor failed")
        return replacement_output

    monkeypatch.setattr(stream_module.sd, "OutputStream", output)
    monkeypatch.setattr(codec, "_setup_aec", lambda: None)
    # Exercise the actual handler and publication contract without reenumerating.
    reload_devices = codec.reload_devices
    monkeypatch.setattr(
        codec, "reload_devices", lambda **kwargs: reload_devices(reenumerate=False)
    )
    plugin = AudioPlugin()
    plugin.codec = codec
    bus = EventBus()
    plugin._ctx = SimpleNamespace(event_bus=bus)
    published = []

    async def changed(value=None):
        published.append(value)

    bus.on(Events.AUDIO_CODEC_CHANGED, changed)
    bus.on(Events.CONFIG_CHANGED, plugin._on_config_changed)
    await bus.emit(Events.CONFIG_CHANGED)
    assert published == [None]
    assert original_input.closed and original_output.closed
    if phase != "input_construct":
        assert replacement_input.closed and not replacement_input.active
    if phase in {"input_start", "output_start"}:
        assert replacement_output.closed and not replacement_output.active
    assert codec.stream_manager is None or not codec.stream_manager.is_active()
    await codec.close()


@pytest.mark.asyncio
async def test_reload_keeps_old_manager_when_native_close_needs_retry(monkeypatch):
    import src.audio_codecs.audio_codec as codec_module

    config = ConfigManager.from_dict()
    codec = AudioCodec(config)
    manager = AudioStreamManager(device_config())
    manager.input_stream = Stream(fail_close=1)
    codec.stream_manager = manager
    construct = Mock()
    monkeypatch.setattr(codec_module, "AudioStreamManager", construct)
    assert await codec.reload_devices(reenumerate=False) is False
    assert codec.stream_manager is manager
    construct.assert_not_called()
    assert manager.input_stream is not None
    await codec.close()
    assert codec._closed and not manager.is_active()


@pytest.mark.parametrize("is_input", [True, False])
def test_single_stream_rebuild_rolls_back_failed_start_without_closing_other(
    monkeypatch, is_input
):
    import src.audio_codecs.stream_manager as stream_module

    manager = AudioStreamManager(device_config())
    original = Stream(fail_stop=1)
    other = Stream()
    replacement = Stream(fail_start=True)
    name = "input_stream" if is_input else "output_stream"
    other_name = "output_stream" if is_input else "input_stream"
    setattr(manager, name, original)
    setattr(manager, other_name, other)
    monkeypatch.setattr(
        stream_module.sd,
        "InputStream" if is_input else "OutputStream",
        lambda **kwargs: replacement,
    )
    assert not manager.reinitialize_stream(
        is_input, input_callback=lambda *args: None, output_callback=lambda *args: None
    )
    assert original.closed and replacement.closed
    assert getattr(manager, name) is None
    assert not other.closed and getattr(manager, other_name) is other
    assert manager.stop()


@pytest.mark.asyncio
async def test_failed_replacement_cleanup_preserves_handle_until_explicit_close(
    monkeypatch,
):
    import src.audio_codecs.stream_manager as stream_module

    config = ConfigManager.from_dict()
    codec = AudioCodec(config)
    codec.device_manager = SimpleNamespace(
        config=config, load_or_detect_devices=device_config
    )
    first = Stream(fail_stop=2, fail_close=2)
    second = Stream(fail_start=True)
    monkeypatch.setattr(stream_module.sd, "InputStream", lambda **kwargs: first)
    monkeypatch.setattr(stream_module.sd, "OutputStream", lambda **kwargs: second)
    monkeypatch.setattr(codec, "_setup_aec", lambda: None)
    assert not await codec.reload_devices(reenumerate=False)
    assert codec.stream_manager.input_stream is first
    assert first.active and not first.closed
    assert second.closed
    await codec.close()
    assert first.closed and codec._closed


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["output_start", "encoded_callback"])
async def test_setup_failure_retains_codec_for_finally_registered_pool(
    monkeypatch, phase
):
    import src.audio_codecs.audio_codec as codec_module
    import src.audio_codecs.stream_manager as stream_module
    import src.utils.audio_utils as audio_utils

    monkeypatch.delenv("XIAOZHI_DISABLE_AUDIO", raising=False)
    first = Stream(
        fail_stop=2 if phase == "output_start" else 0,
        fail_close=2 if phase == "output_start" else 0,
    )
    second = Stream(fail_start=phase == "output_start")
    monkeypatch.setattr(stream_module.sd, "InputStream", lambda **kwargs: first)
    monkeypatch.setattr(stream_module.sd, "OutputStream", lambda **kwargs: second)
    monkeypatch.setattr(
        codec_module.AudioDeviceManager,
        "load_or_detect_devices",
        lambda self: device_config(),
    )
    monkeypatch.setattr(codec_module.OpusCodec, "initialize", lambda self: None)
    if phase == "encoded_callback":
        monkeypatch.setattr(
            AudioCodec,
            "set_encoded_callback",
            Mock(side_effect=RuntimeError("callback setup failed")),
        )

    plugin = AudioPlugin()
    pool = ResourcePool()
    config = ConfigManager.from_dict()
    ctx = SimpleNamespace(
        get_config=lambda: config,
        audio_config=AudioConfig.from_config(config),
        event_bus=EventBus(),
        should_capture_audio=Mock(return_value=True),
    )
    cmd = SimpleNamespace(spawn=Mock())
    published = []
    ctx.event_bus.on(
        Events.AUDIO_CODEC_CHANGED, lambda codec=None: published.append(codec)
    )
    try:
        # This mirrors bootstrap's finally boundary, including failures after initialize.
        try:
            with pytest.raises(
                (OSError, RuntimeError), match="start failed|callback setup failed"
            ):
                await plugin.setup(ctx, cmd)
        finally:
            plugin.register_resources(pool)

        codec = plugin.codec
        assert codec is not None and plugin.failed
        assert [name for name, _ in pool._resources] == ["audio.codec"]
        assert not codec._closed
        assert first.active and not first.closed
        if phase == "output_start":
            # StreamManager rollback and AudioCodec rollback both fail to close it.
            assert first.close_calls == 2
            assert second.closed
        else:
            assert second.active and not second.closed
            assert first.close_calls == second.close_calls == 0

        def close_dsp(original):
            def close():
                assert first.closed and second.closed
                original()

            return Mock(side_effect=close)

        converter_close = close_dsp(codec.converter.close)
        opus_close = close_dsp(codec.opus_codec.close)
        monkeypatch.setattr(codec.converter, "close", converter_close)
        monkeypatch.setattr(codec.opus_codec, "close", opus_close)
        reload_devices = AsyncMock()
        write_audio = AsyncMock()
        stop_for_enumeration = Mock()
        refresh = Mock()
        list_devices = Mock()
        monkeypatch.setattr(codec, "reload_devices", reload_devices)
        monkeypatch.setattr(codec, "write_audio", write_audio)
        monkeypatch.setattr(codec, "stop_streams_for_enumeration", stop_for_enumeration)
        monkeypatch.setattr(audio_utils, "refresh_portaudio_devices", refresh)
        monkeypatch.setattr(audio_utils, "list_audio_devices", list_devices)
        codec._aec = SimpleNamespace(active=True, close=Mock())

        await plugin.start()
        await plugin._on_config_changed()
        future = asyncio.get_running_loop().create_future()
        await plugin._on_devices_refresh_request(future)
        await plugin.on_incoming_audio(b"unusable")
        await plugin.on_device_state_changed(DeviceState.LISTENING)
        plugin._on_encoded_audio(b"unusable")
        assert future.result() == {"input": [], "output": []}
        assert not plugin._music_parallel_enabled()
        assert not plugin._should_send_microphone_audio()
        assert not plugin._accepting and not plugin._uplink
        assert plugin._silence_until == 0.0
        assert published == []
        cmd.spawn.assert_not_called()
        ctx.should_capture_audio.assert_not_called()
        reload_devices.assert_not_awaited()
        write_audio.assert_not_awaited()
        stop_for_enumeration.assert_not_called()
        refresh.assert_not_called()
        list_devices.assert_not_called()
        await plugin.stop()
        assert plugin.codec is codec
        converter_close.assert_not_called()
        opus_close.assert_not_called()
    finally:
        await plugin.stop()
        await pool.shutdown()

    assert first.closed and second.closed and codec._closed
    assert first.close_calls == (3 if phase == "output_start" else 1)
    converter_close.assert_called_once()
    opus_close.assert_called_once()
    assert published == [None]


@pytest.mark.asyncio
@pytest.mark.parametrize("disabled", [True, False])
async def test_setup_without_constructed_codec_registers_no_resource(
    monkeypatch, disabled
):
    if disabled:
        monkeypatch.setenv("XIAOZHI_DISABLE_AUDIO", "1")
    else:
        monkeypatch.delenv("XIAOZHI_DISABLE_AUDIO", raising=False)
    real_import = builtins.__import__
    attempts = []

    def missing_audio(name, *args, **kwargs):
        if name == "src.audio_codecs.audio_codec":
            attempts.append(name)
            raise OSError("PortAudio library not found")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_audio)
    plugin = AudioPlugin()
    pool = ResourcePool()
    try:
        try:
            if disabled:
                await plugin.setup(SimpleNamespace(), SimpleNamespace())
            else:
                with pytest.raises(OSError, match="PortAudio library not found"):
                    await plugin.setup(SimpleNamespace(), SimpleNamespace())
        finally:
            plugin.register_resources(pool)
        assert plugin.codec is None
        assert plugin.failed is not disabled
        assert pool._resources == []
        assert len(attempts) == (0 if disabled else 1)
    finally:
        await plugin.stop()
        await pool.shutdown()
