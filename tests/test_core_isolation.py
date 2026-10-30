"""Independent core runtimes and one owner for conversation decisions."""

import asyncio
import builtins
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.bootstrap.container import ServiceContainer
from src.bootstrap.plugin_wiring import (
    bind_shared_services,
    register_cleanup_resources,
    subscribe_builtin_events,
)
from src.bootstrap.session import ConversationSession
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus, Events
from src.core.state_manager import StateManager
from src.plugins.base import Plugin
from src.plugins.ui_presenter import UiPresenter
from src.plugins.ui_session import SessionActions
from src.utils.config_manager import ConfigManager


def _config(name, frame_duration):
    return ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {
                "DEVICE_ID": name,
                "NETWORK": {
                    "WEBSOCKET_URL": f"wss://{name}.example.test",
                    "WEBSOCKET_ACCESS_TOKEN": f"token-{name}",
                },
            },
            "AUDIO_DEVICES": {"frame_duration": frame_duration},
            "MUSIC": {"SEARCH_URL": f"https://{name}.example.test/search"},
        }
    )


@pytest.mark.asyncio
async def test_independent_containers_need_no_process_configuration(monkeypatch):
    from src.utils import config_manager

    def forbidden():
        raise AssertionError("core must use its injected configuration")

    monkeypatch.setattr(config_manager, "get_config", forbidden)
    first_source = _config("first", 20)
    second_source = _config("second", 60)
    first = ServiceContainer(first_source)
    second = ServiceContainer(second_source)
    defaults = ServiceContainer()
    try:
        for container, source in ((first, first_source), (second, second_source)):
            assert container.config is source
            assert container.protocol.config is source
            assert container.session.config is source
            assert container.create_plugin_context().get_config() is source
            assert (
                container.create_plugin_context().audio_config is container.audio_config
            )
            assert container.protocol.audio_config is container.audio_config
            container.tasks.initialize()
            container.protocol.set_protocol("websocket")
            bind_shared_services(container)
            register_cleanup_resources(container)
            assert container.protocol.protocol.config is source
            assert container.protocol.protocol.audio_config is container.audio_config
            assert container.music_player._config_source is source
            assert container.mcp_server.config is source

        assert first.protocol.protocol.WEBSOCKET_URL == "wss://first.example.test"
        assert second.protocol.protocol.WEBSOCKET_URL == "wss://second.example.test"
        assert first.protocol.protocol.HEADERS["Authorization"] == "Bearer token-first"
        assert (
            second.protocol.protocol.HEADERS["Authorization"] == "Bearer token-second"
        )
        assert first.audio_config.FRAME_DURATION == 20
        assert second.audio_config.FRAME_DURATION == 60
        first_source.update_config("AUDIO_DEVICES.frame_duration", 40, save=False)
        first.audio_config.reload(first_source)
        assert first.protocol.protocol.audio_config.FRAME_DURATION == 40
        assert second.audio_config.FRAME_DURATION == 60
        assert defaults.config is not first.config
        assert defaults.audio_config is not first.audio_config
        assert defaults.event_bus is not first.event_bus
        await first.state.set_device_state(DeviceState.LISTENING)
        assert second.state.is_idle()
        assert defaults.state.is_idle()
    finally:
        await first.shutdown()
        await second.shutdown()
        await defaults.shutdown()
    assert first.tasks.task_count() == 0
    assert second.tasks.task_count() == 0


