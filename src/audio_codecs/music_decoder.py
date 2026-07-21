import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Mapping
from urllib.parse import urlparse

import numpy as np

from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.resource_finder import get_ffmpeg_path, get_ffprobe_path

logger = get_logger()

_SUBPROCESS_KW = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
)

# 本地路径或 http(s) 流
AudioSource = str | Path


def is_http_url(source: AudioSource) -> bool:
    text = str(source).strip()
    return text.startswith("http://") or text.startswith("https://")


def _source_label(source: AudioSource) -> str:
    if is_http_url(source):
        host = urlparse(str(source)).hostname or "http"
        return f"stream:{host}"
    path = Path(source)
    return path.name


def _ffmpeg_header_args(headers: Mapping[str, str] | None) -> list[str]:
    """拼给 ffmpeg 的 -headers / -user_agent（HTTP 源常用）."""
    if not headers:
        return []
    args: list[str] = []
    ua = None
    lines: list[str] = []
    for key, value in headers.items():
        if not value:
            continue
        if key.lower() == "user-agent":
            ua = str(value)
            continue
        lines.append(f"{key}: {value}")
    # 文档要求每行以 \r\n 结尾
    if lines:
        blob = "".join(f"{line}\r\n" for line in lines)
        args.extend(["-headers", blob])
    if ua:
        args.extend(["-user_agent", ua])
    return args


