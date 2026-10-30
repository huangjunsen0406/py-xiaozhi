"""Subprocess proxy cancellation and source/frozen launcher contracts."""

import asyncio
import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from src.mcp.plugins import subprocess_runtime as runtime

ROOT = Path(__file__).resolve().parents[1]


def session_for(root, **kwargs):
    return runtime.PluginSubprocessSession(
        plugin_id="contract",
        plugin_root=root,
        entry="plugin:register",
        platform_tag="",
        allow_get=[],
        capabilities={},
        **kwargs,
    )


def proxy_for(session):
    tools = []
    runtime.register_subprocess_plugin_tools(tools.append, session=session)
    return tools[0]


@pytest.mark.asyncio
async def test_queued_cancelled_proxy_never_enters_request_thread(
    tmp_path, monkeypatch
):
    session = session_for(tmp_path)
    session._tools_meta = [
        {"name": "test.invoke", "properties": [{"name": "label", "type": "string"}]}
    ]
    entered, release = threading.Event(), threading.Event()
    dispatched = []

    def request(method, params, *, timeout):
        label = params["arguments"]["label"]
        dispatched.append(label)
        if label == "A":
            entered.set()
            assert release.wait(2)
        return {"value": label}

    monkeypatch.setattr(session, "_request_locked", request)
    tool = proxy_for(session)
    first = asyncio.create_task(tool.call({"label": "A"}))
    assert await asyncio.to_thread(entered.wait, 2)
    second = asyncio.create_task(tool.call({"label": "B"}))
    # Give B a chance to wait at the async gate or, before the fix, thread lock.
    for _ in range(10):
        await asyncio.sleep(0)
    second.cancel()
    try:
        with pytest.raises(asyncio.CancelledError):
            await second
    finally:
        release.set()
        await first
        await asyncio.to_thread(lambda: session._lock.acquire())
        session._lock.release()
    assert dispatched == ["A"]


@pytest.mark.asyncio
@pytest.mark.parametrize("late_error", [False, True])
async def test_inflight_cancel_keeps_serialization_until_request_finishes(
    tmp_path, monkeypatch, late_error
):
    session = session_for(tmp_path)
    session._tools_meta = [
        {"name": "test.invoke", "properties": [{"name": "label", "type": "string"}]}
    ]
    entered, release = threading.Event(), threading.Event()
    finished = threading.Event()
    dispatched = []

    def request(method, params, *, timeout):
        label = params["arguments"]["label"]
        dispatched.append(label)
        if label == "A":
            entered.set()
            assert release.wait(2)
            finished.set()
            if late_error:
                raise RuntimeError("late request failure")
        return {"value": label}

    monkeypatch.setattr(session, "_request_locked", request)
    tool = proxy_for(session)
    first = asyncio.create_task(tool.call({"label": "A"}))
    assert await asyncio.to_thread(entered.wait, 2)
    first.cancel()
    await asyncio.sleep(0)
    second = asyncio.create_task(tool.call({"label": "B"}))
    try:
        await asyncio.sleep(0)
        assert not first.done()
        first.cancel()  # Repeated cancellation must still retain ownership.
        await asyncio.sleep(0)
        assert not first.done() and not finished.is_set()
    finally:
        release.set()
        await asyncio.gather(first, second, return_exceptions=True)
    assert first.cancelled() and finished.is_set()
    assert dispatched == ["A", "B"]


