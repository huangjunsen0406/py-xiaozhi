"""Behavioral regressions for the music ownership boundary and lifecycle."""

import asyncio
from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.mcp.tools.music import music_player as player_module
from src.mcp.tools.music import playback as playback_module
from src.mcp.tools.music.bus import MusicEventBridge
from src.mcp.tools.music.events import MusicControlRequest
from src.mcp.tools.music.music_player import MusicPlayer
from src.mcp.tools.music.online_search import SearchHit


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["stop", "detach", "codec_removed"])
async def test_decoder_startup_is_owned_until_cancelled_spawn_cleanup_finishes(
    music, monkeypatch, action
):
    entered, cleaning, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def blocked_start(_decoder, *args, **kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaning.set()
            await release.wait()

    monkeypatch.setattr(music.decoder_type, "start_decode", blocked_start)
    request = asyncio.create_task(music.player.search_and_play("First"))
    cleanup = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if action == "codec_removed":
            cleanup = asyncio.create_task(music.player.bind_audio_codec(None))
        else:
            cleanup = asyncio.create_task(getattr(music.player, action)())
        await asyncio.wait_for(cleaning.wait(), 1)
        cleanup.cancel()
        await asyncio.sleep(0)
        cleanup.cancel()
        await asyncio.sleep(0)
        assert not cleanup.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(cleanup, 1)
        assert (await request)["status"] == "error"
        music.decoders[0].stop.assert_awaited_once()
        assert not music.player.is_playing
        assert music.player._engine.decoder is None
        assert music.states == []
        if action != "stop":
            assert music.player._engine.audio_codec is None
        if action == "detach":
            assert music.player._bus.event_bus is None
    finally:
        release.set()
        await asyncio.gather(
            request, *([cleanup] if cleanup is not None else []), return_exceptions=True
        )


@pytest.mark.asyncio
async def test_concurrent_stops_share_cleanup_and_publish_one_terminal_event(music):
    await music.player.search_and_play("First")
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_cancel():
        entered.set()
        await release.wait()

    music.player._downloader.cancel_prefetch = blocked_cancel
    first = asyncio.create_task(music.player.stop())
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(music.player.stop())
        await asyncio.sleep(0)
        assert not first.done() and not second.done()
        release.set()
        await asyncio.gather(first, second)
        music.decoders[0].stop.assert_awaited_once()
        assert [state.state for state in music.states] == ["playing", "stopped"]
    finally:
        release.set()
        await asyncio.gather(
            first, *([second] if second is not None else []), return_exceptions=True
        )


class Codec:
    def __init__(self, rate=24000, duration=20):
        self.audio_config = AudioConfig(
            OUTPUT_SAMPLE_RATE=rate, FRAME_DURATION=duration
        )
        self.pcm = []
        self.written = asyncio.Event()
        self.clear_music_queue = AsyncMock()

    async def write_pcm_direct(self, pcm):
        self.pcm.append(pcm)
        self.written.set()


@pytest.fixture
async def music(tmp_path, monkeypatch):
    decoders = []

    class Decoder:
        get_duration = AsyncMock(return_value=0)

        def __init__(self, sample_rate, channels, frame_duration):
            self.sample_rate = sample_rate
            self.frame_duration = frame_duration
            self.completed_successfully = False
            self.error = None
            self.stop = AsyncMock()
            decoders.append(self)

        async def start_decode(self, source, output_queue, start_position=0, **kwargs):
            self.source = source
            self.position = start_position
            self.queue = output_queue
            return True

    monkeypatch.setattr(playback_module, "MusicDecoder", Decoder)
    player = MusicPlayer()
    player._cache._root = tmp_path
    player._downloader.start_prefetch = AsyncMock()
    player._downloader.resolve_play_url = AsyncMock(return_value="https://media.test/a")
    bus = EventBus()
    states = []
    lyrics = asyncio.Queue()

    async def record_state(data):
        states.append(data)

    async def record_lyric(data):
        await lyrics.put(data)

    bus.on(Events.MUSIC_STATE_CHANGED, record_state)
    bus.on(Events.MUSIC_LYRICS_UPDATE, record_lyric)
    speaking = SimpleNamespace(value=False)
    player.set_event_bus(bus, SimpleNamespace(is_speaking=lambda: speaking.value))
    codec = Codec()
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
    monkeypatch.setattr(
        player_module,
        "search_song",
        AsyncMock(return_value=SearchHit("one", "First", 40, "https://api.test/one")),
    )
    monkeypatch.setattr(
        player_module, "fetch_kuwo_lyrics", AsyncMock(return_value=[(0, "first line")])
    )
    yield SimpleNamespace(
        player=player,
        bus=bus,
        codec=codec,
        decoders=decoders,
        states=states,
        lyrics=lyrics,
        speaking=speaking,
        decoder_type=Decoder,
    )
    await player.detach()


@pytest.mark.asyncio
async def test_bridge_only_needs_public_player_controls_and_snapshot():
    player = SimpleNamespace(
        playback_state=SimpleNamespace(
            is_playing=True, paused=False, pause_source=None
        ),
        bind_audio_codec=AsyncMock(),
        pause=AsyncMock(),
        resume=AsyncMock(),
    )
    bridge = MusicEventBridge(player)
    bus = EventBus()
    bridge.set_event_bus(bus)
    codec = object()
    await bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
    await bus.emit(Events.AUDIO_CODEC_CHANGED, None)
    assert player.bind_audio_codec.await_args_list[0].args == (codec,)
    assert player.bind_audio_codec.await_args_list[1].args == (None,)
    await bus.emit(Events.MUSIC_PAUSE_REQUEST, MusicControlRequest(source="tts"))
    player.pause.assert_awaited_once_with(source="tts")
    player.playback_state.paused = True
    player.playback_state.pause_source = "manual"
    await bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "tts"})
    player.resume.assert_not_awaited()
    await bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "manual"})
    player.resume.assert_awaited_once()
    bridge.detach()
    await bus.emit(Events.MUSIC_RESUME_REQUEST, {})
    player.resume.assert_awaited_once()


