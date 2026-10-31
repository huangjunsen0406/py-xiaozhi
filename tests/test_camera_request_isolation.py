"""Registered image isolation/cancellation with fake devices and memory only."""

import asyncio
import json
import threading

import pytest

from src.mcp.tools.camera import register as photo_registration
from src.mcp.tools.screenshot import register as screen_registration
from src.mcp.tools.screenshot.screenshot_camera import ScreenshotCamera


class FakePhotoCamera:
    def __init__(self):
        self.frame = bytearray()
        self.count = 0

    def capture(self):
        self.count += 1
        self.frame[:] = f"photo-{self.count}".encode()
        return True

    def get_jpeg_data(self):
        return {"buf": self.frame}

    def analyze(self, question, image_data=None):
        assert isinstance(image_data, bytes)
        return json.dumps({"question": question, "image": image_data.decode()})


def registered(kind, monkeypatch):
    photo = FakePhotoCamera()
    tools = []
    if kind == "photo":
        camera = photo
        registration = photo_registration
        registration.register_camera_tools(tools.append, camera)
    else:
        monkeypatch.setattr(ScreenshotCamera, "_import_dependencies", lambda _: None)
        camera = ScreenshotCamera()
        camera.count = 0

        def capture(display_id=None):
            camera.count += 1
            camera.set_jpeg_data(f"screen-{camera.count}".encode())
            return True

        camera.capture = capture
        registration = screen_registration
        monkeypatch.setattr(registration, "create_screenshot_camera", lambda: camera)
        registration.register_screenshot_tools(tools.append, photo_camera=photo)
    return tools[0], camera, photo, registration


def body(reply):
    result = json.loads(reply)
    assert not result["isError"], result
    return json.loads(result["content"][0]["text"])


@pytest.mark.parametrize("kind", ["photo", "screenshot"])
@pytest.mark.asyncio
async def test_each_concurrent_call_analyzes_its_own_captured_bytes(monkeypatch, kind):
    tool, camera, _, _ = registered(kind, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    analyze = camera.analyze

    def delayed(question, image_data=None):
        if question == "first":
            entered.set()
            assert release.wait(2)
        return analyze(question, image_data=image_data)

    camera.analyze = delayed
    first = asyncio.create_task(tool.call({"question": "first"}))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        second = body(await asyncio.wait_for(tool.call({"question": "second"}), 2))
        assert second["image"] == ("photo-2" if kind == "photo" else "screen-2")
    finally:
        release.set()
    original = body(await asyncio.wait_for(first, 2))
    assert original["question"] == "first"
    assert original["image"] == ("photo-1" if kind == "photo" else "screen-1")


@pytest.mark.asyncio
async def test_screenshot_analysis_can_share_a_photo_camera_without_replacing_photo(
    monkeypatch,
):
    screenshot, screen_camera, photo, _ = registered("screenshot", monkeypatch)
    photo_tools = []
    photo_registration.register_camera_tools(photo_tools.append, photo)
    entered, release = threading.Event(), threading.Event()
    analyze = screen_camera.analyze

    def delayed(question, image_data=None):
        entered.set()
        assert release.wait(2)
        return analyze(question, image_data=image_data)

    screen_camera.analyze = delayed
    screen_call = asyncio.create_task(screenshot.call({"question": "screen"}))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        photo_reply = body(
            await asyncio.wait_for(photo_tools[0].call({"question": "photo"}), 2)
        )
        assert photo_reply["image"] == "photo-1"
        assert photo.get_jpeg_data()["buf"] == b"photo-1"
    finally:
        release.set()
    assert body(await asyncio.wait_for(screen_call, 2))["image"] == "screen-1"
    assert photo.get_jpeg_data()["buf"] == b"photo-1"


@pytest.mark.parametrize("kind", ["photo", "screenshot"])
@pytest.mark.asyncio
async def test_cancelled_capture_keeps_device_exclusive_until_worker_finishes(
    monkeypatch, kind
):
    tool, camera, _, registration = registered(kind, monkeypatch)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    capture = camera.capture
    capture_image = registration._capture_image
    captures = []

    def blocked(*args):
        captures.append(True)
        if len(captures) == 1:
            entered.set()
            assert release.wait(2)
        return capture(*args)

    def observed(*args):
        try:
            return capture_image(*args)
        finally:
            if release.is_set():
                finished.set()

    camera.capture = blocked
    monkeypatch.setattr(registration, "_capture_image", observed)
    first = asyncio.create_task(tool.call({"question": "cancel"}))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        busy = body(await asyncio.wait_for(tool.call({"question": "busy"}), 2))
        assert busy["success"] is False
        assert len(captures) == 1
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 2)
    recovered = body(await asyncio.wait_for(tool.call({"question": "retry"}), 2))
    assert recovered["image"] == ("photo-2" if kind == "photo" else "screen-2")
    assert len(captures) == 2


@pytest.mark.parametrize("kind", ["photo", "screenshot"])
@pytest.mark.asyncio
async def test_capture_exception_releases_device_for_the_next_call(monkeypatch, kind):
    tool, camera, _, _ = registered(kind, monkeypatch)
    capture = camera.capture
    failed = False

    def fails_once(*args):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("capture broke")
        return capture(*args)

    camera.capture = fails_once
    assert json.loads(await tool.call({"question": "fail"}))["isError"] is True
    reply = body(await tool.call({"question": "retry"}))
    assert reply["image"] == ("photo-1" if kind == "photo" else "screen-1")


@pytest.mark.parametrize("kind", ["photo", "screenshot"])
@pytest.mark.asyncio
async def test_cancelled_analysis_finishes_with_its_own_image(monkeypatch, kind):
    tool, camera, _, _ = registered(kind, monkeypatch)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    analyze = camera.analyze
    observed = {}

    def delayed(question, image_data=None):
        if question != "cancel":
            return analyze(question, image_data=image_data)
        entered.set()
        try:
            assert release.wait(2)
            result = analyze(question, image_data=image_data)
            observed.update(json.loads(result))
            return result
        finally:
            finished.set()

    camera.analyze = delayed
    first = asyncio.create_task(tool.call({"question": "cancel"}))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        reply = body(await asyncio.wait_for(tool.call({"question": "next"}), 2))
        assert reply["image"] == ("photo-2" if kind == "photo" else "screen-2")
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 2)
    assert observed["image"] == ("photo-1" if kind == "photo" else "screen-1")
