"""Runtime MCP tool names are injected per GUI and refreshed on every read."""

import json
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from src.core.event_bus import EventBus
from src.mcp.mcp_server import McpServer
from src.mcp.tooling import McpTool, PropertyList
from src.ui.shared.factory import create_viewport
from src.utils.config_manager import ConfigManager


@pytest.fixture
def settings_model():
    pytest.importorskip("PySide6.QtCore")
    from src.ui.gui.models.settings_model import SettingsModel

    return SettingsModel


def tool(name):
    return McpTool(name, name, PropertyList(), lambda arguments: name)


def catalog(model):
    return {row["name"]: row for row in json.loads(model.mcpToolsCatalogJson)}


def config_for(tmp_path, disabled=()):
    return ConfigManager.from_dict(
        {
            "WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False},
            "MCP_PLUGINS": {"ENABLED": False, "DIR": str(tmp_path / "plugins")},
            "MCP_TOOLS": {"DISABLED": list(disabled)},
        }
    )


def test_runtime_catalog_isolated_dynamic_and_includes_disabled(
    settings_model, tmp_path
):
    first_server = McpServer(config_for(tmp_path / "first"))
    second_server = McpServer(config_for(tmp_path / "second"))
    first_server.add_tool(tool("first.runtime"))
    second_server.add_tool(tool("second.runtime"))
    first = settings_model(
        config_manager=config_for(tmp_path / "first", ["first.runtime"]),
        runtime_tool_names=lambda: tuple(item.name for item in first_server.tools),
    )
    second = settings_model(
        config_manager=config_for(tmp_path / "second"),
        runtime_tool_names=lambda: tuple(item.name for item in second_server.tools),
    )

    assert catalog(first)["first.runtime"]["enabled"] is False
    assert "second.runtime" not in catalog(first)
    assert "first.runtime" not in catalog(second)
    assert catalog(second)["second.runtime"]["enabled"] is True

    first_server.add_tool(tool("first.added"))
    assert "first.added" in catalog(first)
    assert "first.added" not in catalog(second)
    first_server.remove_tools_by_names(["first.added", "first.runtime"])
    rows = catalog(first)
    assert "first.added" not in rows
    assert rows["first.runtime"]["source"] == "external"
    assert rows["first.runtime"]["enabled"] is False
    assert "second.runtime" in catalog(second)


def test_no_runtime_provider_keeps_builtin_disk_and_disabled_rows(
    settings_model, tmp_path
):
    from src.mcp.tool_catalog import builtin_catalog_rows

    plugin_dir = tmp_path / "plugins" / "disk_plugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.json").write_text(
        json.dumps({"id": "disk_plugin", "tools": ["disk.available"]}),
        encoding="utf-8",
    )
    unrelated_server = McpServer(config_for(tmp_path / "unrelated"))
    unrelated_server.add_tool(tool("unrelated.runtime"))
    model = settings_model(config_manager=config_for(tmp_path, ["removed.disabled"]))
    rows = catalog(model)
    assert model._runtime_tool_names() == ()
    assert "unrelated.runtime" not in rows
    builtin_rows = builtin_catalog_rows()
    assert builtin_rows
    assert {row["name"] for row in builtin_rows} <= rows.keys()
    assert rows["disk.available"]["source"] == "plugin"
    assert rows["removed.disabled"]["source"] == "external"
    assert rows["removed.disabled"]["enabled"] is False