@pytest.mark.asyncio
async def test_tts_pause_keeps_decoder_and_holds_pcm_until_matching_resume(music):
    player = music.player
    assert (await player.search_and_play("First"))["status"] == "success"
    decoder = music.decoders[0]
    await asyncio.sleep(0)
    await music.bus.emit(Events.MUSIC_PAUSE_REQUEST, {"source": "tts"})
    await decoder.queue.put(np.ones(4, dtype=np.float32))
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(music.codec.written.wait(), 0.03)
    decoder.stop.assert_not_awaited()
    music.codec.clear_music_queue.assert_not_awaited()
    assert player.paused
    await music.bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "manual"})
    assert player.paused
    await music.bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "tts"})
    await asyncio.wait_for(music.codec.written.wait(), 1)
    assert len(music.decoders) == 1
    assert not player.paused


@pytest.mark.asyncio
async def test_manual_takeover_of_tts_pause_clears_decoder_and_both_queues(music):
    player = music.player
    await player.search_and_play("First")
    decoder = music.decoders[0]
    await player.pause(source="tts")
    decoder.queue.put_nowait(np.ones(4, dtype=np.float32))
    result = await player.pause(source="manual")
    assert result["status"] == "info"
    assert player.playback_state.pause_source == "manual"
    decoder.stop.assert_awaited_once()
    assert decoder.queue.empty()
    music.codec.clear_music_queue.assert_awaited_once()
    await music.bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "tts"})
    assert player.paused
    assert (await player.resume())["status"] == "success"
    assert len(music.decoders) == 2
    assert music.decoders[1].source == "https://media.test/a"


