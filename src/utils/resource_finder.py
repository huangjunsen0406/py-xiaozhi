"""
统一资源路径解析器 - 开发/打包通用

默认用户数据目录（platformdirs）：
- Windows: C:/Users/xxx/AppData/Local/{app_name}/
- macOS:   ~/Library/Application Support/{app_name}/
- Linux:   ~/.local/share/{app_name}/

默认子目录：config/ cache/ logs/ keywords/ mcp_plugins/

可覆盖（config 目录建议保持默认；其它可迁）：
- 环境变量：XIAOZHI_DATA_DIR / XIAOZHI_CACHE_DIR / XIAOZHI_LOG_DIR /
  XIAOZHI_MUSIC_CACHE_DIR / XIAOZHI_KEYWORDS_DIR
- 配置 PATHS.*（见 apply_path_overrides_from_config；改后可迁移旧目录）

核心 API：
- get_app_root() / get_app_name()
- get_user_data_dir() / get_user_cache_dir() / get_user_log_dir()
- get_music_cache_dir() / get_keywords_dir()
- apply_path_overrides_from_config() / migrate_directory()
"""

from __future__ import annotations

import os
import platform as plat
import shutil
import sys
from functools import lru_cache
from pathlib import Path

import platformdirs

from src.constants.system import SystemConstants

# 环境变量名
ENV_DATA_DIR = "XIAOZHI_DATA_DIR"
ENV_CACHE_DIR = "XIAOZHI_CACHE_DIR"
ENV_LOG_DIR = "XIAOZHI_LOG_DIR"
ENV_MUSIC_CACHE_DIR = "XIAOZHI_MUSIC_CACHE_DIR"
ENV_KEYWORDS_DIR = "XIAOZHI_KEYWORDS_DIR"

# 运行时覆盖（config 加载后 apply；env 优先于这些）
_override_cache: Path | None = None
_override_log: Path | None = None
_override_music: Path | None = None
_override_keywords: Path | None = None


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


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
    """用户数据目录（可写：默认含 config/）

    优先环境变量 XIAOZHI_DATA_DIR，否则 platformdirs。
    配置文件建议始终在此目录下的 config/，保证能读到 PATHS 覆盖项。
    """
    env = _env_path(ENV_DATA_DIR)
    if env is not None:
        p = env
    else:
        p = Path(platformdirs.user_data_dir(get_app_name()))
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_cache_dir() -> Path:
    """缓存目录：XIAOZHI_CACHE_DIR > 运行时覆盖 > {data}/cache."""
    env = _env_path(ENV_CACHE_DIR)
    if env is not None:
        p = env
    elif _override_cache is not None:
        p = _override_cache
    else:
        p = get_user_data_dir() / "cache"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_user_log_dir() -> Path:
    """日志目录：XIAOZHI_LOG_DIR > 运行时覆盖 > {data}/logs."""
    env = _env_path(ENV_LOG_DIR)
    if env is not None:
        p = env
    elif _override_log is not None:
        p = _override_log
    else:
        p = get_user_data_dir() / "logs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_log_dir() -> Path:
    """日志目录（用户数据目录下，打包后可写）."""
    return get_user_log_dir()


def get_music_cache_dir() -> Path:
    """音乐缓存：XIAOZHI_MUSIC_CACHE_DIR > 覆盖 > {cache}/music."""
    env = _env_path(ENV_MUSIC_CACHE_DIR)
    if env is not None:
        p = env
    elif _override_music is not None:
        p = _override_music
    else:
        p = get_user_cache_dir() / "music"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_keywords_dir() -> Path:
    """唤醒词目录：XIAOZHI_KEYWORDS_DIR > 覆盖 > {data}/keywords."""
    env = _env_path(ENV_KEYWORDS_DIR)
    if env is not None:
        p = env
    elif _override_keywords is not None:
        p = _override_keywords
    else:
        p = get_user_data_dir() / "keywords"
    p.mkdir(parents=True, exist_ok=True)
    return p


def clear_path_caches() -> None:
    """清除 get_user_data_dir 等 lru 缓存（测试或 DATA_DIR 变更后）."""
    get_user_data_dir.cache_clear()
    get_app_root.cache_clear()


def migrate_directory(src: Path, dst: Path, *, copy: bool = True) -> dict:
    """将旧目录内容复制到新目录（默认不删除源，安全）.

    Returns:
        {ok, src, dst, files_copied, error?}
    """
    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()
    result: dict = {
        "ok": False,
        "src": str(src),
        "dst": str(dst),
        "files_copied": 0,
    }
    if src == dst:
        result["ok"] = True
        result["skipped"] = "same_path"
        return result
    if not src.is_dir():
        result["ok"] = True
        result["skipped"] = "src_missing"
        return result
    try:
        dst.mkdir(parents=True, exist_ok=True)
        count = 0
        for root, _dirs, files in os.walk(src):
            rel = Path(root).relative_to(src)
            target_root = dst / rel
            target_root.mkdir(parents=True, exist_ok=True)
            for name in files:
                s = Path(root) / name
                d = target_root / name
                if d.exists():
                    continue  # 不覆盖已有
                if copy:
                    shutil.copy2(s, d)
                else:
                    shutil.move(str(s), str(d))
                count += 1
        result["ok"] = True
        result["files_copied"] = count
    except Exception as e:
        result["error"] = str(e)
    return result


