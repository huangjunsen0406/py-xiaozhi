"""可写目录默认路径解析与目录选择框."""

from __future__ import annotations

from pathlib import Path

from src.logging import get_logger

logger = get_logger()

# kind -> (config_path, dialog_title)
PATH_SPECS: dict[str, tuple[str, str]] = {
    "cache": ("PATHS.CACHE_DIR", "选择缓存目录"),
    "log": ("PATHS.LOG_DIR", "选择日志目录"),
    "music": ("PATHS.MUSIC_CACHE_DIR", "选择音乐缓存目录"),
    "keywords": ("PATHS.KEYWORDS_DIR", "选择唤醒词目录"),
    "mcp": ("MCP_PLUGINS.DIR", "选择 MCP 插件目录"),
}


class SettingsSystemOptionsMixin:
    """目录默认路径与系统选择对话框辅助."""

    def _default_data_paths(self) -> dict[str, str]:
        """配置留空时各目录的系统默认绝对路径（不含 PATHS 覆盖）."""
        from src.utils.resource_finder import get_user_data_dir

        data = get_user_data_dir()
        cache_custom = (self._get_value("PATHS.CACHE_DIR", "") or "").strip()
        cache_default = Path(cache_custom) if cache_custom else (data / "cache")
        return {
            "cache": str(data / "cache"),
            "log": str(data / "logs"),
            # 音乐默认挂在「当前缓存」下：自定义了缓存则跟随
            "music": str(cache_default / "music"),
            "keywords": str(data / "keywords"),
            "mcp": str(data / "mcp_plugins"),
        }

    def _get_default_path(self, kind: str) -> str:
        try:
            return self._default_data_paths()[kind]
        except Exception as exc:
            logger.debug("解析默认目录 %s 失败: %s", kind, exc)
            return ""

    def _get_pathHints(self) -> str:
        """只读：数据根与操作提示（默认路径已显示在各输入框占位符）."""
        try:
            from src.utils.resource_finder import get_user_data_dir

            data = get_user_data_dir()
            return (
                f"数据根(配置固定在此): {data}\n"
                f"留空=默认；点「选择」用系统对话框；保存后下次启动迁移"
            )
        except Exception as exc:
            logger.debug("获取用户数据根提示失败: %s", exc)
            return "留空使用默认路径；保存后下次启动迁移"

    def _browse_directory(self, title: str, current: str, which: str = "") -> str:
        """打开系统文件夹选择对话框；取消返回空串（调用方勿覆盖）."""
        from PySide6.QtWidgets import QApplication, QFileDialog

        start = current.strip() if current else ""
        if not start and which:
            start = self._get_default_path(which)
        if not start:
            try:
                from src.utils.resource_finder import get_user_data_dir

                start = str(get_user_data_dir())
            except Exception:
                start = str(Path.home())
        parent = QApplication.activeWindow()
        path = QFileDialog.getExistingDirectory(
            parent,
            title,
            start,
            QFileDialog.Option.ShowDirsOnly
            | QFileDialog.Option.DontResolveSymlinks,
        )
        return path or ""