@pytest.mark.asyncio
async def test_codec_replacement_stops_old_session_and_next_decoder_uses_new_format(
    music,
):
    await music.player.search_and_play("First")
    first = music.decoders[0]
    await music.bus.emit(Events.AUDIO_CODEC_CHANGED, music.codec)
    first.stop.assert_not_awaited()
    replacement = Codec(48000, 60)
    await music.bus.emit(Events.AUDIO_CODEC_CHANGED, replacement)
    first.stop.assert_awaited_once()
    music.codec.clear_music_queue.assert_awaited_once()
    assert not music.player.is_playing
    assert [event.state for event in music.states] == ["playing", "stopped"]
    assert (await music.player.search_and_play("First"))["status"] == "success"
    assert (music.decoders[-1].sample_rate, music.decoders[-1].frame_duration) == (
        48000,
        60,
    )
    assert first.sample_rate == 24000
    await music.decoders[-1].queue.put(np.ones(2, dtype=np.float32))
    await asyncio.wait_for(replacement.written.wait(), 1)
    assert music.codec.pcm == []


@pytest.mark.asyncio
async def test_song_switch_events_and_lyrics_use_the_correct_session(
    music, monkeypatch
):
    assert (await music.player.search_and_play("First"))["song"] == "First"
    first_lyric = await asyncio.wait_for(music.lyrics.get(), 1)
    assert first_lyric.song_id == "one"
    assert "first line" in first_lyric.text
    old_state = music.player.playback_state
    with pytest.raises(FrozenInstanceError):
        old_state.song = "mutated"
    music.player.lyrics.clear()
    assert music.player.lyrics == [(0, "first line")]
    monkeypatch.setattr(
        player_module,
        "search_song",
        AsyncMock(return_value=SearchHit("two", "Second", 90, "https://api.test/two")),
    )
    monkeypatch.setattr(
        player_module, "fetch_kuwo_lyrics", AsyncMock(return_value=[(0, "second line")])
    )
    result = await music.player.search_and_play("Second")
    assert result == {
        "status": "success",
        "message": "正在播放: Second",
        "song": "Second",
        "duration": "01:30",
        "total_seconds": 90,
    }
    assert [(e.state, e.song, e.duration) for e in music.states] == [
        ("playing", "First", 40),
        ("stopped", "First", 40),
        ("playing", "Second", 90),
    ]
    second_lyric = await asyncio.wait_for(music.lyrics.get(), 1)
    assert second_lyric.song_id == "two"
    assert "second line" in second_lyric.text
    assert old_state.song == "First"
    assert music.player.current_url == "https://api.test/two"


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["search", "lyrics", "resolve"])
@pytest.mark.parametrize("action", ["stop", "detach", "codec_removed"])
async def test_late_input_results_cannot_revive_stopped_music(
    music, monkeypatch, stage, action
):
    entered, release = asyncio.Event(), asyncio.Event()
    owner, name = {
        "search": (player_module, "search_song"),
        "lyrics": (player_module, "fetch_kuwo_lyrics"),
        "resolve": (music.player._downloader, "resolve_play_url"),
    }[stage]
    original = getattr(owner, name)

    async def blocked(*args, **kwargs):
        entered.set()
        await release.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(owner, name, blocked)
    request = asyncio.create_task(music.player.search_and_play("First"))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if action == "codec_removed":
            await music.bus.emit(Events.AUDIO_CODEC_CHANGED, None)
        else:
            await getattr(music.player, action)()
        release.set()
        assert (await request)["status"] != "success"
        assert not music.player.is_playing
        assert music.decoders == []
        assert music.states == []
    finally:
        release.set()
        await asyncio.gather(request, return_exceptions=True)


@pytest.mark.asyncio
async def test_stop_does_not_consume_a_decoder_terminal_marker_as_completion(music):
    await music.player.search_and_play("First")
    decoder = music.decoders[0]
    entered, release = asyncio.Event(), asyncio.Event()

    async def blocked_cancel():
        entered.set()
        await release.wait()

    music.player._downloader.cancel_prefetch = blocked_cancel
    stopping = asyncio.create_task(music.player.stop())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        decoder.completed_successfully = True
        await decoder.queue.put(None)
        await asyncio.sleep(0)
        release.set()
        assert (await stopping)["status"] == "success"
        assert [event.state for event in music.states] == ["playing", "stopped"]
        assert music.player.playback_state.error is None
    finally:
        release.set()
        await asyncio.gather(stopping, return_exceptions=True)


