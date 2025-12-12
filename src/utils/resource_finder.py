"""
统一资源路径解析器 - 开发/打包通用

核心 API：
- get_app_root()      应用根目录
- get_app_name()      应用名称（自动推断）
- get_user_data_dir() 用户数据目录
- get_user_cache_dir() 缓存目录
- get_lib_path()      动态库路径
- get_models_dir()    模型目录
- get_assets_dir()    资源目录
- get_config_dir()    配置目录
"""

from __future__ import annotations

import platform as plat
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional


@lru_cache(maxsize=1)
def get_app_root() -> Path:
    """
    应用根目录（开发/打包通用）

    - 开发时: 项目根目录
    - 打包后: _MEIPASS（PyInstaller onedir）
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    # src/utils/resource_finder.py → 往上 3 级
    return Path(__file__).resolve().parent.parent.parent


@lru_cache(maxsize=1)
def get_app_name() -> str:
    """
    获取应用名称（自动推断）

    - 开发时：项目根目录名
    - 打包后：可执行文件名 / .app bundle 名
    """
    if getattr(sys, "frozen", False):
        # macOS: 从 .app bundle 名获取
        if sys.platform == "darwin":
            exe = Path(sys.executable).resolve()
            for p in [exe] + list(exe.parents):
                if p.suffix == ".app":
                    return p.stem
        # Windows/Linux: 从可执行文件名获取
        return Path(sys.executable).stem

    # 开发时：从项目根目录名获取
    return get_app_root().name


@lru_cache(maxsize=1)
def get_user_data_dir() -> Path:
    """
    用户数据目录（可写，存配置/数据库等）

    - Windows: C:/Users/xxx/AppData/Local/{app_name}
    - macOS:   ~/Library/Application Support/{app_name}
    - Linux:   ~/.local/share/{app_name}
    """
    app_name = get_app_name()
    home = Path.home()

    if sys.platform == "win32":
        p = home / "AppData" / "Local" / app_name
    elif sys.platform == "darwin":
        p = home / "Library" / "Application Support" / app_name
    else:
        p = home / ".local" / "share" / app_name

    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_cache_dir() -> Path:
    """用户缓存目录"""
    p = get_user_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


@lru_cache(maxsize=1)
def get_platform_info() -> tuple[str, str]:
    """
    获取平台和架构信息

    Returns:
        (platform_dir, arch_dir) 如 ("mac", "arm64")
    """
    machine = plat.machine().lower()
    is_arm = "arm" in machine or "aarch64" in machine

    if sys.platform == "win32":
        return "win", "x64"
    elif sys.platform == "darwin":
        return "mac", "arm64" if is_arm else "x64"
    else:
        return "linux", "arm64" if is_arm else "x64"


def get_lib_path(lib_name: str) -> Optional[Path]:
    """
    获取动态库路径

    Args:
        lib_name: 库名，如 "libopus", "webrtc_apm"

    Returns:
        库文件的完整路径，找不到返回 None
    """
    plat_dir, arch = get_platform_info()
    root = get_app_root() / "libs" / lib_name

    # 平台目录别名（mac/macos, win/windows）
    plat_aliases = {
        "mac": ["mac", "macos"],
        "win": ["win", "windows"],
        "linux": ["linux"],
    }

    # 扩展名
    ext_map = {"mac": ".dylib", "win": ".dll", "linux": ".so"}
    ext = ext_map.get(plat_dir, ".so")

    # 尝试所有可能的平台目录名
    for plat_name in plat_aliases.get(plat_dir, [plat_dir]):
        lib_dir = root / plat_name / arch
        if not lib_dir.exists():
            continue

        for f in lib_dir.iterdir():
            if f.is_file() and (f.suffix == ext or ext in f.name):
                return f

    return None


def get_lib_dir(lib_name: str) -> Optional[Path]:
    """获取动态库所在目录"""
    lib_path = get_lib_path(lib_name)
    return lib_path.parent if lib_path else None


def get_models_dir() -> Path:
    """模型目录"""
    return get_app_root() / "models"


def get_assets_dir() -> Path:
    """资源目录"""
    return get_app_root() / "assets"


def get_config_dir() -> Path:
    """配置目录（应用内置）"""
    return get_app_root() / "config"
