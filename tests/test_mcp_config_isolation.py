"""MCP 配置、外挂阶段和相机实例隔离回归。"""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.mcp.mcp_server import McpServer
from src.mcp.plugins import subprocess_runtime
from src.mcp.plugins.loader import load_mcp_plugins_from_config
from src.mcp.tool_catalog import discover_plugin_catalog_rows
from src.mcp.tooling import McpTool, PropertyList
from src.utils.config_manager import ConfigManager


def plugin(root, name):
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps({"id": name, "entry": "plugin:register", "tools": [f"{name}.config"]}), encoding="utf-8"
    )
    (directory / "plugin.py").write_text(
        "def register(host):\n"
        "    config = host.get('config_readonly')\n"
        f"    host.tool('{name}.config', 'read local settings')(\n"
        "        lambda _: config.get_config('SYSTEM_OPTIONS.WINDOW_SIZE_MODE'))\n",
        encoding="utf-8",
    )


def config(root, mode, disabled):
    return ConfigManager.from_dict(
        {
            "SYSTEM_OPTIONS": {"WINDOW_SIZE_MODE": mode},
            "MCP_PLUGINS": {"DIR": str(root)},
            "MCP_TOOLS": {"DISABLED": disabled},
        }
    )


@pytest.mark.asyncio
async def test_servers_use_their_own_plugin_directory_policy_and_readonly_config(tmp_path):
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    plugin(first_dir, "first")
    plugin(second_dir, "second")
    first = McpServer(config(first_dir, "compact", ["builtin.test"]))
    second = McpServer(config(second_dir, "expanded", []))
    try:
        for server in (first, second):
            server.add_tool(McpTool("builtin.test", "test", PropertyList(), lambda _: "ok"))
            results = server.reload_external_plugins()
            assert len(results) == 1
            assert results[0].error is None
        assert [tool.name for tool in first._iter_enabled_tools()] == ["first.config"]
        assert [tool.name for tool in second._iter_enabled_tools()] == [
            "builtin.test", "second.config"
        ]
        assert json.loads(await first.tools[-1].call({}))["content"][0]["text"] == "compact"
        assert json.loads(await second.tools[-1].call({}))["content"][0]["text"] == "expanded"
        first._reply_error = AsyncMock()
        second._reply_result = AsyncMock()
        await first._handle_tool_call(1, {"name": "builtin.test"})
        await second._handle_tool_call(1, {"name": "builtin.test"})
        first._reply_error.assert_awaited_once_with(1, "Tool disabled: builtin.test")
        second._reply_result.assert_awaited_once()
        # Updating the injected source changes this server's live policy only.
        first.config.update_config("MCP_TOOLS.DISABLED", [])
        assert [tool.name for tool in first._iter_enabled_tools()][0] == "builtin.test"
        assert second.config.get_config("SYSTEM_OPTIONS.WINDOW_SIZE_MODE") == "expanded"
    finally:
        first.detach()
        second.detach()
        subprocess_runtime.drop_all_sessions()


def test_default_servers_and_cameras_never_read_process_configuration(monkeypatch):
    import src.utils.config_manager as configuration
    from src.mcp.tools.camera import create_camera
    from src.mcp.tools.camera.capture_backend import load_capture_config

    def unexpected():
        raise AssertionError("process configuration was accessed")

    monkeypatch.setattr(configuration, "get_config", unexpected)
    first, second = McpServer(), McpServer()
    first.config.update_config("MCP_TOOLS.DISABLED", ["one"])
    assert second._disabled_tool_names() == set()
    first_camera, second_camera = create_camera(), create_camera()
    first_camera.config.update_config("CAMERA.camera_index", 7)
    assert second_camera.camera_index == 0
    assert load_capture_config().camera_index == 0


def test_default_servers_do_not_scan_user_plugin_directory(monkeypatch):
    import src.mcp.plugins.loader as loader

    def unexpected():
        raise AssertionError("default server scanned user plugins")

    monkeypatch.setattr(loader, "default_plugins_dir", unexpected)
    server = McpServer()
    assert server.reload_external_plugins() == []
    assert loader.load_mcp_plugins_from_config(server.add_tool) == []


