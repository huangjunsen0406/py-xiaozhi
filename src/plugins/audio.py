"""音频插件.

负责音频采集、编码、播放和发送。
"""

import asyncio
import os
from typing import TYPE_CHECKING, Optional

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
        self.codec: Optional[AudioCodec] = None
        self._send_sem = asyncio.Semaphore(MAX_CONCURRENT_AUDIO_SENDS)
        self._in_silence_period = False
        self._audio_consumer_task = None

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)

        if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
            return

        try:
            self.codec = AudioCodec()
            await self.codec.initialize()
            self.codec.set_encoded_callback(self._on_encoded_audio)

            from src.mcp.tools.music.music_player import get_music_player_instance

            music_player = get_music_player_instance()
            music_player.set_audio_codec(self.codec)

            # 订阅配置变更事件
            from src.core.event_bus import Events
            ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)

        except Exception as e:
            logger.error(f"音频插件初始化失败: {e}", exc_info=True)
            self.codec = None

    async def _on_config_changed(self, data=None):
        """配置变更时重新加载音频设备."""
        if self.codec:
            logger.info("AudioPlugin: 收到配置变更事件，重新加载音频设备")
            await self.codec.reload_devices()

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
                    if self.codec:
                        await self.codec.clear_audio_queue()
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
        """
        TTS 开始时暂停音乐.
        """
        try:
            if self.codec:
                await self.codec.clear_audio_queue()
                logger.debug("TTS 开始，已清空音频队列")

            # 通过事件总线发送暂停请求
            try:
                from src.core.event_bus import Events
                from src.mcp.tools.music.events import MusicControlRequest

                logger.info("TTS 开始，发送音乐暂停请求")
                await self._ctx.event_bus.emit(
                    Events.MUSIC_PAUSE_REQUEST, MusicControlRequest(source="tts")
                )
            except Exception as e:
                logger.warning(f"发送音乐暂停请求失败: {e}")
        except Exception as e:
            logger.error(f"TTS 开始处理失败: {e}", exc_info=True)

    async def _resume_music_after_tts(self):
        """TTS 结束后恢复音乐"""
        try:
            # 通过事件总线发送恢复请求
            from src.core.event_bus import Events
            from src.mcp.tools.music.events import MusicControlRequest

            logger.info("TTS 播放完成，发送音乐恢复请求")
            await self._ctx.event_bus.emit(
                Events.MUSIC_RESUME_REQUEST, MusicControlRequest(source="tts")
            )
        except Exception as e:
            logger.error(f"发送音乐恢复请求失败: {e}", exc_info=True)

    async def shutdown(self) -> None:
        if self._audio_consumer_task and not self._audio_consumer_task.done():
            self._audio_consumer_task.cancel()
            try:
                await self._audio_consumer_task
            except asyncio.CancelledError:
                pass

        if self.codec:
            try:
                from src.mcp.tools.music.music_player import get_music_player_instance

                try:
                    music_player = get_music_player_instance()
                    music_player.set_audio_codec(None)
                except Exception as e:
                    logger.debug(f"清理音乐播放器音频编码器失败: {e}")

                await self.codec.close()
            except Exception as e:
                logger.error(f"关闭音频编解码器失败: {e}", exc_info=True)
            finally:
                self.codec = None

    def _on_encoded_audio(self, encoded_data: bytes) -> None:
        """
        音频编码回调（从音频线程调用）.
        """
        try:
            if not self._cmd:
                return
            self._cmd.schedule_command_nowait(self._send_audio_async, encoded_data)
        except Exception as e:
            logger.error(f"调度音频发送失败: {e}")

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
                logger.error(f"发送音频数据失败: {e}")

    def _should_send_microphone_audio(self) -> bool:
        """
        判断是否应该发送麦克风音频.
        """
        try:
            if self._in_silence_period:
                return False
            return self._ctx.should_capture_audio()
        except Exception:
            return False
