"""MCP 外挂注册事务、权限边界与子进程生命周期回归。"""

import asyncio
import json
import sys

import pytest

from src.mcp.mcp_server import McpServer
from src.mcp.plugins import subprocess_runtime as runtime
from src.mcp.plugins.host import McpHost
from src.mcp.plugins.loader import PluginLoader
from src.mcp.plugins.registry import PluginRuntime
from src.mcp.tooling import McpTool, PropertyList


@pytest.fixture(autouse=True)
def restore_plugin_imports(monkeypatch):
    runtimes = []
    original_init = PluginRuntime.__init__

    def track_runtime(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        runtimes.append(self)

    monkeypatch.setattr(PluginRuntime, "__init__", track_runtime)
    original_path = sys.path[:]
    original_modules = sys.modules.copy()
    yield
    for plugin_runtime in runtimes:
        plugin_runtime.unload_all()
    sys.path[:] = original_path
    for name in list(sys.modules):
        if name.startswith(("mcp_plugin_", "mcp_sub_")) or name == "plugin":
            if name in original_modules:
                sys.modules[name] = original_modules[name]
            else:
                sys.modules.pop(name, None)


def package(root, plugin_id, source, *, mode="python-inprocess", **manifest):
    directory = root / plugin_id
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps({"id": plugin_id, "entry": "plugin:register", "runtime": mode, **manifest}),
        encoding="utf-8",
    )
    (directory / "plugin.py").write_text(source, encoding="utf-8")
    return directory


def load(server, root, *, allow=None, capabilities=None, **options):
    host = McpHost(server.add_tool, allow_get=allow, capabilities=capabilities)
    return PluginLoader(
        host, plugins_dir=root, runtime=server._plugin_runtime, **options
    ).load_all()


def tool(name):
    return McpTool(name, "test", PropertyList(), lambda _: "original")


def test_duplicate_host_registration_does_not_claim_existing_tool():
    server = McpServer()
    original = tool("builtin.keep")
    server.add_tool(original)
    host = McpHost(server.add_tool)
    with pytest.raises(ValueError, match="conflict"):
        host.add_tool(tool("builtin.keep"))
    assert host.registered_tool_names == []
    assert server.tools == [original]
    assert server._plugin_tool_owner == {}


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
def test_conflicting_batch_leaves_original_tools_and_owners_unchanged(tmp_path, mode):
    server = McpServer()
    builtin = tool("builtin.keep")
    other = tool("external.keep")
    server.add_tool(builtin)
    server._plugin_runtime.install("original.plugin", [other])
    package(
        tmp_path, "bad.plugin",
        "def register(host):\n"
        "    host.tool('new.partial', 'partial')(lambda _: 'new')\n"
        "    host.tool('builtin.keep', 'conflict')(lambda _: 'bad')\n",
        mode=mode,
    )
    result = load(server, tmp_path)
    assert result[0].error
    assert server.tools == [builtin, other]
    assert server._plugin_tool_owner == {"external.keep": "original.plugin"}
    assert server.unload_plugin("bad.plugin") == 0
    assert server.tools == [builtin, other]
    assert not any(
        installation.session is not None
        for installation in server._plugin_runtime._installations.values()
    )


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
@pytest.mark.parametrize("failure", ["raise", "prefix", "duplicate"])
def test_registration_failures_never_publish_partial_tools(tmp_path, mode, failure):
    server = McpServer()
    suffix = {
        "raise": "    raise RuntimeError('register failed')\n",
        "prefix": "    host.tool('wrong.name', 'bad')(lambda _: 'bad')\n",
        "duplicate": "    host.tool('good.first', 'duplicate')(lambda _: 'bad')\n",
    }[failure]
    package(
        tmp_path, "bad.plugin",
        "def register(host):\n"
        "    host.tool('good.first', 'first')(lambda _: 'first')\n" + suffix,
        mode=mode, tool_name_prefix="good.",
    )
    result = load(server, tmp_path, enforce_prefix=True)
    assert result[0].error
    assert server.tools == []
    assert server._plugin_tool_owner == {}
    assert not any(
        installation.session is not None
        for installation in server._plugin_runtime._installations.values()
    )


def test_single_file_register_failure_is_not_published(tmp_path):
    (tmp_path / "solo.py").write_text(
        "def register(host):\n"
        "    host.tool('solo.partial', 'partial')(lambda _: 'new')\n"
        "    raise RuntimeError('broken')\n", encoding="utf-8",
    )
    server = McpServer()
    result = load(server, tmp_path)
    assert result[0].error
    assert server.tools == []
    assert server._plugin_tool_owner == {}


