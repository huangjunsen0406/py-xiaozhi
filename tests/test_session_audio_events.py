"""Exercise audio lifetime through the real async EventBus contract."""

import logging
from types import SimpleNamespace

import pytest

from src.bootstrap.session import ConversationSession
from src.core.event_bus import EventBus, Events
from src.core.state_manager import StateManager
from src.plugins.audio import AudioPlugin


@pytest.mark.asyncio
@pytest.mark.parametrize("dispatch", ["emit", "emit_sequential"])
async def test_audio_codec_events_set_and_clear_session_without_handler_errors(caplog, dispatch):
    bus = EventBus()
    session = ConversationSession(StateManager(bus), SimpleNamespace())
    session.bind_events(bus)
    session.bind_events(bus)
    assert bus.handler_count(Events.AUDIO_CODEC_CHANGED) == 1
    codec = SimpleNamespace(aec_active=True)
    generation = session.audio_generation

    with caplog.at_level(logging.ERROR, logger="src.core.event_bus"):
        await getattr(bus, dispatch)(Events.AUDIO_CODEC_CHANGED, codec)
        assert session.audio is codec
        assert session.audio_generation == generation + 1
        await getattr(bus, dispatch)(Events.AUDIO_CODEC_CHANGED, None)
        assert session.audio is None
        assert session.audio_generation == generation + 2

    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    session.unbind_events()
    assert bus.handler_count(Events.AUDIO_CODEC_CHANGED) == 0
    await getattr(bus, dispatch)(Events.AUDIO_CODEC_CHANGED, codec)
    assert session.audio is None


@pytest.mark.asyncio
async def test_audio_plugin_publication_supports_start_refresh_and_shutdown(caplog):
    bus = EventBus()
    session = ConversationSession(StateManager(bus), SimpleNamespace())
    session.bind_events(bus)
    plugin = AudioPlugin()
    plugin._ctx = SimpleNamespace(event_bus=bus)
    first = SimpleNamespace(aec_active=True)
    replacement = SimpleNamespace(aec_active=False)

    with caplog.at_level(logging.ERROR, logger="src.core.event_bus"):
        for codec in (first, None, replacement, None):
            await plugin._publish_audio_codec(codec)
            assert session.audio is codec
    assert session.audio_generation == 4
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
