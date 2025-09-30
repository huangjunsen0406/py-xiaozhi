import asyncio
import os
from typing import Any

from src.audio_codecs.audio_codec import AudioCodec
from src.constants.constants import DeviceState, ListeningMode
from src.plugins.base import Plugin

# from src.utils.opus_loader import setup_opus
# setup_opus()


class AudioPlugin(Plugin):
    name = "audio"

    def __init__(self) -> None:
        super().__init__()
        self.app = None  # ApplicationExample
        self.codec: AudioCodec | None = None
        self._loop = None
        self._send_sem = asyncio.Semaphore(4)

    async def setup(self, app: Any) -> None:
        self.app = app
        self._loop = app._main_loop

        if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
            return

        try:
            self.codec = AudioCodec()
            await self.codec.initialize()
            # 录音编码后的回调（来自音频线程）
            self.codec.set_encoded_audio_callback(self._on_encoded_audio)
            # 暴露给应用，便于唤醒词插件使用
            try:
                setattr(self.app, "audio_codec", self.codec)
            except Exception:
                pass
        except Exception:
            self.codec = None

    async def start(self) -> None:
        if self.codec:
            try:
                await self.codec.start_streams()
            except Exception:
                pass

    async def on_protocol_connected(self, protocol: Any) -> None:
        # 协议连上时确保音频流已启动
        if self.codec:
            try:
                await self.codec.start_streams()
            except Exception:
                pass

    async def on_incoming_json(self, message: Any) -> None:
        # 示例：不处理
        await asyncio.sleep(0)

    async def on_incoming_audio(self, data: bytes) -> None:
        if self.codec:
            try:
                await self.codec.write_audio(data)
            except Exception:
                pass

    async def stop(self) -> None:
        """
        停止音频流（保留 codec 实例）
        """
        if self.codec:
            try:
                await self.codec.stop_streams()
            except Exception:
                pass

    async def shutdown(self) -> None:
        """
        完全关闭并释放音频资源.
        """
        if self.codec:
            try:
                # 确保先停止流，再关闭（避免回调还在执行）
                try:
                    await self.codec.stop_streams()
                except Exception:
                    pass

                # 关闭并释放所有音频资源
                await self.codec.close()
            except Exception:
                # 日志已在 codec.close() 中记录
                pass
            finally:
                # 清空引用，帮助 GC
                self.codec = None

        # 清空应用引用，打破潜在循环引用
        if self.app and hasattr(self.app, "audio_codec"):
            try:
                self.app.audio_codec = None
            except Exception:
                pass

    # -------------------------
    # 内部：发送麦克风音频
    # -------------------------
    def _on_encoded_audio(self, encoded_data: bytes) -> None:
        # 音频线程回调 -> 切回主loop
        try:
            if not self.app or not self._loop or not self.app.running:
                return
            if self._loop.is_closed():
                return
            self._loop.call_soon_threadsafe(self._schedule_send_audio, encoded_data)
        except Exception:
            pass

    def _schedule_send_audio(self, encoded_data: bytes) -> None:
        if not self.app or not self.app.running or not self.app.protocol:
            return

        async def _send():
            async with self._send_sem:
                # 仅在允许的设备状态下发送麦克风音频
                try:
                    if not (
                        self.app.protocol
                        and self.app.protocol.is_audio_channel_opened()
                    ):
                        return
                    if self._should_send_microphone_audio():
                        await self.app.protocol.send_audio(encoded_data)
                except Exception:
                    pass

        # 交给应用的任务管理
        self.app.spawn(_send(), name="audio:send")

    def _should_send_microphone_audio(self) -> bool:
        """与应用状态机对齐：

        - LISTENING 时发送
        - SPEAKING 且 AEC 开启 且 keep_listening 且 REALTIME 模式 时发送
        """
        try:
            if not self.app:
                return False
            if self.app.device_state == DeviceState.LISTENING:
                return True
            return (
                self.app.device_state == DeviceState.SPEAKING
                and getattr(self.app, "aec_enabled", False)
                and bool(getattr(self.app, "keep_listening", False))
                and getattr(self.app, "listening_mode", None) == ListeningMode.REALTIME
            )
        except Exception:
            return False
