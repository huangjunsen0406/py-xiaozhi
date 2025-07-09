"""macOS系统应用程序启动器.

提供macOS平台下的应用程序启动功能
"""

import os
import subprocess

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def launch_application(app_name: str) -> bool:
    """在macOS上启动应用程序.

    Args:
        app_name: 应用程序名称

    Returns:
        bool: 启动是否成功
    """
    try:
        logger.info(f"[MacLauncher] 启动应用程序: {app_name}")

        # 方法1: 使用open -a命令
        try:
            subprocess.Popen(["open", "-a", app_name])
            logger.info(f"[MacLauncher] 使用open -a成功启动: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[MacLauncher] open -a启动失败: {app_name}")

        # 方法2: 直接使用应用程序名称
        try:
            subprocess.Popen([app_name])
            logger.info(f"[MacLauncher] 直接启动成功: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[MacLauncher] 直接启动失败: {app_name}")

        # 方法3: 尝试Applications目录
        app_path = f"/Applications/{app_name}.app"
        if os.path.exists(app_path):
            subprocess.Popen(["open", app_path])
            logger.info(f"[MacLauncher] 通过Applications目录启动成功: {app_name}")
            return True

        # 方法4: 使用osascript启动
        script = f'tell application "{app_name}" to activate'
        subprocess.Popen(["osascript", "-e", script])
        logger.info(f"[MacLauncher] 使用osascript启动成功: {app_name}")
        return True

    except Exception as e:
        logger.error(f"[MacLauncher] macOS启动失败: {e}")
        return False
