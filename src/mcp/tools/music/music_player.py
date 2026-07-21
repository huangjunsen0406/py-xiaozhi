"""音乐播放会话.

在线：搜歌 → 解析直链 → FFmpeg 流式播。
本地：走 LocalLibrary 找文件再播。
缓存 / 下载 / 歌词 / 搜歌逻辑在同目录其它文件。
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import numpy as np

from src.audio_codecs.music_decoder import MusicDecoder, is_http_url
from src.constants.constants import AudioConfig
from src.logging import get_logger

from .cache import MusicCache
from .config import load_music_config
from .download import MusicDownloader
from .local_library import LocalLibrary
from .lyrics import fetch_kuwo_lyrics, format_lyric_display, lyric_at
from .online_search import search_song

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec

logger = get_logger()


class MusicPlayer:
    def __init__(self, audio_codec: "AudioCodec | None" = None):
        self._audio_codec = audio_codec
        self._event_bus = None
        self._plugin_ctx = None

        self.decoder: MusicDecoder | None = None
        self._music_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._playback_task: asyncio.Task | None = None

        self.current_song = ""
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0.0
        self.is_playing = False
        self.paused = False
        self.current_position = 0.0
        self.start_play_time = 0.0
        self._pause_source: str | None = None
        self._current_source: str | Path | None = None
        self._stream_headers: dict[str, str] | None = None
        # 在线直链模板，TTS 结束后可重新 resolve 拿新 CDN（避免开了又掐的签名链失效）
        self._api_url: str | None = None

        self.lyrics: list[tuple[float, str]] = []
        self.current_lyric_index = -1
        self._last_lyric_tick = 0.0

        self._config: dict | None = None
        self._cache = MusicCache()
        self._downloader = MusicDownloader(self._cache)
        self._library = LocalLibrary(self._cache)

        logger.debug("MusicPlayer 实例已创建")

    @property
    def cache_dir(self) -> Path:
        return self._cache.root

    @property
    def temp_cache_dir(self) -> Path:
        return self._cache.temp_dir

    def set_audio_codec(self, audio_codec: "AudioCodec | None") -> None:
        self._audio_codec = audio_codec
        if audio_codec:
            logger.info("AudioCodec 已设置到 MusicPlayer")

    def set_event_bus(self, event_bus, plugin_ctx=None) -> None:
        from src.core.event_bus import Events

        self._unsubscribe_event_bus()
        self._event_bus = event_bus
        self._plugin_ctx = plugin_ctx
        if event_bus:
            event_bus.on(Events.MUSIC_PAUSE_REQUEST, self._on_pause_request)
            event_bus.on(Events.MUSIC_RESUME_REQUEST, self._on_resume_request)
            logger.info("MusicPlayer 已连接到 EventBus")

    def _unsubscribe_event_bus(self) -> None:
        if not self._event_bus:
            return
        try:
            from src.core.event_bus import Events

            self._event_bus.off(Events.MUSIC_PAUSE_REQUEST, self._on_pause_request)
            self._event_bus.off(Events.MUSIC_RESUME_REQUEST, self._on_resume_request)
        except Exception as e:
            logger.debug(f"MusicPlayer 取消 EventBus 订阅失败: {e}")

    def detach(self) -> None:
        self._unsubscribe_event_bus()
        self._event_bus = None
        self._plugin_ctx = None
        self._audio_codec = None
        logger.debug("MusicPlayer 已 detach 运行时绑定")

    def _get_audio_codec(self) -> "AudioCodec | None":
        if self._audio_codec is None:
            logger.warning("AudioCodec 未设置，音乐播放功能不可用")
        return self._audio_codec

    async def _clear_music_queue(self) -> int:
        count = 0
        while not self._music_queue.empty():
            try:
                self._music_queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

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

    def _prepare_for_io(self) -> None:
        self.reload_config()
        self._cache.prepare()

    # ---------- 对外 API ----------

    async def get_local_playlist(self, force_refresh: bool = False) -> dict:
        self._prepare_for_io()
        return self._library.get_playlist(force_refresh)

    async def search_local_music(self, query: str) -> dict:
        self._prepare_for_io()
        return self._library.search(query)

    async def play_local_song_by_id(self, file_id: str) -> dict:
        try:
            self._prepare_for_io()
            resolved = self._library.resolve(file_id)
            if resolved is None:
                return {"status": "error", "message": f"本地文件不存在: {file_id}"}

            file_path, metadata = resolved
            self.current_song = metadata.display_name()
            self.song_id = file_id
            self.total_duration = metadata.duration or 0
            self.current_url = str(file_path)
            self.lyrics = []

            duration = await MusicDecoder.get_duration(file_path)
            if duration > 0:
                self.total_duration = duration
                logger.info(f"从音频文件获取准确时长: {duration:.2f}秒")
            elif self.total_duration == 0:
                logger.warning("无法获取音频时长")

            success = await self._start_playback(file_path)
            if success:
                return {
                    "status": "success",
                    "message": f"正在播放: {self.current_song}",
                    "song": self.current_song,
                    "duration": self._format_time(self.total_duration),
                    "total_seconds": self.total_duration,
                }
            return {"status": "error", "message": "播放失败"}
        except Exception as e:
            logger.error(f"播放本地音乐失败: {e}", exc_info=True)
            return {"status": "error", "message": f"播放失败: {str(e)}"}

    async def search_and_play(self, song_name: str) -> dict:
        try:
            self._prepare_for_io()
            hit = await search_song(song_name, self.config)
            if hit is None:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}

            self.current_song = hit.display_name
            self.song_id = hit.song_id
            self.total_duration = hit.duration
            self.current_url = hit.api_url
            await self._fetch_lyrics(hit.song_id)

            success = await self._play_url(hit.api_url)
            if success:
                return {
                    "status": "success",
                    "message": f"正在播放: {self.current_song}",
                    "song": self.current_song,
                    "duration": self._format_time(self.total_duration),
                    "total_seconds": self.total_duration,
                }

            detail = self._downloader.last_error or "未知原因"
            return {"status": "error", "message": f"播放失败: {detail}"}
        except Exception as e:
            logger.error(f"搜索播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"操作失败: {str(e)}"}

    async def _cancel_playback_task(self) -> None:
        task = self._playback_task
        if task is None or task.done():
            self._playback_task = None
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"等待播放任务结束时异常: {e}")
        self._playback_task = None

    async def stop(self) -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            current_song = self.current_song
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            await self._cancel_playback_task()
            cleared = await self._clear_music_queue()
            logger.debug(f"停止时清空 {cleared} 帧音乐数据")

            self.is_playing = False
            self.paused = False
            self._pause_source = None
            self.current_position = 0
            self.current_lyric_index = -1
            self._api_url = None

            await self._emit_state_change("stopped", current_song)
            logger.info(f"停止播放: {current_song}")
            return {"status": "success", "message": "已停止"}
        except Exception as e:
            logger.error(f"停止播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"停止失败: {str(e)}"}

    async def pause(self, source: str = "manual") -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if self.paused:
                if self._pause_source != source:
                    old = self._pause_source
                    self._pause_source = source
                    logger.info(f"更新暂停来源: {old} → {source}")
                return {"status": "info", "message": "已经处于暂停状态"}

            self.paused = True
            self._pause_source = source
            if self.start_play_time > 0:
                self.current_position = time.time() - self.start_play_time

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            cleared = await self._clear_music_queue()
            logger.info(
                f"暂停播放: {self.current_song} at {self._format_time(self.current_position)}, "
                f"来源: {source}, 清空 {cleared} 帧音乐队列"
            )
            return {"status": "success", "message": "已暂停"}
        except Exception as e:
            logger.error(f"暂停播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"暂停失败: {str(e)}"}

    async def resume(self) -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}
            if not self.paused:
                return {"status": "info", "message": "当前未暂停"}

            # 流式：重新 resolve，避免之前开流又掐掉导致 CDN 链失效
            if self._api_url:
                if not await self._refresh_stream_source():
                    return {
                        "status": "error",
                        "message": self._downloader.last_error or "无法刷新播放地址",
                    }
            elif not self._current_source:
                return {"status": "error", "message": "没有可恢复的音源"}
            elif not is_http_url(self._current_source) and not Path(
                self._current_source
            ).exists():
                return {"status": "error", "message": "无法找到音频文件"}

            logger.info(
                f"恢复播放: {self.current_song} from {self._format_time(self.current_position)}"
            )

            # 先停旧循环，再开解码，避免「循环被取消」踩掉新流
            await self._cancel_playback_task()
            cleared = await self._clear_music_queue()
            if cleared > 0:
                logger.debug(f"恢复前清空 {cleared} 帧残留数据")

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            # 从头恢复才写缓存；中途 resume 不写半截
            cache_path = None
            if (
                is_http_url(self._current_source)
                and self.song_id
                and self.current_position <= 0.1
            ):
                self._cache.prepare()
                if self._cache.find_song_file(self.song_id) is None:
                    cache_path = self._cache.path_for_song(self.song_id)

            success = await self.decoder.start_decode(
                self._current_source,
                self._music_queue,
                self.current_position,
                headers=self._stream_headers,
                cache_path=cache_path,
            )
            if not success:
                return {"status": "error", "message": "恢复播放失败"}

            self.paused = False
            self._pause_source = None
            self.start_play_time = time.time() - self.current_position
            self._last_lyric_tick = 0.0
            self._playback_task = asyncio.create_task(
                self._playback_loop(), name="music:playback"
            )
            await self._emit_state_change("playing", self.current_song)
            return {"status": "success", "message": "已恢复播放"}
        except Exception as e:
            logger.error(f"恢复播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"恢复失败: {str(e)}"}

    async def seek(
        self,
        position: float | None = None,
        percent: float | None = None,
    ) -> dict:
        """跳转。position=秒；percent=0~100（按 total_duration 算秒）."""
        try:
            if not self.is_playing:
                return {"status": "error", "message": "没有正在播放的歌曲"}
            if not self._current_source:
                return {"status": "error", "message": "没有可跳转的音源"}
            if not is_http_url(self._current_source) and not Path(
                self._current_source
            ).exists():
                return {"status": "error", "message": "无法找到音频文件"}

            # 时长未知时尽量从本地文件补一次
            if self.total_duration <= 0 and not is_http_url(self._current_source):
                duration = await MusicDecoder.get_duration(self._current_source)
                if duration > 0:
                    self.total_duration = duration

            target: float | None = None
            if percent is not None and percent >= 0:
                if self.total_duration <= 0:
                    return {
                        "status": "error",
                        "message": "未知歌曲总时长，无法按百分比跳转",
                    }
                p = max(0.0, min(100.0, float(percent)))
                target = self.total_duration * (p / 100.0)
                logger.info(
                    f"按百分比跳转: {p:.0f}% → {self._format_time(target)} "
                    f"(总时长 {self._format_time(self.total_duration)})"
                )
            elif position is not None and position >= 0:
                target = float(position)
            else:
                return {
                    "status": "error",
                    "message": "请提供 position（秒）或 percent（0-100）",
                }

            if target < 0:
                target = 0
            if self.total_duration > 0 and target >= self.total_duration:
                target = max(0.0, self.total_duration - 1)

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            await asyncio.sleep(0.05)
            cleared = await self._clear_music_queue()
            audio_codec = self._get_audio_codec()
            if audio_codec:
                await audio_codec.clear_audio_queue()

            logger.info(
                f"跳转到 {self._format_time(target)}，清空 {cleared} 帧音乐数据"
            )
            success = await self._start_playback(
                self._current_source,
                target,
                headers=self._stream_headers,
            )
            if success:
                return {
                    "status": "success",
                    "message": (
                        f"已跳转到 {self._format_time(target)}"
                        + (
                            f"（约 {percent:.0f}%）"
                            if percent is not None and percent >= 0
                            else ""
                        )
                    ),
                }
            return {"status": "error", "message": "跳转失败"}
        except Exception as e:
            logger.error(f"跳转失败: {e}", exc_info=True)
            return {"status": "error", "message": f"跳转失败: {str(e)}"}

    async def get_lyrics(self) -> dict:
        if not self.lyrics:
            return {"status": "info", "message": "当前歌曲没有歌词", "lyrics": []}
        lines = [
            f"[{self._format_time(t)}] {text}" for t, text in self.lyrics
        ]
        return {
            "status": "success",
            "message": f"获取到 {len(self.lyrics)} 行歌词",
            "lyrics": lines,
        }

    async def get_status(self) -> dict:
        position = await self.get_position()
        progress = await self.get_progress()
        if not self.is_playing:
            playing_state = "未播放"
        elif self.paused and self._pause_source == "manual":
            playing_state = "已暂停"
        elif self.is_playing:
            playing_state = "播放中"
        else:
            playing_state = "未知"

        return {
            "status": "success",
            "message": (
                f"当前歌曲: {self.current_song}\n"
                f"播放状态: {playing_state}\n"
                f"暂停来源: {self._pause_source or '无'} (tts=说话时临时暂停)\n"
                f"总时长秒: {int(self.total_duration)}\n"
                f"当前位置秒: {int(position)}\n"
                f"播放时长: {self._format_time(self.total_duration)}\n"
                f"当前位置: {self._format_time(position)}\n"
                f"播放进度: {progress}%\n"
                f"歌词可用: {'是' if len(self.lyrics) > 0 else '否'}\n"
                f"提示: 跳转百分之N请调用 seek(percent=N)，不要用歌词推算"
            ),
        }

    async def get_position(self):
        if not self.is_playing or self.paused:
            return self.current_position
        current_pos = min(self.total_duration, time.time() - self.start_play_time)
        if current_pos >= self.total_duration and self.total_duration > 0:
            await self._handle_playback_finished()
        return current_pos

    async def get_progress(self):
        if self.total_duration <= 0:
            return 0
        position = await self.get_position()
        return round(position * 100 / self.total_duration, 1)

    # ---------- 播放内部 ----------

    async def _refresh_stream_source(self) -> bool:
        """用模板 URL 再要一次 CDN 地址."""
        if not self._api_url:
            return bool(self._current_source)
        self._prepare_for_io()
        media_url = await self._downloader.resolve_play_url(
            self._api_url, song_id=self.song_id or None
        )
        if not media_url:
            logger.error(
                f"刷新播放地址失败: {self._downloader.last_error or '未知'}"
            )
            return False
        self._current_source = media_url
        self._stream_headers = self._downloader.media_headers(media_url)
        host = urlparse(media_url).hostname or media_url[:48]
        logger.info(f"已刷新流地址: {host}")
        return True

    async def _play_url(self, api_url: str) -> bool:
        try:
            if not self._get_audio_codec():
                logger.error("无法获取 AudioCodec，播放失败")
                return False

            if self.is_playing:
                await self.stop()

            self._prepare_for_io()
            self._api_url = api_url

            if self.song_id:
                cached = self._cache.find_song_file(self.song_id)
                if cached is not None:
                    logger.info(f"使用本地缓存播放: {cached}")
                    self._api_url = None  # 本地文件无需刷新
                    duration = await MusicDecoder.get_duration(cached)
                    if duration > 0:
                        self.total_duration = duration
                    return await self._start_playback(cached)

            # 若 TTS 正在说：先记下 api，等 resume 再 resolve+开流，别开了又掐
            if self._plugin_ctx and self._plugin_ctx.is_speaking():
                logger.info("TTS 进行中，先占住播放会话，说完再开流")
                self._current_source = None
                self._stream_headers = None
                self.is_playing = True
                self.paused = True
                self._pause_source = "tts"
                self.current_position = 0.0
                self.start_play_time = 0.0
                self.current_lyric_index = -1
                self._last_lyric_tick = 0.0
                await self._cancel_playback_task()
                if self.decoder:
                    await self.decoder.stop()
                    self.decoder = None
                await self._clear_music_queue()
                return True

            media_url = await self._downloader.resolve_play_url(
                api_url, song_id=self.song_id or None
            )
            if not media_url:
                detail = self._downloader.last_error or "未能解析播放地址"
                logger.error(f"获取播放地址失败: {detail}")
                return False

            headers = self._downloader.media_headers(media_url)
            if self.total_duration <= 0:
                duration = await MusicDecoder.get_duration(media_url, headers=headers)
                if duration > 0:
                    self.total_duration = duration
                    logger.info(f"从流探测时长: {duration:.2f}秒")
                else:
                    logger.warning("无法获取流时长，将使用歌词时长或0")

            host = urlparse(media_url).hostname or media_url[:48]
            logger.info(f"流式播放: {host}")
            return await self._start_playback(media_url, headers=headers)
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            return False

    async def _start_playback(
        self,
        source: str | Path,
        start_position: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> bool:
        try:
            self._current_source = source
            self._stream_headers = headers if is_http_url(source) else None

            # 本地文件若 TTS 占着：同样只挂起，等 resume
            if self._plugin_ctx and self._plugin_ctx.is_speaking():
                logger.info("TTS 进行中，本地音源已就绪，说完再播")
                if self.decoder:
                    await self.decoder.stop()
                    self.decoder = None
                await self._cancel_playback_task()
                await self._clear_music_queue()
                self.is_playing = True
                self.paused = True
                self._pause_source = "tts"
                self.current_position = start_position
                self.start_play_time = 0.0
                self.current_lyric_index = -1
                return True

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            await self._cancel_playback_task()
            cleared = await self._clear_music_queue()
            if cleared > 0:
                logger.debug(f"开始播放前清空 {cleared} 帧音乐数据")

            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            # 在线从头播：边解 PCM 边 copy 到缓存，播完才有文件
            cache_path = None
            if (
                is_http_url(source)
                and self.song_id
                and start_position <= 0.1
            ):
                self._cache.prepare()
                cache_path = self._cache.path_for_song(self.song_id)

            success = await self.decoder.start_decode(
                source,
                self._music_queue,
                start_position,
                headers=self._stream_headers,
                cache_path=cache_path,
            )
            if not success:
                logger.error("启动音频解码器失败")
                return False

            self.is_playing = True
            self.paused = False
            self._pause_source = None
            self.current_position = start_position
            self.start_play_time = time.time() - start_position
            self.current_lyric_index = -1
            self._last_lyric_tick = 0.0

            self._playback_task = asyncio.create_task(
                self._playback_loop(), name="music:playback"
            )

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(f"开始播放: {self.current_song}{position_info}")
            await self._emit_state_change(
                "playing", self.current_song, start_position
            )
            return True
        except Exception as e:
            logger.error(f"启动播放失败: {e}", exc_info=True)
            return False

    async def _playback_loop(self):
        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                await self._tick_lyrics()

                try:
                    audio_data = await asyncio.wait_for(
                        self._music_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("音乐队列读取超时")
                    continue

                if audio_data is None:
                    logger.info("音乐播放完成")
                    await self._handle_playback_finished()
                    break

                await self._write_to_audio_codec(audio_data)
        except asyncio.CancelledError:
            logger.debug("播放循环被取消")
        except Exception as e:
            logger.error(f"播放循环异常: {e}", exc_info=True)

    async def _tick_lyrics(self) -> None:
        if not self.lyrics:
            return
        now = time.time()
        if now - self._last_lyric_tick < 0.2:
            return
        self._last_lyric_tick = now

        position = now - self.start_play_time if self.start_play_time > 0 else 0.0
        hit = lyric_at(self.lyrics, position)
        if hit is None:
            return
        idx, text = hit
        if idx == self.current_lyric_index:
            return
        self.current_lyric_index = idx
        display = format_lyric_display(text, position, self.total_duration)
        await self._emit_lyrics_update(display, self.lyrics[idx][0])
        logger.debug(f"显示歌词: {text}")

    async def _write_to_audio_codec(self, pcm_data: np.ndarray):
        try:
            audio_codec = self._get_audio_codec()
            if not audio_codec:
                return
            if pcm_data.ndim > 1:
                pcm_data = pcm_data.mean(axis=1, dtype=np.float32)
            if pcm_data.dtype != np.float32:
                pcm_data = pcm_data.astype(np.float32)
            await audio_codec.write_pcm_direct(pcm_data)
        except Exception as e:
            logger.error(f"写入 AudioCodec 失败: {e}", exc_info=True)

    async def _fetch_lyrics(self, song_id: str):
        self.lyrics = await fetch_kuwo_lyrics(
            song_id,
            lyrics_url=self.config["LYRICS_URL"],
            headers=self.config["HEADERS"],
        )
        if self.total_duration == 0 and self.lyrics:
            last_time, _ = self.lyrics[-1]
            self.total_duration = last_time + 5.0
            logger.info(f"从歌词提取歌曲时长: {self.total_duration}秒")

    async def _handle_playback_finished(self):
        if not self.is_playing:
            return
        logger.info(f"歌曲播放完成: {self.current_song}")
        if self.decoder:
            # EOF 时 decoder 已 commit 缓存；这里 stop 勿再删已提交文件
            committed = self.decoder.committed_cache_path
            if committed:
                logger.info(f"本曲已缓存，下次可本地播放: {committed.name}")
                self._library.invalidate()
            # 已完整结束：清掉 part 标记，避免 stop 误删
            await self.decoder.stop()
            self.decoder = None

        if self._playback_task and not self._playback_task.done():
            if self._playback_task is not asyncio.current_task():
                await self._cancel_playback_task()
            else:
                self._playback_task = None

        self.is_playing = False
        self.paused = False
        self.current_position = self.total_duration
        self.current_lyric_index = -1
        await self._emit_state_change("completed", self.current_song)

    def _format_time(self, seconds: float) -> str:
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02d}:{secs:02d}"

    async def _emit_state_change(
        self, state: str, song_name: str = None, position: float = None
    ):
        if not self._event_bus:
            return
        try:
            from src.core.event_bus import Events

            from .events import MusicStateData

            data = MusicStateData(
                state=state,
                song=song_name or self.current_song,
                position=position if position is not None else self.current_position,
                duration=self.total_duration,
                pause_source=self._pause_source if state == "paused" else None,
            )
            await self._event_bus.emit(Events.MUSIC_STATE_CHANGED, data)
            logger.debug(f"发送音乐状态变化事件: {state}")
        except Exception as e:
            logger.debug(f"发送状态事件失败: {e}")

    async def _emit_lyrics_update(self, lyrics_text: str, time_sec: float = 0):
        if not self._event_bus:
            return
        try:
            from src.core.event_bus import Events

            from .events import MusicLyricsData

            data = MusicLyricsData(
                text=lyrics_text, time_sec=time_sec, song_id=self.song_id
            )
            await self._event_bus.emit(Events.MUSIC_LYRICS_UPDATE, data)
        except Exception as e:
            logger.debug(f"发送歌词事件失败: {e}")

    async def _on_pause_request(self, data):
        try:
            from .events import MusicControlRequest

            if isinstance(data, MusicControlRequest):
                source = data.source
            elif isinstance(data, dict):
                source = data.get("source", "external")
            else:
                source = "external"

            if self.is_playing and not self.paused:
                logger.info(f"收到暂停请求，来源: {source}")
                await self.pause(source=source)
        except Exception as e:
            logger.error(f"处理暂停请求失败: {e}", exc_info=True)

    async def _on_resume_request(self, data):
        try:
            from .events import MusicControlRequest

            if isinstance(data, MusicControlRequest):
                source = data.source
            elif isinstance(data, dict):
                source = data.get("source", "external")
            else:
                source = None

            if self.is_playing and self.paused:
                if source is None or self._pause_source == source:
                    logger.info(f"收到恢复请求，来源: {source}")
                    await self.resume()
        except Exception as e:
            logger.error(f"处理恢复请求失败: {e}", exc_info=True)

    def __del__(self):
        try:
            cache = getattr(self, "_cache", None)
            if cache is not None and getattr(cache, "_ready", False):
                cache.clean_temp()
        except Exception as e:
            logger.debug(f"__del__ 清理临时缓存失败: {e}")


# 进程内共享：容器 bind 优先，工具侧 get_* 兼容
_music_player_instance: MusicPlayer | None = None
_music_player_bound: bool = False


def bind_music_player(player: MusicPlayer) -> None:
    global _music_player_instance, _music_player_bound
    if (
        _music_player_instance is not None
        and _music_player_instance is not player
    ):
        try:
            _music_player_instance.detach()
        except Exception as e:
            logger.debug(f"替换 MusicPlayer 时 detach 旧实例失败: {e}")
    _music_player_instance = player
    _music_player_bound = True
    logger.info("[MusicPlayer] 已绑定容器实例")


def unbind_music_player() -> None:
    global _music_player_instance, _music_player_bound
    if _music_player_instance is not None:
        try:
            _music_player_instance.detach()
        except Exception as e:
            logger.debug(f"unbind MusicPlayer detach 失败: {e}")
    _music_player_instance = None
    _music_player_bound = False
    logger.debug("[MusicPlayer] 已解除容器绑定")


def get_music_player_instance() -> MusicPlayer:
    global _music_player_instance
    if _music_player_instance is None:
        _music_player_instance = MusicPlayer()
        logger.info("[MusicPlayer] 创建回退实例（容器未绑定）")
    return _music_player_instance


def is_music_player_bound() -> bool:
    return _music_player_bound and _music_player_instance is not None


def reset_music_player_instance() -> None:
    unbind_music_player()
