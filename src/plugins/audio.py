"""音频插件.

负责音频采集、编码、播放和发送。
AudioCodec 经 Events.AUDIO_CODEC_CHANGED 发布，不直连 MusicPlayer。
"""

import asyncio
import os
import threading
import time
from collections import deque
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()

_UPLINK_BACKLOG_MS = 500


class AudioPlugin(Plugin):
    name = "audio"

    def __init__(self) -> None:
        super().__init__()
        self.codec: AudioCodec | None = None
        self._in_silence_period = False
        self._silence_until = 0.0
        self._uplink = deque(maxlen=25)
        self._uplink_lock = threading.Lock()
        self._uplink_ready = asyncio.Event()
        self._wake_pending = False
        self._accepting = False
        self._loop = None
        self._sender_task = None

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)

        if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
            logger.warning("XIAOZHI_DISABLE_AUDIO=1，音频插件以禁用模式运行")
            return

        try:
            from src.audio_codecs.audio_codec import AudioCodec

            self.codec = AudioCodec(
                config=ctx.get_config(), audio_config=ctx.audio_config
            )
            await self.codec.initialize()
            self.codec.set_encoded_callback(self._on_encoded_audio)
            self.codec.set_encode_gate(
                lambda: self._accepting and self._should_send_microphone_audio()
            )

            from src.core.event_bus import Events

            ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)
            ctx.event_bus.on(
                Events.AUDIO_DEVICES_REFRESH_REQUEST, self._on_devices_refresh_request
            )
            # codec 在 start() 再发布：MusicPlayer 在 McpPlugin.setup 中订阅 EventBus

        except Exception as e:
            logger.error(f"音频插件初始化失败: {e}", exc_info=True)
            # 保留已构造 codec 的所有权，供资源池重试 initialize 回滚中失败的关闭。
            self.mark_failed()
            raise

    async def start(self) -> None:
        await super().start()
        if self.codec and not self.failed:
            self._loop = asyncio.get_running_loop()
            self._uplink = deque(
                maxlen=max(
                    1, _UPLINK_BACKLOG_MS // self._ctx.audio_config.FRAME_DURATION
                )
            )
            self._accepting = True
            self._sender_task = self._cmd.spawn(self._consume_uplink(), "audio:uplink")
            await self._publish_audio_codec(self.codec)

    async def stop(self) -> None:
        self._accepting = False
        with self._uplink_lock:
            self._uplink.clear()
            self._wake_pending = False
        if self._sender_task is not None:
            self._sender_task.cancel()
            await asyncio.gather(self._sender_task, return_exceptions=True)
            self._sender_task = None
        await super().stop()

    async def _publish_audio_codec(self, codec) -> None:
        """向订阅者（如 MusicPlayer）发布 AudioCodec 实例或 None."""
        if not self._ctx or not self._ctx.event_bus:
            logger.warning(
                "无法发布 AUDIO_CODEC_CHANGED：PluginContext / EventBus 未就绪"
            )
            return
        from src.core.event_bus import Events

        try:
            await self._ctx.event_bus.emit(Events.AUDIO_CODEC_CHANGED, codec)
        except Exception as e:
            logger.warning(f"发布 AUDIO_CODEC_CHANGED 失败: {e}", exc_info=True)

    async def _on_config_changed(self, data=None):
        """配置变更时重新加载音频设备（含 PortAudio 重枚举）."""
        if self.codec and not self.failed:
            logger.info("AudioPlugin: 收到配置变更事件，重新加载音频设备")
            await self._publish_audio_codec(None)
            if await self.codec.reload_devices(reenumerate=True):
                await self._publish_audio_codec(self.codec)

    async def _on_devices_refresh_request(self, data=None):
        """设置页请求刷新设备列表：停流 → 重枚举 → 再开流.

        payload 可为 asyncio.Future，完成后 set_result(list_audio_devices 结果)。
        """
        future = data if isinstance(data, asyncio.Future) else None
        result = {"input": [], "output": []}
        try:
            if self.failed:
                return

            from src.utils.audio_utils import (
                list_audio_devices,
                refresh_portaudio_devices,
            )

            if self.codec:
                await self._publish_audio_codec(None)
                # 停流后才能安全 _terminate PortAudio
                self.codec.stop_streams_for_enumeration()
                refresh_portaudio_devices(reinitialize=True)
                result = list_audio_devices(include_virtual=True)
                # 按当前配置重新打开流（名称匹配可能已指向新 index）
                ok = await self.codec.reload_devices(reenumerate=False)
                if not ok:
                    logger.error("AudioPlugin: 设备刷新后重新打开音频流失败")
                else:
                    await self._publish_audio_codec(self.codec)
            else:
                # 无 codec（禁用音频）时仍尽量枚举，供设置页展示
                refresh_portaudio_devices(reinitialize=True)
                result = list_audio_devices(include_virtual=True)
            logger.info(
                "AudioPlugin: 设备刷新完成 "
                f"in={len(result.get('input', []))} out={len(result.get('output', []))}"
            )
        except Exception as e:
            logger.error(f"AudioPlugin: 设备刷新失败: {e}", exc_info=True)
        finally:
            if future is not None and not future.done():
                future.set_result(result)

    async def on_device_state_changed(self, state):
        """
        设备状态变化时处理.
        """
        if not self.codec or self.failed:
            return

        from src.constants.constants import DeviceState

        if state == DeviceState.LISTENING:
            self._silence_until = time.monotonic() + 0.2

    async def on_incoming_json(self, message) -> None:
        """
        处理 TTS 事件.
        """
        if not isinstance(message, dict):
            return

        try:
            if message.get("type") == "tts":
                state = message.get("state")
                if state == "start":
                    if self._music_parallel_enabled():
                        logger.debug("TTS 开始（并行模式）：音乐继续播放，混音闪避")
                    else:
                        await self._pause_music_for_tts()
                elif state == "stop":
                    # 并行模式也发恢复：兜底「TTS 期间起播的歌被置为 tts 暂停」
                    await self._resume_music_after_tts()
        except Exception as e:
            logger.error(f"处理 TTS 事件失败: {e}", exc_info=True)

    def _music_parallel_enabled(self) -> bool:
        """并行播放判定：AEC 引擎在位且配置允许时，TTS 不暂停音乐.

        引擎旁路（库缺失/连续失败自禁）时自动回退为暂停策略，
        避免无回声消除的裸并行污染识别。
        """
        try:
            config = self._ctx.get_config()
            if not bool(config.get_config("AEC_OPTIONS.MUSIC_PARALLEL", True)):
                return False
            return bool(self.codec and not self.failed and self.codec.aec_active)
        except Exception:
            return False

    async def on_incoming_audio(self, data: bytes) -> None:
        """
        接收并播放音频数据.
        """
        if self.codec and not self.failed:
            try:
                await self.codec.write_audio(data)
            except Exception as e:
                logger.debug(f"写入音频数据失败: {e}")

    async def _pause_music_for_tts(self):
        """TTS 开始时暂停音乐（TTS/音乐分队列混音，互不丢帧；音乐余量自然淡出）."""
        try:
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicControlRequest

            logger.info("TTS 开始，发送音乐暂停请求")
            await self._ctx.event_bus.emit(
                Events.MUSIC_PAUSE_REQUEST, MusicControlRequest(source="tts")
            )
        except Exception as e:
            logger.warning(f"发送音乐暂停请求失败: {e}", exc_info=True)

    async def _resume_music_after_tts(self):
        """TTS 结束后恢复音乐（并行模式下仅兜底，多数时候无实际暂停）."""
        try:
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicControlRequest

            log = logger.debug if self._music_parallel_enabled() else logger.info
            log("TTS 播放完成，发送音乐恢复请求")
            await self._ctx.event_bus.emit(
                Events.MUSIC_RESUME_REQUEST, MusicControlRequest(source="tts")
            )
        except Exception as e:
            logger.error(f"发送音乐恢复请求失败: {e}", exc_info=True)

    def register_resources(self, pool) -> None:
        codec = self.codec
        # failed 只阻止使用，已构造资源仍必须登记清理。
        if codec is not None:

            async def _cleanup():
                """音频编解码器完整清理：先通知订阅者清 codec，再 close."""
                import gc

                try:
                    # Music 收到 None 会自行 stop；完整 detach 由 mcp/容器负责
                    await self._publish_audio_codec(None)
                except Exception as e:
                    logger.debug(f"发布 codec 清除失败: {e}", exc_info=True)
                gc.collect()
                await codec.close()

            pool.register("audio.codec", _cleanup)

    def _on_encoded_audio(self, encoded_data: bytes) -> None:
        """Audio thread: bounded copies and at most one pending loop wakeup."""
        if (
            not self._accepting
            or self._loop is None
            or not self._should_send_microphone_audio()
        ):
            return
        generation = self._ctx.audio_generation
        with self._uplink_lock:
            if not self._accepting:
                return
            self._uplink.append((generation, encoded_data))
            if self._wake_pending:
                return
            self._wake_pending = True
        try:
            self._loop.call_soon_threadsafe(self._uplink_ready.set)
        except RuntimeError:
            with self._uplink_lock:
                self._uplink.clear()
                self._wake_pending = False

    async def _consume_uplink(self) -> None:
        while True:
            await self._uplink_ready.wait()
            while True:
                with self._uplink_lock:
                    if not self._uplink:
                        self._wake_pending = False
                        self._uplink_ready.clear()
                        break
                    generation, data = self._uplink.popleft()
                await self._send_audio_async(data, generation)

    async def _send_audio_async(
        self, encoded_data: bytes, generation: int | None = None
    ) -> None:
        try:
            if not self._ctx.is_audio_channel_opened():
                return
            if generation is not None and generation != self._ctx.audio_generation:
                return
            capture_allowed = await self._cmd.sync_audio_state()
            if generation is not None and generation != self._ctx.audio_generation:
                return
            if capture_allowed and self._should_send_microphone_audio():
                await self._cmd.send_audio(encoded_data)
        except Exception as e:
            logger.error(f"发送音频数据失败: {e}", exc_info=True)

    def _should_send_microphone_audio(self) -> bool:
        """
        判断是否应该发送麦克风音频.
        """
        try:
            if (
                self.failed
                or self._in_silence_period
                or time.monotonic() < self._silence_until
            ):
                return False
            return self._ctx.should_capture_audio()
        except Exception as e:
            logger.warning(
                f"判断是否发送麦克风音频失败，默认不发送: {e}", exc_info=True
            )
            return False