class MusicDecoder:
    @staticmethod
    async def get_duration(
        source: AudioSource,
        headers: Mapping[str, str] | None = None,
    ) -> float:
        """ffprobe 取时长；source 可以是本地文件或 http(s) URL."""
        try:
            ffprobe = get_ffprobe_path()
            try:
                check = await asyncio.create_subprocess_exec(
                    ffprobe,
                    "-version",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **_SUBPROCESS_KW,
                )
                await check.wait()
            except FileNotFoundError:
                logger.warning(
                    "ffprobe 不可用（未找到内置 libs/ffmpeg 且系统 PATH 无 ffprobe），"
                    f"无法获取音频时长。尝试路径: {ffprobe}"
                )
                return 0
            except OSError as e:
                logger.warning(f"ffprobe 启动失败: {ffprobe}: {e}", exc_info=True)
                return 0

            cmd = [ffprobe, "-v", "error"]
            if is_http_url(source):
                cmd.extend(_ffmpeg_header_args(headers))
            cmd.extend(
                [
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(source),
                ]
            )

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_SUBPROCESS_KW
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                duration_str = stdout.decode("utf-8").strip()
                duration = float(duration_str)
                logger.debug(f"解析音频时长: {duration:.2f}秒 ({_source_label(source)})")
                return duration
            else:
                error_msg = stderr.decode("utf-8", errors="ignore")
                logger.warning(f"ffprobe 获取时长失败: {error_msg}")
                return 0

        except Exception as e:
            logger.warning(f"解析音频时长失败: {e}", exc_info=True)
            return 0

    def __init__(self, sample_rate: int = 24000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._process: subprocess.Process | None = None
        self._decode_task: asyncio.Task | None = None
        self._stopped = False
        # 流式边播边 copy：完整听完才落到 final
        self._cache_part: Path | None = None
        self._cache_final: Path | None = None
        self._cache_committed: Path | None = None

    @property
    def committed_cache_path(self) -> Path | None:
        """完整播完后落盘的缓存路径；中途停止则为 None."""
        return self._cache_committed

    def _discard_cache_part(self) -> None:
        part = self._cache_part
        self._cache_part = None
        self._cache_final = None
        if part is None:
            return
        try:
            if part.exists():
                part.unlink()
                logger.debug(f"丢弃未完成的流缓存: {part.name}")
        except Exception as e:
            logger.debug(f"清理流缓存临时文件失败: {e}")

    def _commit_cache_part(self) -> None:
        part, final = self._cache_part, self._cache_final
        self._cache_part = None
        self._cache_final = None
        if part is None or final is None:
            return
        try:
            if not part.exists() or part.stat().st_size <= 1024:
                # 太小多半是失败/空文件
                if part.exists():
                    part.unlink()
                return
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                final.unlink()
            part.replace(final)
            self._cache_committed = final
            logger.info(f"流式拷贝已写入缓存: {final.name} ({final.stat().st_size} bytes)")
        except Exception as e:
            logger.warning(f"流缓存落盘失败: {e}", exc_info=True)
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass

    async def start_decode(
        self,
        source: AudioSource,
        output_queue: asyncio.Queue,
        start_position: float = 0.0,
        headers: Mapping[str, str] | None = None,
        cache_path: Path | None = None,
    ) -> bool:
        """开始解码。source 为本地路径或 http(s)。

        cache_path: 仅流式且从头播时，FFmpeg 同时 -c copy 写临时文件，
        完整结束后再改名为缓存；中途 stop 会删掉临时文件。
        """
        http = is_http_url(source)
        if not http:
            path = Path(source)
            if not path.exists():
                logger.error(f"音频文件不存在: {path}")
                return False
            source = path

        self._stopped = False
        self._cache_part = None
        self._cache_final = None
        self._cache_committed = None

        # 只有整曲从头流式才边播边拷；seek/半截不写缓存
        write_cache = (
            http
            and cache_path is not None
            and start_position <= 0.1
            and not Path(cache_path).exists()
        )
        if write_cache:
            final = Path(cache_path)
            # 后缀要像 .mp3，否则 ffmpeg 不知道 muxer（.mp3.part 会挂）
            part = final.with_name(f"{final.stem}.part{final.suffix}")
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass
            self._cache_part = part
            self._cache_final = final

        try:
            ffmpeg = get_ffmpeg_path()
            try:
                result = await asyncio.create_subprocess_exec(
                    ffmpeg,
                    "-version",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **_SUBPROCESS_KW,
                )
                await result.wait()
                if result.returncode not in (0, None):
                    logger.error(
                        f"FFmpeg 无法启动（退出码 {result.returncode}）: {ffmpeg}。"
                        "安装包应内置可移植二进制；若仍失败请反馈版本与平台。"
                        "源码运行请执行 ./scripts/bundle_ffmpeg.sh 或安装系统 ffmpeg"
                    )
                    return False
            except FileNotFoundError:
                logger.error(
                    "FFmpeg 不可用：未找到内置 libs/ffmpeg/<plat>/<arch>/ffmpeg，"
                    f"且系统 PATH 中也没有。尝试路径: {ffmpeg}。"
                    "安装包用户无需单独安装系统 FFmpeg；若使用安装包仍失败，"
                    "请重新下载完整安装包。源码运行请安装 ffmpeg 或执行 "
                    "./scripts/bundle_ffmpeg.sh"
                )
                return False
            except OSError as e:
                logger.error(
                    f"FFmpeg 启动失败（可能缺少动态库）: {ffmpeg}: {e}",
                    exc_info=True,
                )
                return False

            cmd = [ffmpeg]

            # HTTP 流：断线重连
            if http:
                cmd.extend(
                    [
                        "-reconnect",
                        "1",
                        "-reconnect_streamed",
                        "1",
                        "-reconnect_delay_max",
                        "5",
                    ]
                )
                cmd.extend(_ffmpeg_header_args(headers))

            if start_position > 0.1:
                cmd.extend(["-ss", f"{start_position:.3f}"])

            cmd.extend(["-i", str(source)])

            # 输出1：原样 copy 到本地（不是另起 requests 下载）
            if self._cache_part is not None:
                # -vn：只要音轨；-f 按后缀推断，.part.mp3 可被识别
                cmd.extend(
                    ["-vn", "-c:a", "copy", "-y", str(self._cache_part)]
                )
                logger.debug(f"流式同时拷贝到: {self._cache_part.name}")

            # 输出2：PCM 给扬声器
            cmd.extend(
                [
                    "-f",
                    "s16le",
                    "-ar",
                    str(self.sample_rate),
                    "-ac",
                    str(self.channels),
                    "-loglevel",
                    "error",
                    "-",
                ]
            )

            self._process = await asyncio.create_subprocess_exec(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_SUBPROCESS_KW
            )

            self._decode_task = asyncio.create_task(self._read_pcm_stream(output_queue))

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            mode = "流式" if http else "文件"
            cache_info = "+缓存" if self._cache_part else ""
            logger.info(
                f"开始解码音频({mode}{cache_info}): {_source_label(source)}"
                f"{position_info} [{self.sample_rate}Hz, {self.channels}ch]"
            )
            return True

        except Exception as e:
            logger.error(f"启动音频解码失败: {e}", exc_info=True)
            self._discard_cache_part()
            return False

    async def _read_pcm_stream(self, output_queue: asyncio.Queue):
        """
        读取 PCM 流并写入队列,使用队列占用率 + 时间兜底的双重限速策略.
        """
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
        start_time = time.time()

        try:
            while not self._stopped:
                chunk = await self._process.stdout.read(frame_size_bytes)

                if not chunk:
                    duration_decoded = frame_count * frame_duration_ms / 1000
                    logger.info(
                        f"音频解码完成，共 {frame_count} 帧，时长约 {duration_decoded:.1f}秒"
                    )

                    if self._process:
                        try:
                            # 等 ffmpeg 把 copy 输出刷完
                            await asyncio.wait_for(self._process.wait(), timeout=5.0)
                        except (asyncio.TimeoutError, Exception):
                            pass
                        try:
                            stderr_output = await self._process.stderr.read()
                            if stderr_output:
                                err = stderr_output.decode("utf-8", errors="ignore")
                                if err.strip():
                                    logger.warning(f"FFmpeg: {err.strip()[:300]}")
                        except Exception as e:
                            logger.debug(f"读取 FFmpeg stderr 失败: {e}")

                    eof_reached = True
                    # 完整播完 → 临时 part 改名进缓存
                    if frame_count > 0:
                        self._commit_cache_part()
                    else:
                        self._discard_cache_part()
                    break

                frame_count += 1

                audio_array_int16 = np.frombuffer(chunk, dtype=np.int16)
                audio_array = audio_array_int16.astype(np.float32) / 32768.0

                if self.channels > 1:
                    audio_array = audio_array.reshape(-1, self.channels)

                queue_ratio = (
                    output_queue.qsize() / output_queue.maxsize
                    if output_queue.maxsize > 0
                    else 0
                )

                if queue_ratio < 0.3:
                    queue_based_sleep = 0
                elif queue_ratio < 0.7:
                    queue_based_sleep = 0.03
                else:
                    queue_based_sleep = 0.06

                expected_elapsed = frame_count * (frame_duration_ms / 1000.0)
                actual_elapsed = time.time() - start_time

                if actual_elapsed < expected_elapsed:
                    time_based_sleep = expected_elapsed - actual_elapsed
                else:
                    time_based_sleep = 0

                target_sleep = max(queue_based_sleep, time_based_sleep)

                if target_sleep > 0:
                    await asyncio.sleep(target_sleep)

                try:
                    await asyncio.wait_for(output_queue.put(audio_array), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(f"音频队列写入超时，跳过帧 {frame_count}")
                    continue

        except asyncio.CancelledError:
            logger.debug("解码任务被取消")
            if not eof_reached:
                self._discard_cache_part()
        except Exception as e:
            logger.error(f"读取 PCM 流失败: {e}", exc_info=True)
            if not eof_reached:
                self._discard_cache_part()
        finally:
            if eof_reached:
                try:
                    await output_queue.put(None)
                except Exception as e:
                    logger.debug(f"发送 EOF 信号失败: {e}")

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
            except Exception as e:
                logger.error(f"解码任务异常: {e}", exc_info=True)

        if self._process:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                try:
                    self._process.kill()
                    await self._process.wait()
                except Exception as e:
                    logger.debug(f"强制终止进程失败: {e}")
            except Exception as e:
                logger.debug(f"终止 FFmpeg 进程失败: {e}")

        # 中途停：不要半截缓存
        if self._cache_committed is None:
            self._discard_cache_part()

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
            except Exception as e:
                logger.error(f"等待解码完成失败: {e}", exc_info=True)
