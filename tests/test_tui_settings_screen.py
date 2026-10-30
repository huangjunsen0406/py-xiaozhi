"""Exercise real Textual settings controls and commit/cancel boundaries."""

from unittest.mock import Mock

import pytest

pytest.importorskip("textual")
from textual.app import App
from textual.widgets import (
    Button,
    Input,
    Select,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
)

from src.ui.tui.settings_screen import DISPLAY_SECTIONS, SettingsScreen, field_id
from src.utils.config_manager import ConfigManager


class Services:
    def __init__(self):
        self.devices = {"input": [], "output": []}
        self.calls = []
        self.rows = [
            {"name": "demo.a", "label": "A", "group": "a", "groupLabel": "分组A"},
            {"name": "demo.a2", "label": "A2", "group": "a", "groupLabel": "分组A"},
            {"name": "demo.b", "label": "B", "group": "b", "groupLabel": "分组B"},
        ]

    async def audio_devices(self, *, refresh=False):
        self.calls.append(refresh)
        return self.devices

    def tool_catalog(self, disabled):
        return self.rows


def category_for(path):
    return next(
        f"section-{i}"
        for i, (_, fields) in enumerate(DISPLAY_SECTIONS)
        if any(f.path == path for f in fields)
    )


def memory_config(tmp_path, extra=None):
    config = ConfigManager.from_dict(
        {
            "MCP_PLUGINS": {"DIR": str(tmp_path)},
            "WAKE_WORD_OPTIONS": {"USE_WAKE_WORD": False},
        }
    )
    for key, value in (extra or {}).items():
        config.update_config(key, value, save=False)
    return config


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [(130, 40), (100, 30), (80, 24)])
async def test_every_category_keeps_actions_inside_small_dialog(tmp_path, size):
    app, services = App(), Services()
    screen = SettingsScreen(memory_config(tmp_path), services=services)
    async with app.run_test(size=size) as pilot:
        await app.push_screen(screen)
        await pilot.pause()
        category = screen.query_one("#settings-content", TabbedContent)
        for value in [f"section-{i}" for i in range(len(DISPLAY_SECTIONS))] + [
            "section-mcp"
        ]:
            tab = category.get_tab(value)
            assert await pilot.click(f"#{tab.id}")
            await pilot.pause()
            assert screen.query_one("#settings-content", TabbedContent).active == value
            pane = screen.query_one("#" + value)
            tab_strip = screen.query_one("#settings-content", TabbedContent).query_one(
                "ContentTabs"
            )
            assert pane.region.y >= tab_strip.region.bottom
            assert pane.region.bottom <= screen.query_one("#settings-status").region.y
            region = screen.query_one("#settings-dialog").content_region
            for name in ("btn-save", "btn-cancel", "settings-status"):
                widget = screen.query_one(f"#{name}")
                assert region.contains_region(widget.region), (size, value, name)
        assert isinstance(
            screen.query_one("#" + field_id("AEC_OPTIONS.ENABLED")), Switch
        )
        assert isinstance(
            screen.query_one("#" + field_id("AUDIO_DEVICES.frame_duration")), Select
        )
        assert screen.query_one(
            "#" + field_id("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN"), Input
        ).password
        await pilot.press("escape")
        assert len(app.screen_stack) == 1


@pytest.mark.asyncio
async def test_cancel_discards_fields_and_tool_toggles(tmp_path):
    config = memory_config(tmp_path)
    before = config.get_config("")
    app, services, results = App(), Services(), []
    screen = SettingsScreen(config, services=services)
    async with app.run_test() as pilot:
        await app.push_screen(screen, results.append)
        screen.query_one(
            "#" + field_id("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL"), Input
        ).value = "edited"
        screen.query_one("#settings-content", TabbedContent).active = "section-mcp"
        await pilot.pause()
        screen.query_one("#mcp-tools", SelectionList).deselect_all()
        await pilot.pause()
        await pilot.click("#btn-cancel")
        assert results == [False]
        assert config.get_config("") == before


@pytest.mark.asyncio
async def test_failed_save_stays_open_and_retry_commits_whole_draft(
    tmp_path, monkeypatch
):
    config = memory_config(
        tmp_path,
        {
            "WAKE_WORD_OPTIONS.NUM_THREADS": 128,
            "SYSTEM_OPTIONS.CLIENT_ID": "keep-client",
        },
    )
    before, original = config.get_config(""), config.commit_draft
    app, results = App(), []
    screen = SettingsScreen(config, services=Services())
    async with app.run_test() as pilot:
        await app.push_screen(screen, results.append)
        screen.query_one(
            "#" + field_id("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL"), Input
        ).value = "edited"
        monkeypatch.setattr(config, "commit_draft", Mock(return_value="模拟写盘失败"))
        await pilot.click("#btn-save")
        assert results == []
        assert app.screen is screen
        assert "模拟写盘失败" in str(
            screen.query_one("#settings-status", Static).render()
        )
        assert config.get_config("") == before
        assert (
            screen.query_one(
                "#" + field_id("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL"), Input
            ).value
            == "edited"
        )
        monkeypatch.setattr(config, "commit_draft", original)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert results == [True]
        assert config.get_config("SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL") == "edited"
        assert config.get_config("WAKE_WORD_OPTIONS.NUM_THREADS") == 128
        assert config.get_config("SYSTEM_OPTIONS.CLIENT_ID") == "keep-client"


