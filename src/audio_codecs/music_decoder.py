import asyncio
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
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
    if lines:
        blob = "".join(f"{line}\r\n" for line in lines)
        args.extend(["-headers", blob])
    if ua:
        args.extend(["-user_agent", ua])
    return args


class MusicDecoder:
    """只负责把音源解成 PCM；缓存预取不走这里（避免和播放进度绑死）."""

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
                logger.debug(
                    f"解析音频时长: {duration:.2f}秒 ({_source_label(source)})"
                )
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
        self._process: asyncio.subprocess.Process | None = None
        self._probe_process: asyncio.subprocess.Process | None = None
        self._decode_task: asyncio.Task | None = None
        self._stopped = False
        self.completed_successfully = False

    @staticmethod
    async def _terminate_process(process: asyncio.subprocess.Process | None) -> None:
        """终止并回收一个可能仍在运行的子进程。"""
        if process is None or process.returncode is not None:
            return
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception as e:
                logger.debug(f"强制结束 FFmpeg 失败: {e}")
        except ProcessLookupError:
            pass
        except Exception as e:
            if str(e).strip():
                logger.debug(f"结束 FFmpeg 进程: {e}")

    @staticmethod
    async def _spawn_process(*args, **kwargs) -> asyncio.subprocess.Process:
        """在启动协程取消时仍取得并回收已创建的子进程。"""
        spawn_task = asyncio.create_task(
            asyncio.create_subprocess_exec(*args, **kwargs)
        )
        try:
            return await asyncio.shield(spawn_task)
        except asyncio.CancelledError:
            try:
                process = await asyncio.shield(spawn_task)
            except asyncio.CancelledError:
                process = await spawn_task
            await MusicDecoder._terminate_process(process)
            raise

    async def start_decode(
        self,
        source: AudioSource,
        output_queue: asyncio.Queue,
        start_position: float = 0.0,
        headers: Mapping[str, str] | None = None,
        cache_path: Path | None = None,
    ) -> bool:
        """开始解码。source 为本地路径或 http(s)。

        cache_path 已废弃忽略：缓存由后台按网速 copy，不跟播放进度绑。
        """
        _ = cache_path
        http = is_http_url(source)
        if not http:
            path = Path(source)
            if not path.exists():
                logger.error(f"音频文件不存在: {path}")
                return False
            source = path

        self._stopped = False
        self.completed_successfully = False

        try:
            ffmpeg = get_ffmpeg_path()
            try:
                result = await self._spawn_process(
                    ffmpeg,
                    "-version",
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    **_SUBPROCESS_KW,
                )
                self._probe_process = result
                if self._stopped:
                    await self._terminate_process(result)
                    self._probe_process = None
                    return False
                await result.wait()
                self._probe_process = None
                if self._stopped:
                    return False
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

            cmd.extend(
                [
                    "-i",
                    str(source),
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

            self._process = await self._spawn_process(
                *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **_SUBPROCESS_KW
            )
            if self._stopped:
                await self.stop()
                return False

            self._decode_task = asyncio.create_task(self._read_pcm_stream(output_queue))

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            mode = "流式" if http else "文件"
            logger.info(
                f"开始解码音频({mode}): {_source_label(source)}{position_info} "
                f"[{self.sample_rate}Hz, {self.channels}ch]"
            )
            return True

        except asyncio.CancelledError:
            await self.stop()
            raise
        except Exception as e:
            logger.error(f"启动音频解码失败: {e}", exc_info=True)
            await self.stop()
            return False

    async def _read_pcm_stream(self, output_queue: asyncio.Queue):
        frame_size_samples = int(self.sample_rate * AudioConfig.FRAME_DURATION / 1000)
        sample_bytes = 2 * self.channels
        frame_size_bytes = frame_size_samples * sample_bytes
        process = self._process
        pending = b""
        cancelled = False
        stderr_task = asyncio.create_task(self._read_stderr(process))
        try:
            while not self._stopped:
                chunk = await process.stdout.read(frame_size_bytes)
                if not chunk:
                    returncode = await asyncio.wait_for(process.wait(), timeout=2.0)
                    self.completed_successfully = returncode == 0 and not pending
                    if not self.completed_successfully:
                        logger.warning(
                            "FFmpeg 解码失败或 PCM 截断，退出码: %s", returncode
                        )
                    break

                pending += chunk
                usable = len(pending) - len(pending) % sample_bytes
                if not usable:
                    continue
                audio = np.frombuffer(pending[:usable], dtype="<i2")
                audio = audio.astype(np.float32) / 32768.0
                pending = pending[usable:]
                if self.channels > 1:
                    audio = audio.reshape(-1, self.channels)
                # 有界队列提供背压，不因网络短读丢弃半个 PCM 样本。
                await output_queue.put(audio)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as e:
            self.completed_successfully = False
            logger.error(f"读取 PCM 流失败: {e}", exc_info=True)
        finally:
            if not self.completed_successfully:
                await self._terminate_process(process)
            if not stderr_task.done():
                stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)
            # 所有非取消终态都唤醒下游；调用方可检查成功标志区分失败。
            if not cancelled and not self._stopped:
                await output_queue.put(None)

    @staticmethod
    async def _read_stderr(process) -> None:
        # 同时排空 stderr，防止大量错误日志填满管道而阻塞 stdout。
        tail = b""
        while chunk := await process.stderr.read(4096):
            tail = (tail + chunk)[-300:]
        if tail.strip():
            logger.warning("FFmpeg: %s", tail.decode("utf-8", errors="replace").strip())

    async def stop(self):
        self._stopped = True
        logger.debug("停止音频解码器")
        task = self._decode_task
        self._decode_task = None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        process, probe = self._process, self._probe_process
        self._process = None
        self._probe_process = None
        await self._terminate_process(process)
        await self._terminate_process(probe)

    def is_running(self) -> bool:
        return (
            not self._stopped
            and self._decode_task is not None
            and not self._decode_task.done()
        )

    async def wait_completion(self):
        if self._decode_task and not self._decode_task.done():
            try:
                await self._decode_task
            except Exception as e:
                logger.error(f"等待解码完成失败: {e}", exc_info=True)
