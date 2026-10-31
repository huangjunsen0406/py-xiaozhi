"""Public music operations: resolve inputs, then delegate session ownership."""

from __future__ import annotations

import asyncio
from pathlib import Path

from src.logging import get_logger

from .bus import MusicEventBridge
from .cache import MusicCache
from .config import load_music_config
from .download import MusicDownloader
from .events import MusicEventPublisher
from .lifecycle import await_cleanup
from .local_library import LocalLibrary
from .lyrics import fetch_kuwo_lyrics
from .online_search import search_song
from .playback import PlaybackDeps, PlaybackEngine
from .state import PlaybackRequest, PlaybackState

logger = get_logger()


class MusicPlayer:
    def __init__(self, config=None):
        from src.utils.config_manager import ConfigManager

        self._config_source = (
            config if config is not None else ConfigManager.from_dict()
        )
        self._config: dict | None = None
        self._cache = MusicCache()
        self._downloader = MusicDownloader(self._cache)
        self._library = LocalLibrary(self._cache)
        self._events = MusicEventPublisher()
        self._engine = PlaybackEngine(
            PlaybackDeps(
                cache=self._cache,
                downloader=self._downloader,
                library=self._library,
                events=self._events,
            )
        )
        self._bus = MusicEventBridge(self)
        # Input lookups can finish out of order, or after stop/detach.
        self._request_generation = 0

    def prepare_for_io(self) -> None:
        self.reload_config()
        self._cache.prepare()

    def is_speaking(self) -> bool:
        return self._engine.is_speaking()

    def format_time(self, seconds: float) -> str:
        return self._format_time(seconds)

    async def tick_lyrics(self) -> None:
        await self._engine.tick_lyrics()

    async def emit_state_change(
        self,
        state: str,
        song_name: str | None = None,
        position: float | None = None,
    ) -> None:
        await self._engine.emit_state_change(state, song_name, position)

    @property
    def playback_state(self) -> PlaybackState:
        return self._engine.state

    @property
    def cache_dir(self) -> Path:
        return self._cache.root

    @property
    def temp_cache_dir(self) -> Path:
        return self._cache.temp_dir

    @property
    def is_playing(self) -> bool:
        return self.playback_state.is_playing

    @property
    def paused(self) -> bool:
        return self.playback_state.paused

    @property
    def current_song(self) -> str:
        return self.playback_state.song

    @property
    def current_url(self) -> str:
        return self.playback_state.source

    @property
    def lyrics(self) -> list[tuple[float, str]]:
        return list(self.playback_state.lyrics)

    @property
    def config(self) -> dict:
        if self._config is None:
            self.reload_config()
        return self._config

    def reload_config(self) -> dict:
        self._config = load_music_config(self._config_source)
        self._downloader.set_config(self._config)
        return self._config

    def set_event_bus(self, event_bus, plugin_ctx=None) -> None:
        self._bus.set_event_bus(event_bus)
        self._events.event_bus = event_bus
        self._engine.set_speaking_provider(
            plugin_ctx.is_speaking if plugin_ctx is not None else None
        )

    async def bind_audio_codec(self, codec=None) -> None:
        self._request_generation += 1
        await self._engine.bind_audio_codec(codec)

    async def detach(self) -> None:
        self._request_generation += 1

        async def close():
            try:
                await self._engine.bind_audio_codec(None)
            finally:
                self._engine.set_speaking_provider(None)
                self._bus.detach()
                self._events.event_bus = None

        await await_cleanup(asyncio.create_task(close()))

    async def stop(self) -> dict:
        self._request_generation += 1
        return await self._engine.stop()

    async def pause(self, source: str = "manual") -> dict:
        return await self._engine.pause(source=source)

    async def resume(self) -> dict:
        self.reload_config()
        return await self._engine.resume()

    async def seek(
        self,
        position: float | None = None,
        percent: float | None = None,
    ) -> dict:
        return await self._engine.seek(position=position, percent=percent)

    async def get_position(self):
        return await self._engine.get_position()

    async def get_progress(self):
        return await self._engine.get_progress()

    async def get_local_playlist(self, force_refresh: bool = False) -> dict:
        self.prepare_for_io()
        return self._library.get_playlist(force_refresh)

    async def search_local_music(self, query: str) -> dict:
        self.prepare_for_io()
        return self._library.search(query)

    def _play_result(self) -> dict:
        state = self.playback_state
        return {
            "status": "success",
            "message": f"正在播放: {state.song}",
            "song": state.song,
            "duration": self._format_time(state.duration),
            "total_seconds": state.duration,
        }

    async def play_local_song_by_id(self, file_id: str) -> dict:
        self._request_generation += 1
        try:
            self.prepare_for_io()
            resolved = self._library.resolve(file_id)
            if resolved is None:
                return {"status": "error", "message": f"本地文件不存在: {file_id}"}
            path, metadata = resolved
            success = await self._engine.play(
                PlaybackRequest(
                    song=metadata.display_name(),
                    song_id=file_id,
                    source=path,
                    duration=metadata.duration or 0,
                )
            )
            if success:
                return self._play_result()
            return {"status": "error", "message": "播放失败"}
        except Exception as error:
            logger.error("播放本地音乐失败: %s", error, exc_info=True)
            return {"status": "error", "message": f"播放失败: {error}"}

    async def search_and_play(self, song_name: str) -> dict:
        self._request_generation += 1
        generation = self._request_generation
        try:
            self.prepare_for_io()
            hit = await search_song(song_name, self.config)
            if generation != self._request_generation:
                return {"status": "info", "message": "播放请求已取消"}
            if hit is None:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}
            lyrics = await fetch_kuwo_lyrics(
                hit.song_id,
                lyrics_url=self.config["LYRICS_URL"],
                headers=self.config["HEADERS"],
            )
            if generation != self._request_generation:
                return {"status": "info", "message": "播放请求已取消"}
            success = await self._engine.play(
                PlaybackRequest(
                    song=hit.display_name,
                    song_id=hit.song_id,
                    source=hit.api_url,
                    duration=hit.duration,
                    lyrics=tuple(lyrics),
                    resolve_url=True,
                )
            )
            if success:
                return self._play_result()
            detail = (
                self._downloader.last_error or self.playback_state.error or "未知原因"
            )
            return {"status": "error", "message": f"播放失败: {detail}"}
        except Exception as error:
            logger.error("搜索播放失败: %s", error, exc_info=True)
            return {"status": "error", "message": f"操作失败: {error}"}

    async def get_lyrics(self) -> dict:
        lyrics = self.playback_state.lyrics
        if not lyrics:
            return {"status": "info", "message": "当前歌曲没有歌词", "lyrics": []}
        return {
            "status": "success",
            "message": f"获取到 {len(lyrics)} 行歌词",
            "lyrics": [f"[{self._format_time(t)}] {text}" for t, text in lyrics],
        }

    async def get_status(self) -> dict:
        state = self.playback_state
        position = await self.get_position()
        progress = await self.get_progress()
        if state.error:
            return {"status": "error", "message": f"播放失败: {state.error}"}
        if not state.is_playing:
            playing_state = "未播放"
        elif state.paused and state.pause_source == "manual":
            playing_state = "已暂停"
        else:
            playing_state = "播放中"
        return {
            "status": "success",
            "message": (
                f"当前歌曲: {state.song}\n"
                f"播放状态: {playing_state}\n"
                f"暂停来源: {state.pause_source or '无'} (tts=说话时临时暂停)\n"
                f"总时长秒: {int(state.duration)}\n"
                f"当前位置秒: {int(position)}\n"
                f"播放时长: {self._format_time(state.duration)}\n"
                f"当前位置: {self._format_time(position)}\n"
                f"播放进度: {progress}%\n"
                f"歌词可用: {'是' if state.lyrics else '否'}\n"
                "提示: 跳转百分之N请调用 seek(percent=N)，不要用歌词推算"
            ),
        }

    @staticmethod
    def _format_time(seconds: float) -> str:
        return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"

    def __del__(self):
        try:
            cache = getattr(self, "_cache", None)
            if cache is not None and getattr(cache, "_ready", False):
                cache.clean_temp()
        except Exception as error:
            logger.debug("__del__ 清理临时缓存失败: %s", error)
