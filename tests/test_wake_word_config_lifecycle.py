"""Wake configuration events coordinate the detector lifecycle without hardware."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.plugins.wake_word import WakeWordPlugin
from src.utils.config_manager import ConfigManager


class Detector:
    def __init__(self):
        self.initialize = AsyncMock(return_value=True)
        self.start = AsyncMock(return_value=True)
        self.stop = AsyncMock()
        self.shutdown = AsyncMock()
        self.reload = AsyncMock(return_value=True)
        self.callback = None
        self.on_error = None

    def on_detected(self, callback):
        self.callback = callback


async def make_plugin(monkeypatch, *, enabled=False, create_hook=None):
    config = ConfigManager.from_dict({"WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": enabled}})
    bus = EventBus()
    ctx = SimpleNamespace(
        event_bus=bus,
        get_config=lambda: config,
        audio_config=AudioConfig.from_config(config),
    )
    commands = SimpleNamespace(wake=AsyncMock())
    codec = object()
    instances = []

    def create(**kwargs):
        assert kwargs == {"config": config, "audio_config": ctx.audio_config}
        detector = Detector()
        if create_hook is not None:
            create_hook(detector)
        instances.append(detector)
        return detector

    monkeypatch.setitem(
        sys.modules,
        "src.audio_processing.wake_word_detect",
        SimpleNamespace(WakeWordDetector=create),
    )
    plugin = WakeWordPlugin(audio=SimpleNamespace(codec=codec))
    await plugin.setup(ctx, commands)
    return plugin, config, bus, commands, codec, instances


@pytest.mark.asyncio
async def test_event_enables_initially_disabled_detector_and_binds_callbacks(
    monkeypatch,
):
    plugin, config, bus, commands, codec, instances = await make_plugin(monkeypatch)
    await plugin.start()
    assert not instances
    config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", True)
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 1
    detector = instances[0]
    detector.initialize.assert_awaited_once()
    detector.start.assert_awaited_once_with(codec)
    assert detector.on_error == plugin._on_error
    await detector.callback("hello", "hello")
    commands.wake.assert_awaited_once()
    assert plugin._started and not plugin.failed
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_disable_releases_detector_and_reenable_creates_working_instance(
    monkeypatch,
):
    plugin, config, bus, _, codec, instances = await make_plugin(
        monkeypatch, enabled=True
    )
    await plugin.start()
    first = instances[0]
    config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
    await bus.emit(Events.CONFIG_CHANGED)
    first.shutdown.assert_awaited_once()
    assert plugin.detector is None
    assert not plugin._started and not plugin.failed
    config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", True)
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 2
    instances[1].start.assert_awaited_once_with(codec)
    assert instances[1].callback == plugin._on_detected
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_failed_reload_cleans_partial_state_and_next_event_recovers(
    monkeypatch, raises
):
    plugin, _, bus, _, codec, instances = await make_plugin(monkeypatch, enabled=True)
    await plugin.start()
    detector = instances[0]
    if raises:
        detector.reload.side_effect = RuntimeError("bad model")
    else:
        detector.reload.return_value = False
    await bus.emit(Events.CONFIG_CHANGED)
    detector.shutdown.assert_awaited_once()
    assert plugin.detector is None
    assert plugin.failed and not plugin._started
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 2
    instances[1].start.assert_awaited_once_with(codec)
    assert plugin._started and not plugin.failed
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_stop_during_reload_prevents_later_config_events_from_restarting(
    monkeypatch,
):
    plugin, _, bus, _, _, instances = await make_plugin(monkeypatch, enabled=True)
    await plugin.start()
    detector = instances[0]
    entered = asyncio.Event()
    release = asyncio.Event()

    async def reload(_path):
        entered.set()
        await release.wait()
        return True

    detector.reload.side_effect = reload
    event = asyncio.create_task(bus.emit(Events.CONFIG_CHANGED))
    await entered.wait()
    queued = asyncio.create_task(bus.emit(Events.CONFIG_CHANGED))
    await asyncio.sleep(0)
    stopped = asyncio.create_task(plugin.stop())
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(event, queued, stopped)
    await bus.emit(Events.CONFIG_CHANGED)
    assert detector.reload.await_count == 1
    assert detector.start.await_count == 1
    assert not plugin._started
    assert bus.handler_count(Events.CONFIG_CHANGED) == 0
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_stop_during_initialization_never_attaches_listener(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def initialize():
        entered.set()
        await release.wait()
        return True

    def gate(detector):
        detector.initialize.side_effect = initialize

    plugin, _, bus, _, _, instances = await make_plugin(
        monkeypatch, enabled=True, create_hook=gate
    )
    started = asyncio.create_task(plugin.start())
    await entered.wait()
    stopped = asyncio.create_task(plugin.stop())
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(started, stopped)
    instances[0].start.assert_not_awaited()
    instances[0].shutdown.assert_awaited_once()
    assert not plugin._started
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 1
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_duplicate_start_does_not_create_another_detection_loop(monkeypatch):
    plugin, _, _, _, codec, instances = await make_plugin(monkeypatch, enabled=True)
    await asyncio.gather(plugin.start(), plugin.start())
    assert len(instances) == 1
    instances[0].start.assert_awaited_once_with(codec)
    await plugin.stop()
    await plugin.start()
    instances[0].initialize.assert_awaited_once()
    assert instances[0].start.await_count == 2
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_cancelled_start_releases_partial_detector_and_can_retry(monkeypatch):
    entered = asyncio.Event()

    def gate(detector):
        async def initialize():
            entered.set()
            await asyncio.Event().wait()

        detector.initialize.side_effect = initialize

    plugin, _, bus, _, _, instances = await make_plugin(
        monkeypatch, enabled=True, create_hook=gate
    )
    started = asyncio.create_task(plugin.start())
    await entered.wait()
    started.cancel()
    with pytest.raises(asyncio.CancelledError):
        await started
    assert plugin.detector is None
    instances[0].shutdown.assert_awaited_once()
    # The same event remains retryable after a cancelled initialization.
    original = sys.modules["src.audio_processing.wake_word_detect"].WakeWordDetector

    def create(**kwargs):
        detector = original(**kwargs)
        detector.initialize.side_effect = None
        return detector

    monkeypatch.setattr(
        sys.modules["src.audio_processing.wake_word_detect"], "WakeWordDetector", create
    )
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 2
    assert plugin._started and not plugin.failed
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_real_detector_releases_listener_and_task_across_config_transitions(
    monkeypatch, tmp_path
):
    import importlib

    from src.audio_processing.wake_word_detect import WakeWordDetector

    detector_module = importlib.import_module("src.audio_processing.wake_word_detect")

    class Codec:
        def __init__(self):
            self.listeners = set()

        def add_audio_listener(self, listener):
            self.listeners.add(listener)

        def remove_audio_listener(self, listener):
            self.listeners.discard(listener)

    def load_model(detector):
        detector._keyword_spotter = SimpleNamespace(create_stream=lambda: object())
        return True

    monkeypatch.setattr(detector_module, "get_resource_root", lambda: tmp_path)
    monkeypatch.setattr(WakeWordDetector, "_load_model", load_model)
    config = ConfigManager.from_dict(
        {"WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False, "MODEL_PATH": "."}}
    )
    bus = EventBus()
    codec = Codec()
    plugin = WakeWordPlugin(audio=SimpleNamespace(codec=codec))
    await plugin.setup(
        SimpleNamespace(
            event_bus=bus, get_config=lambda: config, audio_config=AudioConfig()
        ),
        SimpleNamespace(wake=AsyncMock()),
    )
    await plugin.start()
    try:
        config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", True)
        await bus.emit(Events.CONFIG_CHANGED)
        first = plugin.detector
        assert codec.listeners == {first}
        first_task = first._detection_task
        await bus.emit(Events.CONFIG_CHANGED)
        assert first._detection_task is not first_task
        assert first_task.done()
        assert codec.listeners == {first}

        config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
        await bus.emit(Events.CONFIG_CHANGED)
        assert not codec.listeners
        assert first._detection_task is None
        assert first._audio_queue is None
        assert first._keyword_spotter is None
        assert first._stream is None
        config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", True)
        await bus.emit(Events.CONFIG_CHANGED)
        second = plugin.detector
        assert second is not first
        assert codec.listeners == {second}

        config.update_config("WAKE_WORD_OPTIONS.MODEL_PATH", "missing-model")
        await bus.emit(Events.CONFIG_CHANGED)
        assert plugin.detector is None
        assert not codec.listeners
        assert second._detection_task is None
        config.update_config("WAKE_WORD_OPTIONS.MODEL_PATH", ".")
        await bus.emit(Events.CONFIG_CHANGED)
        assert codec.listeners == {plugin.detector}
        assert plugin._started and not plugin.failed
    finally:
        await plugin.stop()
        await plugin._shutdown_detector()
    assert not codec.listeners


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["initialize", "start"])
async def test_initial_model_or_start_failure_can_recover_on_config_event(
    monkeypatch, phase
):
    attempts = []

    def fail_first(detector):
        if not attempts:
            getattr(detector, phase).return_value = False
        attempts.append(detector)

    plugin, _, bus, _, _, instances = await make_plugin(
        monkeypatch, enabled=True, create_hook=fail_first
    )
    with pytest.raises(RuntimeError):
        await plugin.start()
    instances[0].shutdown.assert_awaited_once()
    assert plugin.failed and plugin.detector is None
    await bus.emit(Events.CONFIG_CHANGED)
    assert len(instances) == 2
    assert plugin._started and not plugin.failed
    await plugin.stop()
    await plugin._shutdown_detector()


@pytest.mark.asyncio
async def test_config_event_during_setup_does_not_start_detector(monkeypatch):
    plugin, _, bus, _, _, instances = await make_plugin(monkeypatch, enabled=True)
    await bus.emit(Events.CONFIG_CHANGED)
    assert not instances
    await plugin.start()
    assert len(instances) == 1
    await plugin.stop()
    await plugin._shutdown_detector()
