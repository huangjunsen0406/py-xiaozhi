"""Linux系统应用程序启动器.

提供Linux平台下的应用程序启动功能
"""

import os
import subprocess

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def launch_application(app_name: str) -> bool:
    """在Linux上启动应用程序.

    Args:
        app_name: 应用程序名称

    Returns:
        bool: 启动是否成功
    """
    try:
        logger.info(f"[LinuxLauncher] 启动应用程序: {app_name}")

        # 方法1: 直接使用应用程序名称
        try:
            subprocess.Popen([app_name])
            logger.info(f"[LinuxLauncher] 直接启动成功: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[LinuxLauncher] 直接启动失败: {app_name}")

        # 方法2: 使用which查找应用程序路径
        try:
            result = subprocess.run(["which", app_name], capture_output=True, text=True)
            if result.returncode == 0:
                app_path = result.stdout.strip()
                subprocess.Popen([app_path])
                logger.info(f"[LinuxLauncher] 通过which启动成功: {app_name}")
                return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[LinuxLauncher] which启动失败: {app_name}")

        # 方法3: 使用xdg-open（适用于桌面环境）
        try:
            subprocess.Popen(["xdg-open", app_name])
            logger.info(f"[LinuxLauncher] 使用xdg-open启动成功: {app_name}")
            return True
        except (OSError, subprocess.SubprocessError):
            logger.debug(f"[LinuxLauncher] xdg-open启动失败: {app_name}")

        # 方法4: 尝试常见的应用程序路径
        common_paths = [
            f"/usr/bin/{app_name}",
            f"/usr/local/bin/{app_name}",
            f"/opt/{app_name}/{app_name}",
            f"/snap/bin/{app_name}",
        ]

        for path in common_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                logger.info(
                    f"[LinuxLauncher] 通过常见路径启动成功: {app_name} ({path})"
                )
                return True

        # 方法5: 尝试.desktop文件启动
        desktop_dirs = [
            "/usr/share/applications",
            "/usr/local/share/applications",
            os.path.expanduser("~/.local/share/applications"),
        ]

        for desktop_dir in desktop_dirs:
            desktop_file = os.path.join(desktop_dir, f"{app_name}.desktop")
            if os.path.exists(desktop_file):
                subprocess.Popen(["gtk-launch", f"{app_name}.desktop"])
                logger.info(f"[LinuxLauncher] 通过desktop文件启动成功: {app_name}")
                return True

        logger.warning(f"[LinuxLauncher] 所有Linux启动方法都失败了: {app_name}")
        return False

    except Exception as e:
        logger.error(f"[LinuxLauncher] Linux启动失败: {e}")
        return False
