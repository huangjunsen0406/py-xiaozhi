"""播放引擎：解码队列、启停/暂停/恢复/跳转与写入 AudioCodec.

独占播放状态、decoder 与歌词进度；接收完整请求并发布完整事件数据。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import numpy as np

from src.audio_codecs.music_decoder import MusicDecoder, is_http_url
from src.constants.constants import AudioConfig
from src.logging import get_logger

from .events import MusicEventPublisher, MusicLyricsData, MusicStateData
from .lifecycle import await_cleanup
from .lyrics import format_lyric_display, lyric_at
from .state import PlaybackRequest, PlaybackState

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec
    from src.mcp.tools.music.cache import MusicCache
    from src.mcp.tools.music.download import MusicDownloader
    from src.mcp.tools.music.local_library import LocalLibrary

logger = get_logger()


@dataclass
class PlaybackDeps:
    cache: MusicCache
    downloader: MusicDownloader
    library: LocalLibrary
    events: MusicEventPublisher


class PlaybackEngine:
    """播放状态机；状态字段挂在本实例上."""

    def __init__(self, deps: PlaybackDeps) -> None:
        self._cache = deps.cache
        self._downloader = deps.downloader
        self._library = deps.library
        self._events = deps.events
        self._is_speaking: Callable[[], bool] = lambda: False
        self._generation = 0
        self._codec_generation = 0
        self._start_lock = asyncio.Lock()

        self._default_audio_config = AudioConfig.from_config()
        self.audio_codec: AudioCodec | None = None
        self.decoder: MusicDecoder | None = None
        self._music_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._playback_task: asyncio.Task | None = None
        self._stop_task: asyncio.Task | None = None
        self._decode_start_task: asyncio.Task | None = None

        self._lyrics: tuple[tuple[float, str], ...] = ()
        self.current_url = ""
        self.current_song = ""
        self.song_id = ""
        self.total_duration = 0.0
        self.is_playing = False
        self.paused = False
        self.current_position = 0.0
        self.start_play_time = 0.0
        self.pause_source: str | None = None
        self._current_source: str | Path | None = None
        self._stream_headers: dict[str, str] | None = None
        # 在线直链模板，TTS 结束后可重新 resolve 拿新 CDN
        self.api_url: str | None = None
        self.current_lyric_index = -1
        self.last_lyric_tick = 0.0
        self.last_error: str | None = None

    @property
    def state(self) -> PlaybackState:
        return PlaybackState(
            song=self.current_song,
            song_id=self.song_id,
            source=self.current_url,
            duration=self.total_duration,
            is_playing=self.is_playing,
            paused=self.paused,
            pause_source=self.pause_source,
            position=self._position(),
            error=self.last_error,
            lyrics=self._lyrics,
        )

    def set_speaking_provider(self, provider: Callable[[], bool] | None) -> None:
        self._is_speaking = provider if provider is not None else lambda: False

    def is_speaking(self) -> bool:
        return self._is_speaking()

    async def bind_audio_codec(self, codec: AudioCodec | None) -> None:
        self._codec_generation += 1
        binding = self._codec_generation
        if codec is self.audio_codec and codec is not None:
            return

        try:
            await self.stop()
        finally:
            if binding == self._codec_generation:
                self.audio_codec = codec

    async def play(self, request: PlaybackRequest) -> bool:
        generation = self._generation + 1
        await self.stop()
        if generation != self._generation:
            return False
        self.current_song = request.song
        self.song_id = request.song_id
        self.current_url = str(request.source)
        self.total_duration = request.duration
        self.current_position = 0.0
        self._lyrics = tuple(request.lyrics)
        if self.total_duration <= 0 and self._lyrics:
            self.total_duration = self._lyrics[-1][0] + 5.0
        self.last_error = None
        if request.resolve_url:
            return await self.play_url(str(request.source))
        self.api_url = None
        duration = await MusicDecoder.get_duration(request.source)
        if generation != self._generation:
            return False
        if duration > 0:
            self.total_duration = duration
        return await self.start_playback(request.source)

    @staticmethod
    def _format_time(seconds: float) -> str:
        return f"{int(seconds) // 60:02d}:{int(seconds) % 60:02d}"

    async def emit_state_change(
        self,
        state: str,
        song_name: str | None = None,
        position: float | None = None,
    ) -> None:
        await self._events.emit_state(
            MusicStateData(
                state=state,
                song=song_name or self.current_song,
                position=self.current_position if position is None else position,
                duration=self.total_duration,
                pause_source=self.pause_source if state == "paused" else None,
            )
        )

    async def tick_lyrics(self) -> None:
        if not self._lyrics:
            return
        now = time.time()
        if now - self.last_lyric_tick < 0.2:
            return
        self.last_lyric_tick = now
        position = await self.get_position()
        hit = lyric_at(self._lyrics, position)
        if hit is None or hit[0] == self.current_lyric_index:
            return
        index, text = hit
        self.current_lyric_index = index
        await self._events.emit_lyrics(
            MusicLyricsData(
                text=format_lyric_display(text, position, self.total_duration),
                time_sec=self._lyrics[index][0],
                song_id=self.song_id,
            )
        )

    def _get_audio_codec(self) -> AudioCodec | None:
        if self.audio_codec is None:
            logger.warning("AudioCodec 未设置，音乐播放功能不可用")
        return self.audio_codec

    def _make_decoder(self) -> MusicDecoder:
        """Resolve the current codec format after device refresh or resume."""
        audio_config = getattr(
            self.audio_codec, "audio_config", self._default_audio_config
        )
        return MusicDecoder(
            sample_rate=audio_config.OUTPUT_SAMPLE_RATE,
            channels=audio_config.CHANNELS,
            frame_duration=audio_config.FRAME_DURATION,
        )

    async def _clear_music_queue(self) -> int:
        count = 0
        while not self._music_queue.empty():
            try:
                self._music_queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    async def _cancel_playback_task(self) -> None:
        task = self._playback_task
        if task is None or task.done():
            self._playback_task = None
            return
        # Revoke ownership before cancel: Python 3.10 wait_for may consume a
        # cancellation racing with a ready queue item. The loop also observes
        # ownership and must still exit in that case.
        self._playback_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"等待播放任务结束时异常: {e}")

    async def stop(self) -> dict:
        self._generation += 1
        task = self._stop_task
        if task is None or task.done():
            task = asyncio.create_task(self._stop_playback(), name="music:stop")
            self._stop_task = task
        try:
            return await await_cleanup(task)
        finally:
            if self._stop_task is task and task.done():
                self._stop_task = None

    async def _stop_playback(self) -> dict:
        was_playing = self.is_playing
        current_song = self.current_song
        self.is_playing = False
        self.paused = False
        self.pause_source = None
        try:
            # Stop consuming before stopping the decoder: its terminal marker
            # must not turn an explicit stop into a completion or failure event.
            await self._cancel_playback_task()
            startup = self._decode_start_task
            if startup is not None:
                if not startup.done():
                    startup.cancel()
                await asyncio.gather(startup, return_exceptions=True)
                if self._decode_start_task is startup:
                    self._decode_start_task = None
            decoder, self.decoder = self.decoder, None
            if decoder:
                await decoder.stop()
            await self.cancel_prefetch()
            cleared = await self._clear_music_queue()
            if self.audio_codec and was_playing:
                await self.audio_codec.clear_music_queue()
            logger.debug(f"停止时清空 {cleared} 帧音乐数据")
            self.current_lyric_index = -1
            self.api_url = None
            if not was_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}
            self.current_position = 0
            await self.emit_state_change("stopped", current_song)
            return {"status": "success", "message": "已停止"}
        except Exception as error:
            logger.error("停止播放失败: %s", error, exc_info=True)
            return {"status": "error", "message": f"停止失败: {error}"}

    async def pause(self, source: str = "manual") -> dict:
        return await await_cleanup(asyncio.create_task(self._pause(source)))

    async def _pause(self, source: str) -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if self.paused:
                if self.pause_source != source:
                    old = self.pause_source
                    self.pause_source = source
                    logger.info(f"更新暂停来源: {old} → {source}")
                if source != "tts":
                    self._generation += 1
                    await self._cancel_playback_task()
                    if self.decoder:
                        await self.decoder.stop()
                        self.decoder = None
                    await self._clear_music_queue()
                    if self.audio_codec:
                        await self.audio_codec.clear_music_queue()
                return {"status": "info", "message": "已经处于暂停状态"}

            self.paused = True
            self.pause_source = source
            if self.start_play_time > 0:
                self.current_position = time.time() - self.start_play_time

            fmt = self._format_time

            if source == "tts":
                # TTS 逐句闪避：保留解码器与队列（解码器会在满队列处
                # 自然等位），恢复零成本，不用逐句重启 ffmpeg
                logger.info(
                    f"暂停播放(tts, 保留解码器): {self.current_song} "
                    f"at {fmt(self.current_position)}"
                )
                return {"status": "success", "message": "已暂停"}

            self._generation += 1
            await self._cancel_playback_task()
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            cleared = await self._clear_music_queue()
            audio_codec = self._get_audio_codec()
            if audio_codec:
                # 手动暂停要立即静音：把 codec 侧音乐余量也清掉
                await audio_codec.clear_music_queue()
            logger.info(
                f"暂停播放: {self.current_song} at {fmt(self.current_position)}, "
                f"来源: {source}, 清空 {cleared} 帧音乐队列"
            )
            return {"status": "success", "message": "已暂停"}
        except Exception as e:
            logger.error(f"暂停播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"暂停失败: {str(e)}"}

    async def resume(self) -> dict:
        generation = self._generation
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}
            if not self.paused:
                return {"status": "info", "message": "当前未暂停"}

            if (
                self.decoder is not None
                and self.pause_source == "tts"
                and self._playback_task is not None
                and not self._playback_task.done()
            ):
                # 快速恢复（tts 闪避路径）：解码器与消费循环都在，仅继续消费
                self.paused = False
                self.pause_source = None
                self.start_play_time = time.time() - self.current_position
                self.last_lyric_tick = 0.0
                logger.info(
                    f"恢复播放(tts, 解码器直连): {self.current_song} from "
                    f"{self._format_time(self.current_position)}"
                )
                await self.emit_state_change("playing", self.current_song)
                return {"status": "success", "message": "已恢复播放"}

            if self.api_url:
                if not await self._refresh_stream_source():
                    return {
                        "status": "error",
                        "message": self._downloader.last_error or "无法刷新播放地址",
                    }
            elif not self._current_source:
                return {"status": "error", "message": "没有可恢复的音源"}
            elif (
                not is_http_url(self._current_source)
                and not Path(self._current_source).exists()
            ):
                return {"status": "error", "message": "无法找到音频文件"}

            fmt = self._format_time
            logger.info(
                f"恢复播放: {self.current_song} from {fmt(self.current_position)}"
            )

            if is_http_url(self._current_source) and self.song_id:
                await self._downloader.start_prefetch(
                    str(self._current_source),
                    self.song_id,
                    self._stream_headers,
                )
            if generation != self._generation:
                return {"status": "info", "message": "播放请求已取消"}
            success = await self.start_playback(
                self._current_source,
                self.current_position,
                headers=self._stream_headers,
            )
            if not success:
                return {"status": "error", "message": "恢复播放失败"}
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
        generation = self._generation
        try:
            if not self.is_playing:
                return {"status": "error", "message": "没有正在播放的歌曲"}
            if not self._current_source:
                return {"status": "error", "message": "没有可跳转的音源"}
            if (
                not is_http_url(self._current_source)
                and not Path(self._current_source).exists()
            ):
                return {"status": "error", "message": "无法找到音频文件"}

            if self.total_duration <= 0 and not is_http_url(self._current_source):
                duration = await MusicDecoder.get_duration(self._current_source)
                if generation != self._generation:
                    return {"status": "info", "message": "播放请求已取消"}
                if duration > 0:
                    self.total_duration = duration

            target: float | None = None
            fmt = self._format_time
            if percent is not None and percent >= 0:
                if self.total_duration <= 0:
                    return {
                        "status": "error",
                        "message": "未知歌曲总时长，无法按百分比跳转",
                    }
                p = max(0.0, min(100.0, float(percent)))
                target = self.total_duration * (p / 100.0)
                logger.info(
                    f"按百分比跳转: {p:.0f}% → {fmt(target)} "
                    f"(总时长 {fmt(self.total_duration)})"
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

            self._generation += 1
            generation = self._generation
            await self._cancel_playback_task()
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            cleared = await self._clear_music_queue()
            audio_codec = self._get_audio_codec()
            if audio_codec:
                # 只清音乐播放队列；TTS 队列独立，不受跳转影响
                await audio_codec.clear_music_queue()

            if generation != self._generation:
                return {"status": "info", "message": "播放请求已取消"}
            logger.info(f"跳转到 {fmt(target)}，清空 {cleared} 帧音乐数据")
            success = await self.start_playback(
                self._current_source,
                target,
                headers=self._stream_headers,
            )
            if success:
                return {
                    "status": "success",
                    "message": (
                        f"已跳转到 {fmt(target)}"
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

    async def get_position(self):
        return self._position()

    def _position(self) -> float:
        if not self.is_playing or self.paused:
            return self.current_position
        current_pos = max(0.0, time.time() - self.start_play_time)
        return (
            min(self.total_duration, current_pos)
            if self.total_duration > 0
            else current_pos
        )

    async def get_progress(self):
        if self.total_duration <= 0:
            return 0
        position = await self.get_position()
        return round(position * 100 / self.total_duration, 1)

    async def _refresh_stream_source(self) -> bool:
        if not self.api_url:
            return bool(self._current_source)
        generation = self._generation
        self._cache.prepare()
        media_url = await self._downloader.resolve_play_url(
            self.api_url, song_id=self.song_id or None
        )
        if generation != self._generation:
            return False
        if not media_url:
            logger.error(f"刷新播放地址失败: {self._downloader.last_error or '未知'}")
            return False
        self._current_source = media_url
        self._stream_headers = self._downloader.media_headers(media_url)
        host = urlparse(media_url).hostname or media_url[:48]
        logger.info(f"已刷新流地址: {host}")
        return True

    async def play_url(self, api_url: str) -> bool:
        generation = self._generation
        try:
            if not self._get_audio_codec():
                logger.error("无法获取 AudioCodec，播放失败")
                return False

            self.last_error = None
            self._cache.prepare()
            self.api_url = api_url

            if self.song_id:
                cached = self._cache.find_song_file(self.song_id)
                if cached is not None:
                    logger.info(f"使用本地缓存播放: {cached}")
                    self.api_url = None
                    duration = await MusicDecoder.get_duration(cached)
                    if generation != self._generation:
                        return False
                    if duration > 0:
                        self.total_duration = duration
                    return await self.start_playback(cached)

            if self._is_speaking():
                logger.info("TTS 进行中，先占住播放会话，说完再开流")
                self._current_source = None
                self._stream_headers = None
                self.is_playing = True
                self.paused = True
                self.pause_source = "tts"
                self.current_position = 0.0
                self.start_play_time = 0.0
                self.current_lyric_index = -1
                self.last_lyric_tick = 0.0
                await self._cancel_playback_task()
                if self.decoder:
                    await self.decoder.stop()
                    self.decoder = None
                await self._clear_music_queue()
                return True

            media_url = await self._downloader.resolve_play_url(
                api_url, song_id=self.song_id or None
            )
            if generation != self._generation:
                return False
            if not media_url:
                detail = self._downloader.last_error or "未能解析播放地址"
                logger.error(f"获取播放地址失败: {detail}")
                return False

            headers = self._downloader.media_headers(media_url)
            if self.total_duration <= 0:
                duration = await MusicDecoder.get_duration(media_url, headers=headers)
                if generation != self._generation:
                    return False
                if duration > 0:
                    self.total_duration = duration
                    logger.info(f"从流探测时长: {duration:.2f}秒")
                else:
                    logger.warning("无法获取流时长，将使用歌词时长或0")

            if generation != self._generation:
                return False
            host = urlparse(media_url).hostname or media_url[:48]
            logger.info(f"流式播放: {host}")
            if self.song_id:
                await self._downloader.start_prefetch(media_url, self.song_id, headers)
            if generation != self._generation:
                return False
            return await self.start_playback(media_url, headers=headers)
        except Exception as e:
            logger.error(f"播放失败: {e}", exc_info=True)
            return False

    async def start_playback(
        self,
        source: str | Path,
        start_position: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> bool:
        generation = self._generation
        async with self._start_lock:
            if generation != self._generation:
                return False
            return await self._start_playback(source, start_position, headers)

    async def _start_playback(
        self,
        source: str | Path,
        start_position: float,
        headers: dict[str, str] | None,
    ) -> bool:
        generation = self._generation
        decoder = None
        startup = None
        try:
            self.last_error = None
            self._current_source = source
            self._stream_headers = headers if is_http_url(source) else None

            if self._is_speaking():
                logger.info("TTS 进行中，本地音源已就绪，说完再播")
                if self.decoder:
                    await self.decoder.stop()
                    self.decoder = None
                await self._cancel_playback_task()
                await self._clear_music_queue()
                if generation != self._generation:
                    return False
                self.is_playing = True
                self.paused = True
                self.pause_source = "tts"
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

            if generation != self._generation:
                return False
            decoder = self._make_decoder()
            self.decoder = decoder
            startup = asyncio.create_task(
                decoder.start_decode(
                    source,
                    self._music_queue,
                    start_position,
                    headers=self._stream_headers,
                ),
                name="music:decoder-start",
            )
            self._decode_start_task = startup
            success = await asyncio.shield(startup)
            if generation != self._generation:
                return False
            if not success:
                await self._handle_playback_failed(
                    decoder.error or "启动音频解码器失败"
                )
                return False

            self.is_playing = True
            self.paused = self._is_speaking()
            self.pause_source = "tts" if self.paused else None
            self.current_position = start_position
            self.start_play_time = 0.0 if self.paused else time.time() - start_position
            self.current_lyric_index = -1
            self.last_lyric_tick = 0.0

            self._playback_task = asyncio.create_task(
                self._playback_loop(), name="music:playback"
            )

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(f"开始播放: {self.current_song}{position_info}")
            await self.emit_state_change(
                "paused" if self.paused else "playing", self.current_song, start_position
            )
            return True
        except asyncio.CancelledError:
            # Cancelling the owned decoder startup is part of stop, not
            # cancellation of the public play request waiting on its result.
            if (
                startup is not None
                and startup.cancelled()
                and generation != self._generation
            ):
                return False
            await self.stop()
            raise
        except Exception as e:
            logger.error(f"启动播放失败: {e}", exc_info=True)
            if generation == self._generation:
                await self._handle_playback_failed(str(e))
            return False
        finally:
            if startup is not None and self._decode_start_task is startup:
                self._decode_start_task = None

    async def _playback_loop(self):
        consumer = asyncio.current_task()
        try:
            while self.is_playing and self._playback_task is consumer:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                await self.tick_lyrics()

                try:
                    audio_data = await asyncio.wait_for(
                        self._music_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("音乐队列读取超时")
                    continue

                # A pause can arrive while queue.get() is suspended. Hold this
                # frame locally until resumed; never write it through a pause.
                while self.paused and self._playback_task is consumer:
                    await asyncio.sleep(0.1)
                if not self.is_playing or self._playback_task is not consumer:
                    break
                if audio_data is None:
                    if self.decoder is not None and self.decoder.completed_successfully:
                        logger.info("音乐播放完成")
                        await self._handle_playback_finished()
                    else:
                        error = getattr(self.decoder, "error", None) or "音频解码失败"
                        await self._handle_playback_failed(error)
                    break

                await self._write_to_audio_codec(audio_data)
        except asyncio.CancelledError:
            logger.debug("播放循环被取消")
        except Exception as e:
            logger.error(f"播放循环异常: {e}", exc_info=True)
            await self._handle_playback_failed(str(e) or type(e).__name__)

    async def _handle_playback_failed(self, error: str) -> None:
        self.last_error = error
        self.current_position = await self.get_position()
        self.is_playing = False
        self.paused = False
        self.pause_source = None
        self.current_lyric_index = -1
        if self.decoder is not None:
            await self.decoder.stop()
            self.decoder = None
        await self._clear_music_queue()
        if self.audio_codec is not None:
            await self.audio_codec.clear_music_queue()
        if self._playback_task is asyncio.current_task():
            self._playback_task = None
        await self.cancel_prefetch()
        await self.emit_state_change("error", self.current_song)
        logger.warning("音乐播放失败: %s", error)

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

    async def _handle_playback_finished(self):
        if not self.is_playing:
            return
        logger.info(f"歌曲播放完成: {self.current_song}")
        await self.cancel_prefetch()
        if self.decoder:
            await self.decoder.stop()
            self.decoder = None
        if self.song_id and self._cache.find_song_file(self.song_id):
            self._library.invalidate()
            logger.debug(f"播放结束，本地缓存可用: {self.song_id}")

        if self._playback_task and not self._playback_task.done():
            if self._playback_task is not asyncio.current_task():
                await self._cancel_playback_task()
            else:
                self._playback_task = None

        self.is_playing = False
        self.paused = False
        self.pause_source = None
        self.current_position = self.total_duration
        self.current_lyric_index = -1
        await self.emit_state_change("completed", self.current_song)

    async def cancel_prefetch(self) -> None:
        await self._downloader.cancel_prefetch()
