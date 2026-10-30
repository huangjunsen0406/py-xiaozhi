"""Prefetch cancellation owns both task and real local child until cleanup."""

import asyncio
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.event_bus import EventBus, Events
from src.mcp.tools.music import download as module
from src.mcp.tools.music.cache import MusicCache
from src.mcp.tools.music.music_player import MusicPlayer
from src.utils.config_manager import ConfigManager


@pytest.fixture
async def local_copy(monkeypatch):
    actual_spawn = asyncio.create_subprocess_exec
    state = SimpleNamespace(
        children=[], outputs=[], ready=asyncio.Queue(), release=asyncio.Event(),
        hold_spawn=False, ignore_term=False, exit_code=None,
    )

    async def spawn(*args, **kwargs):
        output = args[-1]
        exit_code = state.exit_code
        script = (
            "import pathlib,signal,sys,time\n"
            f"output=pathlib.Path({output!r})\n"
            "def stopped(*_):\n"
            "    output.write_bytes(b'late write on termination')\n"
            "    sys.exit(0)\n"
            + ("signal.signal(signal.SIGTERM,signal.SIG_IGN)\n" if state.ignore_term
               else "signal.signal(signal.SIGTERM,stopped)\n")
            + "output.write_bytes(b'cached audio' * 500)\n"
            + "sys.stderr.write('ready\\n'); sys.stderr.flush()\n"
            + (f"sys.exit({exit_code})\n" if exit_code is not None else
               "sys.stderr.write('x' * (256 * 1024)); sys.stderr.flush(); time.sleep(60)\n")
        )
        child = await actual_spawn(sys.executable, "-c", script, **kwargs)
        state.children.append(child)
        state.outputs.append(output)
        assert await child.stderr.readline() == b"ready\n"
        await state.ready.put(child)
        if state.hold_spawn:
            await state.release.wait()
        return child

    monkeypatch.setattr(module.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(module, "get_ffmpeg_path", lambda: "local-copy-substitute")
    yield state
    state.release.set()
    for child in state.children:
        if child.returncode is None:
            child.kill()
        await child.wait()


def assert_clean(downloader, state, root):
    assert downloader._prefetch_task is None
    assert downloader._prefetch_song_id is None
    assert all(child.returncode is not None for child in state.children)
    assert not list(root.glob("*.part.*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "stop", "detach", "codec_removed", "completed"])
async def test_prefetch_lifecycle_waits_for_child_and_removes_late_output(tmp_path, local_copy, action):
    player = MusicPlayer(ConfigManager.from_dict())
    player._cache._root = tmp_path
    bus = EventBus()
    player.set_event_bus(bus)
    try:
        await player._downloader.start_prefetch("https://local-substitute.test/a", "one")
        child = await asyncio.wait_for(local_copy.ready.get(), 3)
        task = player._downloader._prefetch_task
        assert child.returncode is None
        if action == "cancel":
            await player._downloader.cancel_prefetch()
        elif action == "stop":
            # Prefetch can outlive decoding; the !is_playing path must also clean it.
            assert not player.is_playing
            await player.stop()
        elif action == "detach":
            await player.detach()
            assert player._bus.event_bus is None
        elif action == "codec_removed":
            await bus.emit(Events.AUDIO_CODEC_CHANGED, None)
        else:
            player._engine.is_playing = True
            await player._engine._handle_playback_finished()
        assert task.done()
        assert_clean(player._downloader, local_copy, tmp_path)
        assert not (tmp_path / "one.mp3").exists()
    finally:
        await player.detach()


@pytest.mark.asyncio
async def test_switching_song_waits_for_previous_task_before_starting_another(tmp_path, local_copy):
    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    try:
        await downloader.start_prefetch("https://local-substitute.test/a", "one")
        first = await asyncio.wait_for(local_copy.ready.get(), 3)
        previous = downloader._prefetch_task
        await downloader.start_prefetch("https://local-substitute.test/b", "two")
        await asyncio.wait_for(local_copy.ready.get(), 3)
        assert first.returncode is not None
        assert previous.done()
        assert not (tmp_path / "one.mp3").exists()
        assert len(list(tmp_path.glob("*.part.*"))) == 1
    finally:
        await downloader.cancel_prefetch()
    assert_clean(downloader, local_copy, tmp_path)


@pytest.mark.asyncio
async def test_cancel_during_process_creation_keeps_owner_until_child_reaped(tmp_path, local_copy):
    local_copy.hold_spawn = True
    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    cancel = None
    try:
        await downloader.start_prefetch("https://local-substitute.test/a", "one")
        child = await asyncio.wait_for(local_copy.ready.get(), 3)
        worker = downloader._prefetch_task
        cancel = asyncio.create_task(downloader.cancel_prefetch())
        await asyncio.sleep(0)
        assert not cancel.done()
        assert downloader._prefetch_task is worker
        assert child.returncode is None
        local_copy.release.set()
        await asyncio.wait_for(cancel, 3)
        assert worker.done()
        assert_clean(downloader, local_copy, tmp_path)
    finally:
        local_copy.release.set()
        if cancel is not None:
            await asyncio.gather(cancel, return_exceptions=True)
        await downloader.cancel_prefetch()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["cancel", "stop", "detach"])
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signal ignoring local child")
async def test_repeated_cancellation_of_cleanup_still_kills_and_reaps(tmp_path, local_copy, action):
    local_copy.ignore_term = True
    player = MusicPlayer(ConfigManager.from_dict())
    player._cache._root = tmp_path
    downloader = player._downloader
    decoder = SimpleNamespace(stop=AsyncMock())
    if action != "cancel":
        player._engine.is_playing = True
        player._engine.decoder = decoder
        player._engine.audio_codec = SimpleNamespace(clear_music_queue=AsyncMock())
    waiter = None
    try:
        await downloader.start_prefetch("https://local-substitute.test/a", "one")
        child = await asyncio.wait_for(local_copy.ready.get(), 3)
        terminating = asyncio.Event()
        terminate = child.terminate

        def record_terminate():
            terminating.set()
            terminate()

        child.terminate = record_terminate
        cleanup = (
            downloader.cancel_prefetch if action == "cancel"
            else player.stop if action == "stop" else player.detach
        )
        waiter = asyncio.create_task(cleanup())
        await asyncio.wait_for(terminating.wait(), 3)
        waiter.cancel()
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, 5)
        assert_clean(downloader, local_copy, tmp_path)
        if action != "cancel":
            decoder.stop.assert_awaited_once()
            assert not player.is_playing
        if action == "detach":
            assert player._bus.event_bus is None
    finally:
        if waiter is not None:
            await asyncio.gather(waiter, return_exceptions=True)
        await player.detach()


@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 1])
async def test_prefetch_success_publishes_and_failure_discards_output(tmp_path, local_copy, exit_code):
    local_copy.exit_code = exit_code
    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    try:
        await downloader.start_prefetch("https://local-substitute.test/a", "one")
        worker = downloader._prefetch_task
        await asyncio.wait_for(worker, 3)
        assert (tmp_path / "one.mp3").exists() is (exit_code == 0)
        assert_clean(downloader, local_copy, tmp_path)
    finally:
        await downloader.cancel_prefetch()


