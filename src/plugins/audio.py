"""音频插件.

负责音频采集、编码、播放和发送。
AudioCodec 经 Events.AUDIO_CODEC_CHANGED 发布，不直连 MusicPlayer。
"""

import asyncio
import os
from typing import TYPE_CHECKING

from src.audio_codecs.audio_codec import AudioCodec
from src.logging import get_logger
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()

MAX_CONCURRENT_AUDIO_SENDS = 4


class AudioPlugin(Plugin):
    name = "audio"
    priority = 10  # 最高优先级，其他插件依赖 audio_codec

    def __init__(self) -> None:
        super().__init__()
        self.codec: AudioCodec | None = None
        self._send_sem = asyncio.Semaphore(MAX_CONCURRENT_AUDIO_SENDS)
        self._in_silence_period = False

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)

        if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
            logger.warning("XIAOZHI_DISABLE_AUDIO=1，音频插件以禁用模式运行")
            return

        try:
            self.codec = AudioCodec()
            await self.codec.initialize()
            self.codec.set_encoded_callback(self._on_encoded_audio)

            from src.core.event_bus import Events

            ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)
            ctx.event_bus.on(
                Events.AUDIO_DEVICES_REFRESH_REQUEST, self._on_devices_refresh_request
            )
            # codec 在 start() 再发布：MusicPlayer 在 McpPlugin.setup 中订阅 EventBus

        except Exception as e:
            logger.error(f"音频插件初始化失败: {e}", exc_info=True)
            self.codec = None
            self.mark_failed()
            raise

    async def start(self) -> None:
        await super().start()
        if self.codec and not self.failed:
            await self._publish_audio_codec(self.codec)

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
        if self.codec:
            logger.info("AudioPlugin: 收到配置变更事件，重新加载音频设备")
            await self.codec.reload_devices(reenumerate=True)

    async def _on_devices_refresh_request(self, data=None):
        """设置页请求刷新设备列表：停流 → 重枚举 → 再开流.

        payload 可为 asyncio.Future，完成后 set_result(list_audio_devices 结果)。
        """
        from src.utils.audio_utils import list_audio_devices, refresh_portaudio_devices

        future = data if isinstance(data, asyncio.Future) else None
        result = {"input": [], "output": []}
        try:
            if self.codec:
                # 停流后才能安全 _terminate PortAudio
                self.codec.stop_streams_for_enumeration()
                refresh_portaudio_devices(reinitialize=True)
                result = list_audio_devices(include_virtual=True)
                # 按当前配置重新打开流（名称匹配可能已指向新 index）
                ok = await self.codec.reload_devices(reenumerate=False)
                if not ok:
                    logger.error("AudioPlugin: 设备刷新后重新打开音频流失败")
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
        if not self.codec:
            return

        from src.constants.constants import DeviceState

        if state == DeviceState.LISTENING:
            self._in_silence_period = True
            try:
                await asyncio.sleep(0.2)
            finally:
                self._in_silence_period = False

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
                    await self._pause_music_for_tts()
                elif state == "stop":
                    await self._resume_music_after_tts()
        except Exception as e:
            logger.error(f"处理 TTS 事件失败: {e}", exc_info=True)

    async def on_incoming_audio(self, data: bytes) -> None:
        """
        接收并播放音频数据.
        """
        if self.codec:
            try:
                await self.codec.write_audio(data)
            except Exception as e:
                logger.debug(f"写入音频数据失败: {e}")

    async def _pause_music_for_tts(self):
        """TTS 开始时暂停音乐（不清空 output_buffer，避免丢弃 TTS 帧）."""
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
        """TTS 结束后恢复音乐"""
        try:
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicControlRequest

            logger.info("TTS 播放完成，发送音乐恢复请求")
            await self._ctx.event_bus.emit(
                Events.MUSIC_RESUME_REQUEST, MusicControlRequest(source="tts")
            )
        except Exception as e:
            logger.error(f"发送音乐恢复请求失败: {e}", exc_info=True)

    def register_resources(self, pool) -> None:
        codec = self.codec
        if codec:

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
        """
        音频编码回调（从音频线程调用）.
        """
        try:
            if not self._cmd:
                return
            self._cmd.schedule_command_nowait(self._send_audio_async, encoded_data)
        except Exception as e:
            logger.error(f"调度音频发送失败: {e}", exc_info=True)

    async def _send_audio_async(self, encoded_data: bytes) -> None:
        """
        异步发送音频数据.
        """
        async with self._send_sem:
            try:
                if not self._ctx.is_audio_channel_opened():
                    return
                if self._should_send_microphone_audio():
                    await self._cmd.send_audio(encoded_data)
            except Exception as e:
                logger.error(f"发送音频数据失败: {e}", exc_info=True)

    def _should_send_microphone_audio(self) -> bool:
        """
        判断是否应该发送麦克风音频.
        """
        try:
            if self._in_silence_period:
                return False
            return self._ctx.should_capture_audio()
        except Exception as e:
            logger.warning(
                f"判断是否发送麦克风音频失败，默认不发送: {e}", exc_info=True
            )
            return False
