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
    completed_successfully = True

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


async def _wait_for_pcm(codec, count):
    for _ in range(50):
        if len(codec.pcm) >= count:
            return
        await asyncio.sleep(0)
    assert len(codec.pcm) >= count


@pytest.mark.asyncio
async def test_stale_underrun_drain_does_not_finish_newly_queued_audio(monkeypatch):
    from src.notifications import notification_player as module

    class Decoder(_FakeDecoder):
        async def start_decode(self, _url, queue):
            self.queue = queue
            await queue.put(np.ones(240, dtype=np.float32))
            return True

    class Codec(_FakeCodec):
        async def write_notification_pcm(self, pcm):
            await super().write_notification_pcm(pcm)
            if len(self.pcm) == 2:
                # 上一段断粮产生的回调，延迟到新 PCM 入队后才到达。
                self.drained_callback()
                await asyncio.sleep(0)

    monkeypatch.setattr(module, "MusicDecoder", Decoder)
    player = module.NotificationPlayer()
    codec = Codec()
    await player._on_audio_codec_changed(codec)
    finished = asyncio.Queue()

    async def on_finished(generation, success):
        await finished.put((generation, success))

    generation = await player.start("https://example.test/a.ogg", [], on_finished)
    try:
        await _wait_for_pcm(codec, 1)
        codec.progress_callback(240)
        await asyncio.sleep(0)
        decoder = player._decoder
        await decoder.queue.put(np.ones(240, dtype=np.float32))
        await decoder.queue.put(None)
        await _wait_for_pcm(codec, 2)
        for _ in range(10):
            await asyncio.sleep(0)
        assert finished.empty()

        codec.progress_callback(240)
        codec.drained_callback()
        assert await asyncio.wait_for(finished.get(), 1) == (generation, True)
    finally:
        await player.stop()


@pytest.mark.asyncio
async def test_decode_failure_after_partial_audio_is_not_reported_as_success(
    monkeypatch,
):
    from src.notifications import notification_player as module

    class Decoder(_FakeDecoder):
        completed_successfully = False

    monkeypatch.setattr(module, "MusicDecoder", Decoder)
    player = module.NotificationPlayer()
    codec = _FakeCodec()
    await player._on_audio_codec_changed(codec)
    finished = asyncio.Queue()

    async def on_finished(generation, success):
        await finished.put((generation, success))

    generation = await player.start("https://example.test/a.ogg", [], on_finished)
    try:
        await _wait_for_pcm(codec, 1)
        assert await asyncio.wait_for(finished.get(), 1) == (generation, False)
        assert codec.progress_callback is None
        assert codec.drained_callback is None
        assert codec.clear_count == 1
    finally:
        await player.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [RuntimeError("decoder failed"), asyncio.CancelledError()]
)
async def test_decoder_start_failure_restores_idle_and_cleans_resources(
    monkeypatch, failure
):
    from src.bootstrap.session import ConversationSession
    from src.notifications import notification_player as module

    instances = []

    class Decoder(_FakeDecoder):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            instances.append(self)

        async def start_decode(self, _url, _queue):
            raise failure

    monkeypatch.setattr(module, "MusicDecoder", Decoder)
    player = module.NotificationPlayer()
    codec = _FakeCodec()
    await player._on_audio_codec_changed(codec)
    state = _FakeState()
    session = ConversationSession(
        state, object(), _FakePlugins(), notification_player=player
    )
    try:
        with pytest.raises(type(failure)):
            await session._handle_notify({"audio_url": "https://example.test/a.ogg"})
        assert state.is_idle()
        assert not player.is_active
        assert instances[0].stopped
        assert codec.progress_callback is None
        assert codec.drained_callback is None
    finally:
        await player.stop()


@pytest.mark.asyncio
async def test_removing_audio_codec_finishes_notification_and_restores_idle(
    monkeypatch,
):
    from src.bootstrap.session import ConversationSession
    from src.notifications import notification_player as module

    monkeypatch.setattr(module, "MusicDecoder", _FakeDecoder)
    bus = EventBus()
    player = module.NotificationPlayer()
    player.set_event_bus(bus)
    codec = _FakeCodec()
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
    state = _FakeState()
    session = ConversationSession(
        state, object(), _FakePlugins(), notification_player=player
    )
    await session._handle_notify({"audio_url": "https://example.test/a.ogg"})
    await _wait_for_pcm(codec, 1)
    await bus.emit(Events.AUDIO_CODEC_CHANGED, None)
    assert not player.is_active
    assert state.is_idle()
    assert codec.progress_callback is None


@pytest.mark.asyncio
@pytest.mark.parametrize("refresh", [False, True])
@pytest.mark.parametrize("reload_ok", [False, True])
async def test_device_reload_cancels_notification_before_reset(
    monkeypatch, refresh, reload_ok
):
    from types import SimpleNamespace

    from src.bootstrap.session import ConversationSession
    from src.notifications import notification_player as module
    from src.plugins.audio import AudioPlugin
    from src.utils import audio_utils

    monkeypatch.setattr(module, "MusicDecoder", _FakeDecoder)
    bus = EventBus()
    player = module.NotificationPlayer()
    player.set_event_bus(bus)
    state = _FakeState()
    session = ConversationSession(
        state, object(), _FakePlugins(), notification_player=player
    )

    class Codec(_FakeCodec):
        def stop_streams_for_enumeration(self):
            assert not player.is_active

        async def reload_devices(self, **_kwargs):
            assert not player.is_active
            assert state.is_idle()
            return reload_ok

    codec = Codec()
    plugin = AudioPlugin()
    plugin.codec = codec
    plugin._ctx = SimpleNamespace(event_bus=bus)
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
    await session._handle_notify({"audio_url": "https://example.test/a.ogg"})
    await _wait_for_pcm(codec, 1)
    if refresh:
        monkeypatch.setattr(
            audio_utils, "refresh_portaudio_devices", lambda **_kwargs: None
        )
        monkeypatch.setattr(audio_utils, "list_audio_devices", lambda **_kwargs: {})
        await plugin._on_devices_refresh_request()
    else:
        await plugin._on_config_changed()
    assert state.is_idle()
    assert player._codec is (codec if reload_ok else None)
    assert codec.clear_count == 1


@pytest.mark.parametrize(
    "message",
    [
        {"audio_url": "https://[invalid/a.ogg"},
        {"audio_url": "https://example.test/a.ogg", "subtitles": None},
    ],
)
def test_invalid_notify_payload_is_rejected_without_raising(message):
    from src.notifications.notification_player import parse_notification

    assert parse_notification(message) is None


def test_nonfinite_subtitle_time_is_ignored():
    from src.notifications.notification_player import parse_notification

    parsed = parse_notification(
        {
            "audio_url": "https://example.test/a.ogg",
            "subtitles": [{"start_ms": float("nan"), "text": "invalid"}],
        }
    )
    assert parsed == ("https://example.test/a.ogg", [])
