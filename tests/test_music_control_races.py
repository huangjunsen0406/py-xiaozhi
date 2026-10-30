"""Late music controls cannot revive or tear down a newer playback session."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import AudioConfig
from src.mcp.tools.music import playback
from src.mcp.tools.music.music_player import MusicPlayer


@pytest.fixture
async def music(monkeypatch):
    decoders = []

    class Decoder:
        error = None
        completed_successfully = False
        get_duration = AsyncMock(return_value=0)

        def __init__(self, **kwargs):
            self.stopped = False
            decoders.append(self)

        async def start_decode(self, source, queue, *args, **kwargs):
            self.queue = queue
            return not self.stopped

        async def stop(self):
            self.stopped = True

    monkeypatch.setattr(playback, "MusicDecoder", Decoder)
    player = MusicPlayer()
    codec = SimpleNamespace(
        audio_config=AudioConfig(),
        clear_music_queue=AsyncMock(),
        write_pcm_direct=AsyncMock(),
    )
    await player.bind_audio_codec(codec)
    speaking = SimpleNamespace(value=False)
    player._engine.set_speaking_provider(lambda: speaking.value)
    yield SimpleNamespace(
        player=player,
        engine=player._engine,
        codec=codec,
        decoders=decoders,
        decoder_type=Decoder,
        speaking=speaking,
    )
    await player.detach()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["stop", "detach", "codec_removed"])
async def test_duration_probe_cannot_revive_cancelled_seek(music, tmp_path, action):
    source = tmp_path / "track.wav"
    source.write_bytes(b"fake")
    assert await music.engine.start_playback(source)
    entered, release = asyncio.Event(), asyncio.Event()

    async def duration(*args, **kwargs):
        entered.set()
        await release.wait()
        return 100

    music.decoder_type.get_duration = staticmethod(duration)
    request = asyncio.create_task(music.player.seek(percent=50))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if action == "codec_removed":
            await music.player.bind_audio_codec(None)
        else:
            await getattr(music.player, action)()
        release.set()
        assert (await asyncio.wait_for(request, 1))["status"] != "success"
        assert not music.player.is_playing
        assert music.engine.total_duration == 0
        assert len(music.decoders) == 1
    finally:
        release.set()
        await asyncio.gather(request, return_exceptions=True)


@pytest.mark.asyncio
async def test_tts_start_during_decoder_startup_keeps_new_session_paused(
    music, monkeypatch
):
    entered, release = asyncio.Event(), asyncio.Event()

    async def start(decoder, source, queue, *args, **kwargs):
        decoder.queue = queue
        entered.set()
        await release.wait()
        return True

    monkeypatch.setattr(music.decoder_type, "start_decode", start)
    request = asyncio.create_task(
        music.engine.start_playback("https://media.test/track")
    )
    try:
        await asyncio.wait_for(entered.wait(), 1)
        music.speaking.value = True
        await music.player.pause(source="tts")
        release.set()
        assert await asyncio.wait_for(request, 1)
        assert music.player.is_playing and music.player.paused
        assert music.player.playback_state.pause_source == "tts"
        music.codec.write_pcm_direct.assert_not_awaited()
    finally:
        release.set()
        await asyncio.gather(request, return_exceptions=True)


@pytest.mark.asyncio
async def test_late_resume_failure_cannot_stop_newer_successful_resume(
    music, monkeypatch
):
    assert await music.engine.start_playback("https://media.test/track")
    await music.player.pause(source="manual")
    entered, second_entered, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    starts = 0

    async def start(decoder, source, queue, *args, **kwargs):
        nonlocal starts
        starts += 1
        decoder.queue = queue
        if starts == 1:
            entered.set()
            await release.wait()
        else:
            second_entered.set()
        return not decoder.stopped

    monkeypatch.setattr(music.decoder_type, "start_decode", start)
    first = asyncio.create_task(music.player.resume())
    second = None
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(music.player.resume())
        # Both serialization and superseding the first request are valid.
        try:
            await asyncio.wait_for(second_entered.wait(), 0.03)
        except asyncio.TimeoutError:
            pass
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert any(result["status"] == "success" for result in results)
        assert music.player.is_playing and not music.player.paused
        assert music.engine.last_error is None
        assert music.engine.decoder is not None and not music.engine.decoder.stopped
    finally:
        release.set()
        await asyncio.gather(
            first, *([second] if second else []), return_exceptions=True
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("new_binding", [False, True])
async def test_codec_binding_survives_overlapping_stop(music, new_binding, monkeypatch):
    assert await music.engine.start_playback("https://media.test/track")
    entered, release = asyncio.Event(), asyncio.Event()
    decoder = music.engine.decoder

    async def stop():
        entered.set()
        await release.wait()
        decoder.stopped = True

    monkeypatch.setattr(decoder, "stop", stop)
    first = asyncio.create_task(music.player.bind_audio_codec(None))
    second = None
    replacement = SimpleNamespace(audio_config=AudioConfig())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        second = asyncio.create_task(
            music.player.bind_audio_codec(replacement)
            if new_binding
            else music.player.stop()
        )
        await asyncio.sleep(0)
        release.set()
        await asyncio.wait_for(asyncio.gather(first, second), 1)
        assert music.engine.audio_codec is (replacement if new_binding else None)
        assert not music.player.is_playing
    finally:
        release.set()
        await asyncio.gather(
            first, *([second] if second else []), return_exceptions=True
        )
