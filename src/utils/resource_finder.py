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
- get_app_root() / get_resource_root() / get_app_name()
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

_PATH_SPECS: tuple[tuple[str, str, str, str], ...] = (
    # (kind, env_var, config_key, override_attr)
    ("cache", ENV_CACHE_DIR, "PATHS.CACHE_DIR", "_override_cache"),
    ("logs", ENV_LOG_DIR, "PATHS.LOG_DIR", "_override_log"),
    ("music", ENV_MUSIC_CACHE_DIR, "PATHS.MUSIC_CACHE_DIR", "_override_music"),
    ("keywords", ENV_KEYWORDS_DIR, "PATHS.KEYWORDS_DIR", "_override_keywords"),
)


def _env_path(name: str) -> Path | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _resolve_dir(env_name: str, override_attr: str, default_factory) -> Path:
    env = _env_path(env_name)
    if env is not None:
        p = env
    elif (override := globals()[override_attr]) is not None:
        p = override
    else:
        p = default_factory()
    p.mkdir(parents=True, exist_ok=True)
    return p


def _normalize_override(v) -> Path | None:
    if v is None or str(v).strip() == "":
        return None
    return Path(v).expanduser().resolve()


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


def get_resource_root() -> Path:
    """只读资源根：wheel 放在包内；源码和 PyInstaller 保留原布局。"""
    if getattr(sys, "frozen", False):
        return get_app_root()
    bundled = Path(__file__).resolve().parent.parent / "_resources"
    return bundled if bundled.is_dir() else get_app_root()


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
    return _resolve_dir(
        ENV_CACHE_DIR, "_override_cache", lambda: get_user_data_dir() / "cache"
    )


def get_user_log_dir() -> Path:
    """日志目录：XIAOZHI_LOG_DIR > 运行时覆盖 > {data}/logs."""
    return _resolve_dir(
        ENV_LOG_DIR, "_override_log", lambda: get_user_data_dir() / "logs"
    )


def get_log_dir() -> Path:
    """日志目录（用户数据目录下，打包后可写）."""
    return get_user_log_dir()


def get_music_cache_dir() -> Path:
    """音乐缓存：XIAOZHI_MUSIC_CACHE_DIR > 覆盖 > {cache}/music."""
    return _resolve_dir(
        ENV_MUSIC_CACHE_DIR,
        "_override_music",
        lambda: get_user_cache_dir() / "music",
    )


def get_keywords_dir() -> Path:
    """唤醒词目录：XIAOZHI_KEYWORDS_DIR > 覆盖 > {data}/keywords."""
    return _resolve_dir(
        ENV_KEYWORDS_DIR,
        "_override_keywords",
        lambda: get_user_data_dir() / "keywords",
    )


def clear_path_caches() -> None:
    """清除 get_user_data_dir 等 lru 缓存（测试或 DATA_DIR 变更后）."""
    get_user_data_dir.cache_clear()
    get_app_root.cache_clear()


def _migration_paths_overlap(src: Path, dst: Path) -> bool:
    return src != dst and (src.is_relative_to(dst) or dst.is_relative_to(src))


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
    if _migration_paths_overlap(src, dst):
        result["error"] = "source and destination directories overlap"
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


