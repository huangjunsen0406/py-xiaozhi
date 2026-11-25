"""Tests for decoupled MediaPlayer, autonomous Audio Focus, MediaPlayerFacade, and conditional media.* MCP tools."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.mcp.mcp_server import McpServer
from src.mcp.plugins.media_facade import MediaPlayerFacade, PluginLifecycle
from src.media import MediaPlayer, sanitize_headers, validate_media_source
from src.utils.config_manager import ConfigManager


class _DummyTrack:
    def __init__(self):
        self.cleared = 0
        self.chunks = []

    async def write_pcm(self, pcm):
        self.chunks.append(pcm)

    async def clear(self):
        self.cleared += 1
        return 0


class _DummyCodec:
    def __init__(self, *, aec_active: bool = False):
        self.audio_config = AudioConfig()
        self.aec_active = aec_active
        self.track = _DummyTrack()

    def get_background_track(self):
        return self.track


def test_validate_media_source_and_headers(tmp_path):
    url, is_http = validate_media_source("https://cdn.example.com/audio.mp3")
    assert url == "https://cdn.example.com/audio.mp3" and is_http is True

    local = tmp_path / "song.mp3"
    local.write_bytes(b"fake")
    resolved, is_http = validate_media_source(str(local))
    assert resolved == str(local.resolve()) and is_http is False

    for bad in ("", "pipe:0", "concat:a|b", "file:///etc/passwd", "relative.mp3", "https://a\r\nb"):
        with pytest.raises(ValueError):
            validate_media_source(bad)

    cleaned = sanitize_headers(
        {"Referer": "https://a.com", "X-Custom-Unsafe": "1", "User-Agent": "UA"}
    )
    assert cleaned == {"Referer": "https://a.com", "User-Agent": "UA"}

    with pytest.raises(ValueError):
        sanitize_headers({"Referer": "bad\r\nX-Injected: 1"})


@pytest.mark.asyncio
async def test_autonomous_audio_focus_pauses_without_aec_and_keeps_playing_with_aec(
    monkeypatch,
):
    from src.media import media_player as mp_mod

    class _FakeDecoder:
        get_duration = AsyncMock(return_value=120.0)

        def __init__(self, **_kwargs):
            self.error = None
            self.completed_successfully = False
            self.stop = AsyncMock()

        def is_running(self):
            return True

        async def start_decode(self, _src, _q, *_a, **_kw):
            return True

    monkeypatch.setattr(mp_mod, "AudioDecoder", _FakeDecoder)

    # 1) AEC inactive -> TTS start pauses with source="tts", TTS stop resumes
    bus = EventBus()
    player = MediaPlayer(ConfigManager.from_dict({"AEC_OPTIONS": {"MEDIA_PARALLEL": True}}))
    player.attach(bus)
    await player.bind_audio_codec(_DummyCodec(aec_active=False))
    res = await player.play_url("https://example.test/a.mp3", title="Podcast", owner_id="p1")
    assert res["status"] == "success"
    assert player.is_playing and not player.paused

    await bus.emit(Events.SESSION_MESSAGE, {"type": "tts", "state": "start"})
    assert player.is_playing and player.paused and player.pause_source == "tts"

    await bus.emit(Events.SESSION_MESSAGE, {"type": "tts", "state": "stop"})
    assert player.is_playing and not player.paused

    await player.detach()

    # 2) AEC active + MEDIA_PARALLEL=True -> TTS start keeps playing (AudioMixer ducks)
    bus2 = EventBus()
    player2 = MediaPlayer(ConfigManager.from_dict({"AEC_OPTIONS": {"MEDIA_PARALLEL": True}}))
    player2.attach(bus2)
    await player2.bind_audio_codec(_DummyCodec(aec_active=True))
    res2 = await player2.play_url("https://example.test/b.mp3", title="Song", owner_id="p1")
    assert res2["status"] == "success"

    await bus2.emit(Events.SESSION_MESSAGE, {"type": "tts", "state": "start"})
    assert player2.is_playing and not player2.paused
    await player2.detach()


@pytest.mark.asyncio
async def test_media_player_facade_lifecycle_revocation_and_owner_stop(monkeypatch):
    from src.media import media_player as mp_mod

    class _FakeDecoder:
        get_duration = AsyncMock(return_value=60.0)

        def __init__(self, **_kwargs):
            self.error = None
            self.completed_successfully = False
            self.stop = AsyncMock()

        def is_running(self):
            return True

        async def start_decode(self, _src, _q, *_a, **_kw):
            return True

    monkeypatch.setattr(mp_mod, "AudioDecoder", _FakeDecoder)

    player = MediaPlayer(ConfigManager.from_dict())
    await player.bind_audio_codec(_DummyCodec())

    lc_a = PluginLifecycle("plugin_a")
    lc_b = PluginLifecycle("plugin_b")
    facade_a = MediaPlayerFacade(player, plugin_id="plugin_a", lifecycle=lc_a)
    facade_b = MediaPlayerFacade(player, plugin_id="plugin_b", lifecycle=lc_b)

    res = await facade_a.play_url("https://example.test/track.mp3", title="Track A")
    assert res["status"] == "success"
    assert player.owner_id == "plugin_a"

    # Unloading plugin_b does NOT stop plugin_a's playback
    lc_b.revoke()
    await asyncio.sleep(0)
    assert player.is_playing and player.owner_id == "plugin_a"
    with pytest.raises(RuntimeError, match="已卸载"):
        await facade_b.get_status()

    # Unloading plugin_a automatically stops playback owned by plugin_a and revokes handle
    lc_a.revoke()
    await asyncio.sleep(0.02)
    assert not player.is_playing
    with pytest.raises(RuntimeError, match="已卸载"):
        await facade_a.pause()

    await player.detach()


def test_conditional_media_transport_tools_only_registered_when_authorized_and_plugin_loaded(
    tmp_path,
):
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    pdir = plugins_dir / "radio"
    pdir.mkdir()
    (pdir / "plugin.py").write_text(
        "def register(host):\n"
        "    @host.tool('radio.ping', 'ping', [])\n"
        "    def ping(_args):\n"
        "        return 'pong'\n",
        encoding="utf-8",
    )

    player = MediaPlayer(ConfigManager.from_dict())

    # Case 1: media_player NOT authorized -> 0 media.* tools
    cfg1 = ConfigManager.from_dict(
        {
            "MCP_PLUGINS": {
                "ENABLED": True,
                "DIR": str(plugins_dir),
                "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir"],
            }
        }
    )
    server1 = McpServer(config=cfg1)
    server1.reload_external_plugins(media_player=player)
    names1 = {t.name for t in server1.tools}
    assert "radio.ping" in names1
    assert "media.pause" not in names1

    # Case 2: authorized BUT no plugins in directory -> 0 media.* tools
    empty_dir = tmp_path / "empty_plugins"
    empty_dir.mkdir()
    cfg2 = ConfigManager.from_dict(
        {
            "MCP_PLUGINS": {
                "ENABLED": True,
                "DIR": str(empty_dir),
                "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir", "media_player"],
            }
        }
    )
    server2 = McpServer(config=cfg2)
    server2.reload_external_plugins(media_player=player)
    assert "media.pause" not in {t.name for t in server2.tools}

    # Case 3: authorized AND external plugin loaded -> 5 media.* tools exposed
    cfg3 = ConfigManager.from_dict(
        {
            "MCP_PLUGINS": {
                "ENABLED": True,
                "DIR": str(plugins_dir),
                "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir", "media_player"],
            }
        }
    )
    server3 = McpServer(config=cfg3)
    server3.reload_external_plugins(media_player=player)
    names3 = {t.name for t in server3.tools}
    assert {"radio.ping", "media.pause", "media.resume", "media.stop", "media.seek", "media.get_status"} <= names3

    # Unloading the last external plugin removes conditional media.* tools
    server3.unload_plugin("radio")
    names3_after = {t.name for t in server3.tools}
    assert "media.pause" not in names3_after
