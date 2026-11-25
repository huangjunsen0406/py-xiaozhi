"""Real decoder reader results reach MediaPlayer and NotificationPlayer consumers."""

import asyncio
import subprocess
import sys

import numpy as np
import pytest

from src.audio_codecs import audio_decoder as module
from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.media.media_player import MediaPlayer
from src.notifications.notification_player import NotificationPlayer
from src.utils.config_manager import ConfigManager


class Track:
    def __init__(self, codec):
        self._codec = codec

    async def write_pcm(self, pcm):
        await self._codec.write_notification_pcm(pcm)

    async def clear(self):
        await self._codec.clear_notification_queue()
        return 1


class Codec:
    audio_config = AudioConfig()
    aec_active = False

    def __init__(self):
        self.pcm = []
        self.written = asyncio.Event()
        self.cleared = 0
        self.progress = None
        self.drained = None

    def get_background_track(self):
        return Track(self)

    async def write_notification_pcm(self, pcm):
        self.pcm.append(pcm.copy())
        self.written.set()

    async def clear_notification_queue(self):
        self.cleared += 1

    def set_notification_playback_callbacks(
        self, progress_callback=None, drained_callback=None
    ):
        self.progress = progress_callback
        self.drained = drained_callback


@pytest.fixture
async def local_decoder(monkeypatch):
    actual_spawn = asyncio.create_subprocess_exec
    children = []
    mode = {"exit": 0, "pcm": True, "truncated": False}

    async def spawn(*args, **kwargs):
        if "-version" in args:
            child = await actual_spawn(sys.executable, "-c", "pass", **kwargs)
        elif "-show_entries" in args:
            child = await actual_spawn(sys.executable, "-c", "print('10.0')", **kwargs)
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
    monkeypatch.setattr(module, "get_ffprobe_path", lambda: "local-probe-substitute")
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
async def test_media_decode_result_is_not_confused_with_success(
    local_decoder, exit_code, has_pcm
):
    mode, children = local_decoder
    mode.update(exit=exit_code, pcm=has_pcm)
    bus = EventBus()
    events = []
    terminal = asyncio.Event()

    async def state_changed(data):
        events.append(data.state)
        if data.state in {"completed", "error"}:
            terminal.set()

    bus.on(Events.MEDIA_STATE_CHANGED, state_changed)
    player = MediaPlayer(ConfigManager.from_dict())
    player.attach(bus)
    codec = Codec()
    await player.bind_audio_codec(codec)
    try:
        res = await player.play_url("https://local-substitute.test/a.ogg", title="Test")
        assert res["status"] == "success"
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
        assert all(child.returncode is not None for child in children)
    finally:
        await player.stop()
        await player.detach()


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
async def test_notification_decode_result_propagates_after_partial_audio(
    local_decoder, exit_code
):
    mode, children = local_decoder
    mode["exit"] = exit_code
    codec = Codec()
    player = NotificationPlayer()
    await player._on_audio_codec_changed(codec)
    finished = asyncio.Queue()

    async def on_finished(generation, success):
        await finished.put((generation, success))

    try:
        generation = await player.start(
            "https://local-substitute.test/a.ogg", [], on_finished
        )
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
async def test_truncated_sample_fails_media_instead_of_completed(local_decoder):
    mode, children = local_decoder
    mode["truncated"] = True
    player = MediaPlayer(ConfigManager.from_dict())
    codec = Codec()
    await player.bind_audio_codec(codec)
    try:
        res = await player.play_url("https://local-substitute.test/a.ogg")
        assert res["status"] == "success"
        task = player._playback_task
        await asyncio.wait_for(codec.written.wait(), 3)
        finish_decode(children)
        await asyncio.wait_for(task, 3)
        assert player.last_error == "Truncated PCM sample"
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
        generation = await player.start(
            "https://local-substitute.test/a.ogg", [], on_finished
        )
        await asyncio.wait_for(codec.written.wait(), 3)
        finish_decode(children)
        assert await asyncio.wait_for(finished.get(), 3) == (generation, False)
        assert codec.cleared == 1
    finally:
        await player.stop()


@pytest.mark.asyncio
async def test_media_stop_is_not_decode_failure_or_completion(local_decoder):
    _mode, children = local_decoder
    player = MediaPlayer(ConfigManager.from_dict())
    codec = Codec()
    bus = EventBus()
    states = []

    async def record(data):
        states.append(data.state)

    bus.on(Events.MEDIA_STATE_CHANGED, record)
    player.attach(bus)
    await player.bind_audio_codec(codec)
    try:
        res = await player.play_url("https://local-substitute.test/a.ogg")
        assert res["status"] == "success"
        await asyncio.wait_for(codec.written.wait(), 3)
        assert (await player.stop())["status"] == "success"
        assert states == ["playing", "stopped"]
        assert player.last_error is None
        assert all(child.returncode is not None for child in children)
    finally:
        await player.stop()
        await player.detach()
