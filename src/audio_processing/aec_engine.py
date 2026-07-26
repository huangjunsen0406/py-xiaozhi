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

import numpy as np

from src.logging import get_logger

logger = get_logger()

# 连续处理失败达到该次数后自动旁路，避免坏库拖垮音频回调
_MAX_CONSECUTIVE_FAILURES = 5
# far 待处理队列上限（输出回调块数，约 20ms/块 → 0.5s）；
# 采集线程停转时防堆积，超限丢最旧
_FAR_PENDING_MAX_BLOCKS = 25


def _import_webrtc_apm():
    """导入 libs.webrtc_apm，源码运行与打包形态各有路径兜底."""
    try:
        from libs import webrtc_apm

        return webrtc_apm
    except ImportError:
        from src.utils.resource_finder import get_app_root

        root = str(get_app_root())
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
    ):
        """初始化并加载 APM；失败时 active=False（旁路）.

        Args:
            near_rate: 采集协议采样率（16kHz）
            far_rate: 设备输出采样率（far 侧重采样源）
            delay_ms: 播放到采集的估计延迟
            enable_preprocess: 是否同时开高通+噪声抑制
        """
        self._near_rate = int(near_rate)
        self._far_rate = int(far_rate)
        self._delay_ms = int(delay_ms)
        self._frame = self._near_rate // 100  # 10ms
        self._lock = threading.Lock()
        self._active = False
        self._closed = False
        self._fail_count = 0
        self._near_misaligned_logged = False

        self._apm = None
        self._stream_cfg = None
        # far 两级缓冲：pending 由输出回调写入（仅拷贝），
        # buffer 为采集线程重采样后的 16k 样本余量
        self._far_pending: deque = deque()
        self._far_buffer = np.empty(0, dtype=np.float32)
        self._far_resampler = None
        self._far_dropped = 0

        # 复用的 ctypes 帧缓冲（10ms int16）
        self._near_in = (ctypes.c_short * self._frame)()
        self._near_out = (ctypes.c_short * self._frame)()
        self._far_in = (ctypes.c_short * self._frame)()
        self._far_out = (ctypes.c_short * self._frame)()

        try:
            self._init_apm(enable_preprocess)
            if self._far_rate != self._near_rate:
                import soxr

                self._far_resampler = soxr.ResampleStream(
                    self._far_rate,
                    self._near_rate,
                    num_channels=1,
                    dtype="float32",
                    quality="QQ",
                )
            self._active = True
            logger.info(
                f"AEC 引擎已启用 | near {self._near_rate}Hz, "
                f"far {self._far_rate}Hz→{self._near_rate}Hz, "
                f"delay {self._delay_ms}ms, preprocess={enable_preprocess}"
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
            i16 = self._float_to_i16(block)
            out = np.empty(n, dtype=np.float32)

            with self._lock:
                if not self._active:
                    return block
                # far 先于 near：排空输出回调攒下的参考数据，保持因果
                self._drain_far_locked()
                self._apm.set_stream_delay_ms(self._delay_ms)
                for off in range(0, n, self._frame):
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

            self._fail_count = 0
            return out
        except Exception as e:
            self._on_failure("near", e)
            return block

    def feed_far(self, outdata: np.ndarray) -> None:
        """输出回调线程调用：仅下混+拷贝入队，不做重采样/APM（微秒级返回）.

        含静音帧也应喂入，保持 far 流连续；重活由采集线程 process_near 完成。
        """
        if not self._active:
            return

        try:
            if outdata.ndim > 1 and outdata.shape[1] > 1:
                mono = outdata.mean(axis=1, dtype=np.float32)
            else:
                # PortAudio 复用 outdata 内存，必须拷贝
                mono = np.array(outdata, dtype=np.float32).ravel()

            self._far_pending.append(mono)
            # deque 操作在 GIL 下原子；超限丢最旧（采集线程停转时防堆积）
            while len(self._far_pending) > _FAR_PENDING_MAX_BLOCKS:
                self._far_pending.popleft()
                self._far_dropped += 1
        except Exception:
            pass  # 输出路径绝不抛

    def _drain_far_locked(self) -> None:
        """采集线程（已持锁）：重采样 far 队列并喂给 ProcessReverseStream."""
        while self._far_pending:
            mono = self._far_pending.popleft()
            if self._far_resampler is not None:
                mono = self._far_resampler.resample_chunk(mono, last=False)
            if len(mono):
                self._far_buffer = np.concatenate((self._far_buffer, mono))

        n_frames = len(self._far_buffer) // self._frame
        if n_frames == 0:
            return

        usable = n_frames * self._frame
        i16 = self._float_to_i16(self._far_buffer[:usable])
        self._far_buffer = self._far_buffer[usable:]

        for off in range(0, usable, self._frame):
            ctypes.memmove(
                self._far_in, i16[off : off + self._frame].ctypes.data, self._frame * 2
            )
            ret = self._apm.process_reverse_stream(
                self._far_in, self._stream_cfg, self._stream_cfg, self._far_out
            )
            if ret != 0:
                raise RuntimeError(f"process_reverse_stream 返回 {ret}")

    def set_delay_ms(self, delay_ms: int) -> None:
        self._delay_ms = int(delay_ms)

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
        self._far_resampler = None
        self._far_pending.clear()
        self._far_buffer = np.empty(0, dtype=np.float32)
        if self._far_dropped:
            logger.debug(f"AEC far 累计丢弃 {self._far_dropped} 块")

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
