"""TUI commits notify runtime through owned tasks in the correct order."""

import asyncio
import subprocess
import sys

import pytest

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.ui.tui.manager import TuiViewManager
from src.utils.config_manager import ConfigManager


@pytest.mark.asyncio
async def test_saved_tools_reload_before_reconnect_and_unchanged_tools_do_not_reconnect():
    bus, tasks = EventBus(), TaskManager()
    tasks.initialize()
    config = ConfigManager.from_dict()
    view = TuiViewManager(bus, tasks, config)
    delivered = []
    applied, reconnected = asyncio.Event(), asyncio.Event()

    async def changed():
        await asyncio.sleep(0)
        delivered.append("config")
        applied.set()

    async def reconnect():
        delivered.append("reconnect")
        reconnected.set()

    bus.on(Events.CONFIG_CHANGED, changed)
    bus.on(Events.PROTOCOL_RECONNECT_REQUEST, reconnect)
    try:
        config.update_config("MCP_TOOLS.DISABLED", ["demo.disabled"], save=False)
        view._on_settings_saved()
        await asyncio.wait_for(reconnected.wait(), 1)
        assert delivered == ["config", "reconnect"]
        delivered.clear()
        applied.clear()
        view._on_settings_saved()
        await asyncio.wait_for(applied.wait(), 1)
        await asyncio.sleep(0)
        assert delivered == ["config"]
        delivered.clear()
        await tasks.cancel_all()
        config.update_config("MCP_TOOLS.DISABLED", [], save=False)
        view._on_settings_saved()
        await asyncio.sleep(0)
        assert delivered == []
    finally:
        await tasks.cancel_all()


def test_complete_tui_settings_import_without_qt_or_device_enumeration():
    script = """
import builtins
import gc
original = builtins.__import__
def checked(name, *args, **kwargs):
    if name.startswith(('PySide6', 'sounddevice', 'src.ui.gui')) or name == 'src.utils.audio_utils':
        raise AssertionError('unexpected dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = checked
gc.get_objects = lambda: (_ for _ in ()).throw(AssertionError('global discovery'))
from src.ui.tui.app import XiaozhiTuiApp
from src.ui.tui.settings_screen import SettingsScreen
from src.utils.config_manager import ConfigManager
config = ConfigManager.from_dict()
app = XiaozhiTuiApp(config=config)
screen = SettingsScreen(config)
assert app._config is config and screen._config is config
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
