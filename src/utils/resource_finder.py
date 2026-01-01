"""
统一资源路径解析器 - 开发/打包通用

所有用户数据统一存放在用户数据目录下：
- Windows: C:/Users/xxx/AppData/Local/{app_name}/
- macOS:   ~/Library/Application Support/{app_name}/
- Linux:   ~/.local/share/{app_name}/

目录结构：
├── config/      配置文件
├── cache/       缓存文件
├── logs/        日志文件
└── keywords/    唤醒词文件

核心 API：
- get_app_root()      应用根目录（安装目录，只读）
- get_app_name()      应用名称（固定值）
- get_user_data_dir() 用户数据目录（可写）
- get_user_cache_dir() 缓存目录（用户数据目录/cache）
- get_user_log_dir()  日志目录（用户数据目录/logs）
- get_lib_path()      动态库路径
- get_models_dir()    模型目录（安装目录，只读）
- get_assets_dir()    资源目录（安装目录，只读）
- get_config_dir()    配置目录（安装目录，只读，用于默认配置）
- get_user_keywords_path() 唤醒词文件路径（用户目录，自动复制）
"""

from __future__ import annotations

import platform as plat
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

import platformdirs


from src.constants.system import SystemConstants


@lru_cache(maxsize=1)
def get_app_root() -> Path:
    """应用根目录（开发/打包通用）

    - 开发时: 项目根目录
    - 打包后: _MEIPASS（PyInstaller onedir）
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    # src/utils/resource_finder.py → 往上 3 级
    return Path(__file__).resolve().parent.parent.parent


def get_app_name() -> str:
    """获取应用名称（固定值）

    从 SystemConstants.APP_NAME 获取，确保一致性。
    """
    return SystemConstants.APP_NAME


@lru_cache(maxsize=1)
def get_user_data_dir() -> Path:
    """用户数据目录（可写，存配置/数据库等）

    使用 platformdirs 确保符合各平台规范：
    - Windows: C:/Users/xxx/AppData/Local/{app_name}
    - macOS:   ~/Library/Application Support/{app_name}
    - Linux:   ~/.local/share/{app_name} 或 $XDG_DATA_HOME/{app_name}
    """
    p = Path(platformdirs.user_data_dir(get_app_name()))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_cache_dir() -> Path:
    """用户缓存目录（可写，存临时文件/缓存）

    统一存放在用户数据目录下：
    - Windows: C:/Users/xxx/AppData/Local/{app_name}/cache
    - macOS:   ~/Library/Application Support/{app_name}/cache
    - Linux:   ~/.local/share/{app_name}/cache
    """
    p = get_user_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_log_dir() -> Path:
    """用户日志目录（可写）

    统一存放在用户数据目录下：
    - Windows: C:/Users/xxx/AppData/Local/{app_name}/logs
    - macOS:   ~/Library/Application Support/{app_name}/logs
    - Linux:   ~/.local/share/{app_name}/logs
    """
    p = get_user_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_log_dir() -> Path:
    """日志目录（用户数据目录下，打包后可写）.

    Returns:
        日志目录路径
    """
    return get_user_log_dir()


@lru_cache(maxsize=1)
def get_platform_info() -> tuple[str, str]:
    """获取平台和架构信息.

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
    """获取动态库路径.

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
    """
    获取动态库所在目录.
    """
    lib_path = get_lib_path(lib_name)
    return lib_path.parent if lib_path else None


def get_models_dir() -> Path:
    """
    模型目录（只读，安装目录内）.
    """
    return get_app_root() / "models"


def get_assets_dir() -> Path:
    """
    资源目录（只读，安装目录内）.
    """
    return get_app_root() / "assets"


def get_config_dir() -> Path:
    """
    配置目录（应用内置，只读）
    """
    return get_app_root() / "config"


def get_user_keywords_path(lang: str) -> Path:
    """获取 keywords 路径，始终使用用户目录

    首次运行时自动从安装目录复制默认文件到用户目录。

    Args:
        lang: 语言代码，如 "zh" 或 "en"

    Returns:
        用户目录下的 keywords 文件路径
    """
    import shutil

    user_keywords_dir = get_user_data_dir() / "keywords"
    user_keywords = user_keywords_dir / f"{lang}_keywords.txt"

    if not user_keywords.exists():
        # 从安装目录复制默认文件
        default_keywords = get_app_root() / "models" / lang / "keywords.txt"
        if default_keywords.exists():
            user_keywords_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(default_keywords, user_keywords)

    return user_keywords
