"""Duration probing cancellation must reap local child processes."""

import asyncio
import subprocess
import sys

import pytest

from src.audio_codecs import music_decoder as module


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["version", "duration"])
@pytest.mark.parametrize("during_spawn", [False, True])
async def test_duration_cancellation_reaps_child_and_propagates(monkeypatch, stage, during_spawn):
    actual_spawn = asyncio.create_subprocess_exec
    processes = []
    ready = asyncio.Event()
    release_spawn = asyncio.Event()

    async def spawn(*args, **kwargs):
        version = "-version" in args
        target = version == (stage == "version")
        script = "print('ready', flush=True); import time; time.sleep(60)" if target else "pass"
        child = await actual_spawn(
            sys.executable, "-c", script, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        processes.append(child)
        if target:
            assert await child.stdout.readline() == b"ready\n"
            ready.set()
            if during_spawn:
                await release_spawn.wait()
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module, "get_ffprobe_path", lambda: "local-probe-substitute")
    task = asyncio.create_task(module.MusicDecoder.get_duration("local-input.ogg"))
    try:
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel()
        release_spawn.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 4)
        assert all(child.returncode is not None for child in processes)
    finally:
        release_spawn.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in processes:
            if child.returncode is None:
                child.kill()
            await child.wait()


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal ignoring child")
async def test_cancelled_duration_probe_kills_child_that_ignores_terminate(monkeypatch):
    actual_spawn = asyncio.create_subprocess_exec
    ready = asyncio.Event()
    processes = []

    async def spawn(*args, **kwargs):
        child = await actual_spawn(
            sys.executable, "-c",
            "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
            "print('ready',flush=True); time.sleep(60)",
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        processes.append(child)
        assert await child.stdout.readline() == b"ready\n"
        ready.set()
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    task = asyncio.create_task(module.MusicDecoder.get_duration("local-input.ogg"))
    try:
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert processes[0].returncode is not None
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in processes:
            if child.returncode is None:
                child.kill()
            await child.wait()


@pytest.mark.asyncio
async def test_duration_probe_preserves_normal_success(monkeypatch):
    actual_spawn = asyncio.create_subprocess_exec
    processes = []

    async def spawn(*args, **kwargs):
        script = "pass" if "-version" in args else "print('12.5')"
        child = await actual_spawn(sys.executable, "-c", script, **kwargs)
        processes.append(child)
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    assert await module.MusicDecoder.get_duration("local-input.ogg") == 12.5
    assert all(child.returncode == 0 for child in processes)