def apply_path_overrides_from_config(
    config,
    *,
    migrate: bool = True,
) -> list[dict]:
    """从 ConfigManager 读取 PATHS，设置运行时覆盖，并可选迁移旧目录.

    环境变量始终优先于配置。config 目录不由此迁移。

    Returns:
        迁移结果列表（便于 UI/日志）
    """
    global _override_cache, _override_log, _override_music, _override_keywords

    migrations: list[dict] = []

    def _cfg(key: str) -> str | None:
        try:
            v = config.get_config(key, None)
        except Exception:
            return None
        if v is None or str(v).strip() == "":
            return None
        return str(v).strip()

    # 当前有效路径（应用覆盖前）作为迁移源
    old_cache = get_user_cache_dir()
    old_log = get_user_log_dir()
    old_music = get_music_cache_dir()
    old_kw = get_keywords_dir()

    cache_s = _cfg("PATHS.CACHE_DIR")
    log_s = _cfg("PATHS.LOG_DIR")
    music_s = _cfg("PATHS.MUSIC_CACHE_DIR")
    kw_s = _cfg("PATHS.KEYWORDS_DIR")

    # 仅当 env 未设时应用 config 覆盖
    if _env_path(ENV_CACHE_DIR) is None:
        _override_cache = Path(cache_s).expanduser().resolve() if cache_s else None
    if _env_path(ENV_LOG_DIR) is None:
        _override_log = Path(log_s).expanduser().resolve() if log_s else None
    if _env_path(ENV_MUSIC_CACHE_DIR) is None:
        _override_music = Path(music_s).expanduser().resolve() if music_s else None
    if _env_path(ENV_KEYWORDS_DIR) is None:
        _override_keywords = Path(kw_s).expanduser().resolve() if kw_s else None

    if not migrate:
        return migrations

    pairs = [
        ("cache", old_cache, get_user_cache_dir()),
        ("logs", old_log, get_user_log_dir()),
        ("music", old_music, get_music_cache_dir()),
        ("keywords", old_kw, get_keywords_dir()),
    ]
    for kind, src, dst in pairs:
        if src.resolve() == dst.resolve():
            continue
        # 仅当新路径来自配置/env 覆盖时迁移（dst 与默认不同）
        r = migrate_directory(src, dst, copy=True)
        r["kind"] = kind
        migrations.append(r)
        try:
            from src.logging import get_logger

            get_logger().info(
                "路径迁移 %s: %s -> %s (copied=%s, ok=%s)",
                kind,
                src,
                dst,
                r.get("files_copied"),
                r.get("ok"),
            )
        except Exception:
            pass

    return migrations


def set_path_overrides(
    *,
    cache: Path | str | None = None,
    log: Path | str | None = None,
    music: Path | str | None = None,
    keywords: Path | str | None = None,
) -> None:
    """测试或编程方式设置覆盖（env 仍优先）."""
    global _override_cache, _override_log, _override_music, _override_keywords

    def _p(v):
        if v is None or str(v).strip() == "":
            return None
        return Path(v).expanduser().resolve()

    if cache is not None:
        _override_cache = _p(cache)
    if log is not None:
        _override_log = _p(log)
    if music is not None:
        _override_music = _p(music)
    if keywords is not None:
        _override_keywords = _p(keywords)


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


def get_lib_path(lib_name: str) -> Path | None:
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


def get_lib_dir(lib_name: str) -> Path | None:
    """
    获取动态库所在目录.
    """
    lib_path = get_lib_path(lib_name)
    return lib_path.parent if lib_path else None


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径.

    搜索顺序：内置 libs/ffmpeg/ → 系统 PATH
    """
    import shutil

    plat_dir, arch = get_platform_info()
    ext = ".exe" if sys.platform == "win32" else ""
    bundled = get_app_root() / "libs" / "ffmpeg" / plat_dir / arch / f"ffmpeg{ext}"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffmpeg") or "ffmpeg"


def get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径.

    搜索顺序：内置 libs/ffmpeg/ → 系统 PATH
    """
    import shutil

    plat_dir, arch = get_platform_info()
    ext = ".exe" if sys.platform == "win32" else ""
    bundled = get_app_root() / "libs" / "ffmpeg" / plat_dir / arch / f"ffprobe{ext}"
    if bundled.exists():
        return str(bundled)
    return shutil.which("ffprobe") or "ffprobe"


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

    user_keywords_dir = get_keywords_dir()
    user_keywords = user_keywords_dir / f"{lang}_keywords.txt"

    if not user_keywords.exists():
        # 从安装目录复制默认文件
        default_keywords = get_app_root() / "models" / lang / "keywords.txt"
        if default_keywords.exists():
            user_keywords_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(default_keywords, user_keywords)

    return user_keywords
