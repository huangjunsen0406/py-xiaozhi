"""Shared runtime settings rules and ordering, independent of either UI."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bootstrap.session import ConversationSession
from src.constants.constants import AudioConfig, DeviceState
from src.core.event_bus import EventBus, Events
from src.core.settings import SettingsApplier
from src.core.state_manager import StateManager
from src.utils.config_manager import ConfigManager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path,value,reconnect",
    [
        ("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL", "wss://new.example", True),
        ("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN", "new-token", True),
        ("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint", "mqtt.example:8883", True),
        ("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password", "new-password", True),
        ("SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic", "new/topic", True),
        ("SYSTEM_OPTIONS.DEVICE_ID", "new-device", True),
        ("SYSTEM_OPTIONS.CLIENT_ID", "new-client", True),
        ("AUDIO_DEVICES.frame_duration", 40, True),
        ("AUDIO_DEVICES.opus_output_sample_rate", 16000, True),
        ("MCP_TOOLS.DISABLED", ["music_player.stop"], True),
        ("AUDIO_DEVICES.input_device_name", "new-microphone", False),
        ("AEC_OPTIONS.ENABLED", True, False),
        ("SYSTEM_OPTIONS.WINDOW_SIZE_MODE", "compact", False),
        ("MUSIC.URL_API_KEY", "new-key", False),
    ],
)
async def test_only_connection_format_and_tools_changes_reconnect(
    path, value, reconnect
):
    config, bus = ConfigManager.from_dict(), EventBus()
    applier = SettingsApplier(config, bus)
    events = []
    bus.on(Events.CONFIG_CHANGED, lambda: events.append("reload"))
    bus.on(Events.PROTOCOL_RECONNECT_REQUEST, lambda: events.append("reconnect"))
    config.update_config(path, value, save=False)
    await applier.apply()
    assert events == (["reload", "reconnect"] if reconnect else ["reload"])
    events.clear()
    await applier.apply()
    assert events == ["reload"]


@pytest.mark.asyncio
async def test_audio_format_and_tools_finish_reloading_before_reconnect():
    config = ConfigManager.from_dict({"AUDIO_DEVICES": {"frame_duration": 20}})
    audio = AudioConfig.from_config(config)
    bus, events = EventBus(), []
    applier = SettingsApplier(config, bus)

    async def reload():
        await asyncio.sleep(0)
        audio.reload(config)
        events.append(("reload", audio.FRAME_DURATION))

    bus.on(Events.CONFIG_CHANGED, reload)
    bus.on(
        Events.PROTOCOL_RECONNECT_REQUEST,
        lambda: events.append(("reconnect", audio.FRAME_DURATION)),
    )
    config.update_config("AUDIO_DEVICES.frame_duration", 40, save=False)
    config.update_config("MCP_TOOLS.DISABLED", ["music_player.stop"], save=False)
    await applier.apply()
    assert events == [("reload", 40), ("reconnect", 40)]


@pytest.mark.asyncio
async def test_reordered_and_duplicate_disabled_tools_do_not_reconnect():
    config = ConfigManager.from_dict({"MCP_TOOLS": {"DISABLED": ["a.b", "a.c"]}})
    bus = EventBus()
    reconnect = AsyncMock()
    bus.on(Events.PROTOCOL_RECONNECT_REQUEST, reconnect)
    applier = SettingsApplier(config, bus)
    config.update_config("MCP_TOOLS.DISABLED", ["a.c", "a.b", "a.c"], save=False)
    await applier.apply()
    reconnect.assert_not_awaited()


@pytest.mark.asyncio
async def test_overlapping_saves_serialize_reload_and_do_not_repeat_reconnect():
    config, bus = ConfigManager.from_dict(), EventBus()
    applier = SettingsApplier(config, bus)
    entered, release = asyncio.Event(), asyncio.Event()
    events = []

    async def reload():
        events.append("reload")
        entered.set()
        await release.wait()

    bus.on(Events.CONFIG_CHANGED, reload)
    bus.on(Events.PROTOCOL_RECONNECT_REQUEST, lambda: events.append("reconnect"))
    config.update_config("MCP_TOOLS.DISABLED", ["a.b"], save=False)
    first = asyncio.create_task(applier.apply())
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(applier.apply())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert events == ["reload"]
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert events == ["reload", "reconnect", "reload"]
    finally:
        for task in (first, second):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *[task for task in (first, second) if task is not None],
            return_exceptions=True,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("opened", [False, True], ids=["idle_control", "audio_session"])
async def test_settings_refresh_idle_control_or_reopen_audio_without_listening(opened):
    bus = EventBus()
    state = StateManager(bus)
    connected = opened

    async def disconnect():
        nonlocal connected
        connected = False

    protocol = SimpleNamespace(
        is_audio_channel_opened=lambda: connected,
        start=AsyncMock(return_value=True),
        disconnect=AsyncMock(side_effect=disconnect),
        connect=AsyncMock(return_value=True),
    )
    session = ConversationSession(state, protocol)
    await session._on_protocol_reconnect_request()
    if opened:
        protocol.disconnect.assert_awaited_once()
        protocol.connect.assert_awaited_once()
        protocol.start.assert_not_awaited()
    else:
        protocol.start.assert_awaited_once()
        protocol.disconnect.assert_not_awaited()
        protocol.connect.assert_not_awaited()
    assert state.device_state == DeviceState.IDLE
    assert not state.keep_listening