@pytest.mark.parametrize("mode", ["cli", "gpio", "gpio-fallback"])
def test_factory_forwards_provider_only_to_settings_capable_views(monkeypatch, mode):
    from src.ui.shared import factory

    bus, tasks, config = EventBus(), object(), object()
    calls = []

    def terminal(*, event_bus, task_manager):
        calls.append((event_bus, task_manager))
        return "terminal"

    def tui(*, event_bus, task_manager, config_manager, runtime_tool_names):
        calls.append((event_bus, task_manager, config_manager, runtime_tool_names()))
        return "tui"

    for package, name, constructor in (
        ("cli", "CliViewManager", terminal),
        ("gpio", "GpioViewManager", terminal),
        ("tui", "TuiViewManager", tui),
    ):
        module = ModuleType(f"src.ui.{package}")
        setattr(module, name, constructor)
        monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(
        factory.sys, "platform", "darwin" if mode == "gpio-fallback" else "linux"
    )
    viewport = create_viewport(
        "gpio" if mode == "gpio-fallback" else mode,
        bus,
        tasks,
        config,
        lambda: ("runtime.tool",),
    )
    assert viewport == ("tui" if mode == "tui" else "terminal")
    expected = (
        (bus, tasks, config, ("runtime.tool",)) if mode == "tui" else (bus, tasks)
    )
    assert calls == [expected]


def test_ui_factory_imports_without_qt():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import builtins\n"
            "original = builtins.__import__\n"
            "def checked(name, *args, **kwargs):\n"
            "    if name.startswith('PySide6'):\n"
            "        raise AssertionError('Qt imported before GUI selection')\n"
            "    return original(name, *args, **kwargs)\n"
            "builtins.__import__ = checked\n"
            "from src.plugins.ui import UIPlugin\n"
            "from src.ui.shared.factory import create_viewport\n",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.asyncio
async def test_real_assembly_binds_source_and_releases_provider(
    settings_model, monkeypatch, tmp_path
):
    from src.bootstrap.container import ServiceContainer
    from src.bootstrap.plugin_wiring import setup_plugins
    from src.mcp.tools.volume.volume_controller import VolumeController
    from src.utils.resource_finder import clear_path_caches

    monkeypatch.setenv("XIAOZHI_DISABLE_AUDIO", "1")
    for name in ("DATA", "CACHE", "LOG", "MUSIC_CACHE", "KEYWORDS"):
        monkeypatch.setenv(f"XIAOZHI_{name}_DIR", str(tmp_path / name.lower()))
    clear_path_caches()
    monkeypatch.setattr("src.plugins.shortcuts.create_backend", lambda loop: None)
    monkeypatch.setattr(VolumeController, "check_dependencies", lambda: True)
    monkeypatch.setattr(
        VolumeController,
        "_create_backend",
        lambda self: SimpleNamespace(
            get_volume=lambda: 50, set_volume=lambda value: None
        ),
    )
    first = ServiceContainer(config_for(tmp_path / "first", ["first.runtime"]))
    second = ServiceContainer(config_for(tmp_path / "second"))
    try:
        for owner in (first, second):
            await setup_plugins(
                owner,
                "gui",
                owner.create_plugin_context(),
                owner.create_plugin_commands(),
            )
            assert owner.plugins.failed_plugins() == []
        first_plugin = first.plugins.get_plugin("ui")
        second_plugin = second.plugins.get_plugin("ui")
        first_model = first_plugin.viewport.settings_model
        second_model = second_plugin.viewport.settings_model
        first_server, second_server = first.mcp_server, second.mcp_server
        provider = first_plugin._runtime_tool_names
        snapshot = provider()
        assert isinstance(snapshot, tuple)
        first_server.add_tool(tool("first.runtime"))
        second_server.add_tool(tool("second.runtime"))
        assert "first.runtime" not in snapshot
        assert "first.runtime" in provider()
        assert "first.runtime" not in second_plugin._runtime_tool_names()
        assert catalog(first_model)["first.runtime"]["enabled"] is False
        assert "second.runtime" not in catalog(first_model)
        assert "second.runtime" in catalog(second_model)

        first.mcp_server = second_server
        try:
            assert "first.runtime" in provider()
            assert "second.runtime" not in provider()
        finally:
            first.mcp_server = first_server
        first_server.remove_tools_by_names(["first.runtime"])
        assert "first.runtime" not in provider()
        await first.shutdown()
        assert first_plugin._runtime_tool_names is None
        assert first_plugin.viewport._settings._runtime_tool_names is None
        assert first_model._runtime_tool_names() == ()
        assert "second.runtime" in catalog(second_model)
    finally:
        await first.shutdown()
        await second.shutdown()
        clear_path_caches()
