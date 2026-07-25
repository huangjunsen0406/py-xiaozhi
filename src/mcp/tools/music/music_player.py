"""音乐播放会话（公开入口）.

组合：
- PlaybackEngine — 解码队列 / 启停暂停跳转
- MusicEventBridge — EventBus 绑定与状态/歌词发射

状态字段在 engine；本类只保留生产常用属性（is_playing / paused / current_song）。
"""

from __future__ import annotations

import time
from pathlib import Path

from src.audio_codecs.music_decoder import MusicDecoder
from src.logging import get_logger

from .bus import MusicEventBridge
from .cache import MusicCache
from .config import load_music_config
from .download import MusicDownloader
from .local_library import LocalLibrary
from .lyrics import fetch_kuwo_lyrics, format_lyric_display, lyric_at
from .online_search import search_song
from .playback import PlaybackDeps, PlaybackEngine

logger = get_logger()


class MusicPlayer:
    def __init__(self):
        self._config: dict | None = None
        self._cache = MusicCache()
        self._downloader = MusicDownloader(self._cache)
        self._library = LocalLibrary(self._cache)

        self.current_url = ""
        self.lyrics: list[tuple[float, str]] = []

        self._engine = PlaybackEngine(
            PlaybackDeps(
                cache=self._cache,
                downloader=self._downloader,
                library=self._library,
                hooks=self,
            )
        )
        self._bus = MusicEventBridge(self._engine, self)

        logger.debug("MusicPlayer 实例已创建")

    # ----- PlaybackEngine hooks -----

    def prepare_for_io(self) -> None:
        self.reload_config()
        self._cache.prepare()

    def is_speaking(self) -> bool:
        ctx = self._bus.plugin_ctx
        return bool(ctx and ctx.is_speaking())

    def format_time(self, seconds: float) -> str:
        return self._format_time(seconds)

    async def tick_lyrics(self) -> None:
        await self._tick_lyrics()

    async def emit_state_change(
        self,
        state: str,
        song_name: str | None = None,
        position: float | None = None,
    ) -> None:
        await self._bus.emit_state_change(state, song_name, position)

    # ----- 生产常用状态（扁平访问）-----

    @property
    def cache_dir(self) -> Path:
        return self._cache.root

    @property
    def temp_cache_dir(self) -> Path:
        return self._cache.temp_dir

    @property
    def is_playing(self) -> bool:
        return self._engine.is_playing

    @property
    def paused(self) -> bool:
        return self._engine.paused

    @property
    def current_song(self) -> str:
        return self._engine.current_song

    @property
    def config(self) -> dict:
        if self._config is None:
            self.reload_config()
        return self._config

    def reload_config(self) -> dict:
        self._config = load_music_config()
        self._downloader.set_config(self._config)
        logger.debug(
            "MusicPlayer 配置已加载: "
            f"搜索={self._config['SEARCH_URL']}, "
            f"直链={self._config['URL_API']}, "
            f"平台={self._config['DEFAULT_SOURCE']}"
        )
        return self._config

    # ----- 生命周期 / 播放委托 -----

    def set_event_bus(self, event_bus, plugin_ctx=None) -> None:
        self._bus.set_event_bus(event_bus, plugin_ctx)

    def detach(self) -> None:
        self._bus.detach()

    async def stop(self) -> dict:
        return await self._engine.stop()

    async def pause(self, source: str = "manual") -> dict:
        return await self._engine.pause(source=source)

    async def resume(self) -> dict:
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

    # ----- 搜歌 / 本地库 -----

    async def get_local_playlist(self, force_refresh: bool = False) -> dict:
        self.prepare_for_io()
        return self._library.get_playlist(force_refresh)

    async def search_local_music(self, query: str) -> dict:
        self.prepare_for_io()
        return self._library.search(query)

    async def play_local_song_by_id(self, file_id: str) -> dict:
        eng = self._engine
        try:
            self.prepare_for_io()
            resolved = self._library.resolve(file_id)
            if resolved is None:
                return {"status": "error", "message": f"本地文件不存在: {file_id}"}

            file_path, metadata = resolved
            eng.current_song = metadata.display_name()
            eng.song_id = file_id
            eng.total_duration = metadata.duration or 0
            self.current_url = str(file_path)
            self.lyrics = []

            duration = await MusicDecoder.get_duration(file_path)
            if duration > 0:
                eng.total_duration = duration
                logger.info(f"从音频文件获取准确时长: {duration:.2f}秒")
            elif eng.total_duration == 0:
                logger.warning("无法获取音频时长")

            success = await eng.start_playback(file_path)
            if success:
                return {
                    "status": "success",
                    "message": f"正在播放: {eng.current_song}",
                    "song": eng.current_song,
                    "duration": self._format_time(eng.total_duration),
                    "total_seconds": eng.total_duration,
                }
            return {"status": "error", "message": "播放失败"}
        except Exception as e:
            logger.error(f"播放本地音乐失败: {e}", exc_info=True)
            return {"status": "error", "message": f"播放失败: {str(e)}"}

    async def search_and_play(self, song_name: str) -> dict:
        eng = self._engine
        try:
            self.prepare_for_io()
            hit = await search_song(song_name, self.config)
            if hit is None:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}

            eng.current_song = hit.display_name
            eng.song_id = hit.song_id
            eng.total_duration = hit.duration
            self.current_url = hit.api_url
            await self._fetch_lyrics(hit.song_id)

            success = await eng.play_url(hit.api_url)
            if success:
                return {
                    "status": "success",
                    "message": f"正在播放: {eng.current_song}",
                    "song": eng.current_song,
                    "duration": self._format_time(eng.total_duration),
                    "total_seconds": eng.total_duration,
                }

            detail = self._downloader.last_error or "未知原因"
            return {"status": "error", "message": f"播放失败: {detail}"}
        except Exception as e:
            logger.error(f"搜索播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"操作失败: {str(e)}"}

    async def get_lyrics(self) -> dict:
        if not self.lyrics:
            return {"status": "info", "message": "当前歌曲没有歌词", "lyrics": []}
        lines = [f"[{self._format_time(t)}] {text}" for t, text in self.lyrics]
        return {
            "status": "success",
            "message": f"获取到 {len(self.lyrics)} 行歌词",
            "lyrics": lines,
        }

    async def get_status(self) -> dict:
        eng = self._engine
        position = await eng.get_position()
        progress = await eng.get_progress()
        if not eng.is_playing:
            playing_state = "未播放"
        elif eng.paused and eng.pause_source == "manual":
            playing_state = "已暂停"
        elif eng.is_playing:
            playing_state = "播放中"
        else:
            playing_state = "未知"

        return {
            "status": "success",
            "message": (
                f"当前歌曲: {eng.current_song}\n"
                f"播放状态: {playing_state}\n"
                f"暂停来源: {eng.pause_source or '无'} (tts=说话时临时暂停)\n"
                f"总时长秒: {int(eng.total_duration)}\n"
                f"当前位置秒: {int(position)}\n"
                f"播放时长: {self._format_time(eng.total_duration)}\n"
                f"当前位置: {self._format_time(position)}\n"
                f"播放进度: {progress}%\n"
                f"歌词可用: {'是' if len(self.lyrics) > 0 else '否'}\n"
                f"提示: 跳转百分之N请调用 seek(percent=N)，不要用歌词推算"
            ),
        }

    # ----- 歌词 -----

    async def _tick_lyrics(self) -> None:
        if not self.lyrics:
            return
        eng = self._engine
        now = time.time()
        if now - eng.last_lyric_tick < 0.2:
            return
        eng.last_lyric_tick = now

        position = now - eng.start_play_time if eng.start_play_time > 0 else 0.0
        hit = lyric_at(self.lyrics, position)
        if hit is None:
            return
        idx, text = hit
        if idx == eng.current_lyric_index:
            return
        eng.current_lyric_index = idx
        display = format_lyric_display(text, position, eng.total_duration)
        await self._bus.emit_lyrics_update(display, self.lyrics[idx][0])
        logger.debug(f"显示歌词: {text}")

    async def _fetch_lyrics(self, song_id: str):
        eng = self._engine
        self.lyrics = await fetch_kuwo_lyrics(
            song_id,
            lyrics_url=self.config["LYRICS_URL"],
            headers=self.config["HEADERS"],
        )
        if eng.total_duration == 0 and self.lyrics:
            last_time, _ = self.lyrics[-1]
            eng.total_duration = last_time + 5.0
            logger.info(f"从歌词提取歌曲时长: {eng.total_duration}秒")

    def _format_time(self, seconds: float) -> str:
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02d}:{secs:02d}"

    def __del__(self):
        try:
            cache = getattr(self, "_cache", None)
            if cache is not None and getattr(cache, "_ready", False):
                cache.clean_temp()
        except Exception as e:
            logger.debug(f"__del__ 清理临时缓存失败: {e}")