def test_core_import_and_shutdown_work_when_qt_imports_are_unavailable():
    # A clean interpreter catches imports hidden by the rest of the test suite.
    source = """
import asyncio
import builtins
import sys
original_import = builtins.__import__
def without_qt(name, *args, **kwargs):
    if name.split('.')[0] in {'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qasync'}:
        raise AssertionError('core imported Qt: ' + name)
    return original_import(name, *args, **kwargs)
builtins.__import__ = without_qt
from src.bootstrap.container import ServiceContainer
from src.utils.config_manager import get_config
try:
    get_config()
except RuntimeError:
    pass
else:
    raise AssertionError('fresh core unexpectedly initialized process config')
async def main():
    core = ServiceContainer()
    await core.shutdown()
    await core.shutdown()
asyncio.run(main())
assert not any(name.startswith(('PyQt', 'PySide', 'qasync')) for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _session(*, connected=True, aec_active=False):
    state = StateManager(EventBus())
    protocol = SimpleNamespace(
        is_audio_channel_opened=lambda: connected,
        connect=AsyncMock(return_value=False),
        send_start_listening=AsyncMock(),
        send_stop_listening=AsyncMock(),
        send_abort_speaking=AsyncMock(),
        send_wake_word_detected=AsyncMock(),
    )
    audio = SimpleNamespace(aec_active=aec_active, clear_audio_queue=AsyncMock())
    session = ConversationSession(state, protocol, audio=audio)
    return session, state, protocol


@pytest.mark.asyncio
async def test_manual_entry_replaces_previous_realtime_mode():
    session, state, protocol = _session(aec_active=True)
    assert await session.start_listening(ListeningMode.REALTIME)
    assert state.keep_listening
    protocol.send_start_listening.reset_mock()
    assert await session.start_listening_manual()
    assert state.listening_mode == ListeningMode.MANUAL
    assert not state.keep_listening
    assert state.is_listening()
    protocol.send_start_listening.assert_awaited_once_with(ListeningMode.MANUAL)


@pytest.mark.asyncio
async def test_failed_connection_never_sends_user_text_or_listen():
    session, state, protocol = _session(connected=False)
    assert await session.send_user_text("hello", ListeningMode.MANUAL) is False
    protocol.connect.assert_awaited_once()
    protocol.send_start_listening.assert_not_awaited()
    protocol.send_wake_word_detected.assert_not_awaited()
    assert state.is_idle()
    assert not state.keep_listening
    assert not state.should_capture_audio()


@pytest.mark.asyncio
async def test_failed_listen_never_sends_user_text():
    session, state, protocol = _session()
    protocol.send_start_listening.side_effect = RuntimeError("listen failed")
    with pytest.raises(RuntimeError, match="listen failed"):
        await session.send_user_text("hello", ListeningMode.MANUAL)
    protocol.send_wake_word_detected.assert_not_awaited()
    assert state.is_idle()
    assert not state.should_capture_audio()


@pytest.mark.asyncio
async def test_blank_text_does_not_connect_or_change_state():
    session, state, protocol = _session(connected=False)
    assert await session.send_user_text("  ") is False
    protocol.connect.assert_not_awaited()
    protocol.send_wake_word_detected.assert_not_awaited()
    assert state.is_idle()


@pytest.mark.asyncio
async def test_wake_uses_session_entrypoint_and_speaking_interrupts():
    from src.constants.constants import AbortReason

    session, state, protocol = _session()
    session.start_auto_conversation = AsyncMock(return_value=True)
    await session.wake()
    session.start_auto_conversation.assert_awaited_once_with()
    await state.set_device_state(DeviceState.SPEAKING)
    await session.wake()
    protocol.send_abort_speaking.assert_awaited_once_with(
        AbortReason.WAKE_WORD_DETECTED
    )
    session.audio.clear_audio_queue.assert_awaited_once_with()
    assert state.is_idle()


@pytest.mark.asyncio
async def test_ui_uses_only_conversation_intents_and_subscribes_once():
    commands = SimpleNamespace(
        send_user_text=AsyncMock(return_value=True),
        start_auto_conversation=AsyncMock(return_value=True),
        start_listening=AsyncMock(return_value=True),
    )
    context = SimpleNamespace(is_listening=lambda: False, is_speaking=lambda: False)
    viewport = SimpleNamespace(set_button_text=Mock(), set_auto_mode=Mock())
    actions = SessionActions(context, commands, UiPresenter(viewport))
    bus = EventBus()
    actions.subscribe(bus)
    actions.subscribe(bus)
    await bus.emit(Events.UI_SEND_TEXT, {"text": "hello"})
    commands.send_user_text.assert_awaited_once_with("hello", ListeningMode.MANUAL)
    await actions.auto_toggle()
    await actions.send_text("auto")
    commands.send_user_text.assert_awaited_with("auto", ListeningMode.REALTIME)
    await actions.auto_session_toggle()
    commands.start_auto_conversation.assert_awaited_once_with()
    await actions.press()
    commands.start_listening.assert_awaited_once_with(ListeningMode.MANUAL)


@pytest.mark.asyncio
async def test_shortcut_uses_auto_conversation_intent():
    from src.plugins.shortcuts import ShortcutsPlugin

    commands = SimpleNamespace(start_auto_conversation=AsyncMock(return_value=True))
    plugin = ShortcutsPlugin()
    # No configuration or low-level protocol API is needed for this intent.
    plugin._cmd = commands
    await plugin._handle_auto_toggle()
    commands.start_auto_conversation.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_wake_word_plugin_only_submits_wake_intent():
    from src.plugins.wake_word import WakeWordPlugin

    plugin = WakeWordPlugin()
    commands = SimpleNamespace(wake=AsyncMock())
    await plugin.setup(SimpleNamespace(event_bus=EventBus()), commands)
    await plugin._on_detected("xiaozhi", "hello xiaozhi")
    commands.wake.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_rebinding_events_delivers_each_message_once_after_session_state():
    core = ServiceContainer()
    received = []
    changes = []

    class Observer(Plugin):
        name = "observer"

        async def on_incoming_json(self, message):
            received.append((message, core.state.device_state))

        async def on_device_state_changed(self, state):
            changes.append(state)

    core.plugins.register(Observer())
    core.session.bind_events(core.event_bus)
    core.session.bind_events(core.event_bus)
    subscribe_builtin_events(core)
    subscribe_builtin_events(core)
    message = {"type": "tts", "state": "start"}
    try:
        await core.event_bus.emit(Events.INCOMING_JSON, message)
        assert received == [(message, DeviceState.SPEAKING)]
        assert changes == [DeviceState.SPEAKING]
        core.session.unbind_events()
        await core.event_bus.emit(
            Events.INCOMING_JSON, {"type": "tts", "state": "stop"}
        )
        assert received == [(message, DeviceState.SPEAKING)]
    finally:
        await core.shutdown()


@pytest.mark.asyncio
async def test_plugin_failure_does_not_repeat_or_hide_next_plugin_message():
    core = ServiceContainer()
    seen = []

    class Bad(Plugin):
        name = "bad"

        async def on_incoming_json(self, message):
            seen.append("bad")
            raise RuntimeError("plugin failed")

    class Good(Plugin):
        name = "good"

        async def on_incoming_json(self, message):
            seen.append("good")

    core.plugins.register(Bad(), Good())
    core.session.bind_events(core.event_bus)
    subscribe_builtin_events(core)
    try:
        await core.event_bus.emit(
            Events.INCOMING_JSON, {"type": "stt", "text": "hello"}
        )
        assert seen == ["bad", "good"]
    finally:
        await core.shutdown()


@pytest.mark.asyncio
async def test_late_tts_stop_preserves_new_manual_recording():
    session, state, protocol = _session()
    await session.start_listening(ListeningMode.AUTO_STOP)
    await session._on_incoming_json({"type": "tts", "state": "start"})
    await session._on_incoming_json({"type": "tts", "state": "stop"})
    protocol.send_start_listening.reset_mock()
    session.audio.clear_audio_queue.reset_mock()
    await session.start_listening_manual()
    await session._on_incoming_json({"type": "tts", "state": "stop"})
    assert state.is_listening()
    assert state.listening_mode == ListeningMode.MANUAL
    protocol.send_start_listening.assert_awaited_once_with(ListeningMode.MANUAL)
    session.audio.clear_audio_queue.assert_not_awaited()


@pytest.mark.asyncio
async def test_slow_tts_start_keeps_tts_delivery_order_without_blocking_mcp():
    session, state, protocol = _session()
    bus = EventBus()
    session.bind_events(bus)
    state.set_listening_mode(ListeningMode.REALTIME)
    state.set_keep_listening(True)
    entered = asyncio.Event()
    release = asyncio.Event()
    received = []

    async def stop_upload():
        entered.set()
        await release.wait()

    async def observe(message):
        received.append(message)

    protocol.send_stop_listening.side_effect = stop_upload
    bus.on(Events.SESSION_MESSAGE, observe)
    first = asyncio.create_task(
        session._on_incoming_json({"type": "tts", "state": "start"})
    )
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(
            session._on_incoming_json({"type": "tts", "state": "stop"})
        )
        await asyncio.sleep(0)
        assert received == []
        mcp = {"type": "mcp", "payload": {"id": 1}}
        await asyncio.wait_for(session._on_incoming_json(mcp), 1)
        assert received == [mcp]
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert [
            message["state"] for message in received if message["type"] == "tts"
        ] == ["start", "stop"]
        assert state.is_listening()
    finally:
        release.set()
        tasks = [task for task in (first, second) if task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        session.unbind_events()


@pytest.mark.asyncio
async def test_import_failure_closes_protocol_consumer_and_tasks(monkeypatch):
    core = ServiceContainer()
    original_import = builtins.__import__

    def fail_shortcut_import(name, *args, **kwargs):
        if name == "src.plugins.shortcuts":
            raise ImportError("backend import unavailable")
        return original_import(name, *args, **kwargs)

    try:
        with monkeypatch.context() as patch:
            patch.setattr(builtins, "__import__", fail_shortcut_import)
            assert await core.run(mode="cli") == 1
        assert core.tasks.task_count() == 0
        assert not core.protocol._audio_consumer_running
        assert core.protocol._audio_consumer_task is None
        assert not core.event_bus.has_handlers(Events.INCOMING_JSON)
    finally:
        await core.protocol.shutdown()
        await core.tasks.cancel_all()


@pytest.mark.asyncio
async def test_stop_during_realtime_tts_aborts_server_and_clears_playback():
    from src.constants.constants import AbortReason

    session, state, protocol = _session(aec_active=True)
    await session.start_listening(ListeningMode.REALTIME)
    await session._on_incoming_json({"type": "tts", "state": "start"})
    assert state.is_listening()
    assert session._tts_active
    await session.stop_listening()
    protocol.send_stop_listening.assert_awaited_once_with()
    protocol.send_abort_speaking.assert_awaited_once_with(AbortReason.USER_INTERRUPTION)
    session.audio.clear_audio_queue.assert_awaited_once_with()
    assert state.is_idle()
    assert not state.keep_listening
    assert not state.should_capture_audio()
