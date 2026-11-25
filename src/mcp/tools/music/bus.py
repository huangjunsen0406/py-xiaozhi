"""EventBus bidirectional adapter; all playback ownership stays behind MusicPlayer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.core.event_bus import Events
from src.logging import get_logger

from .events import MusicControlRequest, MusicLyricsData, MusicStateData

if TYPE_CHECKING:
    from .music_player import MusicPlayer

logger = get_logger()


class MusicEventBridge:
    def __init__(self, player: MusicPlayer) -> None:
        self._player = player
        self.event_bus = None

    async def on_audio_codec_changed(self, codec=None) -> None:
        # EventBus calls handlers without arguments when its payload is None.
        await self._player.bind_audio_codec(codec)

    def set_event_bus(self, event_bus) -> None:
        self.unsubscribe()
        self.event_bus = event_bus
        if event_bus:
            event_bus.on(Events.MUSIC_PAUSE_REQUEST, self._on_pause_request)
            event_bus.on(Events.MUSIC_RESUME_REQUEST, self._on_resume_request)
            event_bus.on(Events.AUDIO_CODEC_CHANGED, self.on_audio_codec_changed)

    def unsubscribe(self) -> None:
        if not self.event_bus:
            return
        try:
            self.event_bus.off(Events.MUSIC_PAUSE_REQUEST, self._on_pause_request)
            self.event_bus.off(Events.MUSIC_RESUME_REQUEST, self._on_resume_request)
            self.event_bus.off(Events.AUDIO_CODEC_CHANGED, self.on_audio_codec_changed)
        except Exception as error:
            logger.debug("MusicPlayer 取消 EventBus 订阅失败: %s", error)

    def detach(self) -> None:
        self.unsubscribe()
        self.event_bus = None

    async def emit_state(self, data: MusicStateData) -> None:
        await self._emit(Events.MUSIC_STATE_CHANGED, data)

    async def emit_lyrics(self, data: MusicLyricsData) -> None:
        await self._emit(Events.MUSIC_LYRICS_UPDATE, data)

    async def _emit(self, event: str, data: Any) -> None:
        if self.event_bus is None:
            return
        try:
            await self.event_bus.emit(event, data)
        except Exception as error:
            logger.debug("发送音乐事件失败: %s", error)

    @staticmethod
    def _request_source(data: Any, default: str | None) -> str | None:
        if isinstance(data, MusicControlRequest):
            return data.source
        if isinstance(data, dict):
            return data.get("source", default)
        return default

    async def _on_pause_request(self, data: Any) -> None:
        try:
            state = self._player.playback_state
            if state.is_playing and not state.paused:
                await self._player.pause(source=self._request_source(data, "external"))
        except Exception as error:
            logger.error("处理暂停请求失败: %s", error, exc_info=True)

    async def _on_resume_request(self, data: Any) -> None:
        try:
            source = self._request_source(data, None)
            state = self._player.playback_state
            if state.is_playing and state.paused:
                if source is None or state.pause_source == source:
                    await self._player.resume()
        except Exception as error:
            logger.error("处理恢复请求失败: %s", error, exc_info=True)
