"""播放引擎：解码队列、启停/暂停/恢复/跳转与写入 AudioCodec.

由 MusicPlayer 持有；不依赖宿主 self 字段（经 hooks 回调节奏/上下文）。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from urllib.parse import urlparse

import numpy as np

from src.audio_codecs.music_decoder import MusicDecoder, is_http_url
from src.constants.constants import AudioConfig
from src.logging import get_logger

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec
    from src.mcp.tools.music.cache import MusicCache
    from src.mcp.tools.music.download import MusicDownloader
    from src.mcp.tools.music.local_library import LocalLibrary

logger = get_logger()


class PlaybackHooks(Protocol):
    """MusicPlayer 提供给引擎的回调."""

    def prepare_for_io(self) -> None: ...

    def is_speaking(self) -> bool: ...

    def format_time(self, seconds: float) -> str: ...

    async def tick_lyrics(self) -> None: ...

    async def emit_state_change(
        self,
        state: str,
        song_name: str | None = None,
        position: float | None = None,
    ) -> None: ...


@dataclass
class PlaybackDeps:
    cache: MusicCache
    downloader: MusicDownloader
    library: LocalLibrary
    hooks: PlaybackHooks


class PlaybackEngine:
    """播放状态机；状态字段挂在本实例上."""

    def __init__(self, deps: PlaybackDeps) -> None:
        self._cache = deps.cache
        self._downloader = deps.downloader
        self._library = deps.library
        self._hooks = deps.hooks

        self.audio_codec: AudioCodec | None = None
        self.decoder: MusicDecoder | None = None
        self._music_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._playback_task: asyncio.Task | None = None

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

    def _get_audio_codec(self) -> AudioCodec | None:
        if self.audio_codec is None:
            logger.warning("AudioCodec 未设置，音乐播放功能不可用")
        return self.audio_codec

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
            audio_codec = self._get_audio_codec()
            if audio_codec:
                await audio_codec.clear_music_queue()
            logger.debug(f"停止时清空 {cleared} 帧音乐数据")

            self.is_playing = False
            self.paused = False
            self.pause_source = None
            self.current_position = 0
            self.current_lyric_index = -1
            self.api_url = None

            await self._hooks.emit_state_change("stopped", current_song)
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
                if self.pause_source != source:
                    old = self.pause_source
                    self.pause_source = source
                    logger.info(f"更新暂停来源: {old} → {source}")
                return {"status": "info", "message": "已经处于暂停状态"}

            self.paused = True
            self.pause_source = source
            if self.start_play_time > 0:
                self.current_position = time.time() - self.start_play_time

            fmt = self._hooks.format_time

            if source == "tts":
                # TTS 逐句闪避：保留解码器与队列（解码器会在满队列处
                # 自然等位），恢复零成本，不用逐句重启 ffmpeg
                logger.info(
                    f"暂停播放(tts, 保留解码器): {self.current_song} "
                    f"at {fmt(self.current_position)}"
                )
                return {"status": "success", "message": "已暂停"}

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
                    f"{self._hooks.format_time(self.current_position)}"
                )
                await self._hooks.emit_state_change("playing", self.current_song)
                return {"status": "success", "message": "已恢复播放"}

            if self.api_url:
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

            fmt = self._hooks.format_time
            logger.info(
                f"恢复播放: {self.current_song} from {fmt(self.current_position)}"
            )

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
            if is_http_url(self._current_source) and self.song_id:
                self._downloader.start_prefetch(
                    str(self._current_source),
                    self.song_id,
                    self._stream_headers,
                )

            success = await self.decoder.start_decode(
                self._current_source,
                self._music_queue,
                self.current_position,
                headers=self._stream_headers,
            )
            if not success:
                return {"status": "error", "message": "恢复播放失败"}

            self.paused = False
            self.pause_source = None
            self.start_play_time = time.time() - self.current_position
            self.last_lyric_tick = 0.0
            self._playback_task = asyncio.create_task(
                self._playback_loop(), name="music:playback"
            )
            await self._hooks.emit_state_change("playing", self.current_song)
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

            if self.total_duration <= 0 and not is_http_url(self._current_source):
                duration = await MusicDecoder.get_duration(self._current_source)
                if duration > 0:
                    self.total_duration = duration

            target: float | None = None
            fmt = self._hooks.format_time
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

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            await asyncio.sleep(0.05)
            cleared = await self._clear_music_queue()
            audio_codec = self._get_audio_codec()
            if audio_codec:
                # 只清音乐播放队列；TTS 队列独立，不受跳转影响
                await audio_codec.clear_music_queue()

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

    async def _refresh_stream_source(self) -> bool:
        if not self.api_url:
            return bool(self._current_source)
        self._hooks.prepare_for_io()
        media_url = await self._downloader.resolve_play_url(
            self.api_url, song_id=self.song_id or None
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
        if self.song_id:
            self._downloader.start_prefetch(
                media_url, self.song_id, self._stream_headers
            )
        return True

    async def play_url(self, api_url: str) -> bool:
        try:
            if not self._get_audio_codec():
                logger.error("无法获取 AudioCodec，播放失败")
                return False

            if self.is_playing:
                await self.stop()

            self._hooks.prepare_for_io()
            self.api_url = api_url

            if self.song_id:
                cached = self._cache.find_song_file(self.song_id)
                if cached is not None:
                    logger.info(f"使用本地缓存播放: {cached}")
                    self.api_url = None
                    duration = await MusicDecoder.get_duration(cached)
                    if duration > 0:
                        self.total_duration = duration
                    return await self.start_playback(cached)

            if self._hooks.is_speaking():
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
            if self.song_id:
                self._downloader.start_prefetch(media_url, self.song_id, headers)
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
        try:
            self._current_source = source
            self._stream_headers = headers if is_http_url(source) else None

            if self._hooks.is_speaking():
                logger.info("TTS 进行中，本地音源已就绪，说完再播")
                if self.decoder:
                    await self.decoder.stop()
                    self.decoder = None
                await self._cancel_playback_task()
                await self._clear_music_queue()
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

            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            success = await self.decoder.start_decode(
                source,
                self._music_queue,
                start_position,
                headers=self._stream_headers,
            )
            if not success:
                logger.error("启动音频解码器失败")
                return False

            self.is_playing = True
            self.paused = False
            self.pause_source = None
            self.current_position = start_position
            self.start_play_time = time.time() - start_position
            self.current_lyric_index = -1
            self.last_lyric_tick = 0.0

            self._playback_task = asyncio.create_task(
                self._playback_loop(), name="music:playback"
            )

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(f"开始播放: {self.current_song}{position_info}")
            await self._hooks.emit_state_change(
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

                await self._hooks.tick_lyrics()

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
        self.current_position = self.total_duration
        self.current_lyric_index = -1
        await self._hooks.emit_state_change("completed", self.current_song)

    def cancel_prefetch(self) -> None:
        try:
            self._downloader.cancel_prefetch()
        except Exception:
            pass
