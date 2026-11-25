"""AEC 引擎：libs/webrtc_apm 的实时封装（P0 Self far）.

数据流：
- near：采集帧（16kHz 单声道 float32）→ ProcessStream → 消回声后上行
- far：设备实际写出的最终 PCM（TTS + 音乐混合，设备采样率/声道）
       → 下混 → 重采样到 16kHz → ProcessReverseStream

线程模型（关键）：
- 输出回调线程只做「下混 + 拷贝入队」（feed_far，微秒级、无锁）；
  重采样与 APM 调用全部在采集线程（process_near 开头先排空 far 队列）。
  两个实时回调之间不共享锁，避免输入侧持锁被 GIL 卡住时拖垮输出回调。

设计约束：
- 库加载/处理失败一律旁路（active=False），不影响通话主链路
- WebRTC APM 按 10ms 帧处理；协议帧 20/40/60ms 均为其整数倍
"""

import ctypes
import sys
import threading
from collections import deque
from typing import Protocol

import numpy as np

from src.logging import get_logger

logger = get_logger()

# 连续处理失败达到该次数后自动旁路，避免坏库拖垮音频回调
_MAX_CONSECUTIVE_FAILURES = 5
# far 待处理队列上限（输出回调块数，约 20ms/块 → 0.5s）；
# 采集线程停转时防堆积，超限丢最旧
_FAR_PENDING_MAX_BLOCKS = 25


class FarEndSource(Protocol):
    """AEC 远端参考源协议（支持 SelfFar 与未来跨平台 SystemLoopback 扩展）."""

    def feed_self_output(self, outdata: np.ndarray) -> None:
        """接收本进程输出回调的最终 PCM（系统回环实现可忽略）."""
        ...

    def drain_16k(self) -> np.ndarray:
        """在采集线程中排空并重采样为 16kHz 单声道 float32 参考样本."""
        ...

    def close(self) -> None:
        """释放远端采集/重采样资源."""
        ...


class SelfFarEndSource:
    """默认远端参考源：来自本进程 AudioCodec 输出回调的混合 PCM."""

    def __init__(self, *, far_rate: int, target_rate: int) -> None:
        self._far_rate = int(far_rate)
        self._target_rate = int(target_rate)
        self._pending: deque[np.ndarray] = deque()
        self._resampler = None
        self._dropped = 0
        self._error_logged = False
        if self._far_rate != self._target_rate:
            import soxr

            self._resampler = soxr.ResampleStream(
                self._far_rate,
                self._target_rate,
                num_channels=1,
                dtype="float32",
                quality="QQ",
            )

    def feed_self_output(self, outdata: np.ndarray) -> None:
        try:
            if outdata.ndim > 1 and outdata.shape[1] > 1:
                mono = outdata.mean(axis=1, dtype=np.float32)
            else:
                # PortAudio 复用 outdata 内存，必须拷贝
                mono = np.array(outdata, dtype=np.float32).ravel()

            self._pending.append(mono)
            # deque 操作在 GIL 下原子；超限丢最旧（采集线程停转时防堆积）
            while len(self._pending) > _FAR_PENDING_MAX_BLOCKS:
                self._pending.popleft()
                self._dropped += 1
        except Exception as exc:
            self._dropped += 1
            if not self._error_logged:
                self._error_logged = True
                logger.warning("AEC feed_far 异常（后续同类错误静默计数）: %s", exc)

    def drain_16k(self) -> np.ndarray:
        chunks: list[np.ndarray] = []
        while self._pending:
            mono = self._pending.popleft()
            if self._resampler is not None:
                mono = self._resampler.resample_chunk(mono, last=False)
            if len(mono):
                chunks.append(mono)
        if not chunks:
            return np.empty(0, dtype=np.float32)
        if len(chunks) == 1:
            return chunks[0]
        return np.concatenate(chunks)

    def close(self) -> None:
        self._resampler = None
        self._pending.clear()
        if self._dropped:
            logger.debug(f"AEC far 累计丢弃 {self._dropped} 块")


