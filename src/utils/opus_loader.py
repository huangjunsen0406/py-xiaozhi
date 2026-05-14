"""Opus 库加载器 - 确保 opuslib 能找到 opus 动态库."""

from __future__ import annotations

import ctypes
import ctypes.util
import os
import sys
from pathlib import Path

from src.logging import get_logger
from src.utils.resource_finder import get_lib_path

logger = get_logger()

_opus_loaded = False


def _find_system_opus() -> str | None:
    """查找系统安装的 opus 库."""
    if sys.platform == "win32":
        return None

    if sys.platform == "darwin":
        candidates = [
            "/opt/homebrew/lib/libopus.dylib",
            "/usr/local/lib/libopus.dylib",
        ]
    else:
        candidates = [
            "/usr/lib/libopus.so.0",
            "/usr/lib/x86_64-linux-gnu/libopus.so.0",
            "/usr/lib/aarch64-linux-gnu/libopus.so.0",
            "/usr/local/lib/libopus.so",
        ]

    for path in candidates:
        if Path(path).exists():
            return path

    return ctypes.util.find_library("opus")


def _try_load(path: str | Path) -> bool:
    """尝试加载动态库."""
    try:
        ctypes.CDLL(str(path))
        return True
    except OSError:
        return False


def _patch_find_library(lib_path: str):
    """修补 ctypes.util.find_library，让 opuslib 能找到 opus."""
    original = ctypes.util.find_library

    def patched(name: str) -> str | None:
        if name == "opus":
            return lib_path
        return original(name)

    ctypes.util.find_library = patched


def setup_opus() -> bool:
    """设置 opus 库，供 opuslib 使用.

    搜索顺序：
    1. 项目内置 opus（libs/libopus/）— 版本可控、部署一致
    2. 系统 opus（brew/apt）— 兜底

    Returns:
        是否成功加载
    """
    global _opus_loaded
    if _opus_loaded:
        return True

    # 1. 优先内置 opus
    bundled_path = get_lib_path("libopus")
    if bundled_path and bundled_path.exists():
        if sys.platform == "win32":
            lib_dir = str(bundled_path.parent)
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(lib_dir)
            os.environ["PATH"] = lib_dir + os.pathsep + os.environ.get("PATH", "")

        if _try_load(bundled_path):
            logger.debug(f"使用内置 opus: {bundled_path}")
            _patch_find_library(str(bundled_path))
            _opus_loaded = True
            return True

    # 2. 兜底：系统 opus
    system_path = _find_system_opus()
    if system_path and _try_load(system_path):
        logger.debug(f"使用系统 opus: {system_path}")
        _patch_find_library(system_path)
        _opus_loaded = True
        return True

    logger.warning(
        "未找到 opus 库，音频编解码可能无法工作。"
        "Linux/macOS 可通过包管理器安装: brew install opus / apt install libopus0"
    )
    return False
