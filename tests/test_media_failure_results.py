"""Real decoder reader results reach music and notification consumers."""

import asyncio
import subprocess
import sys
import time

import numpy as np
import pytest

from src.audio_codecs import music_decoder as module
from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.mcp.tools.music.music_player import MusicPlayer
from src.notifications.notification_player import NotificationPlayer
from src.utils.config_manager import ConfigManager


class Codec:
    audio_config = AudioConfig()

    def __init__(self):
        self.pcm = []
        self.written = asyncio.Event()
        self.cleared = 0
        self.progress = None
        self.drained = None

    async def write_pcm_direct(self, pcm):
        self.pcm.append(pcm.copy())
        self.written.set()

    write_notification_pcm = write_pcm_direct

    async def clear_music_queue(self):
        self.cleared += 1

    clear_notification_queue = clear_music_queue

    def set_notification_playback_callbacks(self, progress_callback=None, drained_callback=None):
        self.progress = progress_callback
        self.drained = drained_callback


@pytest.fixture
async def local_decoder(monkeypatch):
    actual_spawn = asyncio.create_subprocess_exec
    children = []
    # The child waits on stdin after its first partial frame, so consuming it
    # proves we still stream instead of waiting for all decoder output.
    mode = {"exit": 0, "pcm": True, "truncated": False}

    async def spawn(*args, **kwargs):
        if "-version" in args:
            child = await actual_spawn(sys.executable, "-c", "pass", **kwargs)
        else:
            payload = b"\x00\x40" * 7 if mode["pcm"] else b""
            if mode["truncated"]:
                payload += b"\x00"
            script = (
                "import sys; "
                f"sys.stdout.buffer.write({payload!r}); sys.stdout.buffer.flush(); "
                "sys.stdin.buffer.read(1); "
                f"sys.exit({mode['exit']})"
            )
            child = await actual_spawn(
                sys.executable, "-c", script, stdin=subprocess.PIPE, **kwargs
            )
        children.append(child)
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module, "get_ffmpeg_path", lambda: "local-decoder-substitute")
    yield mode, children
    for child in children:
        if child.returncode is None:
            child.kill()
        await child.wait()


def finish_decode(children):
    children[-1].stdin.write(b"x")


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
@pytest.mark.parametrize("has_pcm", [False, True])
async def test_music_decode_result_is_not_confused_with_success(local_decoder, exit_code, has_pcm):
    mode, children = local_decoder
    mode.update(exit=exit_code, pcm=has_pcm)
    bus = EventBus()
    events = []
    terminal = asyncio.Event()

    async def state_changed(data):
        events.append(data.state)
        if data.state in {"completed", "error"}:
            terminal.set()

    bus.on(Events.MUSIC_STATE_CHANGED, state_changed)
    player = MusicPlayer(ConfigManager.from_dict())
    player.set_event_bus(bus)
    codec = Codec()
    player._engine.audio_codec = codec
    try:
        assert await player._engine.start_playback("https://local-substitute.test/a.ogg")
        if has_pcm:
            await asyncio.wait_for(codec.written.wait(), 3)
            np.testing.assert_allclose(codec.pcm[0], np.full(7, 0.5))
            assert not terminal.is_set()
        finish_decode(children)
        await asyncio.wait_for(terminal.wait(), 3)
        assert events == ["playing", "completed" if exit_code == 0 else "error"]
        assert not player.is_playing
        status = await player.get_status()
        assert status["status"] == ("success" if exit_code == 0 else "error")
        assert codec.cleared == (0 if exit_code == 0 else 1)
        assert all(child.returncode is not None for child in children)
    finally:
        await player.stop()
        await player.detach()


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
async def test_notification_decode_result_propagates_after_partial_audio(local_decoder, exit_code):
    mode, children = local_decoder
    mode["exit"] = exit_code
    codec = Codec()
    player = NotificationPlayer()
    await player._on_audio_codec_changed(codec)
    finished = asyncio.Queue()

    async def on_finished(generation, success):
        await finished.put((generation, success))

    try:
        generation = await player.start("https://local-substitute.test/a.ogg", [], on_finished)
        await asyncio.wait_for(codec.written.wait(), 3)
        assert finished.empty()
        finish_decode(children)
        if exit_code == 0:
            codec.progress(7)
            codec.drained()
        assert await asyncio.wait_for(finished.get(), 3) == (generation, exit_code == 0)
        assert codec.cleared == (0 if exit_code == 0 else 1)
        assert not player.is_active
        assert all(child.returncode is not None for child in children)
    finally:
        await player.stop()


@pytest.mark.asyncio
async def test_truncated_sample_fails_music_instead_of_completed(local_decoder):
    mode, children = local_decoder
    mode["truncated"] = True
    player = MusicPlayer(ConfigManager.from_dict())
    codec = Codec()
    player._engine.audio_codec = codec
    try:
        assert await player._engine.start_playback("https://local-substitute.test/a.ogg")
        task = player._engine._playback_task
        await asyncio.wait_for(codec.written.wait(), 3)
        finish_decode(children)
        await asyncio.wait_for(task, 3)
        assert player._engine.last_error == "Truncated PCM sample"
        assert (await player.get_status())["status"] == "error"
    finally:
        await player.stop()
        await player.detach()


@pytest.mark.asyncio
async def test_truncated_sample_fails_notification(local_decoder):
    mode, children = local_decoder
    mode["truncated"] = True
    codec = Codec()
    player = NotificationPlayer()
    await player._on_audio_codec_changed(codec)
    finished = asyncio.Queue()

    async def on_finished(generation, success):
        await finished.put((generation, success))

    try:
        generation = await player.start("https://local-substitute.test/a.ogg", [], on_finished)
        await asyncio.wait_for(codec.written.wait(), 3)
        finish_decode(children)
        assert await asyncio.wait_for(finished.get(), 3) == (generation, False)
        assert codec.cleared == 1
    finally:
        await player.stop()


@pytest.mark.asyncio
async def test_music_stop_is_not_decode_failure_or_completion(local_decoder):
    _mode, children = local_decoder
    player = MusicPlayer(ConfigManager.from_dict())
    codec = Codec()
    player._engine.audio_codec = codec
    states = []
    bus = EventBus()

    async def record(data):
        states.append(data.state)

    bus.on(Events.MUSIC_STATE_CHANGED, record)
    player.set_event_bus(bus)
    try:
        assert await player._engine.start_playback("https://local-substitute.test/a.ogg")
        await asyncio.wait_for(codec.written.wait(), 3)
        assert (await player.stop())["status"] == "success"
        assert states == ["playing", "stopped"]
        assert player._engine.last_error is None
        assert all(child.returncode is not None for child in children)
    finally:
        await player.stop()
        await player.detach()


@pytest.mark.asyncio
async def test_elapsed_duration_does_not_bypass_decoder_result(local_decoder):
    _mode, children = local_decoder
    player = MusicPlayer(ConfigManager.from_dict())
    codec = Codec()
    player._engine.audio_codec = codec
    try:
        player._engine.total_duration = 1
        assert await player._engine.start_playback("https://local-substitute.test/a.ogg")
        await asyncio.wait_for(codec.written.wait(), 3)
        player._engine.start_play_time = time.time() - 5
        assert await player._engine.get_position() == 1
        assert player.is_playing
        assert children[-1].returncode is None
    finally:
        await player.stop()
        await player.detach()
