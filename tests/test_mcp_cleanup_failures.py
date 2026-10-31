"""One failing plugin cleanup must not strand other workers or bindings."""

from unittest.mock import Mock

import pytest

from src.mcp.mcp_server import McpServer
from src.mcp.plugins.subprocess_runtime import PluginSubprocessSession
from src.mcp.tooling import McpTool, PropertyList


@pytest.mark.parametrize("failure", ["terminate", "stdin_close"])
def test_detach_cleans_all_installations_after_one_worker_failure(failure, tmp_path):
    server = McpServer()
    callback, camera = object(), object()
    server.set_send_callback(callback)
    server.set_camera(camera)
    process = None
    if failure == "terminate":
        first = Mock()
        first.terminate.side_effect = OSError("injected worker stop failure")
    else:
        first = PluginSubprocessSession(
            plugin_id="first",
            plugin_root=tmp_path,
            entry="plugin:register",
            platform_tag="test",
            allow_get=[],
            capabilities={},
        )
        process = Mock()
        process.poll.return_value = None
        process.stdin.close.side_effect = OSError("injected pipe close failure")
        first._proc = process
    second = Mock()
    tool = McpTool("first.tool", "test", PropertyList(), lambda _: "ok")
    server._plugin_runtime.install("first", [tool], session=first)
    # Zero-tool workers must be cleaned, too.
    server._plugin_runtime.install("second", [], session=second)

    server.detach()
    assert not server.tools
    assert not server._plugin_runtime._installations
    assert server._send_callback is None and server.get_camera() is None
    second.terminate.assert_called_once_with()
    if process is not None:
        process.terminate.assert_called_once_with()
        process.wait.assert_called_once_with(timeout=2)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close.assert_called_once_with()
        assert first._proc is None
    else:
        first.terminate.assert_called_once_with()
    server.detach()
    second.terminate.assert_called_once_with()


def test_detach_unbinds_dependencies_even_if_unloader_raises(monkeypatch):
    server = McpServer()
    server.set_send_callback(object())
    server.set_camera(object())
    monkeypatch.setattr(
        server, "_unload_external_plugins", Mock(side_effect=RuntimeError("unload"))
    )
    with pytest.raises(RuntimeError, match="unload"):
        server.detach()
    assert server._send_callback is None and server.get_camera() is None
