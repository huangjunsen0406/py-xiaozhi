import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import numpy as np

from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MusicDecoder:

    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._process: Optional[subprocess.Process] = None
        self._decode_task: Optional[asyncio.Task] = None
        self._stopped = False

    async def start_decode(
        self, file_path: Path, output_queue: asyncio.Queue, start_position: float = 0.0
    ) -> bool:
        if not file_path.exists():
            logger.error(f"音频文件不存在: {file_path}")
            return False

        self._stopped = False

        try:
            try:
                result = await asyncio.create_subprocess_exec(
                    "ffmpeg",
                    "-version",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                await result.wait()
            except FileNotFoundError:
                logger.error("FFmpeg 未安装或不在 PATH 中")
                return False

            cmd = ["ffmpeg"]

            if start_position > 0:
                cmd.extend(["-ss", str(start_position)])

            cmd.extend(
                [
                    "-i",
                    str(file_path),  # 输入文件
                    "-f",
                    "s16le",  # 输出格式：16位小端 PCM
                    "-ar",
                    str(self.sample_rate),  # 采样率
                    "-ac",
                    str(self.channels),  # 声道数
                    "-loglevel",
                    "error",  # 只输出错误信息
                    "-",  # 输出到 stdout
                ]
            )

            self._process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            # 启动读取任务
            self._decode_task = asyncio.create_task(self._read_pcm_stream(output_queue))

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(
                f"开始解码音频: {file_path.name}{position_info} "
                f"[{self.sample_rate}Hz, {self.channels}ch]"
            )
            return True

        except Exception as e:
            logger.error(f"启动音频解码失败: {e}")
            return False

    async def _read_pcm_stream(self, output_queue: asyncio.Queue):
        """读取 PCM 流并写入队列,使用队列占用率 + 时间兜底的双重限速策略."""
        import time

        frame_duration_ms = AudioConfig.FRAME_DURATION
        frame_size_samples = int(self.sample_rate * (frame_duration_ms / 1000))
        frame_size_bytes = frame_size_samples * 2 * self.channels
        logger.info(
            f"解码器参数: 帧大小={frame_size_samples}样本, "
            f"{frame_size_bytes}字节, {frame_duration_ms}ms"
        )

        eof_reached = False
        frame_count = 0
        start_time = time.time()  # 记录解码开始时间

        try:
            while not self._stopped:
                # 读取一帧数据
                chunk = await self._process.stdout.read(frame_size_bytes)

                if not chunk:
                    # EOF - 文件解码完成
                    duration_decoded = frame_count * frame_duration_ms / 1000
                    logger.info(
                        f"音频解码完成，共 {frame_count} 帧，时长约 {duration_decoded:.1f}秒"
                    )

                    if self._process and self._process.returncode is not None:
                        try:
                            stderr_output = await self._process.stderr.read()
                            if stderr_output:
                                logger.error(
                                    f"FFmpeg 错误输出: {stderr_output.decode('utf-8', errors='ignore')}"
                                )
                        except Exception:
                            pass

                    eof_reached = True
                    break

                frame_count += 1

                audio_array = np.frombuffer(chunk, dtype=np.int16)

                if self.channels > 1:
                    audio_array = audio_array.reshape(-1, self.channels)

                # ========== 双重限速策略 ==========

                # 策略1: 基于队列占用率的动态限速
                queue_ratio = output_queue.qsize() / output_queue.maxsize if output_queue.maxsize > 0 else 0

                if queue_ratio < 0.3:
                    # 队列低于30%，快速填充
                    queue_based_sleep = 0
                elif queue_ratio < 0.7:
                    # 队列30-70%，适度限速
                    queue_based_sleep = 0.03
                else:
                    # 队列70%+，大幅限速
                    queue_based_sleep = 0.06

                # 策略2: 时间兜底，确保不超过理论播放速度
                expected_elapsed = frame_count * (frame_duration_ms / 1000.0)
                actual_elapsed = time.time() - start_time

                if actual_elapsed < expected_elapsed:
                    # 解码速度超过理论播放速度，强制等待
                    time_based_sleep = expected_elapsed - actual_elapsed
                else:
                    time_based_sleep = 0

                # 取两种策略的最大值，确保既不过快填充队列，也不超过播放速度
                target_sleep = max(queue_based_sleep, time_based_sleep)

                if target_sleep > 0:
                    await asyncio.sleep(target_sleep)

                # 写入队列（带超时保护）
                try:
                    await asyncio.wait_for(output_queue.put(audio_array), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"音频队列写入超时，跳过帧 {frame_count}")
                    continue

        except asyncio.CancelledError:
            logger.debug("解码任务被取消")
        except Exception as e:
            logger.error(f"读取 PCM 流失败: {e}")
        finally:
            if eof_reached:
                try:
                    await output_queue.put(None)
                except Exception:
                    pass

    async def stop(self):
        if self._stopped:
            return

        self._stopped = True
        logger.debug("停止音频解码器")

        if self._decode_task and not self._decode_task.done():
            self._decode_task.cancel()
            try:
                await self._decode_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # 强制杀死
                try:
                    self._process.kill()
                    await self._process.wait()
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"终止 FFmpeg 进程失败: {e}")

    def is_running(self) -> bool:
        return (
            not self._stopped
            and self._process is not None
            and self._process.returncode is None
        )

    async def wait_completion(self):
        if self._decode_task and not self._decode_task.done():
            try:
                await self._decode_task
            except Exception:
                pass
