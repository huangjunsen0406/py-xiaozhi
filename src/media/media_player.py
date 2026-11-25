"""宿主唯一、无音源依赖的通用媒体播放器.

职责：
- 播放任意经校验的 HTTP(S) 音频流或本地音频文件（基于 AudioDecoder）；
- 向 AudioCodec 的 background 轨道写入 PCM（前景 TTS/通知自动闪避）；
- 自主监听 EventBus（AUDIO_CODEC_CHANGED / SESSION_MESSAGE），在 TTS 期间按
  AEC 在位状态自动选择「并行混音闪避」或「临时暂停 + 播完恢复」，彻底解耦 AudioPlugin；
- 记录当前播放归属 owner_id，支持外挂插件卸载时精准停播。
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from src.audio_codecs.audio_decoder import AudioDecoder, is_http_url
from src.constants.constants import AudioConfig
from src.logging import get_logger

from .events import MediaStateData, MediaSubtitleData, format_duration
from .validation import sanitize_headers, validate_media_source

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec
    from src.audio_codecs.mixer import AudioTrackHandle
    from src.core.event_bus import EventBus

logger = get_logger()

_MEDIA_QUEUE_SIZE = 100


async def _await_cleanup(task: asyncio.Task) -> Any:
    """屏蔽外层取消直到清理任务结束，避免资源半销毁。"""
    cancelled = False
    while True:
        try:
            result = await asyncio.shield(task)
            break
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return result


def _default_title(source: str, *, is_http: bool) -> str:
    if is_http:
        parsed = urlparse(source)
        leaf = Path(parsed.path).name
        return leaf or parsed.hostname or "在线音频"
    return Path(source).stem or Path(source).name


class MediaPlayer:
    """宿主通用媒体播放器（零音源业务）."""

    def __init__(
        self,
        config=None,
        audio_config: AudioConfig | None = None,
    ) -> None:
        from src.utils.config_manager import ConfigManager

        self._config = config if config is not None else ConfigManager.from_dict()
        self._default_audio_config = (
            audio_config
            if audio_config is not None
            else AudioConfig.from_config(self._config)
        )
        self._event_bus: EventBus | None = None
        self._is_speaking: Callable[[], bool] = lambda: False

        self._codec: AudioCodec | None = None
        self._track: AudioTrackHandle | None = None
        self._decoder: AudioDecoder | None = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=_MEDIA_QUEUE_SIZE)
        self._playback_task: asyncio.Task | None = None
        self._decode_start_task: asyncio.Task | None = None
        self._stop_task: asyncio.Task | None = None
        self._start_lock = asyncio.Lock()

        self._generation = 0
        self._codec_generation = 0

        self.is_playing = False
        self.paused = False
        self.pause_source: str | None = None
        self.current_title = ""
        self.current_source = ""
        self._current_headers: dict[str, str] | None = None
        self.total_duration = 0.0
        self.current_position = 0.0
        self.start_play_time = 0.0
        self.last_error: str | None = None
        self._owner_id: str | None = None

    @property
    def owner_id(self) -> str | None:
        return self._owner_id

    def attach(self, event_bus: EventBus, plugin_ctx=None) -> None:
        """绑定 EventBus（AudioCodec 变更 + 会话 TTS 自主焦点协调）."""
        self._unbind_event_bus()
        self._event_bus = event_bus
        self._is_speaking = (
            plugin_ctx.is_speaking if plugin_ctx is not None else (lambda: False)
        )
        from src.core.event_bus import Events

        event_bus.on(Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed)
        event_bus.on(Events.SESSION_MESSAGE, self._on_session_message)

    def _unbind_event_bus(self) -> None:
        if self._event_bus is None:
            return
        try:
            from src.core.event_bus import Events

            self._event_bus.off(
                Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed
            )
            self._event_bus.off(Events.SESSION_MESSAGE, self._on_session_message)
        except Exception as exc:
            logger.debug("MediaPlayer 取消 EventBus 订阅失败: %s", exc)
        self._event_bus = None

    async def bind_audio_codec(self, codec: AudioCodec | None = None) -> None:
        self._codec_generation += 1
        binding = self._codec_generation
        if codec is self._codec and codec is not None:
            return
        try:
            await self.stop()
        finally:
            if binding == self._codec_generation:
                self._codec = codec
                self._track = (
                    codec.get_background_track() if codec is not None else None
                )

    async def detach(self) -> None:
        self._generation += 1

        async def _close() -> None:
            try:
                await self.bind_audio_codec(None)
            finally:
                self._is_speaking = lambda: False
                self._unbind_event_bus()

        await _await_cleanup(asyncio.create_task(_close()))

    async def _on_audio_codec_changed(self, codec=None) -> None:
        await self.bind_audio_codec(codec)
        if codec is not None:
            logger.info("AudioCodec 已绑定到 MediaPlayer")

    def _media_parallel_enabled(self) -> bool:
        """并行播放判定：AEC 在位且配置允许时，TTS 期间继续播并由混音器闪避."""
        try:
            parallel = self._config.get_config("AEC_OPTIONS.MEDIA_PARALLEL", None)
            if parallel is None:
                parallel = self._config.get_config("AEC_OPTIONS.MUSIC_PARALLEL", True)
            if not bool(parallel):
                return False
            return bool(self._codec is not None and self._codec.aec_active)
        except Exception:
            return False

    async def _on_session_message(self, message: Any) -> None:
        """自主 Audio Focus：监听 TTS 起止，决定闪避并行还是临时暂停/恢复."""
        if not isinstance(message, dict) or message.get("type") != "tts":
            return
        state = message.get("state")
        if state == "start":
            if self._media_parallel_enabled():
                logger.debug("TTS 开始（并行模式）：背景媒体继续播放并由混音器闪避")
            elif self.is_playing and not self.paused:
                logger.info("TTS 开始，临时暂停背景媒体")
                await self.pause(source="tts")
        elif state == "stop":
            if self.is_playing and self.paused and self.pause_source == "tts":
                logger.info("TTS 结束，恢复背景媒体播放")
                await self.resume()

    def _make_decoder(self) -> AudioDecoder:
        audio_config = getattr(
            self._codec, "audio_config", self._default_audio_config
        )
        return AudioDecoder(
            sample_rate=audio_config.OUTPUT_SAMPLE_RATE,
            channels=audio_config.CHANNELS,
            frame_duration=audio_config.FRAME_DURATION,
        )

    def _position_now(self) -> float:
        if not self.is_playing:
            return 0.0
        if self.paused:
            return self.current_position
        if self.start_play_time > 0:
            pos = time.time() - self.start_play_time
            if self.total_duration > 0:
                return min(pos, self.total_duration)
            return pos
        return self.current_position

    async def _emit_state(
        self,
        state: str,
        *,
        title: str | None = None,
        position: float | None = None,
        owner_id: str | None = None,
    ) -> None:
        if self._event_bus is None:
            return
        from src.core.event_bus import Events

        await self._event_bus.emit(
            Events.MEDIA_STATE_CHANGED,
            MediaStateData(
                state=state,
                title=self.current_title if title is None else title,
                position=self._position_now() if position is None else position,
                duration=self.total_duration,
                pause_source=self.pause_source if state == "paused" else None,
                owner_id=self._owner_id if owner_id is None else owner_id,
            ),
        )

    def _clear_local_queue(self) -> int:
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    async def _cancel_playback_task(self) -> None:
        task = self._playback_task
        if task is None or task.done():
            self._playback_task = None
            return
        self._playback_task = None
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("等待媒体播放任务结束异常: %s", exc)

    async def _teardown_pipeline(
        self,
        *,
        clear_track: bool = False,
        cancel_startup: bool = False,
    ) -> int:
        await self._cancel_playback_task()
        if cancel_startup:
            startup = self._decode_start_task
            if startup is not None:
                if not startup.done():
                    startup.cancel()
                await asyncio.gather(startup, return_exceptions=True)
                if self._decode_start_task is startup:
                    self._decode_start_task = None
        decoder, self._decoder = self._decoder, None
        if decoder is not None:
            await decoder.stop()
        cleared = self._clear_local_queue()
        if clear_track and self._track is not None:
            await self._track.clear()
        return cleared

    async def play_url(
        self,
        source: str | Path,
        *,
        title: str = "",
        start_position: float = 0.0,
        headers: Mapping[str, str] | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        """播放 HTTP(S) 音频流或本地绝对路径音频文件."""
        try:
            normalized, is_http = validate_media_source(source)
            clean_headers = sanitize_headers(headers) if is_http else None
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

        if self._codec is None or self._track is None:
            return {"status": "error", "message": "音频输出设备未就绪"}

        try:
            start_pos = max(0.0, float(start_position or 0.0))
        except (TypeError, ValueError):
            start_pos = 0.0

        display_title = (title or "").strip() or _default_title(
            normalized, is_http=is_http
        )

        # 停止旧流并抢占新代际
        await self.stop()
        self._generation += 1
        generation = self._generation

        self.current_title = display_title
        self.current_source = normalized
        self._current_headers = clean_headers
        self._owner_id = owner_id
        self.total_duration = 0.0
        self.current_position = start_pos
        self.start_play_time = 0.0
        self.last_error = None

        duration = await AudioDecoder.get_duration(normalized, headers=clean_headers)
        if generation != self._generation:
            return {"status": "info", "message": "播放请求已取消"}
        if duration > 0:
            self.total_duration = duration
            if start_pos >= duration:
                start_pos = 0.0
                self.current_position = 0.0

        ok = await self._start_playback(
            normalized,
            start_position=start_pos,
            headers=clean_headers,
            generation=generation,
        )
        if not ok:
            detail = self.last_error or "播放启动失败"
            return {"status": "error", "message": f"播放失败: {detail}"}

        return {
            "status": "success",
            "message": f"正在播放: {self.current_title}",
            "title": self.current_title,
            "duration": format_duration(self.total_duration),
            "total_seconds": self.total_duration,
            "owner_id": self._owner_id,
        }

    async def _start_playback(
        self,
        source: str,
        *,
        start_position: float,
        headers: dict[str, str] | None,
        generation: int,
    ) -> bool:
        async with self._start_lock:
            if generation != self._generation:
                return False
            if self._codec is None or self._track is None:
                self.last_error = "音频输出设备未就绪"
                return False

            # TTS 正在说话且未启用并行模式时，先占住播放会话，TTS 结束自动开流
            if self._is_speaking() and not self._media_parallel_enabled():
                logger.info("TTS 进行中，先占住媒体会话，说完自动播放: %s", self.current_title)
                await self._teardown_pipeline(clear_track=False)
                if generation != self._generation:
                    return False
                self.is_playing = True
                self.paused = True
                self.pause_source = "tts"
                self.current_position = start_position
                self.start_play_time = 0.0
                return True

            await self._teardown_pipeline(clear_track=True)
            if generation != self._generation:
                return False

            decoder = self._make_decoder()
            self._decoder = decoder
            startup = asyncio.create_task(
                decoder.start_decode(
                    source,
                    self._queue,
                    start_position=start_position,
                    headers=headers if is_http_url(source) else None,
                ),
                name="media:decoder-start",
            )
            self._decode_start_task = startup
            try:
                started = await startup
            except asyncio.CancelledError:
                await decoder.stop()
                if self._decoder is decoder:
                    self._decoder = None
                return False
            finally:
                if self._decode_start_task is startup:
                    self._decode_start_task = None

            if not started or generation != self._generation:
                await decoder.stop()
                if self._decoder is decoder:
                    self._decoder = None
                if not started:
                    self.last_error = decoder.error or "无法启动音频解码器"
                return False

            self.is_playing = True
            self.paused = False
            self.pause_source = None
            self.current_position = start_position
            self.start_play_time = time.time() - start_position
            self._playback_task = asyncio.create_task(
                self._playback_loop(generation, decoder),
                name="media:playback",
            )
            await self._emit_state("playing")
            return True

    async def _playback_loop(self, generation: int, decoder: AudioDecoder) -> None:
        completed = False
        failed = False
        try:
            while self.is_playing and generation == self._generation:
                if self.paused:
                    await asyncio.sleep(0.05)
                    continue
                try:
                    pcm = await asyncio.wait_for(self._queue.get(), timeout=2.0)
                except asyncio.TimeoutError:
                    if not decoder.is_running():
                        failed = not decoder.completed_successfully
                        completed = decoder.completed_successfully
                        break
                    continue

                if generation != self._generation:
                    return
                if pcm is None:
                    completed = decoder.completed_successfully
                    failed = not completed
                    break

                track = self._track
                if track is None:
                    failed = True
                    self.last_error = "音频输出已断开"
                    break
                await track.write_pcm(pcm)

            if generation != self._generation:
                return

            if failed:
                self.last_error = decoder.error or "音频解码失败"
                self.is_playing = False
                self.paused = False
                self.pause_source = None
                await self._emit_state("error")
            elif completed:
                self.is_playing = False
                self.paused = False
                self.pause_source = None
                self.current_position = self.total_duration
                await self._emit_state("completed")
        except asyncio.CancelledError:
            return
        except Exception as exc:
            logger.error("媒体播放循环异常: %s", exc, exc_info=True)
            if generation == self._generation:
                self.last_error = str(exc)
                self.is_playing = False
                self.paused = False
                self.pause_source = None
                await self._emit_state("error")
        finally:
            if self._decoder is decoder and not self.is_playing:
                self._decoder = None
                await decoder.stop()

    async def pause(self, *, source: str = "manual") -> dict[str, Any]:
        return await _await_cleanup(asyncio.create_task(self._pause(source)))

    async def _pause(self, source: str) -> dict[str, Any]:
        if not self.is_playing:
            return {"status": "info", "message": "当前没有正在播放的媒体"}

        if self.paused:
            if self.pause_source != source:
                self.pause_source = source
            if source != "tts":
                self._generation += 1
                await self._teardown_pipeline(clear_track=True)
            return {"status": "info", "message": "已经处于暂停状态"}

        self.paused = True
        self.pause_source = source
        if self.start_play_time > 0:
            self.current_position = max(0.0, time.time() - self.start_play_time)

        if source == "tts":
            # TTS 临时闪避：保留解码器与队列，恢复零成本
            return {"status": "success", "message": "已暂停"}

        self._generation += 1
        await self._teardown_pipeline(clear_track=True)
        await self._emit_state("paused")
        return {"status": "success", "message": f"已暂停: {self.current_title}"}

    async def resume(self) -> dict[str, Any]:
        if not self.is_playing:
            return {"status": "info", "message": "当前没有正在播放的媒体"}
        if not self.paused:
            return {"status": "info", "message": "当前未暂停"}

        # 快速路径：TTS 临时暂停且解码管线仍在
        if (
            self._decoder is not None
            and self.pause_source == "tts"
            and self._playback_task is not None
            and not self._playback_task.done()
        ):
            self.paused = False
            self.pause_source = None
            self.start_play_time = time.time() - self.current_position
            await self._emit_state("playing")
            return {"status": "success", "message": f"已恢复播放: {self.current_title}"}

        if not self.current_source:
            return {"status": "error", "message": "没有可恢复的媒体地址"}

        self._generation += 1
        ok = await self._start_playback(
            self.current_source,
            start_position=self.current_position,
            headers=self._current_headers,
            generation=self._generation,
        )
        if not ok:
            return {
                "status": "error",
                "message": f"恢复播放失败: {self.last_error or '未知原因'}",
            }
        return {"status": "success", "message": f"已恢复播放: {self.current_title}"}

    async def stop(self, *, only_owner: str | None = None) -> dict[str, Any]:
        if only_owner is not None and self._owner_id != only_owner:
            return {"status": "info", "message": "当前播放不属于该插件"}

        self._generation += 1
        task = self._stop_task
        if task is None or task.done():
            task = asyncio.create_task(self._stop_playback(), name="media:stop")
            self._stop_task = task
        try:
            return await _await_cleanup(task)
        finally:
            if self._stop_task is task and task.done():
                self._stop_task = None

    async def _stop_playback(self) -> dict[str, Any]:
        was_playing = self.is_playing
        title = self.current_title
        owner = self._owner_id
        self.is_playing = False
        self.paused = False
        self.pause_source = None
        self._owner_id = None
        await self._teardown_pipeline(clear_track=was_playing, cancel_startup=True)
        if not was_playing:
            return {"status": "info", "message": "当前没有正在播放的媒体"}
        self.current_position = 0.0
        self.start_play_time = 0.0
        await self._emit_state("stopped", title=title, position=0.0, owner_id=owner)
        return {"status": "success", "message": "已停止播放"}

    async def seek(
        self,
        *,
        position: float | None = None,
        percent: float | None = None,
    ) -> dict[str, Any]:
        if not self.is_playing or not self.current_source:
            return {"status": "info", "message": "当前没有正在播放的媒体"}

        if percent is not None:
            if self.total_duration <= 0:
                return {"status": "error", "message": "当前媒体总时长未知，无法按百分比跳转"}
            pct = max(0.0, min(100.0, float(percent)))
            target = self.total_duration * pct / 100.0
        elif position is not None:
            target = max(0.0, float(position))
            if self.total_duration > 0:
                target = min(target, self.total_duration)
        else:
            return {"status": "error", "message": "请提供 position（秒）或 percent（0~100）"}

        self._generation += 1
        ok = await self._start_playback(
            self.current_source,
            start_position=target,
            headers=self._current_headers,
            generation=self._generation,
        )
        if not ok:
            return {
                "status": "error",
                "message": f"跳转失败: {self.last_error or '未知原因'}",
            }
        return {
            "status": "success",
            "message": f"已跳转到 {format_duration(target)}",
            "position": target,
        }

    async def get_status(self) -> dict[str, Any]:
        position = self._position_now()
        duration = self.total_duration
        progress = int(position * 100 / duration) if duration > 0 else 0
        if self.last_error and not self.is_playing:
            state = "error"
            state_label = f"播放失败: {self.last_error}"
        elif not self.is_playing:
            state = "idle"
            state_label = "未播放"
        elif self.paused and self.pause_source == "manual":
            state = "paused"
            state_label = "已暂停"
        else:
            state = "playing"
            state_label = "播放中"

        return {
            "status": "error" if state == "error" else "success",
            "state": state,
            "title": self.current_title,
            "position": round(position, 2),
            "duration": round(duration, 2),
            "progress": progress,
            "pause_source": self.pause_source,
            "owner_id": self._owner_id,
            "error": self.last_error,
            "message": (
                f"当前媒体: {self.current_title or '无'}\n"
                f"播放状态: {state_label}\n"
                f"当前位置: {format_duration(position)} / {format_duration(duration)} ({progress}%)"
            ),
        }

    async def set_subtitle(
        self, text: str, *, owner_id: str | None = None
    ) -> dict[str, Any]:
        if (
            owner_id is not None
            and self.is_playing
            and self._owner_id is not None
            and self._owner_id != owner_id
        ):
            return {"status": "info", "message": "当前播放不属于该插件，忽略字幕更新"}
        clean = str(text or "").strip()
        if self._event_bus is not None:
            from src.core.event_bus import Events

            await self._event_bus.emit(
                Events.MEDIA_SUBTITLE_UPDATE,
                MediaSubtitleData(text=clean, owner_id=owner_id),
            )
        return {"status": "success"}
