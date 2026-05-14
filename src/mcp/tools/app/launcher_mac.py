"""macOS系统应用程序启动器.

提供macOS平台下的应用程序启动功能。
所有 subprocess 调用均使用列表形式，不使用 shell=True。
"""

import os
import subprocess

from src.logging import get_logger

logger = get_logger()


def launch_application(app_name: str) -> bool:
    """在macOS上启动应用程序.

    Args:
        app_name: 应用程序名称

    Returns:
        bool: 启动是否成功
    """
    try:
        logger.info(f"[MacLauncher] 启动应用程序: {app_name}")

        # 方法1: 使用open -a命令（安全的列表形式）
        try:
            subprocess.Popen(
                ["open", "-a", app_name],
                start_new_session=True,
            )
            logger.info(f"[MacLauncher] 使用open -a成功启动: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[MacLauncher] open -a启动失败: {app_name}")

        # 方法2: 直接使用应用程序名称
        try:
            subprocess.Popen(
                [app_name],
                start_new_session=True,
            )
            logger.info(f"[MacLauncher] 直接启动成功: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[MacLauncher] 直接启动失败: {app_name}")

        # 方法3: 尝试Applications目录
        app_path = f"/Applications/{app_name}.app"
        if os.path.exists(app_path):
            subprocess.Popen(
                ["open", app_path],
                start_new_session=True,
            )
            logger.info(f"[MacLauncher] 通过Applications目录启动成功: {app_name}")
            return True

        # 方法4: 再次使用open -a（作为最终尝试，不使用osascript）
        # 之前使用 osascript + f-string 拼接存在 AppleScript 注入漏洞，已移除
        try:
            subprocess.Popen(
                ["open", "-a", app_name, "--background"],
                start_new_session=True,
            )
            logger.info(f"[MacLauncher] 使用open -a(后台模式)启动成功: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[MacLauncher] open -a(后台模式)启动失败: {app_name}")

        logger.warning(f"[MacLauncher] 所有macOS启动方法都失败了: {app_name}")
        return False

    except Exception as e:
        logger.error(f"[MacLauncher] macOS启动失败: {e}")
        return False
