"""Real Qt queued delivery under slow, failed, repeated, and closing scans."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtCore")
from PySide6.QtCore import QCoreApplication, QThread, QTimer
from PySide6.QtTest import QTest

from src.ui.gui.models.settings_model import SettingsModel
from src.utils.config_manager import ConfigManager


@pytest.fixture
def qt():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app
    app.processEvents()


def until(qt, predicate):
    deadline = time.monotonic() + 3
    while not predicate() and time.monotonic() < deadline:
        qt.processEvents()
        # Explicitly release the GIL so the Python worker can enqueue its Qt
        # callback; tight qWait/processEvents loops can starve it on CI.
        time.sleep(0.001)
    assert predicate(), "queued result did not arrive"


@pytest.fixture
def model(qt):
    instance = SettingsModel(config_manager=ConfigManager.from_dict())
    yield instance
    instance.close()


@pytest.mark.parametrize("close_early", [False, True])
def test_slow_audio_scan_is_nonblocking_coalesced_and_main_thread_only(
    qt, model, monkeypatch, close_early
):
    entered, release, finished = (threading.Event() for _ in range(3))
    scans, applied, heartbeat = [], [], []

    def scan(**kwargs):
        scans.append(QThread.currentThread())
        entered.set()
        try:
            assert release.wait(3)
            return {"input": [{"name": "fake mic"}], "output": []}
        finally:
            finished.set()

    monkeypatch.setattr("src.utils.audio_utils.list_audio_devices", scan)
    model.devicesChanged.connect(lambda: applied.append(QThread.currentThread()))
    assert model.getInputDevices() == []
    assert entered.wait(1)
    QTimer.singleShot(0, lambda: heartbeat.append(True))
    until(qt, lambda: heartbeat)
    model.getOutputDevices()
    model._load_audio_devices(force=True)
    model.refreshDevices()
    assert len(scans) == 1
    assert scans[0] != model.thread()
    assert model._audio_devices_loading
    if close_early:
        model.close()
    release.set()
    assert finished.wait(1)
    if close_early:
        QTest.qWait(20)
        qt.processEvents()
        assert not applied and model._input_devices == []
    else:
        until(qt, lambda: model._audio_devices_loaded)
        assert applied == [model.thread()]
        assert model.getInputDevices() == ["fake mic"]
        assert not model._audio_devices_loading


def test_failed_audio_scan_preserves_previous_devices_and_allows_retry(
    qt, model, monkeypatch
):
    errors = []
    model.statusMessage.connect(errors.append)
    model._apply_device_lists({"input": [{"name": "previous"}]})

    def fail(**kwargs):
        raise OSError("injected discovery failure")

    monkeypatch.setattr("src.utils.audio_utils.list_audio_devices", fail)
    model._load_audio_devices(force=True)
    until(qt, lambda: not model._audio_devices_loading)
    assert model.getInputDevices() == ["previous"]
    assert any("injected discovery failure" in error for error in errors)
    monkeypatch.setattr(
        "src.utils.audio_utils.list_audio_devices", lambda **kwargs: {"input": []}
    )
    model._load_audio_devices(force=True)
    until(qt, lambda: not model._audio_devices_loading)
    assert model.getInputDevices() == []


def test_camera_scan_applies_only_on_main_thread(qt, model, monkeypatch):
    scanned, applied = [], []

    def scan(**kwargs):
        scanned.append(QThread.currentThread())
        return [
            SimpleNamespace(
                key="1", index=1, name="fake camera", kind="opencv", path=""
            )
        ]

    monkeypatch.setattr(
        "src.mcp.tools.camera.capture_backend.list_camera_devices", scan
    )
    model.devicesChanged.connect(lambda: applied.append(QThread.currentThread()))
    model._load_cameras()
    until(qt, lambda: not model._cameras_loading)
    assert scanned[0] != model.thread()
    assert applied == [model.thread()]
    assert model.getCameras() == ["fake camera"]


def test_coordinated_refresh_done_callback_queues_on_qt_thread(qt, model):
    callback_threads, applied = [], []

    async def emit(event, future):
        callback_threads.append(QThread.currentThread())
        future.set_result({"input": [], "output": [{"name": "new output"}]})

    with ThreadPoolExecutor(max_workers=1) as executor:
        model._event_bus = SimpleNamespace(emit=emit)
        model._task_manager = SimpleNamespace(
            spawn=lambda coroutine, **kwargs: executor.submit(asyncio.run, coroutine)
        )
        model.devicesChanged.connect(lambda: applied.append(QThread.currentThread()))
        model.refreshDevices()
        until(qt, lambda: not model._audio_devices_refreshing)
    assert callback_threads[0] != model.thread()
    assert applied == [model.thread()]
    assert model.getOutputDevices() == ["new output"]


def test_removed_properties_are_absent_and_old_json_survives(qt):
    config = ConfigManager.from_dict(
        {"CAMERA": {"fps": 59}, "MUSIC": {"DEFAULT_PLATFORM": "old"}}
    )
    model = SettingsModel(config_manager=config)
    try:
        assert model.metaObject().indexOfProperty("fps") == -1
        assert model.metaObject().indexOfProperty("musicDefaultPlatform") == -1
        model.frameWidth = 800
        assert model.save()
        assert config.get_config("CAMERA.fps") == 59
        assert config.get_config("MUSIC.DEFAULT_PLATFORM") == "old"
    finally:
        model.close()


@pytest.mark.parametrize("cancel", [False, True])
def test_refresh_failure_preserves_devices_and_clears_busy(qt, model, cancel):
    from concurrent.futures import Future

    messages = []
    model.statusMessage.connect(messages.append)
    model._apply_device_lists({"input": [{"name": "previous"}]})
    model._event_bus = SimpleNamespace()

    def spawn(coroutine, **kwargs):
        coroutine.close()
        if not cancel:
            return None
        future = Future()
        future.cancel()
        return future

    model._task_manager = SimpleNamespace(spawn=spawn)
    model.refreshDevices()
    until(qt, lambda: not model._audio_devices_refreshing)
    assert model.getInputDevices() == ["previous"]
    assert any("[错误]" in message for message in messages)
    assert not any("设备列表已刷新" in message for message in messages)