@pytest.mark.asyncio
async def test_loader_uses_its_configuration_for_readonly_capability(tmp_path):
    plugin(tmp_path, "local")
    server = McpServer(config(tmp_path, "local", []))
    foreign = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"WINDOW_SIZE_MODE": "foreign"}})
    try:
        results = load_mcp_plugins_from_config(
            server.add_tool, config=server.config,
            capabilities={"config_readonly": foreign}, tool_owner=server._plugin_tool_owner,
        )
        assert results[0].error is None
        result = json.loads(await server.tools[0].call({}))
        assert result["content"][0]["text"] == "local"
    finally:
        server.detach()


def test_builtin_registration_does_not_reload_or_unload_external_plugins(tmp_path, monkeypatch):
    import src.mcp.tools.volume as volume

    plugin(tmp_path, "external")
    server = McpServer(config(tmp_path, "compact", []))
    monkeypatch.setattr(
        volume, "register_volume_tools",
        lambda add, _: add(McpTool("builtin.test", "test", PropertyList(), lambda _: "ok")),
    )
    try:
        server.reload_external_plugins()
        external = server.tools[0]
        server.register_builtin_tools()
        assert external in server.tools
        assert server._plugin_tool_owner == {"external.config": "external"}
        server.register_builtin_tools()
        assert external in server.tools
        assert len([tool for tool in server.tools if tool.name == "builtin.test"]) == 1
    finally:
        server.detach()


def test_common_tools_compatibility_invokes_each_stage_once(monkeypatch):
    server = McpServer()
    calls = []
    monkeypatch.setattr(server, "register_builtin_tools", lambda *args: calls.append("builtin"))
    monkeypatch.setattr(server, "reload_external_plugins", lambda *args: calls.append("external"))
    server.add_common_tools()
    assert calls == ["builtin", "external"]


def test_camera_capture_and_analysis_use_injected_instance_configuration(monkeypatch):
    import src.mcp.tools.camera.base_camera as base
    import src.mcp.tools.camera.normal_camera as normal
    from src.mcp.tools.camera import create_camera

    first_config = ConfigManager.from_dict({
        "CAMERA": {"camera_index": 2, "frame_width": 800},
        "SYSTEM_OPTIONS": {"DEVICE_ID": "first", "CLIENT_ID": "first-client"},
    })
    second_config = ConfigManager.from_dict({"CAMERA": {"camera_index": 5}})
    first, second = create_camera(first_config), create_camera(second_config)
    seen = []
    monkeypatch.setattr(base, "capture_jpeg", lambda cfg: seen.append(cfg) or b"jpeg")
    first_config.update_config("CAMERA.camera_index", 3)
    assert first.capture() and second.capture()
    assert [(cfg.camera_index, cfg.frame_width) for cfg in seen] == [(3, 800), (5, 640)]
    requests = []
    monkeypatch.setattr(
        normal.requests, "post",
        lambda *args, **kwargs: requests.append(kwargs) or SimpleNamespace(status_code=200, text="ok"),
    )
    first.set_explain_url("https://example.test/vision")
    assert first.analyze("what") == "ok"
    assert requests[0]["headers"] == {"Device-Id": "first", "Client-Id": "first-client"}


def test_visual_camera_factory_passes_configuration_to_capture_and_analysis(monkeypatch):
    import src.mcp.tools.camera.vl_camera as visual
    from src.mcp.tools.camera import create_camera

    seen = []
    monkeypatch.setattr(visual, "OpenAI", lambda **kwargs: seen.append(kwargs) or object())
    settings = ConfigManager.from_dict({"CAMERA": {
        "VLapi_key": "test-key", "Local_VL_url": "https://example.test/v1",
        "models": "test-model", "camera_index": 4,
    }})
    camera = create_camera(settings)
    assert camera.config is settings
    assert camera.camera_index == 4 and camera.model == "test-model"
    assert seen[0]["api_key"] == "test-key"
    assert seen[0]["base_url"] == "https://example.test/v1"


def test_plugin_catalog_directory_is_explicit_per_configuration(tmp_path):
    first_dir, second_dir = tmp_path / "first", tmp_path / "second"
    plugin(first_dir, "first")
    plugin(second_dir, "second")
    first = discover_plugin_catalog_rows(config(first_dir, "compact", []))
    second = discover_plugin_catalog_rows(config(second_dir, "expanded", []))
    assert {row["group"] for row in first} == {"first"}
    assert {row["group"] for row in second} == {"second"}
