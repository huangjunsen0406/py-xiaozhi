"""FFmpeg 终态、PCM 短读及启动取消回归。"""

import asyncio
from unittest.mock import AsyncMock

import numpy as np
import pytest

from src.audio_codecs import music_decoder as module


class Process:
    def __init__(self, chunks=(), exit_code=0, blocked=False):
        self.stdout = asyncio.StreamReader()
        self.stderr = asyncio.StreamReader()
        for chunk in chunks:
            self.stdout.feed_data(chunk)
        self.stdout.feed_eof()
        self.stderr.feed_eof()
        self.returncode = None
        self.exit_code = exit_code
        self.released = asyncio.Event()
        self.waiting = asyncio.Event()
        self.terminated = False
        if not blocked:
            self.released.set()

    async def wait(self):
        self.waiting.set()
        await self.released.wait()
        if self.returncode is None:
            self.returncode = self.exit_code
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = -15
        self.released.set()

    def kill(self):
        self.terminate()


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", [20, 40, 60])
async def test_pcm_read_size_uses_decoder_frame_duration(duration):
    decoder = module.MusicDecoder(sample_rate=16000, frame_duration=duration)
    process = Process()
    process.stdout = AsyncMock()
    process.stdout.read.return_value = b""
    decoder._process = process
    await decoder._read_pcm_stream(asyncio.Queue())
    process.stdout.read.assert_awaited_once_with(16000 * duration // 1000 * 2)


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
async def test_decoder_reports_exit_status_after_partial_pcm(exit_code):
    decoder = module.MusicDecoder()
    decoder._process = Process([b"\x00\x40" * 240], exit_code=exit_code)
    queue = asyncio.Queue()
    await decoder._read_pcm_stream(queue)
    assert np.allclose(queue.get_nowait(), 0.5)
    assert queue.get_nowait() is None
    assert decoder.completed_successfully is (exit_code == 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("channels", [1, 2])
async def test_short_reads_preserve_sample_and_channel_alignment(channels):
    decoder = module.MusicDecoder(channels=channels)
    samples = np.array([100, -200, 300, -400], dtype="<i2")
    data = samples.tobytes()
    process = Process()
    chunks = iter([data[:1], data[1:3], data[3:5], data[5:], b""])
    process.stdout = AsyncMock()
    process.stdout.read.side_effect = lambda _size: next(chunks)
    decoder._process = process
    queue = asyncio.Queue()
    await decoder._read_pcm_stream(queue)
    actual = []
    while (chunk := queue.get_nowait()) is not None:
        actual.append(chunk.reshape(-1))
    np.testing.assert_allclose(np.concatenate(actual), samples / 32768.0)
    assert decoder.completed_successfully


@pytest.mark.asyncio
async def test_stdout_failure_sends_terminal_and_reaps_live_process():
    decoder = module.MusicDecoder()
    process = Process(blocked=True)
    process.stdout = AsyncMock()
    process.stdout.read.side_effect = OSError("broken pipe")
    decoder._process = process
    queue = asyncio.Queue()
    await decoder._read_pcm_stream(queue)
    assert queue.get_nowait() is None
    assert not decoder.completed_successfully
    assert process.terminated


@pytest.mark.asyncio
async def test_truncated_pcm_is_failure():
    decoder = module.MusicDecoder()
    decoder._process = Process([b"\x00"])
    queue = asyncio.Queue()
    await decoder._read_pcm_stream(queue)
    assert queue.get_nowait() is None
    assert not decoder.completed_successfully


@pytest.mark.asyncio
async def test_stop_during_version_probe_prevents_decoder_spawn(monkeypatch):
    probe = Process(blocked=True)
    spawn = AsyncMock(return_value=probe)
    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    decoder = module.MusicDecoder()
    task = asyncio.create_task(
        decoder.start_decode("https://example.test/a.ogg", asyncio.Queue())
    )
    await asyncio.wait_for(probe.waiting.wait(), 1)
    await decoder.stop()
    assert await asyncio.wait_for(task, 1) is False
    assert probe.terminated
    assert spawn.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_task", [False, True])
@pytest.mark.parametrize("spawn_index", [0, 1])
async def test_stop_or_cancel_during_process_creation_reaps_late_process(
    monkeypatch, cancel_task, spawn_index
):
    probe = Process()
    process = Process(blocked=True)
    created = [probe, process]
    spawning = asyncio.Event()
    release_spawn = asyncio.Event()
    calls = 0

    async def spawn(*_args, **_kwargs):
        nonlocal calls
        index = calls
        calls += 1
        if index == spawn_index:
            spawning.set()
            await release_spawn.wait()
        return created[index]

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    decoder = module.MusicDecoder()
    task = asyncio.create_task(
        decoder.start_decode("https://example.test/a.ogg", asyncio.Queue())
    )
    await asyncio.wait_for(spawning.wait(), 1)
    if cancel_task:
        task.cancel()
    else:
        await decoder.stop()
    release_spawn.set()
    if cancel_task:
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
    else:
        assert await asyncio.wait_for(task, 1) is False
    assert created[spawn_index].terminated
    assert not decoder.is_running()
    assert decoder._process is None
    assert decoder._probe_process is None
