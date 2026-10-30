"""TUI runtime queries respect audio ownership and instance boundaries."""

import asyncio
import gc
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from src.core.event_bus import EventBus, Events
from src.ui.tui.settings_services import SettingsServices
from src.utils.config_manager import ConfigManager


@pytest.fixture
def config(tmp_path):
    return ConfigManager.from_dict({"MCP_PLUGINS": {"DIR": str(tmp_path)}})


@pytest.fixture
def audio(monkeypatch):
    devices = {
        "input": [
            {
                "index": 0,
                "name": "Mic",
                "raw_name": "Mic",
                "sample_rate": 48000,
                "channels": 1,
            }
        ],
        "output": [],
    }
    module = ModuleType("src.utils.audio_utils")
    module.list_audio_devices = Mock(return_value=devices)
    module.refresh_portaudio_devices = Mock(side_effect=AssertionError("unsafe reinit"))
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return module


@pytest.mark.asyncio
async def test_queries_copy_results_and_only_refresh_through_audio_owner(config, audio):
    service = SettingsServices(config)
    result = await service.audio_devices()
    assert result == audio.list_audio_devices.return_value
    result["input"][0]["name"] = "edited"
    assert audio.list_audio_devices.return_value["input"][0]["name"] == "Mic"
    audio.list_audio_devices.assert_called_once_with(include_virtual=True)
    bus = EventBus()
    loop = asyncio.get_running_loop()

    async def refresh(future):
        assert future.get_loop() is loop
        future.set_result({"input": [], "output": []})

    bus.on(Events.AUDIO_DEVICES_REFRESH_REQUEST, refresh)
    audio.list_audio_devices.reset_mock()
    assert await SettingsServices(config, bus).audio_devices(refresh=True) == {
        "input": [],
        "output": [],
    }
    audio.list_audio_devices.assert_not_called()
    audio.refresh_portaudio_devices.assert_not_called()


@pytest.mark.asyncio
async def test_failed_audio_plugin_does_not_trigger_fallback(config, audio):
    from src.plugins.audio import AudioPlugin

    plugin = AudioPlugin()
    plugin.mark_failed()
    bus = EventBus()
    bus.on(Events.AUDIO_DEVICES_REFRESH_REQUEST, plugin._on_devices_refresh_request)
    assert await SettingsServices(config, bus).audio_devices(refresh=True) == {
        "input": [],
        "output": [],
    }
    audio.list_audio_devices.assert_not_called()


@pytest.mark.asyncio
async def test_no_subscriber_queries_without_reinitialization(config, audio):
    result = await asyncio.wait_for(
        SettingsServices(config, EventBus()).audio_devices(refresh=True), 1
    )
    assert result == audio.list_audio_devices.return_value
    audio.refresh_portaudio_devices.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reply", [False, True])
async def test_broken_refresh_is_visible(config, audio, reply):
    bus = EventBus()

    async def broken(future):
        if reply:
            future.set_exception(ValueError("unavailable"))
        else:
            raise RuntimeError("handler failed")

    bus.on(Events.AUDIO_DEVICES_REFRESH_REQUEST, broken)
    with pytest.raises((RuntimeError, ValueError)):
        await SettingsServices(config, bus).audio_devices(refresh=True)
    audio.list_audio_devices.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_error", [False, True])
async def test_cancelled_refresh_cleans_handler_and_reply(config, reply_error):
    bus = EventBus()
    entered, exited = asyncio.Event(), asyncio.Event()
    received, errors = [], []
    loop = asyncio.get_running_loop()
    old_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, context: errors.append(context))

    async def refresh(future):
        received.append(future)
        if reply_error:
            future.set_exception(ValueError("late reply"))
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            exited.set()

    bus.on(Events.AUDIO_DEVICES_REFRESH_REQUEST, refresh)
    try:
        task = asyncio.create_task(
            SettingsServices(config, bus).audio_devices(refresh=True)
        )
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert exited.is_set()
        assert received[0].done()
        received.clear()
        del task
        gc.collect()
        await asyncio.sleep(0)
        assert not errors
    finally:
        loop.set_exception_handler(old_handler)


def test_tool_catalog_is_live_isolated_and_retains_disabled(config, tmp_path):
    names = ["first.live", "first.disabled"]
    first = SettingsServices(config, runtime_tool_names=lambda: tuple(names))
    second = SettingsServices(
        ConfigManager.from_dict({"MCP_PLUGINS": {"DIR": str(tmp_path / "second")}}),
        runtime_tool_names=lambda: ("second.live",),
    )
    rows = {row["name"]: row for row in first.tool_catalog(["first.disabled"])}
    assert rows["first.disabled"]["source"] == "runtime"
    assert "second.live" not in rows
    names[:] = ["first.new"]
    rows = {row["name"]: row for row in first.tool_catalog(["first.disabled"])}
    assert "first.live" not in rows
    assert "first.new" in rows
    assert rows["first.disabled"]["source"] == "external"
    assert "first.new" not in {row["name"] for row in second.tool_catalog([])}
    first.close()
    assert "first.new" not in {row["name"] for row in first.tool_catalog([])}
