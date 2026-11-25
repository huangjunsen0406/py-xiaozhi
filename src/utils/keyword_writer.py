"""GUI/TUI 共用的原子关键词写入与配置提交。"""

from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path

from src.utils.common_utils import atomic_write_bytes
from src.utils.config_manager import ConfigManager

_keyword_lock = threading.RLock()


def _atomic_write(target: Path, content: bytes) -> None:
    """Only replace the target after the complete contents reach the temporary file."""
    atomic_write_bytes(target, content, suffix="", replace=os.replace)


def commit_with_keywords(
    config: ConfigManager,
    draft: dict,
    lang: str,
    keyword_line: str,
    *,
    commit: Callable[[], str | None] | None = None,
) -> str | None:
    """Write keywords, commit, and restore previous keywords on rejected saves.

    A post-write reload failure deliberately preserves the new config on disk;
    retain matching keywords in that case, so restarting can load the saved pair.
    PATHS overrides apply next start: always write the currently active directory.
    Serializing both UI paths prevents a failed save from undoing a later save.
    """
    if lang not in {"zh", "en"} or not keyword_line.strip():
        raise ValueError("唤醒词转换结果无效")
    from src.utils.resource_finder import get_keywords_dir

    target = Path(get_keywords_dir()).resolve() / f"{lang}_keywords.txt"
    with _keyword_lock, config._lock:
        previous = target.read_bytes() if target.exists() else None
        _atomic_write(target, (keyword_line + "\n").encode("utf-8"))
        try:
            error = commit() if commit is not None else config.commit_draft(draft)
        except Exception as exc:
            error = f"保存配置失败: {exc}"
        if error is None:
            return None

        if config.config_file is not None:
            try:
                persisted = json.loads(config.config_file.read_text(encoding="utf-8"))
                if persisted == draft:
                    return error
            except FileNotFoundError:
                pass
            except (OSError, ValueError):
                # Cannot prove the config was rejected: preserve complete new data
                # and expose the uncertainty instead of risking a mismatched pair.
                return f"{error}；无法确认磁盘配置，已保留新关键词，请重试"
        try:
            if previous is None:
                # The target is the resolved active directory plus a validated name.
                target.unlink(missing_ok=True)
            else:
                _atomic_write(target, previous)
        except OSError as exc:
            return f"{error}；恢复旧关键词失败: {exc}，请重试保存"
        return error
