import asyncio
import os
from typing import Any

from src.audio_codecs.audio_codec import AudioCodec
from src.plugins.base import Plugin
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 常量配置
AUDIO_QUEUE_SIZE = 50
MAX_CONCURRENT_AUDIO_SENDS = 4


class AudioPlugin(Plugin):
    name = "audio"

    def __init__(self) -> None:
        super().__init__()
        self.app = None
        self.codec: AudioCodec | None = None
        self._main_loop = None
        self._send_sem = asyncio.Semaphore(MAX_CONCURRENT_AUDIO_SENDS)
        self._audio_queue: asyncio.Queue | None = None
        self._audio_consumer_task: asyncio.Task | None = None

    async def setup(self, app: Any) -> None:
        self.app = app
        self._main_loop = app._main_loop

        if os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
            return

        try:
            self.codec = AudioCodec()
            await self.codec.initialize()

            # 创建音频队列
            self._audio_queue = asyncio.Queue(maxsize=AUDIO_QUEUE_SIZE)

            # 设置编码音频回调：录音数据入队，由消费者发送
            self.codec.set_encoded_callback(self._enqueue_audio)

            # 启动音频消费者任务
            self._audio_consumer_task = app.spawn(
                self._audio_consumer(),
                "audio:consumer"
            )

            # 暴露给应用，便于唤醒词插件使用
            self.app.audio_codec = self.codec
        except Exception as e:
            logger.error(f"音频插件初始化失败: {e}", exc_info=True)
            self.codec = None

    async def on_incoming_audio(self, data: bytes) -> None:
        """
        接收服务端返回的音频数据并播放

        Args:
            data: 服务端返回的Opus编码音频数据
        """
        if self.codec:
            try:
                await self.codec.write_audio(data)
            except Exception as e:
                logger.debug(f"写入音频数据失败: {e}")

    async def shutdown(self) -> None:
        """
        完全关闭并释放音频资源.
        """
        # 停止音频消费者任务
        if self._audio_consumer_task and not self._audio_consumer_task.done():
            self._audio_consumer_task.cancel()
            try:
                await self._audio_consumer_task
            except asyncio.CancelledError:
                pass

        if self.codec:
            try:
                await self.codec.close()
            except Exception as e:
                logger.error(f"关闭音频编解码器失败: {e}", exc_info=True)
            finally:
                self.codec = None

        # 清空应用引用
        if self.app:
            self.app.audio_codec = None

    # -------------------------
    # 内部：音频队列处理
    # -------------------------
    def _enqueue_audio(self, encoded_data: bytes) -> None:
        """音频线程回调：安全入队"""
        if not self._audio_queue or not self._main_loop:
            return
        try:
            # 使用 call_soon_threadsafe 在主循环中入队
            self._main_loop.call_soon_threadsafe(
                self._audio_queue.put_nowait, encoded_data
            )
        except asyncio.QueueFull:
            # 队列满时丢弃最旧数据
            try:
                self._main_loop.call_soon_threadsafe(self._audio_queue.get_nowait)
                self._main_loop.call_soon_threadsafe(
                    self._audio_queue.put_nowait, encoded_data
                )
            except Exception:
                pass
        except Exception:
            pass

    async def _audio_consumer(self) -> None:
        """异步消费音频队列"""
        while True:
            try:
                encoded_data = await self._audio_queue.get()
                await self._process_audio(encoded_data)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # 继续处理，避免消费者崩溃
                logger.debug(f"音频消费者处理异常: {e}")
                await asyncio.sleep(0.01)

    async def _process_audio(self, encoded_data: bytes) -> None:
        """处理单个音频数据包"""
        async with self._send_sem:
            try:
                if not (
                    self.app
                    and self.app.running
                    and self.app.protocol
                    and self.app.protocol.is_audio_channel_opened()
                ):
                    return

                if self._should_send_microphone_audio():
                    await self.app.protocol.send_audio(encoded_data)
            except Exception:
                pass

    def _should_send_microphone_audio(self) -> bool:
        """委托给应用的统一状态机规则"""
        try:
            return self.app and self.app.should_capture_audio()
        except Exception:
            return False
