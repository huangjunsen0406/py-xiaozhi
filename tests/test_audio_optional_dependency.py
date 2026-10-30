"""Missing native audio drivers stay inside the plugin health boundary."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

STARTUP_PROBE = r"""
import asyncio
import importlib.abc
import json
import logging
import sys
from types import SimpleNamespace

attempts = []

class MissingPortAudio(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "sounddevice":
            attempts.append(fullname)
            raise OSError("PortAudio library not found")

sys.meta_path.insert(0, MissingPortAudio())
logging.disable(logging.CRITICAL)

from src.bootstrap.container import ServiceContainer
from src.bootstrap import plugin_wiring
from src.core.event_bus import Events
from src.plugins.base import Plugin
from src.plugins.mcp import McpPlugin
import src.plugins.shortcuts as shortcuts
import src.plugins.ui as ui
from src.utils.config_manager import ConfigManager

async def noop(*args, **kwargs):
    pass

class TextViewport:
    def __init__(self):
        self.started = False
        self.closed = False
        self.notices = []

    async def start(self, **kwargs):
        self.started = True
        await asyncio.Future()

    async def close(self):
        self.closed = True

    def set_status(self, text, connected):
        self.notices.append(text)

viewport = TextViewport()
ui.create_viewport = lambda *args, **kwargs: viewport
shortcuts.create_backend = lambda *args, **kwargs: None
McpPlugin.setup = Plugin.setup

def bind_services(container):
    # No camera/tool discovery, media player, subprocess plugin, or notification IO.
    container.mcp_server = SimpleNamespace(detach=lambda: None)
    container.music_player = SimpleNamespace(stop=noop, detach=noop)

plugin_wiring.bind_shared_services = bind_services

async def main():
    config = ConfigManager.from_dict({
        "WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False},
        "SHORTCUTS": {"ENABLED": False},
    })
    container = ServiceContainer(config=config)
    # Replace the protocol backend and shutdown waiter; exercise real assembly,
    # AudioPlugin setup/failure, PluginManager, UIPlugin, and startup health policy.
    container.protocol.set_protocol = lambda *args, **kwargs: None
    container.protocol.start = noop
    container.tasks.wait_shutdown = noop
    notices = []
    container.event_bus.on(Events.SYSTEM_NOTICE, lambda notice: notices.append(notice))
    code = await container.run(mode="cli")
    audio = container.plugins.get_plugin("audio")
    ui_plugin = container.plugins.get_plugin("ui")
    print(json.dumps({
        "code": code,
        "native_attempts": attempts,
        "codec_imported": "src.audio_codecs.audio_codec" in sys.modules,
        "audio_failed": audio.failed if audio else None,
        "ui_failed": ui_plugin.failed if ui_plugin else None,
        "ui_started": viewport.started,
        "ui_closed": viewport.closed,
        "degraded": container._degraded_audio,
        "notices": notices,
        "viewport_notices": viewport.notices,
        "managed_tasks": container.tasks.task_count(),
        "qt_imported": any(name.startswith("PySide6") for name in sys.modules),
        "models_imported": "sherpa_onnx" in sys.modules,
    }))

asyncio.run(main())
"""


@pytest.mark.parametrize(
    ("policy", "expected_code", "failed", "degraded"),
    [
        ("disabled", 0, False, False),
        ("degraded", 0, True, True),
        ("default", 1, True, False),
    ],
)
def test_missing_portaudio_obeys_audio_startup_policy(
    tmp_path, policy, expected_code, failed, degraded
):
    env = os.environ.copy()
    env.pop("XIAOZHI_DISABLE_AUDIO", None)
    env.pop("XIAOZHI_DEGRADED_AUDIO", None)
    if policy == "disabled":
        env["XIAOZHI_DISABLE_AUDIO"] = "1"
    elif policy == "degraded":
        env["XIAOZHI_DEGRADED_AUDIO"] = "1"
    for name in (
        "XIAOZHI_DATA_DIR",
        "XIAOZHI_LOG_DIR",
        "XIAOZHI_CACHE_DIR",
        "XIAOZHI_KEYWORDS_DIR",
        "XIAOZHI_MUSIC_CACHE_DIR",
    ):
        env[name] = str(tmp_path / name.lower())
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", "-W", "error::RuntimeWarning", "-c", STARTUP_PROBE],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report["code"] == expected_code, report
    assert report["audio_failed"] is failed
    assert report["ui_failed"] is False
    assert report["ui_started"] and report["ui_closed"]
    assert report["degraded"] is degraded
    assert report["managed_tasks"] == 0
    assert not report["qt_imported"] and not report["models_imported"]
    assert not report["codec_imported"]
    if policy == "disabled":
        assert report["native_attempts"] == []
        assert report["notices"] == []
    else:
        assert report["native_attempts"] == ["sounddevice"]
    if degraded:
        assert len(report["notices"]) == 1
        assert "音频不可用" in report["notices"][0]
        assert report["viewport_notices"] == report["notices"]
