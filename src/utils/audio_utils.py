import asyncio
import os
import re
import sys
from typing import Any

import numpy as np
import sounddevice as sd

from src.logging import get_logger

logger = get_logger()


class ALSAErrorSuppressor:
    """
    ALSA 错误输出抑制器。

    在 Linux 系统上，ALSA 库会输出大量警告和错误信息到 stderr，
    这些信息会干扰终端输出。此上下文管理器可临时抑制这些输出。

    用法:
        with ALSAErrorSuppressor():
            # 执行 PyAudio 初始化等操作
            audio = pyaudio.PyAudio()

    注意:
        - 仅在 Linux 系统上生效
        - 在 Windows/macOS 上无操作
        - 退出上下文时会恢复 stderr
    """

    def __init__(self):
        self._old_stderr = None
        self._devnull = None
        self._is_linux = sys.platform.startswith("linux")

    def __enter__(self):
        if not self._is_linux:
            return self

        try:
            self._old_stderr = os.dup(2)
            self._devnull = os.open("/dev/null", os.O_WRONLY)
            os.dup2(self._devnull, 2)
        except OSError:
            # 如果无法操作文件描述符，静默失败
            self._old_stderr = None
            self._devnull = None

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._is_linux:
            return False

        if self._old_stderr is not None:
            try:
                os.dup2(self._old_stderr, 2)
                os.close(self._old_stderr)
            except OSError:
                pass

        if self._devnull is not None:
            try:
                os.close(self._devnull)
            except OSError:
                pass

        return False  # 不抑制异常


def suppress_alsa_errors():
    """返回 ALSA 错误抑制器上下文管理器."""
    return ALSAErrorSuppressor()


# 可选：屏蔽常见虚拟/聚合设备（默认不选它们）
_VIRTUAL_PATTERNS = [
    r"blackhole",
    r"aggregate",
    r"multi[-\s]?output",  # macOS
    r"monitor",
    r"echo[-\s]?cancel",  # Linux Pulse/PipeWire
    r"vb[-\s]?cable",
    r"voicemeeter",
    r"cable (input|output)",  # Windows
    r"loopback",
]


def _is_virtual(name: str) -> bool:
    n = name.casefold()
    return any(re.search(pat, n) for pat in _VIRTUAL_PATTERNS)


def downmix_to_mono(
    pcm: np.ndarray | bytes,
    *,
    keepdims: bool = True,
    dtype: np.dtype | str = np.int16,
    in_channels: int | None = None,
) -> np.ndarray | bytes:
    """将任意格式的音频下混为单声道.

    支持两种输入:
    1. np.ndarray: 形状 (N,) 或 (N, C) 的 PCM 数组
    2. bytes: PCM 字节流 (需指定 dtype 和 in_channels)

    Args:
        pcm: 输入音频数据 (ndarray 或 bytes)
        keepdims: True 返回 (N,1)，False 返回 (N,) (仅 ndarray 输入)
        dtype: PCM 数据类型 (仅 bytes 输入时使用)
        in_channels: 输入声道数 (仅 bytes 输入时必需)

    Returns:
        单声道音频数据 (与输入类型相同)

    Examples:
        >>> # ndarray 输入
        >>> stereo = np.random.randint(-32768, 32767, (1000, 2), dtype=np.int16)
        >>> mono = downmix_to_mono(stereo, keepdims=False)  # shape: (1000,)

        >>> # bytes 输入
        >>> stereo_bytes = b'...'  # 立体声 PCM 数据
        >>> mono_bytes = downmix_to_mono(stereo_bytes, dtype=np.int16, in_channels=2)
    """
    # bytes 输入: 转换 -> 处理 -> 转回 bytes
    if isinstance(pcm, bytes):
        if in_channels is None:
            raise ValueError("bytes 输入必须指定 in_channels 参数")
        arr = np.frombuffer(pcm, dtype=dtype).reshape(-1, in_channels)
        mono_arr = downmix_to_mono(arr, keepdims=False)  # bytes 输出不需要 keepdims
        return mono_arr.tobytes()

    # ndarray 输入: 直接处理
    x = np.asarray(pcm)
    if x.ndim == 1:
        return x[:, None] if keepdims else x

    # 已经是单声道
    if x.shape[1] == 1:
        return x if keepdims else x[:, 0]

    # 多声道下混
    if np.issubdtype(x.dtype, np.integer):
        # 先转浮点求平均，再四舍五入回原整数类型，避免溢出
        y = np.rint(x.astype(np.float32).mean(axis=1))
        info = np.iinfo(x.dtype)
        y = np.clip(y, info.min, info.max).astype(x.dtype)
    else:
        # 浮点：保持原 dtype（比如 float32），避免默认为 float64
        y = x.mean(axis=1, dtype=x.dtype)

    return y[:, None] if keepdims else y


