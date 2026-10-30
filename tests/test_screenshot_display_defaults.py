"""Registered screenshot defaults reach the native backend without a false error."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

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
    camera.analyze.assert_called_once_with("screen")
    assert not [record for record in caplog.records if record.levelno >= 40]
