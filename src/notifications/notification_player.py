"""流式播放服务端 ``notify`` 消息中的音频。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from src.audio_codecs.music_decoder import MusicDecoder
from src.constants.constants import AudioConfig
from src.logging import get_logger

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec
    from src.core.event_bus import EventBus

logger = get_logger()

_QUEUE_SIZE = 24
_FinishCallback = Callable[[int, bool], Awaitable[None]]


@dataclass(frozen=True)
class NotificationSubtitle:
    start_ms: int
    text: str


def parse_notification(
    message: dict[str, Any],
) -> tuple[str, list[NotificationSubtitle]] | None:
    """验证并标准化服务端通知字段。"""
    audio_url = message.get("audio_url")
    if not isinstance(audio_url, str):
        return None

    audio_url = audio_url.strip()
    parsed = urlparse(audio_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    raw_subtitles = message.get("subtitles", [])
    if raw_subtitles is None:
        raw_subtitles = []
    if not isinstance(raw_subtitles, list):
        return None

    subtitles: list[NotificationSubtitle] = []
    for item in raw_subtitles:
        if not isinstance(item, dict):
            continue
        start_ms = item.get("start_ms")
        text = item.get("text")
        if (
            isinstance(start_ms, bool)
            or not isinstance(start_ms, (int, float))
            or start_ms < 0
            or start_ms > 0xFFFFFFFF
            or not isinstance(text, str)
        ):
            logger.warning("忽略无效通知字幕")
            continue
        subtitles.append(NotificationSubtitle(start_ms=int(start_ms), text=text))

    subtitles.sort(key=lambda item: item.start_ms)
    return audio_url, subtitles


class NotificationPlayer:
    """仅承担一条 notify 的流式解码、播放与字幕进度。"""

    def __init__(self) -> None:
        self._event_bus: EventBus | None = None
        self._codec: AudioCodec | None = None
        self._decoder: MusicDecoder | None = None
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None
        self._drained_event: asyncio.Event | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

        self._generation = 0
        self._active_generation = 0
        self._active = False
        self._saw_audio = False
        self._played_samples = 0
        self._subtitles: list[NotificationSubtitle] = []
        self._next_subtitle_index = 0
        self._displayed_text = ""
        self._finished_callback: _FinishCallback | None = None

    @property
    def is_active(self) -> bool:
        return self._active

    def set_event_bus(self, event_bus: EventBus) -> None:
        """绑定 AudioCodec 生命周期事件。"""
        self.detach()
        self._event_bus = event_bus
        from src.core.event_bus import Events

        event_bus.on(Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed)

    def detach(self) -> None:
        if self._event_bus is not None:
            try:
                from src.core.event_bus import Events

                self._event_bus.off(
                    Events.AUDIO_CODEC_CHANGED, self._on_audio_codec_changed
                )
            except Exception as e:
                logger.debug(f"取消通知 AudioCodec 订阅失败: {e}")
        self._event_bus = None
        self._codec = None

    async def _on_audio_codec_changed(self, codec=None) -> None:
        if codec is None:
            await self.stop()
            self._codec = None
            return
        self._codec = codec
        logger.info("AudioCodec 已设置到 NotificationPlayer")

    async def start(
        self,
        audio_url: str,
        subtitles: list[NotificationSubtitle],
        finished_callback: _FinishCallback,
    ) -> int | None:
        """开始一条通知；成功时返回本次 generation。"""
        async with self._lock:
            if self._active or self._consumer_task is not None:
                logger.warning("已有通知正在播放，忽略新的 notify")
                return None
            if self._codec is None:
                logger.warning("AudioCodec 未就绪，忽略 notify")
                return None

            self._generation += 1
            generation = self._generation
            self._active_generation = generation
            self._active = True
            self._saw_audio = False
            self._played_samples = 0
            self._subtitles = subtitles
            self._next_subtitle_index = 0
            self._displayed_text = ""
            self._finished_callback = finished_callback
            self._queue = asyncio.Queue(maxsize=_QUEUE_SIZE)
            self._drained_event = asyncio.Event()
            self._decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )
            self._loop = asyncio.get_running_loop()
            codec = self._codec
            decoder = self._decoder
            queue = self._queue
            codec.set_notification_playback_callbacks(
                lambda samples: self._on_audio_progress(generation, samples),
                lambda: self._on_audio_drained(generation),
            )

        started = await decoder.start_decode(audio_url, queue)
        if not started:
            await self._reset_after_failed_start(generation, codec)
            return None

        task = asyncio.create_task(
            self._consume(generation, codec, decoder, queue),
            name="notification:playback",
        )
        async with self._lock:
            if self._active and self._active_generation == generation:
                self._consumer_task = task
                return generation
        task.cancel()
        await decoder.stop()
        return None

    async def stop(self) -> None:
        """取消当前通知并立即清空其 PCM 余量。"""
        async with self._lock:
            if not self._active and self._consumer_task is None:
                return
            self._generation += 1
            self._active = False
            self._active_generation = 0
            decoder = self._decoder
            consumer_task = self._consumer_task
            codec = self._codec
            self._decoder = None
            self._consumer_task = None
            self._queue = None
            self._drained_event = None
            self._finished_callback = None
            self._subtitles = []

        if codec is not None:
            codec.set_notification_playback_callbacks()
            await codec.clear_notification_queue()
        if decoder is not None:
            await decoder.stop()
        if (
            consumer_task is not None
            and not consumer_task.done()
            and consumer_task is not asyncio.current_task()
        ):
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"等待通知播放任务退出失败: {e}")

    async def _reset_after_failed_start(
        self, generation: int, codec: AudioCodec
    ) -> None:
        async with self._lock:
            if self._active_generation != generation:
                return
            self._active = False
            self._active_generation = 0
            self._decoder = None
            self._queue = None
            self._drained_event = None
            self._finished_callback = None
            self._subtitles = []
        codec.set_notification_playback_callbacks()
        await codec.clear_notification_queue()

    async def _consume(
        self,
        generation: int,
        codec: AudioCodec,
        decoder: MusicDecoder,
        queue: asyncio.Queue,
    ) -> None:
        success = False
        try:
            while True:
                try:
                    pcm = await asyncio.wait_for(queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    if not decoder.is_running():
                        logger.warning("通知解码器提前停止")
                        break
                    continue

                if pcm is None:
                    if not self._saw_audio:
                        logger.warning("通知音频没有可播放内容")
                        break
                    drained_event = self._drained_event
                    if drained_event is not None:
                        await drained_event.wait()
                    success = True
                    break

                if not self._is_current(generation):
                    return
                self._saw_audio = True
                drained_event = self._drained_event
                if drained_event is not None:
                    drained_event.clear()
                await codec.write_notification_pcm(pcm)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"通知播放失败: {e}", exc_info=True)
        finally:
            await self._finish(generation, success)

    def _is_current(self, generation: int) -> bool:
        return self._active and self._active_generation == generation

    def _on_audio_progress(self, generation: int, samples: int) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._record_audio_progress, generation, samples)

    def _record_audio_progress(self, generation: int, samples: int) -> None:
        if not self._is_current(generation):
            return
        self._played_samples += samples
        position_ms = int(self._played_samples * 1000 / AudioConfig.OUTPUT_SAMPLE_RATE)
        text = None
        while (
            self._next_subtitle_index < len(self._subtitles)
            and self._subtitles[self._next_subtitle_index].start_ms <= position_ms
        ):
            text = self._subtitles[self._next_subtitle_index].text
            self._next_subtitle_index += 1

        if text is not None and text != self._displayed_text:
            self._displayed_text = text
            asyncio.create_task(
                self._emit_subtitle(generation, text), name="notification:subtitle"
            )

    def _on_audio_drained(self, generation: int) -> None:
        loop = self._loop
        if loop is not None:
            loop.call_soon_threadsafe(self._mark_audio_drained, generation)

    def _mark_audio_drained(self, generation: int) -> None:
        if not self._is_current(generation):
            return
        if self._drained_event is not None:
            self._drained_event.set()

    async def _emit_subtitle(self, generation: int, text: str) -> None:
        if not self._is_current(generation) or self._event_bus is None:
            return
        from src.core.event_bus import Events

        await self._event_bus.emit(Events.NOTIFICATION_SUBTITLE, text)

    async def _finish(self, generation: int, success: bool) -> None:
        async with self._lock:
            if not self._is_current(generation):
                return
            callback = self._finished_callback
            codec = self._codec
            decoder = self._decoder
            self._active = False
            self._active_generation = 0
            self._decoder = None
            self._consumer_task = None
            self._queue = None
            self._drained_event = None
            self._finished_callback = None
            self._subtitles = []

        if codec is not None:
            codec.set_notification_playback_callbacks()
            if not success:
                await codec.clear_notification_queue()
        if decoder is not None:
            await decoder.stop()
        if callback is not None:
            try:
                await callback(generation, success)
            except Exception as e:
                logger.error(f"通知完成回调失败: {e}", exc_info=True)