@pytest.fixture
def plugin_root(tmp_path):
    (tmp_path / "plugin.py").write_text(
        "def register(host):\n"
        "    @host.tool('test.ping', 'ping')\n"
        "    def ping(args):\n"
        "        import sys\n"
        "        assert 'src.cli' not in sys.modules\n"
        "        assert 'src.bootstrap.container' not in sys.modules\n"
        "        assert 'PySide6' not in sys.modules\n"
        "        return 'pong'\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize("mode", ["source", "frozen", "frozen_windowed", "override"])
def test_real_worker_bootstraps_in_source_and_frozen_dispatch(
    plugin_root, monkeypatch, mode
):
    real_popen = subprocess.Popen
    python = sys.executable
    launched = []
    monkeypatch.setattr(sys, "frozen", mode != "source", raising=False)
    if mode != "source":
        monkeypatch.setattr(sys, "executable", "/fake/frozen-app")

    def popen(argv, **kwargs):
        launched.append(argv)
        if mode in {"frozen", "frozen_windowed"}:
            assert argv == ["/fake/frozen-app", "--mcp-plugin-worker"]
            if mode == "frozen_windowed":
                script = (
                    "import runpy,sys; "
                    "sys.stdin=sys.stdout=sys.stderr=None; "
                    "sys.__stdin__=sys.__stdout__=sys.__stderr__=None; "
                    f"sys.argv={[str(ROOT / 'main.py'), '--mcp-plugin-worker']!r}; "
                    f"runpy.run_path({str(ROOT / 'main.py')!r}, run_name='__main__')"
                )
                argv = [python, "-c", script]
            else:
                argv = [python, str(ROOT / "main.py"), *argv[1:]]
        else:
            assert argv == [python, str(ROOT / "src/mcp/plugins/subprocess_worker.py")]
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(runtime.subprocess, "Popen", popen)
    session = session_for(
        plugin_root, **({"python_executable": python} if mode == "override" else {})
    )
    try:
        assert [meta["name"] for meta in session.start_and_bootstrap()] == ["test.ping"]
        assert session.call_tool_sync("test.ping", {}) == "pong"
        process = session._proc
    finally:
        session.terminate()
    assert len(launched) == 1
    assert process.poll() is not None


async def wait_for_file(path):
    async def wait():
        while not path.exists():
            await asyncio.sleep(0.005)

    await asyncio.wait_for(wait(), timeout=2)


@pytest.mark.asyncio
async def test_real_worker_cancelled_queue_never_writes_and_inflight_reply_is_drained(
    tmp_path,
):
    (tmp_path / "plugin.py").write_text(
        "from pathlib import Path\nimport time\n"
        "def register(host):\n"
        "    @host.tool('test.slow', 'slow', props=[{'name': 'label', 'type': 'string'}])\n"
        "    def slow(args):\n"
        "        label = args['label']\n"
        "        root = Path(__file__).parent\n"
        "        (root / label).write_text('called')\n"
        "        while label == 'A' and not (root / 'release').exists():\n"
        "            time.sleep(0.005)\n"
        "        return label\n",
        encoding="utf-8",
    )
    session = session_for(tmp_path, call_timeout=2)
    session.start_and_bootstrap()
    tool = proxy_for(session)
    tasks = []
    try:
        first = asyncio.create_task(tool.call({"label": "A"}))
        tasks.append(first)
        await wait_for_file(tmp_path / "A")
        first.cancel()
        second = asyncio.create_task(tool.call({"label": "B"}))
        tasks.append(second)
        await asyncio.sleep(0)
        second.cancel()
        with pytest.raises(asyncio.CancelledError):
            await second
        third = asyncio.create_task(tool.call({"label": "C"}))
        tasks.append(third)
        await asyncio.sleep(0)
        assert not first.done() and not third.done()
        assert not (tmp_path / "B").exists()
        assert not (tmp_path / "C").exists()
        (tmp_path / "release").touch()
        with pytest.raises(asyncio.CancelledError):
            await first
        response = json.loads(await third)
        assert not response["isError"]
        assert response["content"][0]["text"] == "C"
        assert not (tmp_path / "B").exists()
        # The discarded A reply must not be mistaken for the next request ID.
        response = json.loads(await tool.call({"label": "D"}))
        assert response["content"][0]["text"] == "D"
        process = session._proc
    finally:
        (tmp_path / "release").touch()
        await asyncio.gather(*tasks, return_exceptions=True)
        session.terminate()
    assert process.poll() is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["timeout", "terminate"])
async def test_cancelled_inflight_request_reaps_worker_and_releases_gate(
    tmp_path, finish
):
    (tmp_path / "plugin.py").write_text(
        "from pathlib import Path\nimport time\n"
        "def register(host):\n"
        "    @host.tool('test.hang', 'hang')\n"
        "    def hang(args):\n"
        "        (Path(__file__).parent / 'started').touch()\n"
        "        while True: time.sleep(0.005)\n",
        encoding="utf-8",
    )
    session = session_for(tmp_path, call_timeout=0.15)
    session.start_and_bootstrap()
    process = session._proc
    tool = proxy_for(session)
    first = asyncio.create_task(tool.call({}))
    try:
        await wait_for_file(tmp_path / "started")
        first.cancel()
        if finish == "terminate":
            session.terminate()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, timeout=2)
        assert process.poll() is not None
        assert session._proc is None
        # A later call returns a transport error rather than hanging at a lock
        # abandoned by cancellation, or writing after the worker was reaped.
        reply = json.loads(await asyncio.wait_for(tool.call({}), timeout=0.5))
        assert reply["isError"]
    finally:
        session.terminate()
        await asyncio.gather(first, return_exceptions=True)


def test_windowed_windows_worker_recovers_inherited_standard_handles(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    from unittest.mock import Mock, call

    from src.mcp.plugins import subprocess_worker as worker

    get_handle = Mock(side_effect=[2**33 + 1, 2**33 + 2, 2**33 + 3])
    open_handle = Mock(side_effect=[3, 4, 5])
    dup2, close = Mock(), Mock()
    streams = [object(), object(), object()]
    fdopen = Mock(side_effect=streams)
    with monkeypatch.context() as patch:
        patch.setattr(sys, "platform", "win32")
        for name in (
            "stdin",
            "stdout",
            "stderr",
            "__stdin__",
            "__stdout__",
            "__stderr__",
        ):
            patch.setattr(sys, name, None)
        patch.setattr(
            ctypes,
            "windll",
            SimpleNamespace(kernel32=SimpleNamespace(GetStdHandle=get_handle)),
            raising=False,
        )
        patch.setitem(
            sys.modules, "msvcrt", SimpleNamespace(open_osfhandle=open_handle)
        )
        patch.setattr(worker.os, "dup2", dup2)
        patch.setattr(worker.os, "close", close)
        patch.setattr(worker.os, "fdopen", fdopen)
        worker._restore_standard_streams()
        assert [sys.stdin, sys.stdout, sys.stderr] == streams
        assert [sys.__stdin__, sys.__stdout__, sys.__stderr__] == streams
    assert get_handle.call_args_list == [call(-10), call(-11), call(-12)]
    assert get_handle.restype is ctypes.c_void_p
    assert dup2.call_args_list == [call(3, 0), call(4, 1), call(5, 2)]
    assert close.call_args_list == [call(3), call(4), call(5)]
