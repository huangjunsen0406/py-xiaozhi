import asyncio
import platform
import re
from typing import Any, Dict, List, Optional

import numpy as np
import sounddevice as sd

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


def _valid(devs: List[dict], idx: int, kind: str, include_virtual: bool) -> bool:
    if not isinstance(idx, int) or idx < 0 or idx >= len(devs):
        return False
    d = devs[idx]
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    if int(d.get(key, 0)) <= 0:
        return False
    if not include_virtual and _is_virtual(d.get("name", "")):
        return False
    return True


def select_audio_device(
    kind: str,
    *,
    include_virtual: bool = False,
    allow_name_hints: Optional[bool] = None,  # None=Linux 才启用；True/False 可强制
) -> Optional[Dict[str, Any]]:
    """
    选择音频设备：HostAPI 默认 →（可选：设备名 hints，仅 Linux）→ sounddevice 系统默认 → 第一个可用 返回：{index, name,
    sample_rate, channels} 或 None.
    """
    assert kind in ("input", "output")
    system = platform.system().lower()

    # HostAPI 优先表
    if system == "windows":
        host_order = ["wasapi", "wdm-ks", "directsound", "mme"]
    elif system == "darwin":
        host_order = ["core audio"]
    else:
        host_order = ["alsa", "jack", "oss"]  # 多数 Linux 的 PortAudio 只有 ALSA

    # Linux 才默认启用 name hints；其它平台默认关闭（可通过参数打开）
    if allow_name_hints is None:
        allow_name_hints = system == "linux"

    DEVICE_NAME_HINTS = {
        "input": ["default", "sysdefault", "pulse", "pipewire"],
        "output": ["default", "sysdefault", "dmix", "pulse", "pipewire"],
    }

    # 枚举
    try:
        hostapis = list(sd.query_hostapis())
        devices = list(sd.query_devices())
    except Exception:
        hostapis, devices = [], []

    key_host_default = (
        "default_input_device" if kind == "input" else "default_output_device"
    )
    key_channels = "max_input_channels" if kind == "input" else "max_output_channels"

    def pack(idx: int, base: Optional[dict] = None) -> Optional[Dict[str, Any]]:
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

    # 1) 按 HostAPI 名称匹配（包含、忽略大小写）→ 取该 HostAPI 的“默认设备”
    for token in host_order:
        t = token.casefold()
        for ha in hostapis:
            if t in str(ha.get("name", "")).casefold():
                idx = ha.get(key_host_default, -1)
                info = pack(idx)
                if info:
                    return info

    # 1.5) （可选）设备名 hints，仅当 allow_name_hints=True 时启用（默认 Linux）
    if allow_name_hints and devices:
        hints = [h.casefold() for h in DEVICE_NAME_HINTS[kind]]
        cands: List[int] = []
        for i, d in enumerate(devices):
            if not _valid(devices, i, kind, include_virtual):
                continue
            name_low = str(d.get("name", "")).casefold()
            if any(h in name_low for h in hints):
                cands.append(i)
        if cands:
            cands.sort()  # 稳定：索引小优先
            info = pack(cands[0])
            if info:
                return info

    # 2) sounddevice 的系统默认（已考虑平台默认路由）
    try:
        info = sd.query_devices(
            kind=kind
        )  # dict，含 index / default_samplerate / max_*_channels
        packed = pack(int(info.get("index")), base=info)
        if packed:
            return packed
    except Exception:
        pass

    # 3) 兜底：第一个可用（且非虚拟，除非允许）
    for i, d in enumerate(devices):
        if _valid(devices, i, kind, include_virtual):
            return pack(i)

    return None
