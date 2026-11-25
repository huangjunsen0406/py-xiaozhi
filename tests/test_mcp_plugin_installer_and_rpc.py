"""Tests for MCP plugin installer (ZIP/folder/rollback/security) and subprocess bidirectional media_player RPC."""

from __future__ import annotations

import json
import zipfile
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import AudioConfig
from src.mcp.mcp_server import McpServer
from src.mcp.plugins.installer import (
    install_plugin_from_dir,
    install_plugin_from_zip,
    list_installed_plugins,
    uninstall_plugin,
)
from src.media.media_player import MediaPlayer
from src.utils import resource_finder as rf
from src.utils.config_manager import ConfigManager


class _DummyTrack:
    async def write_pcm(self, _pcm):
        return None

    async def clear(self):
        return 0


class _DummyCodec:
    audio_config = AudioConfig()
    aec_active = False

    def get_background_track(self):
        return _DummyTrack()


def _make_plugin_zip(zip_path, *, root_prefix="my_plugin/", manifest=None, plugin_py=None):
    manifest = manifest or {
        "id": "my_plugin",
        "name": "My Plugin",
        "version": "1.0.0",
        "runtime": "python-inprocess",
        "entry": "plugin:register",
    }
    plugin_py = plugin_py or (
        "def register(host):\n"
        "    @host.tool('my_plugin.hello', 'hello', [])\n"
        "    def hello(_a):\n"
        "        return 'hi'\n"
    )
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(f"{root_prefix}manifest.json", json.dumps(manifest))
        zf.writestr(f"{root_prefix}plugin.py", plugin_py)


def test_installer_zip_dir_list_and_uninstall(tmp_path):
    plugins_dir = tmp_path / "plugins"
    zip_file = tmp_path / "pkg.zip"
    _make_plugin_zip(zip_file)

    info = install_plugin_from_zip(zip_file, plugins_dir)
    assert info["ok"] is True
    assert info["id"] == "my_plugin"
    assert info["replaced"] is False

    listed = list_installed_plugins(plugins_dir)
    assert len(listed) == 1
    assert listed[0]["id"] == "my_plugin"
    assert listed[0]["version"] == "1.0.0"

    # Re-importing same ID overwrites cleanly
    info2 = install_plugin_from_zip(zip_file, plugins_dir)
    assert info2["replaced"] is True

    # Folder import
    folder_src = tmp_path / "folder_plugin"
    folder_src.mkdir()
    (folder_src / "plugin.py").write_text("def register(host): pass\n", encoding="utf-8")
    finfo = install_plugin_from_dir(folder_src, plugins_dir)
    assert finfo["ok"] is True and finfo["id"] == "folder_plugin"

    # Uninstall
    ures = uninstall_plugin("my_plugin", plugins_dir)
    assert ures["ok"] is True
    assert [p["id"] for p in list_installed_plugins(plugins_dir)] == ["folder_plugin"]


def test_installer_rejects_zip_slip(tmp_path):
    plugins_dir = tmp_path / "plugins"
    bad_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(bad_zip, "w") as zf:
        zf.writestr("../escape.txt", "boom")

    with pytest.raises(ValueError, match="路径穿越"):
        install_plugin_from_zip(bad_zip, plugins_dir)


@pytest.mark.asyncio
async def test_subprocess_plugin_can_call_media_player_and_data_dir_via_rpc(
    tmp_path, monkeypatch
):
    from src.media import media_player as mp_mod

    class _FakeDecoder:
        get_duration = AsyncMock(return_value=42.0)

        def __init__(self, **_kwargs):
            self.error = None
            self.completed_successfully = False
            self.stop = AsyncMock()

        def is_running(self):
            return True

        async def start_decode(self, _src, _q, *_a, **_kw):
            return True

    monkeypatch.setattr(mp_mod, "AudioDecoder", _FakeDecoder)
    monkeypatch.setenv(rf.ENV_DATA_DIR, str(tmp_path / "user_data"))
    rf.clear_path_caches()

    plugins_dir = tmp_path / "plugins"
    pdir = plugins_dir / "sub_radio"
    pdir.mkdir(parents=True)
    (pdir / "manifest.json").write_text(
        json.dumps(
            {
                "id": "sub_radio",
                "name": "Subprocess Radio",
                "runtime": "python-subprocess",
                "entry": "plugin:register",
            }
        ),
        encoding="utf-8",
    )
    (pdir / "plugin.py").write_text(
        "import json\n"
        "def register(host):\n"
        "    player = host.get('media_player')\n"
        "    data_dir = host.get('data_dir')\n"
        "    @host.tool('sub_radio.play', 'play via host media_player', [])\n"
        "    async def play(_args):\n"
        "        (data_dir / 'marker.txt').write_text('ok', encoding='utf-8')\n"
        "        res = await player.play_url('https://example.test/radio.mp3', title='FM 88.8')\n"
        "        st = await player.get_status()\n"
        "        return json.dumps({'play': res, 'status': st}, ensure_ascii=False)\n",
        encoding="utf-8",
    )

    cfg = ConfigManager.from_dict(
        {
            "MCP_PLUGINS": {
                "ENABLED": True,
                "DIR": str(plugins_dir),
                "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir", "media_player"],
            }
        }
    )
    player = MediaPlayer(cfg)
    await player.bind_audio_codec(_DummyCodec())
    server = McpServer(config=cfg)
    try:
        loaded = server.reload_external_plugins(media_player=player)
        assert len(loaded) == 1 and not loaded[0].error
        tool = next(t for t in server.tools if t.name == "sub_radio.play")
        raw = await tool.callback({})
        payload = json.loads(raw)
        assert payload["play"]["status"] == "success"
        assert payload["status"]["state"] == "playing"
        assert payload["status"]["title"] == "FM 88.8"
        assert payload["status"]["owner_id"] == "sub_radio"
        assert (rf.get_mcp_plugin_data_dir("sub_radio") / "marker.txt").read_text() == "ok"

        # Unloading subprocess plugin automatically stops its playback
        server.unload_plugin("sub_radio")
        import asyncio

        await asyncio.sleep(0.05)
        assert not player.is_playing
    finally:
        server.detach()
        await player.detach()
        rf.clear_path_caches()
