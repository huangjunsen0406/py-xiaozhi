"""Server-owned plugin installations, atomic publication and worker cleanup."""

import asyncio
import gc
import json
import sys

import pytest

from src.mcp.mcp_server import McpServer
from src.mcp.plugins import subprocess_runtime
from src.mcp.plugins.host import McpHost
from src.mcp.plugins.loader import PluginLoader
from src.mcp.tooling import McpTool, PropertyList


@pytest.fixture(autouse=True)
def restore_plugin_imports():
    original_path = sys.path[:]
    original_modules = sys.modules.copy()
    yield
    sys.path[:] = original_path
    for name in list(sys.modules):
        if name.startswith("mcp_plugin_") or name == "plugin":
            if name in original_modules:
                sys.modules[name] = original_modules[name]
            else:
                sys.modules.pop(name, None)


def package(root, source, *, mode="python-subprocess", **manifest):
    directory = root / "owned.plugin"
    directory.mkdir()
    (directory / "manifest.json").write_text(
        json.dumps({"id": "owned.plugin", "runtime": mode, **manifest}),
        encoding="utf-8",
    )
    (directory / "plugin.py").write_text(source, encoding="utf-8")


def loader_for(server, root):
    # No bound method: publication must use the explicitly injected runtime.
    def unexpected_add(tool):
        raise AssertionError("loader published a tool through McpHost")

    return PluginLoader(
        McpHost(unexpected_add), runtime=server._plugin_runtime, plugins_dir=root
    )


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
def test_explicit_owner_outlives_loader_and_owns_all_tools(tmp_path, mode):
    package(
        tmp_path,
        "def register(host):\n"
        "    host.tool('owned.first', 'first')(lambda _: 'one')\n"
        "    host.tool('owned.second', 'second')(lambda _: 'two')\n",
        mode=mode,
    )
    server = McpServer()
    loader = loader_for(server, tmp_path)
    try:
        assert loader.load_all()[0].error is None
        del loader
        gc.collect()
        assert server._plugin_tool_owner == {
            "owned.first": "owned.plugin", "owned.second": "owned.plugin"
        }
        snapshot = server._plugin_tool_owner
        snapshot.clear()
        assert server._plugin_tool_owner
        installation = server._plugin_runtime._installations["owned.plugin"]
        process = installation.session._proc if installation.session else None
        response = json.loads(asyncio.run(server.tools[-1].call({})))
        assert response["content"][0]["text"] == "two"
        assert server.unload_plugin("owned.plugin") == 2
        assert not server.tools and not server._plugin_tool_owner
        assert not server._plugin_runtime.has_plugin("owned.plugin")
        if process:
            assert process.poll() is not None
    finally:
        server.detach()


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
def test_same_plugin_id_tools_and_workers_are_isolated_per_server(tmp_path, mode):
    servers = [McpServer(), McpServer()]
    try:
        for index, server in enumerate(servers):
            root = tmp_path / str(index)
            root.mkdir()
            package(
                root,
                "def register(host):\n"
                f"    host.tool('owned.ping', 'ping')(lambda _: '{index}')\n",
                mode=mode,
            )
            assert loader_for(server, root).load_all()[0].error is None
        second_installation = servers[1]._plugin_runtime._installations["owned.plugin"]
        assert servers[0].unload_plugin("owned.plugin") == 1
        servers[0].detach()
        assert not servers[0].tools
        assert servers[1]._plugin_runtime._installations["owned.plugin"] is second_installation
        assert servers[1]._plugin_tool_owner == {"owned.ping": "owned.plugin"}
        response = json.loads(asyncio.run(servers[1].tools[0].call({})))
        assert response["content"][0]["text"] == "1"
        if second_installation.session:
            assert second_installation.session._proc.poll() is None
    finally:
        for server in servers:
            server.detach()


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
def test_zero_tool_installation_rejects_duplicate_and_reuses_loader_after_unload(
    tmp_path, mode
):
    package(tmp_path, "def register(host):\n    pass\n", mode=mode)
    server = McpServer()
    loader = loader_for(server, tmp_path)
    try:
        assert loader.load_all()[0].error is None
        installation = server._plugin_runtime._installations["owned.plugin"]
        assert server._plugin_tool_owner == {}
        assert "id 冲突" in loader_for(server, tmp_path).load_all()[0].error
        assert "id 冲突" in loader.load_all()[0].error
        assert server._plugin_runtime._installations["owned.plugin"] is installation
        if installation.session:
            assert installation.session._proc.poll() is None
        assert server.unload_plugin("owned.plugin") == 0
        assert not server._plugin_runtime.has_plugin("owned.plugin")
        assert loader.load_all()[0].error is None
    finally:
        server.detach()


