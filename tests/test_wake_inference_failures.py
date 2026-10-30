"""Persistent native inference errors terminate and clean the real detector."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from src.audio_processing import wake_word_detect as module
from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.plugins.wake_word import WakeWordPlugin
from src.utils.config_manager import ConfigManager


class Codec:
    def __init__(self):
        self.listeners = set()

    def add_audio_listener(self, listener):
        self.listeners.add(listener)

    def remove_audio_listener(self, listener):
        self.listeners.discard(listener)


class Spotter:
    def __init__(self, exception):
        self.exception = exception
        self.decode_count = 0

    def create_stream(self):
        return SimpleNamespace(accept_waveform=Mock())

    def is_ready(self, stream):
        return True

    def decode_stream(self, stream):
        self.decode_count += 1
        if self.exception is not None:
            raise self.exception("native inference failed")

    def get_result(self, stream):
        return ""


def fast_retries(monkeypatch):
    sleep = asyncio.sleep

    async def fast_sleep(_delay):
        await sleep(0)

    monkeypatch.setattr(module.asyncio, "sleep", fast_sleep)


@pytest.mark.asyncio
@pytest.mark.parametrize("exception", [ValueError, RuntimeError])
async def test_inference_errors_report_and_stop_after_threshold(monkeypatch, exception):
    fast_retries(monkeypatch)
    detector = module.WakeWordDetector()
    detector.enabled = True
    spotter = Spotter(exception)
    detector._keyword_spotter = spotter
    codec = Codec()
    errors = asyncio.Queue()
    detector.on_error = errors.put_nowait
    await detector.start(codec)
    task = detector._detection_task
    try:
        # Empty polling between failures must not reset the inference counter.
        for _ in range(5):
            detector.on_audio_data(np.zeros(320, dtype=np.float32))
            error = await asyncio.wait_for(errors.get(), timeout=0.2)
            assert isinstance(error, exception)
            await asyncio.sleep(0)
        await asyncio.wait_for(task, timeout=0.2)
        assert spotter.decode_count == 5
        assert not detector._running and not detector.enabled
        assert not codec.listeners
        assert detector._detection_task is None
        assert detector._audio_queue is None
        assert detector.audio_codec is None
    finally:
        await detector.shutdown()


@pytest.mark.asyncio
async def test_successful_frame_resets_consecutive_error_count(monkeypatch):
    fast_retries(monkeypatch)
    detector = module.WakeWordDetector()
    detector.enabled = True
    spotter = Spotter(ValueError)
    detector._keyword_spotter = spotter
    codec = Codec()
    errors = asyncio.Queue()
    detector.on_error = errors.put_nowait
    await detector.start(codec)
    task = detector._detection_task
    try:
        for _ in range(2):
            detector.on_audio_data(np.zeros(320, dtype=np.float32))
            await asyncio.wait_for(errors.get(), timeout=0.2)
        spotter.exception = None
        detector.on_audio_data(np.zeros(320, dtype=np.float32))
        while spotter.decode_count < 3:
            await asyncio.sleep(0)
        spotter.exception = ValueError
        for _ in range(4):
            detector.on_audio_data(np.zeros(320, dtype=np.float32))
            await asyncio.wait_for(errors.get(), timeout=0.2)
        assert detector._running
        detector.on_audio_data(np.zeros(320, dtype=np.float32))
        await asyncio.wait_for(errors.get(), timeout=0.2)
        await asyncio.wait_for(task, timeout=0.2)
        assert not detector._running
        assert spotter.decode_count == 8
    finally:
        await detector.shutdown()


@pytest.mark.asyncio
async def test_plugin_failure_is_visible_and_config_event_restarts_inference(
    monkeypatch, tmp_path
):
    fast_retries(monkeypatch)
    failing = True

    def load_model(detector):
        detector._keyword_spotter = Spotter(ValueError if failing else None)
        return True

    monkeypatch.setattr(module, "get_resource_root", lambda: tmp_path)
    monkeypatch.setattr(module.WakeWordDetector, "_load_model", load_model)
    config = ConfigManager.from_dict(
        {"WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": True, "MODEL_PATH": "."}}
    )
    bus = EventBus()
    codec = Codec()
    plugin = WakeWordPlugin(audio=SimpleNamespace(codec=codec))
    await plugin.setup(
        SimpleNamespace(
            event_bus=bus, get_config=lambda: config, audio_config=AudioConfig()
        ),
        SimpleNamespace(),
    )
    await plugin.start()
    first = plugin.detector
    task = first._detection_task
    try:
        for _ in range(5):
            first.on_audio_data(np.zeros(320, dtype=np.float32))
        await asyncio.wait_for(task, timeout=0.2)
        assert plugin.failed and not plugin._started
        assert not codec.listeners
        failing = False
        await bus.emit(Events.CONFIG_CHANGED)
        assert not plugin.failed and plugin._started
        assert plugin.detector._running
        assert codec.listeners == {plugin.detector}
    finally:
        await plugin.stop()
        await plugin._shutdown_detector()