@pytest.mark.asyncio
async def test_deferred_online_request_resolves_only_after_tts_resume(music):
    music.speaking.value = True
    assert (await music.player.search_and_play("First"))["status"] == "success"
    assert music.player.is_playing and music.player.paused
    assert music.decoders == []
    music.player._downloader.resolve_play_url.assert_not_awaited()
    music.speaking.value = False
    await music.bus.emit(Events.MUSIC_RESUME_REQUEST, {"source": "tts"})
    assert music.player.is_playing and not music.player.paused
    assert len(music.decoders) == 1
    assert music.player.current_song == "First"


@pytest.mark.asyncio
async def test_local_play_switches_from_online_and_drops_online_lyrics_and_api(
    music, tmp_path, monkeypatch
):
    await music.player.search_and_play("First")
    path = tmp_path / "local.mp3"
    path.write_bytes(b"local audio")
    metadata = SimpleNamespace(display_name=lambda: "Local", duration=12)
    monkeypatch.setattr(music.player._library, "resolve", lambda _: (path, metadata))
    result = await music.player.play_local_song_by_id("local")
    assert result["song"] == "Local"
    assert result["total_seconds"] == 12
    assert music.player.lyrics == []
    assert music.player.current_url == str(path)
    assert music.player._engine.api_url is None
    assert music.decoders[-1].source == path
    assert [(e.state, e.song) for e in music.states] == [
        ("playing", "First"),
        ("stopped", "First"),
        ("playing", "Local"),
    ]


@pytest.mark.asyncio
async def test_seek_percentage_restarts_at_duration_based_position(music):
    await music.player.search_and_play("First")
    result = await music.player.seek(percent=50)
    assert result["status"] == "success"
    assert music.decoders[-1].position == 20
    music.decoders[0].stop.assert_awaited_once()
    music.codec.clear_music_queue.assert_awaited_once()
    assert music.player.current_song == "First"
    assert music.player.lyrics == [(0, "first line")]


@pytest.mark.asyncio
async def test_lyrics_ticks_are_throttled_without_losing_the_current_line(
    music, monkeypatch
):
    clock = SimpleNamespace(value=100.0)
    monkeypatch.setattr(
        playback_module, "time", SimpleNamespace(time=lambda: clock.value)
    )
    monkeypatch.setattr(
        player_module,
        "fetch_kuwo_lyrics",
        AsyncMock(return_value=[(0, "first"), (1, "second"), (1.05, "third")]),
    )
    await music.player.search_and_play("First")
    assert "first" in (await asyncio.wait_for(music.lyrics.get(), 1)).text
    clock.value = 101.51
    await music.player.tick_lyrics()
    assert "second" in (await asyncio.wait_for(music.lyrics.get(), 1)).text
    clock.value = 101.56
    await music.player.tick_lyrics()
    assert music.lyrics.empty()
    clock.value = 101.8
    await music.player.tick_lyrics()
    assert "third" in (await asyncio.wait_for(music.lyrics.get(), 1)).text


@pytest.mark.asyncio
async def test_idle_stop_after_completion_preserves_position_and_terminal_event(music):
    completed = asyncio.Event()

    async def record(data):
        if data.state == "completed":
            completed.set()

    music.bus.on(Events.MUSIC_STATE_CHANGED, record)
    await music.player.search_and_play("First")
    decoder = music.decoders[0]
    decoder.completed_successfully = True
    await decoder.queue.put(None)
    await asyncio.wait_for(completed.wait(), 1)
    assert (await music.player.stop())["status"] == "info"
    assert await music.player.get_position() == 40
    assert music.player.playback_state.position == 40
    assert [state.state for state in music.states] == ["playing", "completed"]