def test_failed_atomic_commit_reaps_unowned_worker_and_keeps_existing_tool(
    tmp_path, monkeypatch
):
    package(
        tmp_path,
        "def register(host):\n"
        "    host.tool('owned.partial', 'new')(lambda _: 'new')\n"
        "    host.tool('builtin.keep', 'conflict')(lambda _: 'bad')\n",
    )
    started = []
    original_start = subprocess_runtime.PluginSubprocessSession.start_and_bootstrap

    def capture_start(session):
        result = original_start(session)
        started.append((session, session._proc))
        return result

    monkeypatch.setattr(
        subprocess_runtime.PluginSubprocessSession, "start_and_bootstrap", capture_start
    )
    server = McpServer()
    original = McpTool("builtin.keep", "keep", PropertyList(), lambda _: "old")
    server.add_tool(original)
    try:
        assert loader_for(server, tmp_path).load_all()[0].error
        assert server.tools == [original]
        assert not server._plugin_tool_owner
        assert not server._plugin_runtime.has_plugin("owned.plugin")
        assert len(started) == 1
        session, process = started[0]
        assert session._proc is None
        assert process.poll() is not None
    finally:
        server.detach()


def test_builtin_reinstall_preserves_zero_tool_worker_and_installation(
    tmp_path, monkeypatch
):
    import src.mcp.tools.volume as volume

    package(tmp_path, "def register(host):\n    pass\n")
    monkeypatch.setattr(
        volume, "register_volume_tools",
        lambda add, _: add(McpTool("builtin.test", "test", PropertyList(), lambda _: "ok")),
    )
    server = McpServer()
    try:
        assert loader_for(server, tmp_path).load_all()[0].error is None
        installation = server._plugin_runtime._installations["owned.plugin"]
        process = installation.session._proc
        server.register_builtin_tools()
        server.register_builtin_tools()
        assert server._plugin_runtime._installations["owned.plugin"] is installation
        assert process.poll() is None
    finally:
        server.detach()
    assert process.poll() is not None


@pytest.mark.asyncio
async def test_detach_reaps_cancelled_inflight_worker_and_releases_queued_call(tmp_path):
    package(
        tmp_path,
        "from pathlib import Path\nimport time\n"
        "def register(host):\n"
        "    @host.tool('owned.hang', 'hang')\n"
        "    def hang(args):\n"
        "        (Path(__file__).parent / 'started').touch()\n"
        "        while True: time.sleep(0.005)\n",
        call_timeout=2,
    )
    server = McpServer()
    tasks = []
    try:
        assert loader_for(server, tmp_path).load_all()[0].error is None
        process = server._plugin_runtime._installations["owned.plugin"].session._proc
        tool = server.tools[0]
        first = asyncio.create_task(tool.call({}))
        tasks.append(first)

        async def wait_started():
            while not (tmp_path / "owned.plugin" / "started").exists():
                await asyncio.sleep(0.005)

        await asyncio.wait_for(wait_started(), 2)
        first.cancel()
        second = asyncio.create_task(tool.call({}))
        tasks.append(second)
        await asyncio.sleep(0)
        server.detach()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(first, 2)
        reply = json.loads(await asyncio.wait_for(second, 2))
        assert reply["isError"]
        assert process.poll() is not None
        assert not server.tools and not server._plugin_tool_owner
        assert not server._plugin_runtime.has_plugin("owned.plugin")
        server.detach()
    finally:
        server.detach()
        await asyncio.gather(*tasks, return_exceptions=True)