def _get_dir_by_kind(kind: str) -> Path:
    return {
        "cache": get_user_cache_dir,
        "logs": get_user_log_dir,
        "music": get_music_cache_dir,
        "keywords": get_keywords_dir,
    }[kind]()


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
    migrations: list[dict] = []

    def _cfg(key: str) -> str | None:
        try:
            v = config.get_config(key, None)
        except Exception:
            return None
        if v is None or str(v).strip() == "":
            return None
        return str(v).strip()

    old_dirs = {kind: _get_dir_by_kind(kind) for kind, *_ in _PATH_SPECS}
    configured = {kind: _cfg(cfg_key) for kind, _, cfg_key, _ in _PATH_SPECS}

    # 先解析并校验所有候选路径，不能先激活/创建目标再发现迁移重叠。
    def _candidate(env_name: str, cfg_val: str | None, default: Path) -> Path:
        env = _env_path(env_name)
        if env is not None:
            return env
        return Path(cfg_val).expanduser().resolve() if cfg_val else default.resolve()

    data = get_user_data_dir()
    proposed: dict[str, Path] = {}
    proposed["cache"] = _candidate(ENV_CACHE_DIR, configured["cache"], data / "cache")
    proposed["logs"] = _candidate(ENV_LOG_DIR, configured["logs"], data / "logs")
    proposed["music"] = _candidate(
        ENV_MUSIC_CACHE_DIR, configured["music"], proposed["cache"] / "music"
    )
    proposed["keywords"] = _candidate(
        ENV_KEYWORDS_DIR, configured["keywords"], data / "keywords"
    )

    if migrate:
        for kind, *_ in _PATH_SPECS:
            old_resolved = old_dirs[kind].resolve()
            new_path = proposed[kind]
            if _migration_paths_overlap(old_resolved, new_path):
                migrations.append(
                    {
                        "kind": kind,
                        "ok": False,
                        "src": str(old_resolved),
                        "dst": str(new_path),
                        "files_copied": 0,
                        "error": "source and destination directories overlap",
                    }
                )
        if migrations:
            for r in migrations:
                _log_migration(r["kind"], Path(r["src"]), Path(r["dst"]), r)
            return migrations

    # 仅当 env 未设时应用 config 覆盖
    for kind, env_var, _, override_attr in _PATH_SPECS:
        if _env_path(env_var) is None:
            globals()[override_attr] = _normalize_override(configured[kind])

    if not migrate:
        return migrations

    new_dirs = {kind: _get_dir_by_kind(kind) for kind, *_ in _PATH_SPECS}

    # cache 迁移时：若旧 music 在旧 cache 下但新 music 独立，则跳过 cache/music 子树
    cache_skip: set[str] = set()
    try:
        music_under_old_cache = (
            old_dirs["music"].resolve() == (old_dirs["cache"] / "music").resolve()
        )
        music_stays_default = (
            new_dirs["music"].resolve() == (new_dirs["cache"] / "music").resolve()
        )
        if music_under_old_cache and not music_stays_default:
            cache_skip.add("music")
    except OSError:
        pass

    for kind, *_ in _PATH_SPECS:
        old_p, new_p = old_dirs[kind], new_dirs[kind]
        if old_p.resolve() == new_p.resolve():
            continue
        skip_names = (cache_skip or None) if kind == "cache" else None
        r = migrate_directory(old_p, new_p, copy=True, skip_dir_names=skip_names)
        r["kind"] = kind
        migrations.append(r)
        _log_migration(kind, old_p, new_p, r)

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
    updates = (
        ("_override_cache", cache),
        ("_override_log", log),
        ("_override_music", music),
        ("_override_keywords", keywords),
    )
    for attr, value in updates:
        if value is not ...:
            globals()[attr] = _normalize_override(value)


def clear_path_overrides(
    *,
    cache: bool = False,
    log: bool = False,
    music: bool = False,
    keywords: bool = False,
    all: bool = False,
) -> None:
    """清除运行时路径覆盖（测试或恢复默认）."""
    flags = (
        ("_override_cache", cache),
        ("_override_log", log),
        ("_override_music", music),
        ("_override_keywords", keywords),
    )
    for attr, should_clear in flags:
        if all or should_clear:
            globals()[attr] = None


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
    root = get_resource_root() / "libs" / lib_name

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


def _get_bundled_binary(name: str) -> str:
    """获取内置 ffmpeg/ffprobe 可执行文件路径，不存在时回退系统 PATH."""
    plat_dir, arch = get_platform_info()
    ext = ".exe" if sys.platform == "win32" else ""
    bundled = (
        get_resource_root() / "libs" / "ffmpeg" / plat_dir / arch / f"{name}{ext}"
    )
    if bundled.exists():
        return str(bundled)
    return shutil.which(name) or name


def get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径（搜索顺序：内置 libs/ffmpeg/ → 系统 PATH）."""
    return _get_bundled_binary("ffmpeg")


def get_ffprobe_path() -> str:
    """获取 ffprobe 可执行文件路径（搜索顺序：内置 libs/ffmpeg/ → 系统 PATH）."""
    return _get_bundled_binary("ffprobe")


def get_models_dir() -> Path:
    """
    模型目录（只读，安装目录内）.
    """
    return get_resource_root() / "models"


def get_assets_dir() -> Path:
    """
    资源目录（只读，安装目录内）.
    """
    return get_resource_root() / "assets"


def get_config_dir() -> Path:
    """
    配置目录（应用内置，只读）
    """
    return get_resource_root() / "config"


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
        default_keywords = get_resource_root() / "models" / lang / "keywords.txt"
        if default_keywords.exists():
            user_keywords_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(default_keywords, user_keywords)

    return user_keywords
