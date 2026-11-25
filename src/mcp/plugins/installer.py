"""外挂 MCP 插件事务型安装、扫描与卸载管理器.

提供安全导入 ZIP / 文件夹（防路径穿越、防符号链接、大小上限、单顶层目录剥离、
覆盖备份与失败回滚）、已安装插件状态汇总与安全卸载。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import uuid
import zipfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from src.logging import get_logger
from src.mcp.plugins.loader import SUPPORTED_RUNTIMES
from src.utils.resource_finder import get_mcp_plugin_data_dir

logger = get_logger()

PLUGIN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")
MAX_ARCHIVE_FILES = 2000
MAX_ARCHIVE_FILE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 128 * 1024 * 1024
_IGNORED_TOP_NAMES = frozenset({"__MACOSX", ".DS_Store", "Thumbs.db"})
_COPY_IGNORE_NAMES = frozenset({"__pycache__", ".git", ".DS_Store", "Thumbs.db"})


def open_directory_in_file_manager(path: Path) -> bool:
    """在系统文件管理器中打开目录."""
    target = Path(path).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        elif sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(target)])
        return True
    except Exception as exc:
        logger.warning("打开目录失败 %s: %s", target, exc)
        return False


def _validate_plugin_id(plugin_id: str) -> str:
    pid = (plugin_id or "").strip()
    if not pid or pid in (".", "..") or not PLUGIN_ID_RE.match(pid):
        raise ValueError(f"无效的插件 ID: {plugin_id!r}")
    return pid


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _extract_zip_safely(zip_path: Path, dest_dir: Path) -> None:
    if not zip_path.is_file():
        raise ValueError(f"ZIP 文件不存在: {zip_path}")
    dest_resolved = dest_dir.resolve()
    total_bytes = 0
    file_count = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename
            if not name or name.startswith("/") or name.startswith("\\"):
                raise ValueError(f"压缩包包含非法绝对路径: {name}")
            if _is_zip_symlink(info):
                raise ValueError(f"压缩包不允许包含符号链接: {name}")

            parts = Path(name).parts
            if any(part == ".." for part in parts):
                raise ValueError(f"压缩包包含路径穿越条目: {name}")
            if parts and parts[0] in _IGNORED_TOP_NAMES:
                continue

            target = (dest_resolved / name).resolve()
            if not target.is_relative_to(dest_resolved):
                raise ValueError(f"压缩包条目逃逸目标目录: {name}")

            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            file_count += 1
            if file_count > MAX_ARCHIVE_FILES:
                raise ValueError(f"压缩包文件数超过上限 ({MAX_ARCHIVE_FILES})")
            if info.file_size > MAX_ARCHIVE_FILE_BYTES:
                raise ValueError(f"压缩包单文件过大: {name}")
            total_bytes += info.file_size
            if total_bytes > MAX_ARCHIVE_TOTAL_BYTES:
                raise ValueError("压缩包解压总大小超过上限")

            target.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with zf.open(info, "r") as src, target.open("wb") as dst:
                while chunk := src.read(65536):
                    written += len(chunk)
                    if written > MAX_ARCHIVE_FILE_BYTES:
                        raise ValueError(f"压缩包单文件实际大小超限: {name}")
                    dst.write(chunk)


def _resolve_unpacked_root(stage_dir: Path) -> Path:
    entries = [
        p
        for p in stage_dir.iterdir()
        if p.name not in _IGNORED_TOP_NAMES and not p.name.startswith("._")
    ]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return stage_dir


def _inspect_plugin_root(plugin_root: Path) -> tuple[str, dict[str, Any]]:
    """校验待安装插件目录结构，返回 ``(plugin_id, manifest)``."""
    manifest_file = plugin_root / "manifest.json"
    if manifest_file.is_file():
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"manifest.json 解析失败: {exc}") from exc
        if not isinstance(manifest, dict):
            raise ValueError("manifest.json 必须为 JSON 对象")
        plugin_id = _validate_plugin_id(str(manifest.get("id") or plugin_root.name))
        runtime = str(manifest.get("runtime") or "python-inprocess")
        if runtime not in SUPPORTED_RUNTIMES:
            raise ValueError(f"不支持的插件 runtime: {runtime}")
        entry = str(manifest.get("entry") or "plugin:register")
        if ":" not in entry:
            raise ValueError(f"manifest.entry 格式无效: {entry}")
        module_part = entry.split(":", 1)[0].strip()
        if not module_part:
            raise ValueError(f"manifest.entry 模块名为空: {entry}")
        mod_file = plugin_root / f"{module_part.replace('.', '/')}.py"
        mod_pkg = plugin_root / module_part.replace(".", "/") / "__init__.py"
        if not mod_file.is_file() and not mod_pkg.is_file():
            raise ValueError(f"未找到入口模块文件: {module_part}")
        return plugin_id, manifest

    if (plugin_root / "plugin.py").is_file():
        plugin_id = _validate_plugin_id(plugin_root.name)
        return plugin_id, {
            "id": plugin_id,
            "name": plugin_id,
            "entry": "plugin:register",
            "runtime": "python-inprocess",
        }

    raise ValueError("插件目录缺少 manifest.json 或 plugin.py")


def _copy_dir_safely(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src, followlinks=False):
        dirs[:] = [
            d
            for d in dirs
            if d not in _COPY_IGNORE_NAMES and not (Path(root) / d).is_symlink()
        ]
        rel = Path(root).relative_to(src)
        target_root = dst / rel
        target_root.mkdir(parents=True, exist_ok=True)
        for fname in files:
            if fname in _COPY_IGNORE_NAMES:
                continue
            src_file = Path(root) / fname
            if src_file.is_symlink():
                raise ValueError(f"插件目录不允许包含符号链接: {src_file.name}")
            shutil.copy2(src_file, target_root / fname)


def _commit_staged_plugin(
    plugin_root: Path, plugin_id: str, plugins_dir: Path
) -> tuple[Path, bool]:
    """原子替换目标插件目录，失败自动回滚."""
    plugins_root = Path(plugins_dir).expanduser().resolve()
    plugins_root.mkdir(parents=True, exist_ok=True)
    target = (plugins_root / plugin_id).resolve()
    if not target.is_relative_to(plugins_root) or target == plugins_root:
        raise ValueError(f"非法安装目标路径: {plugin_id}")

    backup: Path | None = None
    replaced = False
    try:
        if target.exists():
            replaced = True
            backup = plugins_root / f".backup-{plugin_id}-{uuid.uuid4().hex[:8]}"
            shutil.move(str(target), str(backup))
        shutil.move(str(plugin_root), str(target))
        if backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        return target, replaced
    except Exception:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        if backup is not None and backup.exists():
            shutil.move(str(backup), str(target))
        raise


def install_plugin_from_zip(
    zip_path: str | Path, plugins_dir: Path
) -> dict[str, Any]:
    """从 ZIP 包安全导入插件（事务型，支持覆盖回滚）."""
    src = Path(zip_path).expanduser().resolve()
    plugins_root = Path(plugins_dir).expanduser().resolve()
    plugins_root.mkdir(parents=True, exist_ok=True)
    stage_dir = plugins_root / f".staging-{uuid.uuid4().hex[:8]}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    try:
        _extract_zip_safely(src, stage_dir)
        plugin_root = _resolve_unpacked_root(stage_dir)
        plugin_id, manifest = _inspect_plugin_root(plugin_root)
        target, replaced = _commit_staged_plugin(plugin_root, plugin_id, plugins_root)
        logger.info("[MCP插件] ZIP 导入成功: %s -> %s", plugin_id, target)
        return {
            "ok": True,
            "id": plugin_id,
            "name": str(manifest.get("name") or plugin_id),
            "version": str(manifest.get("version") or ""),
            "runtime": str(manifest.get("runtime") or "python-inprocess"),
            "path": str(target),
            "replaced": replaced,
        }
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)


def install_plugin_from_dir(
    src_dir: str | Path, plugins_dir: Path
) -> dict[str, Any]:
    """从本地文件夹安全导入插件（事务型，支持覆盖回滚）."""
    src = Path(src_dir).expanduser().resolve()
    if not src.is_dir():
        raise ValueError(f"插件目录不存在: {src}")
    plugin_id, manifest = _inspect_plugin_root(src)
    plugins_root = Path(plugins_dir).expanduser().resolve()
    plugins_root.mkdir(parents=True, exist_ok=True)
    stage_dir = plugins_root / f".staging-{uuid.uuid4().hex[:8]}"
    try:
        _copy_dir_safely(src, stage_dir)
        target, replaced = _commit_staged_plugin(stage_dir, plugin_id, plugins_root)
        logger.info("[MCP插件] 文件夹导入成功: %s -> %s", plugin_id, target)
        return {
            "ok": True,
            "id": plugin_id,
            "name": str(manifest.get("name") or plugin_id),
            "version": str(manifest.get("version") or ""),
            "runtime": str(manifest.get("runtime") or "python-inprocess"),
            "path": str(target),
            "replaced": replaced,
        }
    finally:
        if stage_dir.exists():
            shutil.rmtree(stage_dir, ignore_errors=True)


def uninstall_plugin(
    plugin_id: str,
    plugins_dir: Path,
    *,
    remove_data: bool = False,
) -> dict[str, Any]:
    """安全卸载已安装插件代码目录（可选清理其隔离数据目录）."""
    pid = _validate_plugin_id(plugin_id)
    plugins_root = Path(plugins_dir).expanduser().resolve()
    if not plugins_root.is_dir():
        return {"ok": False, "error": "插件目录不存在"}

    target: Path | None = None
    for child in sorted(plugins_root.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith((".", "_")):
            continue
        if child.is_dir():
            cid = child.name
            mf = child / "manifest.json"
            if mf.is_file():
                try:
                    data = json.loads(mf.read_text(encoding="utf-8"))
                    if isinstance(data, dict) and data.get("id"):
                        cid = str(data["id"])
                except Exception:
                    pass
            if cid == pid:
                target = child.resolve()
                break
        elif child.is_file() and child.suffix == ".py" and child.stem == pid:
            target = child.resolve()
            break

    if target is None:
        return {"ok": False, "error": f"未找到插件: {pid}"}
    if not target.is_relative_to(plugins_root) or target == plugins_root:
        return {"ok": False, "error": f"拒绝删除非法路径: {target}"}

    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()

    if remove_data:
        data_dir = get_mcp_plugin_data_dir(pid)
        if data_dir.is_dir():
            shutil.rmtree(data_dir, ignore_errors=True)

    logger.info("[MCP插件] 已卸载: %s (%s)", pid, target)
    return {"ok": True, "id": pid, "path": str(target)}


def list_installed_plugins(
    plugins_dir: Path,
    runtime_loaded: Sequence[Any] | None = None,
) -> list[dict[str, Any]]:
    """扫描已安装插件并合并当前运行时加载状态，供设置页展示."""
    root = Path(plugins_dir).expanduser().resolve()
    loaded_by_id: dict[str, Any] = {
        getattr(item, "plugin_id", ""): item for item in (runtime_loaded or [])
    }

    if not root.is_dir():
        return []

    rows: list[dict[str, Any]] = []
    for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
        if child.name.startswith((".", "_")):
            continue
        if not child.is_dir() and not (child.is_file() and child.suffix == ".py"):
            continue

        plugin_id = child.stem if child.is_file() else child.name
        name = plugin_id
        version = ""
        description = ""
        runtime = "python-inprocess"
        parse_error: str | None = None

        if child.is_dir():
            mf = child / "manifest.json"
            if mf.is_file():
                try:
                    manifest = json.loads(mf.read_text(encoding="utf-8"))
                    if isinstance(manifest, dict):
                        plugin_id = str(manifest.get("id") or plugin_id)
                        name = str(manifest.get("name") or plugin_id)
                        version = str(manifest.get("version") or "")
                        description = str(manifest.get("description") or "")
                        runtime = str(manifest.get("runtime") or "python-inprocess")
                    else:
                        parse_error = "manifest.json 须为 JSON 对象"
                except Exception as exc:
                    parse_error = f"manifest.json 无效: {exc}"
            elif not (child / "plugin.py").is_file():
                continue

        live = loaded_by_id.get(plugin_id)
        if parse_error:
            status = "error"
            error = parse_error
            tool_names: list[str] = []
        elif live is not None:
            error = getattr(live, "error", None)
            tool_names = list(getattr(live, "tool_names", []) or [])
            runtime = str(getattr(live, "runtime", runtime) or runtime)
            if error == "disabled":
                status = "disabled"
            elif error:
                status = "error"
            else:
                status = "loaded"
        else:
            status = "pending"
            error = None
            tool_names = []

        rows.append(
            {
                "id": plugin_id,
                "name": name,
                "version": version,
                "description": description,
                "runtime": runtime,
                "path": str(child),
                "status": status,
                "error": error or "",
                "toolNames": tool_names,
            }
        )
    return rows
