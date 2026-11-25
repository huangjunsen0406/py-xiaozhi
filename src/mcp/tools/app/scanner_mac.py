"""macOS应用程序扫描器.

专门用于macOS系统的应用程序扫描和管理
"""

import platform
from pathlib import Path
from typing import Dict, List

from src.logging import get_logger

from .utils import clean_app_name

logger = get_logger()


def scan_installed_applications() -> List[Dict[str, str]]:
    """扫描macOS系统中已安装的应用程序.

    Returns:
        List[Dict[str, str]]: 应用程序列表
    """
    if platform.system() != "Darwin":
        return []

    apps = []

    # 扫描 /Applications 目录
    applications_dir = Path("/Applications")
    if applications_dir.exists():
        for app_path in applications_dir.glob("*.app"):
            app_name = app_path.stem
            clean_name = clean_app_name(app_name)
            apps.append(
                {
                    "name": clean_name,
                    "display_name": app_name,
                    "path": str(app_path),
                    "type": "application",
                }
            )

    # 扫描用户应用程序目录
    user_apps_dir = Path.home() / "Applications"
    if user_apps_dir.exists():
        for app_path in user_apps_dir.glob("*.app"):
            app_name = app_path.stem
            clean_name = clean_app_name(app_name)
            apps.append(
                {
                    "name": clean_name,
                    "display_name": app_name,
                    "path": str(app_path),
                    "type": "user_application",
                }
            )

    # 添加常用系统应用
    system_apps = [
        {
            "name": "Calculator",
            "display_name": "计算器",
            "path": "Calculator",
            "type": "system",
        },
        {
            "name": "TextEdit",
            "display_name": "文本编辑",
            "path": "TextEdit",
            "type": "system",
        },
        {
            "name": "Preview",
            "display_name": "预览",
            "path": "Preview",
            "type": "system",
        },
        {
            "name": "Safari",
            "display_name": "Safari浏览器",
            "path": "Safari",
            "type": "system",
        },
        {"name": "Finder", "display_name": "访达", "path": "Finder", "type": "system"},
        {
            "name": "Terminal",
            "display_name": "终端",
            "path": "Terminal",
            "type": "system",
        },
        {
            "name": "System Preferences",
            "display_name": "系统偏好设置",
            "path": "System Preferences",
            "type": "system",
        },
    ]
    apps.extend(system_apps)

    logger.info(f"[MacScanner] 扫描完成，找到 {len(apps)} 个应用程序")
    return apps
