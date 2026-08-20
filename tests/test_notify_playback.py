"""服务端单向 notify 的状态与播放回归测试。"""

import asyncio

import numpy as np
import pytest

from src.constants.constants import DeviceState
from src.core.event_bus import EventBus, Events


class _FakeState:
    def __init__(self, state=DeviceState.IDLE):
        self.device_state = state
        self.keep_listening = False
        self.listening_mode = None
        self.states = []

    def is_idle(self):
        return self.device_state == DeviceState.IDLE

    def set_listening_mode(self, mode):
        self.listening_mode = mode

    def set_keep_listening(self, _value):
        return None

    async def set_device_state(self, state):
        self.device_state = state
        self.states.append(state)


class _FakePlugins:
    async def notify_incoming_json(self, _message):
        return None

    async def notify_device_state_changed(self, _state):
        return None


class _FakeNotificationPlayer:
    def __init__(self):
        self.is_active = False
        self.started = []
        self.finished_callback = None
        self.stop_count = 0

    async def start(self, audio_url, subtitles, finished_callback):
        self.is_active = True
        self.started.append((audio_url, subtitles))
        self.finished_callback = finished_callback
        return 7

    async def stop(self):
        self.stop_count += 1
        self.is_active = False


@pytest.mark.asyncio
async def test_notify_only_starts_while_idle_and_returns_after_matching_finish():
    from src.bootstrap.session import ConversationSession

    state = _FakeState()
    player = _FakeNotificationPlayer()
    session = ConversationSession(
        state=state,
        protocol=object(),
        plugins=_FakePlugins(),
        notification_player=player,
    )

    message = {
        "type": "notify",
        "audio_url": "https://cdn.example.test/task.ogg",
        "subtitles": [{"start_ms": 100, "text": "done"}],
    }
    await session._on_incoming_json(message)

    assert state.device_state == DeviceState.NOTIFYING
    assert len(player.started) == 1
    assert player.started[0][1][0].text == "done"

    await session._on_incoming_json(message)
    assert len(player.started) == 1

    await player.finished_callback(6, True)
    assert state.device_state == DeviceState.NOTIFYING

    await player.finished_callback(7, True)
    assert state.device_state == DeviceState.IDLE


@pytest.mark.asyncio
async def test_notify_is_ignored_when_busy_or_invalid():
    from src.bootstrap.session import ConversationSession

    player = _FakeNotificationPlayer()
    session = ConversationSession(
        state=_FakeState(DeviceState.SPEAKING),
        protocol=object(),
        plugins=_FakePlugins(),
        notification_player=player,
    )

    await session._on_incoming_json(
        {"type": "notify", "audio_url": "https://cdn.example.test/task.ogg"}
    )
    await session._on_incoming_json({"type": "notify", "audio_url": "file:///tmp/a"})

    assert player.started == []


@pytest.mark.asyncio
async def test_start_listening_cancels_notification_first():
    from src.bootstrap.session import ConversationSession
    from src.constants.constants import ListeningMode

    class _Protocol:
        def is_audio_channel_opened(self):
            return True

        async def send_start_listening(self, _mode):
            return None

    state = _FakeState(DeviceState.NOTIFYING)
    player = _FakeNotificationPlayer()
    player.is_active = True
    session = ConversationSession(
        state=state,
        protocol=_Protocol(),
        plugins=_FakePlugins(),
        notification_player=player,
    )

    await session.start_listening(ListeningMode.MANUAL)

    assert player.stop_count == 1
    assert state.states == [DeviceState.IDLE, DeviceState.LISTENING]


class _FakeCodec:
    def __init__(self):
        self.progress_callback = None
        self.drained_callback = None
        self.pcm = []
        self.clear_count = 0

    def set_notification_playback_callbacks(
        self, progress_callback=None, drained_callback=None
    ):
        self.progress_callback = progress_callback
        self.drained_callback = drained_callback

    async def write_notification_pcm(self, pcm):
        self.pcm.append(pcm)

    async def clear_notification_queue(self):
        self.clear_count += 1


class _FakeDecoder:
    def __init__(self, *args, **kwargs):
        self.running = True
        self.stopped = False

    async def start_decode(self, _url, queue):
        await queue.put(np.ones(240, dtype=np.float32))
        await queue.put(None)
        return True

    async def stop(self):
        self.running = False
        self.stopped = True

    def is_running(self):
        return self.running


@pytest.mark.asyncio
async def test_notification_player_waits_for_audio_drain_and_emits_subtitle(
    monkeypatch,
):
    from src.notifications import notification_player as module
    from src.notifications.notification_player import (
        NotificationPlayer,
        NotificationSubtitle,
    )

    monkeypatch.setattr(module, "MusicDecoder", _FakeDecoder)
    bus = EventBus()
    codec = _FakeCodec()
    player = NotificationPlayer()
    player.set_event_bus(bus)
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)

    subtitles = []
    finished = []
    finished_event = asyncio.Event()

    async def on_subtitle(text):
        subtitles.append(text)

    async def on_finished(generation, success):
        finished.append((generation, success))
        finished_event.set()

    bus.on(Events.NOTIFICATION_SUBTITLE, on_subtitle)
    generation = await player.start(
        "https://cdn.example.test/task.ogg",
        [NotificationSubtitle(0, "Task completed")],
        on_finished,
    )
    assert generation is not None

    for _ in range(20):
        if codec.pcm:
            break
        await asyncio.sleep(0)
    assert len(codec.pcm) == 1
    assert not finished_event.is_set()

    codec.progress_callback(240)
    codec.drained_callback()
    await asyncio.wait_for(finished_event.wait(), timeout=1)

    assert subtitles == ["Task completed"]
    assert finished == [(generation, True)]
    assert player.is_active is False