def _import_webrtc_apm():
    """导入 libs.webrtc_apm，源码运行与打包形态各有路径兜底."""
    try:
        from libs import webrtc_apm

        return webrtc_apm
    except ImportError:
        from src.utils.resource_finder import get_resource_root

        root = str(get_resource_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        from libs import webrtc_apm

        return webrtc_apm


class AecEngine:
    """WebRTC APM 封装：AEC + 可选 NS/高通，near/far 双流."""

    def __init__(
        self,
        near_rate: int = 16000,
        far_rate: int = 48000,
        delay_ms: int = 60,
        enable_preprocess: bool = True,
        far_end_source: FarEndSource | None = None,
        near_delay_ms: int = 0,
    ):
        """初始化并加载 APM；失败时 active=False（旁路）.

        Args:
            near_rate: 采集协议采样率（16kHz）
            far_rate: 设备输出采样率（far 侧重采样源）
            delay_ms: 播放到采集的估计延迟
            enable_preprocess: 是否同时开高通+噪声抑制
            far_end_source: 可选自定义远端参考源（默认 SelfFarEndSource）
            near_delay_ms: 近端因果对齐缓冲时长（ms）；系统回环采集晚于麦克风时用于保证因果
        """
        self._near_rate = int(near_rate)
        self._far_rate = int(far_rate)
        self._delay_ms = int(delay_ms)
        self._frame = self._near_rate // 100  # 10ms
        self._near_delay_samples = max(0, (int(near_delay_ms) // 10) * self._frame)
        self._near_delay_fifo = (
            np.zeros(self._near_delay_samples, dtype=np.float32)
            if self._near_delay_samples > 0
            else None
        )
        self._first_near_call = True
        self._lock = threading.Lock()
        self._active = False
        self._closed = False
        self._fail_count = 0
        self._near_misaligned_logged = False

        self._apm = None
        self._stream_cfg = None
        self._far_end: FarEndSource | None = None
        self._far_buffer = np.empty(0, dtype=np.float32)

        # 复用的 ctypes 帧缓冲（10ms int16）
        self._near_in = (ctypes.c_short * self._frame)()
        self._near_out = (ctypes.c_short * self._frame)()
        self._far_in = (ctypes.c_short * self._frame)()
        self._far_out = (ctypes.c_short * self._frame)()

        try:
            self._init_apm(enable_preprocess)
            self._far_end = (
                far_end_source
                if far_end_source is not None
                else SelfFarEndSource(
                    far_rate=self._far_rate, target_rate=self._near_rate
                )
            )
            self._active = True
            far_mode = getattr(self._far_end, "mode", "self")
            logger.info(
                f"AEC 引擎已启用 | near {self._near_rate}Hz, "
                f"far {self._far_rate}Hz→{self._near_rate}Hz, "
                f"ref={far_mode}, delay {self._delay_ms}ms, "
                f"near_delay {self._near_delay_samples // self._frame * 10}ms, "
                f"preprocess={enable_preprocess}"
            )
        except Exception as e:
            logger.warning(f"AEC 引擎初始化失败，已旁路: {e}")
            self._release()

    def _init_apm(self, enable_preprocess: bool) -> None:
        """加载动态库、应用配置、创建流配置."""
        apm_mod = _import_webrtc_apm()

        self._apm = apm_mod.WebRTCAudioProcessing()

        config = apm_mod.create_default_config()
        config.echo.enabled = True
        config.echo.mobile_mode = False
        if enable_preprocess:
            config.high_pass.enabled = True
            config.noise_suppress.enabled = True
            config.noise_suppress.noise_level = apm_mod.NoiseSuppressionLevel.MODERATE

        ret = self._apm.apply_config(config)
        if ret != 0:
            raise RuntimeError(f"apply_config 返回 {ret}")

        # near/far 均为 16kHz 单声道，共用一份流配置
        self._stream_cfg = self._apm.create_stream_config(self._near_rate, 1)
        self._apm.set_stream_delay_ms(self._delay_ms)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def far_end_mode(self) -> str:
        """当前实际生效的远端参考模式（'self' / 'system' / 'self_fallback' / 'off'）."""
        if not self._active or self._far_end is None:
            return "off"
        return str(getattr(self._far_end, "mode", "self"))

    def process_near(self, block: np.ndarray) -> np.ndarray:
        """处理采集帧（16kHz 单声道 float32），返回消回声后的同长数据.

        任何失败都返回原始数据；连续失败自动旁路。
        """
        if not self._active:
            return block

        n = block.shape[0]
        if n % self._frame != 0:
            if not self._near_misaligned_logged:
                self._near_misaligned_logged = True
                logger.warning(f"采集帧长 {n} 非 10ms 整数倍，AEC 旁路该路径")
            return block

        try:
            with self._lock:
                if not self._active:
                    return block
                # 1. 拉取远端参考样本；首次进入采集回调时裁掉启动前积压的陈旧预热样本
                self._pull_far_locked(block_samples=n)

                # 2. 系统回环模式下通过近端因果 FIFO 补偿 OS 回环晚于麦克风的负延迟
                near_block = block
                if self._near_delay_fifo is not None:
                    combined = np.concatenate((self._near_delay_fifo, block))
                    near_block = combined[:n]
                    self._near_delay_fifo = combined[n:]

                i16 = self._float_to_i16(near_block)
                out = np.empty(n, dtype=np.float32)

                # 3. 逐 10ms 交替喂入 far -> near（1:1 交织），消除长帧块（如 60ms）的突发锯齿
                self._apm.set_stream_delay_ms(self._delay_ms)
                for off in range(0, n, self._frame):
                    self._feed_one_far_frame_locked()
                    ctypes.memmove(
                        self._near_in,
                        i16[off : off + self._frame].ctypes.data,
                        self._frame * 2,
                    )
                    ret = self._apm.process_stream(
                        self._near_in, self._stream_cfg, self._stream_cfg, self._near_out
                    )
                    if ret != 0:
                        raise RuntimeError(f"process_stream 返回 {ret}")
                    out[off : off + self._frame] = (
                        np.frombuffer(self._near_out, dtype=np.int16).astype(np.float32)
                        / 32768.0
                    )

                # 若远端仍有明显富余（>=40ms 且超过当前块），追平 1 帧防止跨时钟长期堆积
                if len(self._far_buffer) >= max(n, self._frame * 4):
                    self._feed_one_far_frame_locked()

            self._fail_count = 0
            return out
        except Exception as e:
            self._on_failure("near", e)
            return block

    def feed_far(self, outdata: np.ndarray) -> None:
        """输出回调线程调用：投递本进程最终输出 PCM 给远端参考源."""
        if not self._active or self._far_end is None:
            return
        self._far_end.feed_self_output(outdata)

    def _pull_far_locked(self, *, block_samples: int) -> None:
        """采集线程（已持锁）：从远端参考源拉取最新 16kHz 样本并保持队列有界."""
        if self._far_end is not None:
            fresh = self._far_end.drain_16k()
            if self._first_near_call:
                self._first_near_call = False
                # 启动阶段音频流尚未开启时，系统回环可能已攒下数百毫秒静音；只保留最近 1 块
                if len(fresh) > block_samples:
                    fresh = fresh[-block_samples:]
            if len(fresh):
                self._far_buffer = (
                    fresh
                    if not len(self._far_buffer)
                    else np.concatenate((self._far_buffer, fresh))
                )

        # 上限保护（约 2.5 个采集块，至少 160ms）：防止跨时钟漂移造成延迟累积
        max_keep = max(block_samples * 2 + self._frame * 4, self._frame * 16)
        if len(self._far_buffer) > max_keep:
            self._far_buffer = self._far_buffer[-max_keep:]

    def _feed_one_far_frame_locked(self) -> None:
        """采集线程（已持锁）：从远端缓冲取出 1 帧（10ms）送入 ProcessReverseStream."""
        if len(self._far_buffer) < self._frame:
            return
        frame_f32 = self._far_buffer[: self._frame]
        self._far_buffer = self._far_buffer[self._frame :]
        i16 = self._float_to_i16(frame_f32)
        ctypes.memmove(self._far_in, i16.ctypes.data, self._frame * 2)
        ret = self._apm.process_reverse_stream(
            self._far_in, self._stream_cfg, self._stream_cfg, self._far_out
        )
        if ret != 0:
            raise RuntimeError(f"process_reverse_stream 返回 {ret}")

    def close(self) -> None:
        """释放 APM 资源；须在音频流停止后调用."""
        if self._closed:
            return
        self._closed = True
        with self._lock:
            self._active = False
            self._release()
        logger.info("AEC 引擎已关闭")

    def _release(self) -> None:
        self._active = False
        try:
            if self._apm is not None and self._stream_cfg is not None:
                self._apm.destroy_stream_config(self._stream_cfg)
        except Exception:
            pass
        self._stream_cfg = None
        self._apm = None
        if self._far_end is not None:
            try:
                self._far_end.close()
            except Exception:
                pass
            self._far_end = None
        self._far_buffer = np.empty(0, dtype=np.float32)

    def _on_failure(self, side: str, err: Exception) -> None:
        self._fail_count += 1
        if self._fail_count >= _MAX_CONSECUTIVE_FAILURES:
            logger.error(
                f"AEC {side} 连续失败 {self._fail_count} 次，自动旁路: {err}",
                exc_info=True,
            )
            with self._lock:
                self._release()
        else:
            logger.debug(f"AEC {side} 处理失败（{self._fail_count}）: {err}")

    @staticmethod
    def _float_to_i16(x: np.ndarray) -> np.ndarray:
        return np.clip(x * 32768.0, -32768.0, 32767.0).astype(np.int16)
