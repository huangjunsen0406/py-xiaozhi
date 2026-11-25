"""Cross-platform system audio loopback ctypes wrapper.

Loads the precompiled platform library from ``libs/system_loopback/<os>/<arch>/``
and exposes :class:`SystemLoopbackStream` for non-blocking mono float32 reads.
"""

from __future__ import annotations

import ctypes
import platform
from enum import IntEnum
from pathlib import Path

import numpy as np


class SystemLoopbackStatus(IntEnum):
    """Status codes matching ``slb_status_t`` in ``system_loopback.h``."""

    OK = 0
    ERR_UNSUPPORTED = -1
    ERR_PERMISSION_DENIED = -2
    ERR_DEVICE_NOT_FOUND = -3
    ERR_INIT_FAILED = -4
    ERR_DEVICE_LOST = -5
    ERR_INVALID_ARG = -6


class SystemLoopbackError(RuntimeError):
    """Raised when native system loopback creation/start/read fails."""

    def __init__(self, status: SystemLoopbackStatus, message: str = "") -> None:
        self.status = status
        detail = f": {message}" if message else ""
        super().__init__(f"{status.name} ({int(status)}){detail}")


def _get_library_path() -> str:
    """Resolve platform/architecture-specific native loopback library path."""
    current_dir = Path(__file__).parent
    system = platform.system().lower()
    arch = platform.machine().lower()

    if arch in ("x86_64", "amd64"):
        arch = "x64"
    elif arch in ("aarch64", "arm64"):
        arch = "arm64"
    elif arch in ("i386", "i686", "x86"):
        arch = "x86"

    if system == "linux":
        lib_path = current_dir / "linux" / arch / "libsystem_loopback.so"
    elif system == "darwin":
        lib_path = current_dir / "macos" / arch / "libsystem_loopback.dylib"
    elif system == "windows":
        lib_path = current_dir / "windows" / arch / "system_loopback.dll"
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    if not lib_path.exists():
        raise FileNotFoundError(f"System loopback library not found: {lib_path}")

    return str(lib_path)


_lib = None


def _ensure_library_loaded():
    global _lib
    if _lib is not None:
        return _lib

    lib = ctypes.CDLL(_get_library_path())
    lib.slb_create.argtypes = [
        ctypes.c_char_p,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.slb_create.restype = ctypes.c_int

    lib.slb_start.argtypes = [ctypes.c_void_p]
    lib.slb_start.restype = ctypes.c_int

    lib.slb_read_f32.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_float),
        ctypes.c_int,
    ]
    lib.slb_read_f32.restype = ctypes.c_int

    lib.slb_last_error.argtypes = [ctypes.c_void_p]
    lib.slb_last_error.restype = ctypes.c_char_p

    lib.slb_stop.argtypes = [ctypes.c_void_p]
    lib.slb_stop.restype = None

    lib.slb_destroy.argtypes = [ctypes.c_void_p]
    lib.slb_destroy.restype = None

    _lib = lib
    return _lib


def is_library_available() -> bool:
    """Return True if the precompiled native loopback binary exists for this host."""
    try:
        _get_library_path()
        return True
    except Exception:
        return False


class SystemLoopbackStream:
    """High-level wrapper around a native ``SystemLoopback`` handle."""

    def __init__(self, target_device_name: str | None = None) -> None:
        self._lib = _ensure_library_loaded()
        self._handle = ctypes.c_void_p(0)
        self._closed = False
        self._sample_rate = 0
        self._channels = 1

        rate = ctypes.c_int(0)
        channels = ctypes.c_int(0)
        handle = ctypes.c_void_p(0)
        hint = target_device_name.encode("utf-8") if target_device_name else None

        rc = self._lib.slb_create(
            hint, ctypes.byref(rate), ctypes.byref(channels), ctypes.byref(handle)
        )
        if rc != int(SystemLoopbackStatus.OK) or not handle.value:
            status = _coerce_status(rc)
            raw_err = self._lib.slb_last_error(None)
            detail = raw_err.decode("utf-8", errors="replace") if raw_err else ""
            raise SystemLoopbackError(
                status, detail or _default_hint_for_status(status)
            )

        self._handle = handle
        self._sample_rate = int(rate.value) or 48000
        self._channels = int(channels.value) or 1

        start_rc = self._lib.slb_start(self._handle)
        if start_rc != int(SystemLoopbackStatus.OK):
            err_msg = self._get_last_error()
            self.close()
            status = _coerce_status(start_rc)
            raise SystemLoopbackError(
                status, err_msg or _default_hint_for_status(status)
            )

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def _get_last_error(self) -> str:
        if not self._handle or not self._handle.value:
            return ""
        raw = self._lib.slb_last_error(self._handle)
        return raw.decode("utf-8", errors="replace") if raw else ""

    def read_f32(self, max_frames: int = 8192) -> np.ndarray:
        """Non-blocking read of mono float32 samples; raises on device loss."""
        if self._closed or not self._handle or not self._handle.value:
            return np.empty(0, dtype=np.float32)

        buf = np.empty(max_frames, dtype=np.float32)
        n = self._lib.slb_read_f32(
            self._handle,
            buf.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            int(max_frames),
        )
        if n < 0:
            status = _coerce_status(n)
            raise SystemLoopbackError(
                status, self._get_last_error() or _default_hint_for_status(status)
            )
        if n == 0:
            return np.empty(0, dtype=np.float32)
        return buf[:n]

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._handle and self._handle.value:
            try:
                self._lib.slb_stop(self._handle)
            finally:
                self._lib.slb_destroy(self._handle)
                self._handle = ctypes.c_void_p(0)

    def __enter__(self) -> SystemLoopbackStream:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


def _coerce_status(code: int) -> SystemLoopbackStatus:
    try:
        return SystemLoopbackStatus(code)
    except ValueError:
        return SystemLoopbackStatus.ERR_INIT_FAILED


def _default_hint_for_status(status: SystemLoopbackStatus) -> str:
    hints = {
        SystemLoopbackStatus.ERR_UNSUPPORTED: "OS or audio runtime does not support system loopback (macOS requires 14.2+, Linux requires PulseAudio/PipeWire)",
        SystemLoopbackStatus.ERR_PERMISSION_DENIED: "System audio capture permission denied",
        SystemLoopbackStatus.ERR_DEVICE_NOT_FOUND: "No active output or monitor audio device found",
        SystemLoopbackStatus.ERR_DEVICE_LOST: "System output audio device was invalidated or disconnected",
    }
    return hints.get(status, "")


__all__ = [
    "SystemLoopbackStatus",
    "SystemLoopbackError",
    "SystemLoopbackStream",
    "is_library_available",
]
