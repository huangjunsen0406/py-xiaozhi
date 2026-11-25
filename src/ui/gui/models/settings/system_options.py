"""用户数据目录只读展示与系统文件管理器打开辅助."""

from __future__ import annotations

from src.logging import get_logger

logger = get_logger()


class SettingsSystemOptionsMixin:
    """用户数据目录展示与打开."""

    def _get_userDataDir(self) -> str:
        try:
            from src.utils.resource_finder import get_user_data_dir

            return str(get_user_data_dir())
        except Exception as exc:
            logger.debug("解析用户数据目录失败: %s", exc)
            return ""

    def _open_user_data_dir(self) -> bool:
        try:
            from src.mcp.plugins.installer import open_directory_in_file_manager
            from src.utils.resource_finder import get_user_data_dir

            return open_directory_in_file_manager(get_user_data_dir())
        except Exception as exc:
            logger.warning("打开用户数据目录失败: %s", exc)
            return False
