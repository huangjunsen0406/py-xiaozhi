"""AEC 实际可用性与会话半双工降级回归。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from src.bootstrap.adapters import PluginCommandsAdapter, PluginContextAdapter
from src.bootstrap.session import ConversationSession
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus
from src.core.state_manager import StateManager
from src.plugins.audio import AudioPlugin
from src.plugins.manager import PluginManager


class FakeCodec:
    def __init__(self, active):
        self.active = active
        self.engine = None
        self.clear_audio_queue = AsyncMock()

    @property
    def aec_active(self):
        return self.engine.active if self.engine is not None else self.active


@pytest.fixture
def conversation():
    state = StateManager(EventBus())
    protocol = SimpleNamespace(
        is_audio_channel_opened=lambda: True,
        send_start_listening=AsyncMock(),
        send_stop_listening=AsyncMock(),
        send_audio=AsyncMock(),
        send_abort_speaking=AsyncMock(),
    )
    audio = AudioPlugin()
    audio.codec = FakeCodec(False)
    plugins = PluginManager()
    plugins.register(audio)
    session = ConversationSession(state, protocol, plugins)
    container = SimpleNamespace(state=state, protocol=protocol, session=session)
    audio._ctx = PluginContextAdapter(container)
    audio._cmd = PluginCommandsAdapter(container)
    return SimpleNamespace(
        session=session, state=state, protocol=protocol, audio=audio, codec=audio.codec
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
@pytest.mark.parametrize("entrypoint", ["auto", "realtime"])
async def test_conversation_mode_uses_actual_aec(conversation, active, entrypoint):
    c = conversation
    c.codec.active = active
    if entrypoint == "auto":
        await c.session.start_auto_conversation()
    else:
        await c.session.start_listening(ListeningMode.REALTIME)
    expected = ListeningMode.REALTIME if active else ListeningMode.AUTO_STOP
    assert c.state.aec_enabled is active
    assert c.state.listening_mode == expected
    c.protocol.send_start_listening.assert_awaited_once_with(expected)

    await c.session._handle_tts_start()
    await c.audio._send_audio_async(b"microphone")
    assert c.state.device_state == (
        DeviceState.LISTENING if active else DeviceState.SPEAKING
    )
    assert c.protocol.send_audio.await_count == int(active)


@pytest.mark.asyncio
async def test_aec_initialization_failure_starts_half_duplex(conversation, monkeypatch):
    from src.audio_processing.aec_engine import AecEngine

    def fail_initialization(self, _preprocess):
        raise RuntimeError("unavailable APM library")

    monkeypatch.setattr(AecEngine, "_init_apm", fail_initialization)
    conversation.codec.engine = AecEngine()
    assert not conversation.codec.engine.active
    await conversation.session.start_auto_conversation()
    await conversation.session._handle_tts_start()
    await conversation.audio._send_audio_async(b"raw microphone")
    assert conversation.state.listening_mode == ListeningMode.AUTO_STOP
    assert not conversation.state.should_capture_audio()
    conversation.protocol.send_audio.assert_not_awaited()
    conversation.codec.engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("stop_fails", [False, True])
async def test_runtime_aec_failure_blocks_audio_and_resumes_after_tts(
    conversation, monkeypatch, stop_fails
):
    from src.audio_processing.aec_engine import AecEngine

    def initialize_broken_apm(self, _preprocess):
        self._stream_cfg = object()
        self._apm = SimpleNamespace(
            set_stream_delay_ms=lambda _delay: None,
            process_stream=lambda *_args: 1,
            destroy_stream_config=lambda _cfg: None,
        )

    monkeypatch.setattr(AecEngine, "_init_apm", initialize_broken_apm)
    c = conversation
    c.codec.engine = AecEngine(far_rate=16000)
    await c.session.start_auto_conversation()
    await c.session._handle_tts_start()
    assert c.state.device_state == DeviceState.LISTENING
    if stop_fails:
        c.protocol.send_stop_listening.side_effect = OSError("connection lost")

    for _ in range(5):
        c.codec.engine.process_near(np.zeros(320, dtype=np.float32))
    assert not c.codec.engine.active
    await c.audio._send_audio_async(b"raw microphone")
    await c.audio._send_audio_async(b"next raw microphone")
    assert not c.state.aec_enabled
    assert c.state.listening_mode == ListeningMode.AUTO_STOP
    assert c.state.device_state == DeviceState.SPEAKING
    c.protocol.send_stop_listening.assert_awaited_once()
    c.protocol.send_audio.assert_not_awaited()

    await c.session._handle_tts_stop()
    c.protocol.send_start_listening.assert_awaited_with(ListeningMode.AUTO_STOP)
    assert c.state.device_state == DeviceState.LISTENING
    await c.audio._send_audio_async(b"new user speech")
    c.protocol.send_audio.assert_awaited_once_with(b"new user speech")
    c.codec.engine.close()


@pytest.mark.asyncio
async def test_failure_between_last_frame_and_tts_stop_restarts_listening(conversation):
    c = conversation
    c.codec.active = True
    await c.session.start_auto_conversation()
    await c.session._handle_tts_start()
    c.codec.active = False
    await c.session._handle_tts_stop()
    assert c.state.listening_mode == ListeningMode.AUTO_STOP
    c.protocol.send_start_listening.assert_awaited_with(ListeningMode.AUTO_STOP)
    assert c.state.should_capture_audio()


@pytest.mark.asyncio
async def test_failure_while_listening_updates_server_and_keeps_user_audio(
    conversation,
):
    c = conversation
    c.codec.active = True
    await c.session.start_auto_conversation()
    c.codec.active = False
    await c.audio._send_audio_async(b"user speech")
    assert c.state.listening_mode == ListeningMode.AUTO_STOP
    c.protocol.send_start_listening.assert_awaited_with(ListeningMode.AUTO_STOP)
    c.protocol.send_audio.assert_awaited_once_with(b"user speech")
    await c.session._handle_tts_start()
    await c.audio._send_audio_async(b"echo")
    assert c.protocol.send_audio.await_count == 1


@pytest.mark.asyncio
async def test_recovered_aec_is_used_for_next_auto_session(conversation):
    c = conversation
    await c.session.start_auto_conversation()
    assert c.state.listening_mode == ListeningMode.AUTO_STOP
    c.codec.active = True
    await c.session.start_auto_conversation()
    assert c.state.listening_mode == ListeningMode.REALTIME
    await c.session._handle_tts_start()
    await c.audio._send_audio_async(b"user interruption")
    c.protocol.send_audio.assert_awaited_once_with(b"user interruption")


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [False, True])
async def test_manual_mode_is_preserved(conversation, active):
    c = conversation
    c.codec.active = active
    await c.session.start_listening(ListeningMode.MANUAL)
    assert c.state.listening_mode == ListeningMode.MANUAL
    assert not c.state.keep_listening
    await c.session._handle_tts_start()
    await c.audio._send_audio_async(b"echo")
    c.protocol.send_audio.assert_not_awaited()
    await c.session._handle_tts_stop()
    assert c.state.is_idle()


@pytest.mark.asyncio
async def test_missing_audio_plugin_never_enables_realtime(conversation):
    c = conversation
    c.session.plugins = PluginManager()
    await c.session.start_auto_conversation()
    assert not c.state.aec_enabled
    assert c.state.listening_mode == ListeningMode.AUTO_STOP


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["upload", "tts_start"])
async def test_tts_stop_during_downgrade_does_not_replay_old_audio_or_state(
    conversation, operation
):
    c = conversation
    c.codec.active = True
    await c.session.start_auto_conversation()
    if operation == "upload":
        await c.session._handle_tts_start()
    c.codec.active = False
    entered = asyncio.Event()
    resume = asyncio.Event()

    async def blocked_stop():
        entered.set()
        await resume.wait()

    c.protocol.send_stop_listening.side_effect = blocked_stop
    action = (
        c.audio._send_audio_async(b"old echo")
        if operation == "upload"
        else c.session._handle_tts_start()
    )
    pending = asyncio.create_task(action)
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await c.session._handle_tts_stop()
        assert c.state.device_state == DeviceState.LISTENING
    finally:
        resume.set()
        await pending
    assert c.state.device_state == DeviceState.LISTENING
    c.protocol.send_audio.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("new_event", ["tts_start", "channel_closed"])
async def test_old_tts_stop_does_not_clear_or_override_new_state(
    conversation, new_event
):
    c = conversation
    await c.session.start_auto_conversation()
    await c.session._handle_tts_start()
    entered = asyncio.Event()
    resume = asyncio.Event()

    async def blocked_listen(_mode):
        entered.set()
        await resume.wait()

    c.protocol.send_start_listening.side_effect = blocked_listen
    pending = asyncio.create_task(c.session._handle_tts_stop())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if new_event == "tts_start":
            await c.session._handle_tts_start()
            expected = DeviceState.SPEAKING
        else:
            await c.session._on_audio_channel_closed()
            expected = DeviceState.IDLE
        assert c.state.device_state == expected
    finally:
        resume.set()
        await pending
    assert c.state.device_state == expected
    c.codec.clear_audio_queue.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["abort", "manual", "manual_method"])
async def test_explicit_user_action_clears_old_tts_without_server_stop(
    conversation, operation
):
    c = conversation
    c.codec.active = True
    await c.session.start_auto_conversation()
    await c.session._handle_tts_start()
    if operation == "abort":
        await c.session.abort_speaking("user_interruption")
    elif operation == "manual":
        await c.session.start_listening(ListeningMode.MANUAL)
    else:
        await c.session.start_listening_manual()
    c.codec.active = False
    await c.audio._send_audio_async(b"new user speech")
    assert c.state.device_state == DeviceState.LISTENING
    c.protocol.send_audio.assert_awaited_once_with(b"new user speech")