@pytest.mark.asyncio
async def test_tool_group_edits_survive_navigation_and_preserve_unknown_disabled(
    tmp_path,
):
    config = memory_config(tmp_path, {"MCP_TOOLS.DISABLED": ["removed.tool"]})
    app, services = App(), Services()
    screen = SettingsScreen(config, services=services)
    async with app.run_test(size=(80, 24)) as pilot:
        await app.push_screen(screen)
        screen.query_one("#settings-content", TabbedContent).active = "section-mcp"
        await pilot.pause()
        screen.query_one("#mcp-group", Select).value = "a"
        await pilot.pause()
        await pilot.click("#mcp-disable")
        screen.query_one("#mcp-group", Select).value = "b"
        await pilot.pause()
        assert screen.query_one("#mcp-tools", SelectionList).selected == ["demo.b"]
        screen.query_one("#settings-content", TabbedContent).active = "section-0"
        await pilot.pause()
        screen.query_one("#settings-content", TabbedContent).active = "section-mcp"
        await pilot.pause()
        screen.query_one("#mcp-group", Select).value = "a"
        await pilot.pause()
        assert screen.query_one("#mcp-tools", SelectionList).selected == []
        await pilot.click("#btn-save")
        assert set(config.get_config("MCP_TOOLS.DISABLED")) == {
            "removed.tool",
            "demo.a",
            "demo.a2",
        }


@pytest.mark.asyncio
async def test_device_refresh_preserves_choice_and_updates_ids(tmp_path):
    config = memory_config(
        tmp_path,
        {"AUDIO_DEVICES.input_device_name": "Mic", "AUDIO_DEVICES.input_device_id": 4},
    )
    services = Services()

    def device(index, name):
        return {
            "index": index,
            "name": name,
            "raw_name": name,
            "sample_rate": 48000,
            "channels": 1,
        }

    services.devices = {"input": [device(2, "Mic"), device(3, "USB")], "output": []}
    app = App()
    screen = SettingsScreen(config, services=services)
    async with app.run_test() as pilot:
        await app.push_screen(screen)
        screen.query_one("#settings-content", TabbedContent).active = category_for(
            "AUDIO_DEVICES.input_device_name"
        )
        await pilot.pause()
        selector = screen.query_one(
            "#" + field_id("AUDIO_DEVICES.input_device_name"), Select
        )
        assert selector.value == 2
        selector.value = 3
        services.devices = {"input": [], "output": []}
        await pilot.click("#devices-refresh")
        await pilot.pause()
        assert selector.value == -2
        await pilot.click("#btn-save")
        assert config.get_config("AUDIO_DEVICES.input_device_name") == "USB"
        assert config.get_config("AUDIO_DEVICES.input_device_id") == 3


@pytest.mark.asyncio
async def test_stale_device_worker_cannot_unlock_or_overwrite_newer_refresh(tmp_path):
    import asyncio

    entered = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]

    class SlowServices(Services):
        def __init__(self):
            super().__init__()
            self.requests = 0

        async def audio_devices(self, *, refresh=False):
            if not refresh:
                return self.devices
            index = self.requests
            self.requests += 1
            entered[index].set()
            try:
                await release[index].wait()
            except asyncio.CancelledError:
                await release[index].wait()
            row = {
                "index": index,
                "name": f"Mic{index}",
                "raw_name": f"Mic{index}",
                "sample_rate": 48000,
                "channels": 1,
            }
            return {"input": [row], "output": []}

    app = App()
    screen = SettingsScreen(memory_config(tmp_path), services=SlowServices())
    async with app.run_test() as pilot:
        await app.push_screen(screen)
        screen._start_device_load(True)
        await asyncio.wait_for(entered[0].wait(), 1)
        screen._start_device_load(True)
        await asyncio.wait_for(entered[1].wait(), 1)
        release[0].set()
        await pilot.pause()
        assert screen.query_one("#btn-save", Button).disabled
        assert screen._device_lists["input"] == []
        screen.action_save()
        assert app.screen is screen
        release[1].set()
        await pilot.pause()
        assert not screen.query_one("#btn-save", Button).disabled
        assert screen._device_lists["input"][0]["name"] == "Mic1"