def safe_queue_put(
    queue: asyncio.Queue, item: Any, replace_oldest: bool = True
) -> bool:
    """安全地将项目放入队列，队列满时可选择丢弃最旧数据.

    Args:
        queue: asyncio.Queue 对象
        item: 要入队的数据
        replace_oldest: True=队列满时丢弃最旧数据并放入新数据, False=直接丢弃新数据

    Returns:
        True=成功入队, False=队列满且未入队
    """
    try:
        queue.put_nowait(item)
        return True
    except asyncio.QueueFull:
        if replace_oldest:
            try:
                queue.get_nowait()  # 丢弃最旧的
                queue.put_nowait(item)  # 放入新数据
                return True
            except asyncio.QueueEmpty:
                # 理论上不会发生,但保险起见
                queue.put_nowait(item)
                return True
        return False


def upmix_mono_to_channels(mono_data: np.ndarray, num_channels: int) -> np.ndarray:
    """将单声道音频上混到多声道（复制到所有声道）

    Args:
        mono_data: 单声道音频数据，形状 (N,)
        num_channels: 目标声道数

    Returns:
        多声道音频数据，形状 (N, num_channels)
    """
    if num_channels == 1:
        return mono_data.reshape(-1, 1)

    # 复制单声道到所有声道
    return np.tile(mono_data.reshape(-1, 1), (1, num_channels))


def _valid(devs: list[dict], idx: int, kind: str, include_virtual: bool) -> bool:
    if not isinstance(idx, int) or idx < 0 or idx >= len(devs):
        return False
    d = devs[idx]
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    if int(d.get(key, 0)) <= 0:
        return False
    if not include_virtual and _is_virtual(d.get("name", "")):
        return False
    return True


def refresh_portaudio_devices(*, reinitialize: bool = True) -> list[dict]:
    """重新枚举 PortAudio 设备列表（热插拔友好）.

    调用方须先停掉本进程内所有 sounddevice 流，再调本函数；
    有活跃流时 ``sd._terminate`` 不安全。

    Args:
        reinitialize: True 时尝试 ``_terminate`` + ``_initialize`` 强制
            重建 PortAudio 上下文（有利于 macOS 后连蓝牙出现在列表中）。
            失败则降级为普通 ``query_devices``。

    Returns:
        设备信息 dict 列表（与 ``list(sd.query_devices())`` 同形）
    """
    if reinitialize:
        terminate = getattr(sd, "_terminate", None)
        initialize = getattr(sd, "_initialize", None)
        if callable(terminate) and callable(initialize):
            try:
                terminate()
                initialize()
                logger.info("PortAudio 已重新初始化，准备重新枚举设备")
            except Exception as e:
                logger.warning(
                    f"PortAudio 重初始化失败，降级为普通枚举: {e}",
                    exc_info=True,
                )
        else:
            logger.debug("当前 sounddevice 无 _terminate/_initialize，跳过重初始化")

    try:
        devices = list(sd.query_devices())
    except Exception as e:
        logger.error(f"query_devices 失败: {e}", exc_info=True)
        return []

    logger.info(f"音频设备枚举完成: {len(devices)} 个")
    return devices


