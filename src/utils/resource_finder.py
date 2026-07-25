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


def migrate_directory(
    src: Path,
    dst: Path,
    *,
    copy: bool = True,
    skip_dir_names: set[str] | frozenset[str] | None = None,
) -> dict:
    """将旧目录内容复制到新目录（默认不删除源，安全）.

    skip_dir_names: 顶层（相对 src）目录名集合，整棵子树跳过不拷
        （例如 cache 迁移时 music 已单独配置则跳过 music/）。

    Returns:
        {ok, src, dst, files_copied, error?}
    """
    src = src.expanduser().resolve()
    dst = dst.expanduser().resolve()
    skip = set(skip_dir_names or ())
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
        for root, dirs, files in os.walk(src):
            rel = Path(root).relative_to(src)
            # 顶层目录过滤：os.walk 可改 dirs in-place
            if rel == Path("."):
                dirs[:] = [d for d in dirs if d not in skip]
            else:
                # 若相对路径第一段在 skip 中（防御）
                if rel.parts and rel.parts[0] in skip:
                    dirs[:] = []
                    continue
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

    new_cache = get_user_cache_dir()
    new_log = get_user_log_dir()
    new_music = get_music_cache_dir()
    new_kw = get_keywords_dir()

    # cache 迁移时：若 music 已单独指到其它目录（或即将单独迁），跳过 cache/music 子树
    cache_skip: set[str] = set()
    try:
        music_under_old_cache = old_music.resolve() == (old_cache / "music").resolve()
        music_stays_default_under_new = new_music.resolve() == (
            new_cache / "music"
        ).resolve()
        # 旧 music 在 cache 下，但新 music 不是「新 cache/music」→ 由 music 项单独迁，cache 勿再拷
        if music_under_old_cache and not music_stays_default_under_new:
            cache_skip.add("music")
        # 即使 music 仍默认挂 cache：若 old→new cache 会先拷 music，再 music 对 同内容
        # 一般 ok；仅当 music 路径显式独立时跳过
    except Exception:
        pass

    if old_cache.resolve() != new_cache.resolve():
        r = migrate_directory(
            old_cache, new_cache, copy=True, skip_dir_names=cache_skip or None
        )
        r["kind"] = "cache"
        migrations.append(r)
        _log_migration("cache", old_cache, new_cache, r)

    if old_log.resolve() != new_log.resolve():
        r = migrate_directory(old_log, new_log, copy=True)
        r["kind"] = "logs"
        migrations.append(r)
        _log_migration("logs", old_log, new_log, r)

    if old_music.resolve() != new_music.resolve():
        r = migrate_directory(old_music, new_music, copy=True)
        r["kind"] = "music"
        migrations.append(r)
        _log_migration("music", old_music, new_music, r)

    if old_kw.resolve() != new_kw.resolve():
        r = migrate_directory(old_kw, new_kw, copy=True)
        r["kind"] = "keywords"
        migrations.append(r)
        _log_migration("keywords", old_kw, new_kw, r)

    return migrations


def _log_migration(kind: str, src: Path, dst: Path, r: dict) -> None:
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


def set_path_overrides(
    *,
    cache: Path | str | None | object = ...,
    log: Path | str | None | object = ...,
    music: Path | str | None | object = ...,
    keywords: Path | str | None | object = ...,
) -> None:
    """测试或编程方式设置覆盖（env 仍优先）.

    - 不传某参数：保持该覆盖不变
    - 传路径字符串/Path：设置覆盖
    - 显式传 None：清除该覆盖（恢复默认/仅 env）
    """
    global _override_cache, _override_log, _override_music, _override_keywords

    def _p(v):
        if v is None or str(v).strip() == "":
            return None
        return Path(v).expanduser().resolve()

    if cache is not ...:
        _override_cache = _p(cache)
    if log is not ...:
        _override_log = _p(log)
    if music is not ...:
        _override_music = _p(music)
    if keywords is not ...:
        _override_keywords = _p(keywords)


def clear_path_overrides(
    *,
    cache: bool = False,
    log: bool = False,
    music: bool = False,
    keywords: bool = False,
    all: bool = False,
) -> None:
    """清除运行时路径覆盖（测试或恢复默认）."""
    global _override_cache, _override_log, _override_music, _override_keywords
    if all or cache:
        _override_cache = None
    if all or log:
        _override_log = None
    if all or music:
        _override_music = None
    if all or keywords:
        _override_keywords = None


@lru_cache(maxsize=1)
def get_platform_info() -> tuple[str, str]:
    """获取平台和架构信息.

    Returns:
        (platform_dir, arch_dir) 如 ("mac", "arm64") / ("win", "x64")
    """
    machine = plat.machine().lower()
    # Windows ARM 常见为 ARM64；部分环境仅环境变量可靠
    env_arch = (os.environ.get("PROCESSOR_ARCHITECTURE") or "").lower()
    env_arch_w6432 = (os.environ.get("PROCESSOR_ARCHITEW6432") or "").lower()
    is_arm = any(
        token in s
        for s in (machine, env_arch, env_arch_w6432)
        for token in ("arm", "aarch64")
    )

    if sys.platform == "win32":
        return "win", "arm64" if is_arm else "x64"
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

    # 扩展名与优先文件名（避免目录里多个候选时捡错）
    ext_map = {"mac": ".dylib", "win": ".dll", "linux": ".so"}
    ext = ext_map.get(plat_dir, ".so")
    preferred_names = {
        "libopus": {
            "mac": ["libopus.dylib", "libopus.0.dylib"],
            "linux": ["libopus.so", "libopus.so.0"],
            "win": ["opus.dll", "libopus.dll", "libopus-0.dll"],
        },
        "webrtc_apm": {
            "mac": ["libwebrtc_apm.dylib", "webrtc_apm.dylib"],
            "linux": ["libwebrtc_apm.so", "webrtc_apm.so"],
            "win": ["webrtc_apm.dll", "libwebrtc_apm.dll"],
        },
    }
    prefer = preferred_names.get(lib_name, {}).get(plat_dir, [])

    for plat_name in plat_aliases.get(plat_dir, [plat_dir]):
        lib_dir = root / plat_name / arch
        if not lib_dir.is_dir():
            continue

        # 1) 精确优先名
        for pname in prefer:
            cand = lib_dir / pname
            if cand.is_file():
                return cand

        # 2) 回退：按扩展名，优先「短名字 / 无多余后缀」
        candidates: list[Path] = []
        for f in lib_dir.iterdir():
            if not f.is_file():
                continue
            # 跳过说明文件
            if f.suffix.lower() in {".txt", ".md", ".json"}:
                continue
            if f.suffix == ext or ext in f.name:
                candidates.append(f)
        if not candidates:
            continue
        candidates.sort(key=lambda p: (len(p.name), p.name))
        return candidates[0]

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
