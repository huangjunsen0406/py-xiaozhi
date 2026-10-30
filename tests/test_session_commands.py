"""Semantic commands must also handle speaking during realtime listening."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.bootstrap.adapters import PluginContextAdapter
from src.bootstrap.session import ConversationSession
from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.core.event_bus import EventBus
from src.core.state_manager import StateManager
from src.utils.config_manager import ConfigManager


def make_session(*, aec_enabled=True):
    state = StateManager(EventBus())
    audio = SimpleNamespace(aec_active=True, clear_audio_queue=AsyncMock())
    protocol = SimpleNamespace(
        is_audio_channel_opened=lambda: True,
        send_start_listening=AsyncMock(),
        send_stop_listening=AsyncMock(),
        send_abort_speaking=AsyncMock(),
        send_wake_word_detected=AsyncMock(),
    )
    session = ConversationSession(
        state,
        protocol,
        audio=audio,
        config=ConfigManager.from_dict({"AEC_OPTIONS": {"ENABLED": aec_enabled}}),
    )
    return session, state, audio, protocol


@pytest.mark.asyncio
@pytest.mark.parametrize("entry", ["manual", "wake", "text"])
async def test_commands_interrupt_actual_tts_while_device_is_listening(entry):
    session, state, audio, protocol = make_session()
    await session.start_auto_conversation()
    await session._handle_tts_start()
    assert state.device_state == DeviceState.LISTENING
    assert session._tts_active
    ctx = PluginContextAdapter(SimpleNamespace(state=state, session=session))
    assert ctx.is_listening()
    assert ctx.is_speaking()
    protocol.send_start_listening.reset_mock()

    if entry == "manual":
        assert await session.start_listening(ListeningMode.MANUAL)
        protocol.send_abort_speaking.assert_awaited_once_with(None)
        assert state.listening_mode == ListeningMode.MANUAL
    elif entry == "wake":
        await session.wake()
        protocol.send_abort_speaking.assert_awaited_once_with(
            AbortReason.WAKE_WORD_DETECTED
        )
        protocol.send_start_listening.assert_not_awaited()
    else:
        assert await session.send_user_text(" new question ", ListeningMode.REALTIME)
        protocol.send_abort_speaking.assert_awaited_once_with(
            AbortReason.USER_INTERRUPTION
        )
        protocol.send_wake_word_detected.assert_awaited_once_with("new question")
        protocol.send_start_listening.assert_not_awaited()
    assert not session._tts_active
    audio.clear_audio_queue.assert_awaited_once()
    await session._handle_tts_stop()
    assert state.device_state == DeviceState.LISTENING


@pytest.mark.asyncio
async def test_auto_text_respects_configured_aec_preference_even_if_engine_active():
    session, state, _audio, protocol = make_session(aec_enabled=False)
    assert await session.send_user_text("question", ListeningMode.REALTIME)
    protocol.send_start_listening.assert_awaited_once_with(ListeningMode.AUTO_STOP)
    assert state.listening_mode == ListeningMode.AUTO_STOP