def list_audio_devices(
    *, include_virtual: bool = True
) -> dict[str, list[dict[str, Any]]]:
    """列出输入/输出设备（设置页与调试用）.

    不主动重初始化 PortAudio；需要热插拔刷新时先
    ``refresh_portaudio_devices()``，再调本函数。

    Returns:
        ``{"input": [...], "output": [...]}``，每项含 index/name/sample_rate/channels
    """
    try:
        devices = list(sd.query_devices())
    except Exception as e:
        logger.error(f"列出音频设备失败: {e}", exc_info=True)
        return {"input": [], "output": []}

    default_input = None
    default_output = None
    try:
        if sd.default.device is not None:
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]
    except Exception:
        pass

    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    for i, d in enumerate(devices):
        name = d.get("name", "Unknown")
        if not include_virtual and _is_virtual(name):
            continue
        sr = d.get("default_samplerate", 48000)
        sample_rate = int(sr) if isinstance(sr, (int, float)) else 48000
        idx = int(d.get("index", i))

        in_ch = int(d.get("max_input_channels", 0) or 0)
        out_ch = int(d.get("max_output_channels", 0) or 0)

        if in_ch > 0:
            mark = " (默认)" if idx == default_input else ""
            inputs.append(
                {
                    "index": idx,
                    "name": name + mark,
                    "raw_name": name,
                    "sample_rate": sample_rate,
                    "channels": in_ch,
                }
            )
        if out_ch > 0:
            mark = " (默认)" if idx == default_output else ""
            outputs.append(
                {
                    "index": idx,
                    "name": name + mark,
                    "raw_name": name,
                    "sample_rate": sample_rate,
                    "channels": out_ch,
                }
            )

    return {"input": inputs, "output": outputs}


def find_device_by_name(
    kind: str, device_name: str, *, include_virtual: bool = False
) -> dict[str, Any] | None:
    """按名称查找设备（模糊匹配）

    Args:
        kind: "input" 或 "output"
        device_name: 设备名称（支持部分匹配）
        include_virtual: 是否包含虚拟设备

    Returns:
        设备信息字典，或 None
    """
    assert kind in ("input", "output")

    try:
        devices = list(sd.query_devices())
    except Exception:
        return None

    key_channels = "max_input_channels" if kind == "input" else "max_output_channels"
    search_name = device_name.casefold().strip()

    # 1. 精确匹配（忽略大小写）
    for i, d in enumerate(devices):
        if not _valid(devices, i, kind, include_virtual):
            continue
        if d.get("name", "").casefold().strip() == search_name:
            sr = d.get("default_samplerate", None)
            return {
                "index": int(d.get("index", i)),
                "name": d.get("name", "Unknown"),
                "sample_rate": int(sr) if isinstance(sr, (int, float)) else None,
                "channels": int(d.get(key_channels, 0)),
            }

    # 2. 模糊匹配（包含关系）
    for i, d in enumerate(devices):
        if not _valid(devices, i, kind, include_virtual):
            continue
        device_full_name = d.get("name", "").casefold()
        if search_name in device_full_name or device_full_name in search_name:
            sr = d.get("default_samplerate", None)
            return {
                "index": int(d.get("index", i)),
                "name": d.get("name", "Unknown"),
                "sample_rate": int(sr) if isinstance(sr, (int, float)) else None,
                "channels": int(d.get(key_channels, 0)),
            }

    return None


def select_audio_device(
    kind: str, *, include_virtual: bool = False
) -> dict[str, Any] | None:
    """自动选择音频设备（简化版）

    策略：
    1. 系统默认设备（sounddevice 推荐）
    2. 第一个可用的非虚拟设备

    Args:
        kind: "input" 或 "output"
        include_virtual: 是否包含虚拟设备

    Returns:
        {index, name, sample_rate, channels} 或 None
    """
    assert kind in ("input", "output")

    try:
        devices = list(sd.query_devices())
    except Exception:
        return None

    key_channels = "max_input_channels" if kind == "input" else "max_output_channels"

    def pack(idx: int, base: dict | None = None) -> dict[str, Any] | None:
        if base is None:
            if not _valid(devices, idx, kind, include_virtual):
                return None
            d = devices[idx]
        else:
            d = base
            if not include_virtual and _is_virtual(d.get("name", "")):
                return None
        sr = d.get("default_samplerate", None)
        return {
            "index": int(d.get("index", idx)),
            "name": d.get("name", "Unknown"),
            "sample_rate": int(sr) if isinstance(sr, (int, float)) else None,
            "channels": int(d.get(key_channels, 0)),
        }

    # 1. sounddevice 系统默认（最可靠）
    try:
        info = sd.query_devices(kind=kind)
        packed = pack(int(info.get("index")), base=info)
        if packed:
            return packed
    except Exception:
        logger.debug(f"查询系统默认{kind}设备失败，尝试兜底策略")

    # 2. 兜底：第一个可用的非虚拟设备
    for i, _d in enumerate(devices):
        if _valid(devices, i, kind, include_virtual):
            return pack(i)

    return None
