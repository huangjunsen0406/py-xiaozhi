"""Session intents commit only successful sends and discard stale completions."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.bootstrap.session import ConversationSession
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus, Events
from src.core.state_manager import StateManager


def make_session():
    bus = EventBus()
    state = StateManager(bus)
    protocol = SimpleNamespace(
        is_audio_channel_opened=Mock(return_value=True),
        connect=AsyncMock(return_value=True),
        send_start_listening=AsyncMock(return_value=True),
        send_stop_listening=AsyncMock(return_value=True),
        send_abort_speaking=AsyncMock(return_value=True),
        send_wake_word_detected=AsyncMock(return_value=True),
    )
    audio = SimpleNamespace(aec_active=False, clear_audio_queue=AsyncMock())
    session = ConversationSession(state, protocol, audio=audio, event_bus=bus)
    session.bind_events(bus)
    return session, state, protocol, audio, bus


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_stage", ["abort", "clear", "resume"])
async def test_stop_wins_over_older_abort_completion(blocked_stage):
    session, state, protocol, audio, bus = make_session()
    assert await session.start_listening(ListeningMode.AUTO_STOP)
    await bus.emit(Events.INCOMING_JSON, {"type": "tts", "state": "start"})
    entered, release = asyncio.Event(), asyncio.Event()

    blocked_calls = 0

    async def blocked(*args):
        nonlocal blocked_calls
        blocked_calls += 1
        if blocked_calls == 1:
            entered.set()
            await release.wait()
        return True

    target = {
        "abort": protocol.send_abort_speaking,
        "clear": audio.clear_audio_queue,
        "resume": protocol.send_start_listening,
    }[blocked_stage]
    target.side_effect = blocked
    pending = asyncio.create_task(session.abort_speaking("user"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await session.stop_listening()
        assert state.is_idle() and not state.should_capture_audio()
    finally:
        release.set()
        await asyncio.wait_for(pending, 1)
    assert state.is_idle()
    assert not state.keep_listening
    assert not state.should_capture_audio()


@pytest.mark.asyncio
async def test_rejected_initial_listen_does_not_commit_capture_or_send_text():
    session, state, protocol, _, _ = make_session()
    protocol.send_start_listening.return_value = False
    assert not await session.send_user_text("must not be reported as sent")
    protocol.send_wake_word_detected.assert_not_awaited()
    assert state.is_idle() and not state.should_capture_audio()


@pytest.mark.asyncio
@pytest.mark.parametrize("already_listening", [False, True])
async def test_rejected_text_returns_failure_without_stopping_an_existing_intent(
    already_listening,
):
    session, state, protocol, _, _ = make_session()
    if already_listening:
        assert await session.start_listening(ListeningMode.MANUAL)
    protocol.send_wake_word_detected.return_value = False
    assert not await session.send_user_text("rejected")
    assert state.is_listening() if already_listening else state.is_idle()


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["tts_stop", "abort"])
async def test_failed_resume_does_not_enable_microphone(message):
    session, state, protocol, _, bus = make_session()
    assert await session.start_listening(ListeningMode.AUTO_STOP)
    await bus.emit(Events.INCOMING_JSON, {"type": "tts", "state": "start"})
    protocol.send_start_listening.return_value = False
    if message == "tts_stop":
        await bus.emit(Events.INCOMING_JSON, {"type": "tts", "state": "stop"})
    else:
        await session.abort_speaking("user")
    assert state.is_idle()
    assert not state.keep_listening and not state.should_capture_audio()


@pytest.mark.asyncio
async def test_stop_during_listening_state_notification_invalidates_start_result():
    session, state, _, _, bus = make_session()
    entered, release = asyncio.Event(), asyncio.Event()

    async def delayed_ui(data):
        if data["new_state"] == DeviceState.LISTENING:
            entered.set()
            await release.wait()

    bus.on(Events.DEVICE_STATE_CHANGED, delayed_ui)
    pending = asyncio.create_task(session.start_listening(ListeningMode.MANUAL))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await session.stop_listening()
    finally:
        release.set()
    assert not await asyncio.wait_for(pending, 1)
    assert state.is_idle() and not state.should_capture_audio()


@pytest.mark.asyncio
async def test_failed_aec_fallback_does_not_keep_capture_running():
    session, state, protocol, audio, _ = make_session()
    audio.aec_active = True
    assert await session.start_listening(ListeningMode.REALTIME)
    audio.aec_active = False
    protocol.send_start_listening.return_value = False
    assert not await session.sync_audio_state()
    assert state.is_idle() and not state.should_capture_audio()
    assert not state.keep_listening


@pytest.mark.asyncio
async def test_late_text_publish_does_not_report_a_stopped_intent_as_success():
    session, state, protocol, _, _ = make_session()
    entered, release = asyncio.Event(), asyncio.Event()

    async def send(text):
        entered.set()
        await release.wait()
        return True

    protocol.send_wake_word_detected.side_effect = send
    pending = asyncio.create_task(session.send_user_text("late"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await session.stop_listening()
    finally:
        release.set()
    assert not await asyncio.wait_for(pending, 1)
    assert state.is_idle() and not state.should_capture_audio()


@pytest.mark.asyncio
async def test_plugin_adapter_preserves_rejected_sends():
    from src.bootstrap.container import ServiceContainer

    container = ServiceContainer()
    try:
        commands = container.create_plugin_commands()
        assert await commands.send_audio(b"audio") is False
        assert await commands.send_mcp_message("{}") is False
    finally:
        await container.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("command", ["text", "manual", "auto"])
@pytest.mark.parametrize("blocked_stage", ["connect", "listen"])
async def test_abort_revokes_a_pending_listen_intent(command, blocked_stage):
    session, state, protocol, _, bus = make_session()
    entered, release = asyncio.Event(), asyncio.Event()
    if blocked_stage == "connect":
        protocol.is_audio_channel_opened.return_value = False

    async def blocked(*args):
        entered.set()
        await release.wait()
        protocol.is_audio_channel_opened.return_value = True
        return True

    target = (
        protocol.connect
        if blocked_stage == "connect"
        else protocol.send_start_listening
    )
    target.side_effect = blocked
    action = {
        "text": lambda: session.send_user_text("cancelled"),
        "manual": session.start_listening_manual,
        "auto": session.start_auto_conversation,
    }[command]

    async def abort(_data=None):
        await session.abort_speaking("user_interruption")

    bus.on(Events.UI_ABORT_REQUEST, abort)
    pending = asyncio.create_task(action())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await bus.emit(Events.UI_ABORT_REQUEST)
        assert state.is_idle() and not state.should_capture_audio()
    finally:
        release.set()
    assert not await asyncio.wait_for(pending, 1)
    assert state.is_idle() and not state.keep_listening
    assert not state.should_capture_audio()
    protocol.send_wake_word_detected.assert_not_awaited()
    if blocked_stage == "connect":
        protocol.send_start_listening.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_speaking_abort_does_not_invalidate_inflight_cleanup():
    session, state, protocol, _, bus = make_session()
    assert await session.start_listening(ListeningMode.AUTO_STOP)
    await bus.emit(Events.INCOMING_JSON, {"type": "tts", "state": "start"})
    entered, release = asyncio.Event(), asyncio.Event()

    async def send(*args):
        entered.set()
        await release.wait()
        return True

    protocol.send_abort_speaking.side_effect = send
    first = asyncio.create_task(session.abort_speaking("user"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await session.abort_speaking("user")
    finally:
        release.set()
        await asyncio.wait_for(first, 1)
    protocol.send_abort_speaking.assert_awaited_once_with("user")
    assert state.is_listening() and state.should_capture_audio()
    assert not state.aborted


@pytest.mark.asyncio
async def test_old_start_completion_does_not_hide_a_new_pending_abort():
    session, state, protocol, _, _ = make_session()
    protocol.is_audio_channel_opened.return_value = False
    entered = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]
    calls = 0

    async def connect():
        nonlocal calls
        index = calls
        calls += 1
        entered[index].set()
        await release[index].wait()
        return True

    protocol.connect.side_effect = connect
    first = asyncio.create_task(session.start_listening_manual())
    second = None
    try:
        await asyncio.wait_for(entered[0].wait(), 1)
        await session.stop_listening()
        second = asyncio.create_task(session.start_auto_conversation())
        await asyncio.wait_for(entered[1].wait(), 1)
        release[0].set()
        assert not await asyncio.wait_for(first, 1)
        await session.abort_speaking("user")
    finally:
        for gate in release:
            gate.set()
        await asyncio.gather(*[task for task in (first, second) if task is not None])
    assert second is not None and second.result() is False
    protocol.send_start_listening.assert_not_awaited()
    assert state.is_idle() and not state.should_capture_audio()


def test_decode_error_is_presented_as_failure(caplog):
    from src.mcp.tools.music.events import MusicStateData
    from src.plugins.ui_presenter import UiPresenter

    viewport = SimpleNamespace(set_music_line=Mock())
    UiPresenter(viewport).show_music_state(
        MusicStateData(state="error", song="track", position=0, duration=1)
    )
    viewport.set_music_line.assert_called_once_with("播放失败: track")
    assert not [record for record in caplog.records if record.levelno >= 40]