@pytest.mark.asyncio
async def test_prefetch_spawn_failure_cleans_task_ownership(tmp_path, monkeypatch):
    monkeypatch.setattr(
        module.asyncio, "create_subprocess_exec", AsyncMock(side_effect=FileNotFoundError)
    )
    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    await downloader.start_prefetch("https://local-substitute.test/a", "one")
    worker = downloader._prefetch_task
    await asyncio.wait_for(worker, 1)
    assert downloader._prefetch_task is None
    assert not list(tmp_path.glob("*.part.*"))


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["connect", "read", "read_error"])
async def test_blocking_download_cancellation_waits_for_worker_before_return(tmp_path, monkeypatch, stage):
    import threading

    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    downloader.resolve_play_url = AsyncMock(return_value="https://local-substitute.test/a")
    blocked = asyncio.Event()
    release = threading.Event()
    closed = threading.Event()
    loop = asyncio.get_running_loop()
    calls = []
    publications = []
    original_move = module.shutil.move

    def move(*args):
        publications.append(args)
        return original_move(*args)

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            closed.set()

        def raise_for_status(self):
            pass

        def iter_content(self, **_kwargs):
            yield b"initial audio"
            loop.call_soon_threadsafe(blocked.set)
            assert release.wait(3), "test did not release blocking response"
            if stage == "read_error":
                raise module.requests.ConnectionError("cancelled read")
            yield b"late audio"

    def get(*args, **kwargs):
        calls.append((args, kwargs))
        if stage == "connect":
            loop.call_soon_threadsafe(blocked.set)
            assert release.wait(3), "test did not release blocking connect"
        return Response()

    monkeypatch.setattr(module.requests, "get", get)
    monkeypatch.setattr(module.shutil, "move", move)
    # An existing cache file must survive cancellation of its replacement.
    final = tmp_path / "one.mp3"
    final.write_bytes(b"existing audio")
    task = asyncio.create_task(downloader.download("unused", "one.mp3"))
    try:
        await asyncio.wait_for(blocked.wait(), 3)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        assert not closed.is_set()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 3)
        assert closed.is_set()
        assert not publications
        assert final.read_bytes() == b"existing audio"
        assert list((tmp_path / "temp").iterdir()) == []
        assert len(calls) == 1
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [False, True])
async def test_blocking_download_success_and_failure_close_response(tmp_path, monkeypatch, failure):
    downloader = module.MusicDownloader(MusicCache(root=tmp_path))
    downloader.resolve_play_url = AsyncMock(return_value="https://local-substitute.test/a")
    closed = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            closed.append(True)

        def raise_for_status(self):
            pass

        def iter_content(self, **_kwargs):
            yield b"audio"
            if failure:
                raise module.requests.ConnectionError("read failed")
            yield b" tail"

    monkeypatch.setattr(module.requests, "get", lambda *a, **kw: Response())
    result = await downloader.download("unused", "one.mp3")
    final = tmp_path / "one.mp3"
    assert result == (None if failure else final)
    assert final.exists() is (not failure)
    if not failure:
        assert final.read_bytes() == b"audio tail"
    assert len(closed) == (3 if failure else 1)
    assert list((tmp_path / "temp").iterdir()) == []


@pytest.mark.asyncio
async def test_concurrent_instances_keep_distinct_partial_output(tmp_path, local_copy):
    first = module.MusicDownloader(MusicCache(root=tmp_path))
    second = module.MusicDownloader(MusicCache(root=tmp_path))
    try:
        await first.start_prefetch("https://local-substitute.test/a", "same")
        await asyncio.wait_for(local_copy.ready.get(), 3)
        await second.start_prefetch("https://local-substitute.test/a", "same")
        await asyncio.wait_for(local_copy.ready.get(), 3)
        assert local_copy.outputs[0] != local_copy.outputs[1]
        await first.cancel_prefetch()
        assert local_copy.children[0].returncode is not None
        assert local_copy.children[1].returncode is None
        assert len(list(tmp_path.glob("*.part.*"))) == 1
    finally:
        await first.cancel_prefetch()
        await second.cancel_prefetch()
    assert_clean(second, local_copy, tmp_path)
