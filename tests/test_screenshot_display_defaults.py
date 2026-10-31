"""Registered screenshot defaults reach the native backend without a false error."""

import json
import os
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, mock_open

import pytest
from PIL import Image

from src.mcp.tools.screenshot import register as registration
from src.mcp.tools.screenshot import screenshot_camera


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("arguments", "selected"),
    [
        ({}, None),
        ({"display": ""}, None),
        ({"display": "  "}, None),
        ({"display": "main"}, 1),
        ({"display": " MAIN "}, 1),
        ({"display": " 主屏 "}, 1),
        ({"display": "secondary"}, 2),
        ({"display": "3"}, 3),
    ],
)
async def test_registered_display_selection_uses_native_capture(
    monkeypatch, caplog, arguments, selected
):
    # Keep actual tool parsing, capture routing and JPEG conversion. All screen
    # and service boundaries are in memory; no native screenshot is taken.
    def dependencies(camera):
        camera._subprocess_available = True
        camera._pil_available = True

    monkeypatch.setattr(
        screenshot_camera.ScreenshotCamera, "_import_dependencies", dependencies
    )
    monkeypatch.setattr(screenshot_camera, "sys", SimpleNamespace(platform="darwin"))
    camera = screenshot_camera.ScreenshotCamera()
    image = Image.new("RGB", (2, 2), "white")
    camera._capture_all_displays_macos = Mock(return_value=image)
    camera._capture_single_display_macos = Mock(return_value=image)
    camera._capture_with_pil = Mock(return_value=b"fallback")
    camera.analyze = Mock(return_value=json.dumps({"success": True}))
    monkeypatch.setattr(registration, "create_screenshot_camera", lambda: camera)
    tools = []
    registration.register_screenshot_tools(tools.append)

    response = json.loads(await tools[0].call({"question": "screen", **arguments}))

    assert not response["isError"]
    assert json.loads(response["content"][0]["text"])["success"]
    if selected is None:
        camera._capture_all_displays_macos.assert_called_once_with()
        camera._capture_single_display_macos.assert_not_called()
    else:
        camera._capture_single_display_macos.assert_called_once_with(selected)
        camera._capture_all_displays_macos.assert_not_called()
    camera._capture_with_pil.assert_not_called()
    assert camera.get_jpeg_data()["buf"].startswith(b"\xff\xd8")
    camera.analyze.assert_called_once_with(
        "screen", image_data=camera.get_jpeg_data()["buf"]
    )
    assert not [record for record in caplog.records if record.levelno >= 40]


@pytest.fixture
def fake_screenshot_files(monkeypatch):
    active_files = set()
    entered, exited = [], []

    class FakeDirectory:
        def __init__(self, **kwargs):
            self.name = f"/virtual/xiaozhi-screenshot-{len(entered)}"

        def __enter__(self):
            entered.append(self.name)
            return self.name

        def __exit__(self, *args):
            active_files.difference_update(
                path for path in tuple(active_files) if path.startswith(self.name + "/")
            )
            exited.append(self.name)

    monkeypatch.setattr(tempfile, "TemporaryDirectory", FakeDirectory)
    monkeypatch.setattr(os.path, "exists", lambda path: path in active_files)
    return SimpleNamespace(files=active_files, entered=entered, exited=exited)


@pytest.mark.parametrize("all_displays", [False, True])
@pytest.mark.parametrize(
    "outcome", ["timeout", "missing", "decode-error", "nonzero", "success"]
)
def test_macos_commands_are_bounded_and_cleanup_every_exit(
    monkeypatch, fake_screenshot_files, all_displays, outcome
):
    state = fake_screenshot_files
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert 0 < kwargs["timeout"] <= 10
        assert cmd[0] == "screencapture"
        state.files.add(cmd[-1])
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        if outcome == "missing":
            raise FileNotFoundError("screencapture missing")
        return SimpleNamespace(
            returncode=1 if outcome == "nonzero" else 0, stderr="fake result"
        )

    def open_image(path):
        assert path in state.files
        if outcome == "decode-error":
            raise OSError("invalid screenshot image")
        return Image.new("RGB", (2, 2), "white")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(Image, "open", open_image)
    camera = screenshot_camera.ScreenshotCamera.__new__(
        screenshot_camera.ScreenshotCamera
    )
    result = (
        camera._capture_all_displays_macos()
        if all_displays
        else camera._capture_single_display_macos(1)
    )
    if outcome == "success":
        assert result.getpixel((0, 0)) == (255, 255, 255)
        result.close()
    else:
        assert result is None
    assert len(calls) == (4 if all_displays else 1)
    assert state.entered == state.exited
    assert len(state.entered) == len(calls)
    assert not state.files


@pytest.mark.parametrize(
    "outcome", ["timeout", "missing", "read-error", "nonzero", "success"]
)
def test_linux_attempts_cleanup_files_after_failure_and_success(
    monkeypatch, fake_screenshot_files, outcome
):
    state = fake_screenshot_files
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert 0 < kwargs["timeout"] <= 10
        state.files.add(cmd[-1])
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        if outcome == "missing":
            raise FileNotFoundError("screenshot command missing")
        return SimpleNamespace(returncode=1 if outcome == "nonzero" else 0)

    open_file = mock_open(read_data=b"fake-jpeg")
    if outcome == "read-error":
        open_file.side_effect = OSError("cannot read screenshot")
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr("builtins.open", open_file)
    camera = screenshot_camera.ScreenshotCamera.__new__(
        screenshot_camera.ScreenshotCamera
    )
    result = camera._capture_linux()
    assert result == (b"fake-jpeg" if outcome == "success" else None)
    assert len(calls) == (1 if outcome == "success" else 3)
    assert state.entered == state.exited
    assert len(state.entered) == len(calls)
    assert not state.files