@pytest.mark.parametrize("manifest", [None, [], 42, "invalid"])
def test_non_object_manifest_does_not_stop_scanning(tmp_path, manifest):
    bad = tmp_path / "a.bad"
    bad.mkdir()
    (bad / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    package(tmp_path, "z.good", "def register(host):\n    host.tool('good.ping', 'ping')(lambda _: 'ok')\n")
    server = McpServer()
    result = load(server, tmp_path)
    assert result[0].error and "manifest" in result[0].error
    assert result[1].error is None
    assert [t.name for t in server.tools] == ["good.ping"]


class _Config:
    def __init__(self):
        self.data = {
            "CONFIG_VERSION": 1,
            "SYSTEM_OPTIONS": {
                "NETWORK": {
                    "OTA_VERSION_URL": "https://user:secret@example.test/ota?token=secret#secret",
                    "ACTIVATION_VERSION": "v2",
                    "WEBSOCKET_ACCESS_TOKEN": "secret",
                    "MQTT_INFO": {"password": "secret"},
                },
            },
            "CAMERA": {"VLapi_key": "secret"},
        }

    def get_config(self, path, default=None):
        value = self.data
        for key in path.split("."):
            if not isinstance(value, dict) or key not in value:
                return default
            value = value[key]
        return value


def test_config_capability_is_independent_readonly_and_redacted():
    config = _Config()
    host = McpHost(lambda _: None, capabilities={"config_readonly": config})
    readonly = host.get("config_readonly")
    assert not hasattr(readonly, "update_config")
    assert not hasattr(readonly, "save_config")
    assert readonly.get_config("SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL") == "https://example.test/ota"
    assert readonly.get_config("CAMERA") is None
    assert readonly.get_config("SYSTEM_OPTIONS.NETWORK.MQTT_INFO") is None
    with pytest.raises(TypeError):
        readonly["SYSTEM_OPTIONS"]["NETWORK"]["ACTIVATION_VERSION"] = "changed"
    config.data["SYSTEM_OPTIONS"]["NETWORK"]["ACTIVATION_VERSION"] = "v3"
    assert readonly.get_config("SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION") == "v2"
    assert "secret" not in str(dict(readonly))


def test_subprocess_serialization_filters_before_copying_capabilities(tmp_path):
    config = _Config()
    session = runtime.PluginSubprocessSession(
        plugin_id="test", plugin_root=tmp_path, entry="plugin:register", platform_tag="",
        allow_get=[], capabilities={},
    )
    caps = {"config_readonly": config, "denied": {"token": "secret"}}
    assert session._json_safe_caps(caps) == {}
    session.allow_get = ["config_readonly", "safe"]
    caps["safe"] = {"nested": [1]}
    exported = session._json_safe_caps(caps)
    assert "secret" not in json.dumps(exported)
    exported["safe"]["nested"].append(2)
    assert caps["safe"] == {"nested": [1]}


@pytest.mark.parametrize("allow", [[], ["config_readonly"]])
def test_worker_output_is_isolated_and_empty_allow_list_is_respected(tmp_path, allow):
    source = """import os
import sys
print('import debug')
os.write(1, b'native debug\\n')

def register(host):
    print('register debug')
    cfg = host.get('config_readonly')
    def inspect(args):
        print('call debug')
        sys.__stdout__.write('original stdout debug\\n')
        os.write(1, b'fd debug\\n')
        if cfg is None:
            return 'denied'
        return cfg.get_config('SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION')
    host.tool('test.inspect', 'inspect')(inspect)
"""
    package(tmp_path, "noisy.plugin", source, mode="python-subprocess")
    server = McpServer()
    result = load(server, tmp_path, allow=allow, capabilities={"config_readonly": _Config()})
    assert result[0].error is None
    for _ in range(2):
        response = json.loads(asyncio.run(server.tools[0].call({})))
        assert response["isError"] is False
        assert response["content"][0]["text"] == ("v2" if allow else "denied")
    server.detach()
    assert not any(
        installation.session is not None
        for installation in server._plugin_runtime._installations.values()
    )


def test_reload_detach_and_unload_reap_zero_tool_workers_per_server(tmp_path, monkeypatch):
    package(tmp_path, "same.plugin", "def register(host):\n    pass\n", mode="python-subprocess")
    servers = [McpServer(), McpServer()]
    for server in servers:
        assert load(server, tmp_path)[0].error is None
    sessions = [server._plugin_runtime._installations["same.plugin"].session for server in servers]
    processes = [session._proc for session in sessions]
    assert all(process.poll() is None for process in processes)
    monkeypatch.setattr("src.mcp.plugins.loader.load_mcp_plugins_from_config", lambda *a, **kw: [])
    servers[0].reload_external_plugins()
    assert processes[0].poll() is not None
    assert processes[1].poll() is None
    assert servers[0]._plugin_tool_owner == {}
    servers[1].unload_plugin("same.plugin")
    assert processes[1].poll() is not None
    assert all(not server._plugin_runtime._installations for server in servers)
    # detach must also reap a worker with no tool ownership records and be idempotent.
    assert load(servers[0], tmp_path)[0].error is None
    process = servers[0]._plugin_runtime._installations["same.plugin"].session._proc
    servers[0].detach()
    servers[0].detach()
    assert process.poll() is not None
    assert all(not server._plugin_runtime._installations for server in servers)


def test_loader_can_be_reused_after_unload(tmp_path):
    package(tmp_path, "reload.demo", "def register(host):\n    host.tool('reload.ping', 'ping')(lambda _: 'ok')\n")
    server = McpServer()
    loader = PluginLoader(
        McpHost(server.add_tool), plugins_dir=tmp_path,
        runtime=server._plugin_runtime,
    )
    assert loader.load_all()[0].error is None
    assert server.unload_plugin("reload.demo") == 1
    assert loader.load_all()[0].error is None
    assert [t.name for t in server.tools] == ["reload.ping"]


def test_common_tools_reassembly_replaces_callbacks_and_reloads_plugins(tmp_path, monkeypatch):
    import src.mcp.tools.volume as volume_tools

    generation = [0]

    def register(add_tool, controller):
        current = generation[0]
        add_tool(McpTool("common.test", "test", PropertyList(), lambda _: current))

    monkeypatch.setattr(volume_tools, "register_volume_tools", register)
    package(tmp_path, "external.demo", "def register(host):\n    host.tool('external.ping', 'ping')(lambda _: 'ok')\n")

    def load_config(add_tool, **kwargs):
        return PluginLoader(
            McpHost(add_tool, capabilities=kwargs.get("capabilities")),
            runtime=kwargs["runtime"], plugins_dir=tmp_path,
        ).load_all()

    monkeypatch.setattr("src.mcp.plugins.loader.load_mcp_plugins_from_config", load_config)
    server = McpServer()
    camera = tool("take_photo")
    server.add_tool(camera)
    server.add_common_tools()
    old_callback = next(t.callback for t in server.tools if t.name == "common.test")
    generation[0] = 1
    server.add_common_tools()
    names = [t.name for t in server.tools]
    assert len(names) == len(set(names))
    assert camera in server.tools
    assert old_callback({}) == 0
    assert next(t.callback({}) for t in server.tools if t.name == "common.test") == 1
    assert server._plugin_tool_owner == {"external.ping": "external.demo"}
    server.detach()
    assert camera in server.tools
    assert "external.ping" not in [t.name for t in server.tools]


def test_common_registration_failure_preserves_existing_tools(monkeypatch):
    import src.mcp.tools.volume as volume_tools

    server = McpServer()
    original = tool("original.keep")
    server.add_tool(original)

    def broken(add_tool, controller):
        add_tool(tool("partial"))
        raise RuntimeError("registration failed")

    monkeypatch.setattr(volume_tools, "register_volume_tools", broken)
    with pytest.raises(RuntimeError, match="registration failed"):
        server.add_common_tools()
    assert server.tools == [original]


@pytest.mark.parametrize("mode", ["python-inprocess", "python-subprocess"])
def test_plugin_checker_accepts_supported_runtimes(tmp_path, mode):
    from scripts.check_mcp_plugin import check_plugin

    directory = package(tmp_path, "check.demo", "def register(host):\n    pass\n", mode=mode)
    assert check_plugin(directory) == []
    (directory / "manifest.json").write_text("[]", encoding="utf-8")
    assert check_plugin(directory) == ["manifest.json 须为对象"]


def test_worker_unicode_protocol_ignores_inherited_stdio_encoding(tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252")
    package(
        tmp_path, "unicode.demo",
        "def register(host):\n"
        "    host.tool('unicode.echo', '中文描述', [{'name': 'text', 'type': 'string'}])(lambda args: args['text'])\n",
        mode="python-subprocess",
    )
    server = McpServer()
    assert load(server, tmp_path)[0].error is None
    response = json.loads(asyncio.run(server.tools[0].call({"text": "你好，世界！"})))
    assert response["isError"] is False
    assert response["content"][0]["text"] == "你好，世界！"
    server.detach()
