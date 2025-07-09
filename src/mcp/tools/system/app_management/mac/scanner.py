"""macOS应用程序扫描器.

专门用于macOS系统的应用程序扫描和管理
"""

import platform
import subprocess
from pathlib import Path
from typing import Dict, List

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


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
            clean_name = _clean_app_name(app_name)
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
            clean_name = _clean_app_name(app_name)
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


def scan_running_applications() -> List[Dict[str, str]]:
    """扫描macOS系统中正在运行的应用程序.

    Returns:
        List[Dict[str, str]]: 正在运行的应用程序列表
    """
    if platform.system() != "Darwin":
        return []

    apps = []

    try:
        # 使用ps命令获取进程信息
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,comm,command"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # 跳过标题行

            for line in lines:
                parts = line.strip().split(None, 3)
                if len(parts) >= 4:
                    pid, ppid, comm, command = parts

                    # 过滤掉不需要的进程
                    if _should_include_process(comm, command):
                        display_name = _extract_app_name(comm, command)
                        clean_name = _clean_app_name(display_name)

                        apps.append(
                            {
                                "pid": int(pid),
                                "ppid": int(ppid),
                                "name": clean_name,
                                "display_name": display_name,
                                "command": command,
                                "type": "application",
                            }
                        )

        logger.info(f"[MacScanner] 找到 {len(apps)} 个正在运行的应用程序")
        return apps

    except Exception as e:
        logger.error(f"[MacScanner] 扫描运行应用失败: {e}")
        return []


def _should_include_process(comm: str, command: str) -> bool:
    """判断是否应该包含该进程.

    Args:
        comm: 进程名称
        command: 完整命令

    Returns:
        bool: 是否包含
    """
    # 排除系统进程和服务
    system_processes = {
        # 系统核心进程
        "kernel_task",
        "launchd",
        "kextd",
        "UserEventAgent",
        "cfprefsd",
        "loginwindow",
        "WindowServer",
        "SystemUIServer",
        "Dock",
        "Finder",
        "ControlCenter",
        "NotificationCenter",
        "WallpaperAgent",
        "Spotlight",
        "WiFiAgent",
        "CoreLocationAgent",
        "bluetoothd",
        "wirelessproxd",
        # 系统服务
        "com.apple.",
        "suhelperd",
        "softwareupdated",
        "cloudphotod",
        "identityservicesd",
        "imagent",
        "sharingd",
        "remindd",
        "contactsd",
        "accountsd",
        "CallHistorySyncHelper",
        "CallHistoryPluginHelper",
        # 驱动和扩展
        "AppleSpell",
        "coreaudiod",
        "audio",
        "webrtc",
        "chrome_crashpad_handler",
        "crashpad_handler",
        "fsnotifier",
        "mdworker",
        "mds",
        "spotlight",
        # 其他系统组件
        "automountd",
        "autofsd",
        "aslmanager",
        "syslogd",
        "ntpd",
        "mDNSResponder",
        "distnoted",
        "notifyd",
        "powerd",
        "thermalmonitord",
        "watchdogd",
    }

    # 检查是否是系统进程
    comm_lower = comm.lower()
    command_lower = command.lower()

    # 排除空名称或系统路径
    if not comm or comm_lower in system_processes:
        return False

    # 排除系统路径下的进程
    if any(
        path in command_lower
        for path in [
            "/system/library/",
            "/library/apple/",
            "/usr/libexec/",
            "/system/applications/utilities/",
            "/private/var/",
            "com.apple.",
            ".xpc/",
            ".framework/",
            ".appex/",
            "helper (gpu)",
            "helper (renderer)",
            "helper (plugin)",
            "crashpad_handler",
            "fsnotifier",
        ]
    ):
        return False

    # 排除明显的系统服务
    if any(
        keyword in command_lower
        for keyword in [
            "xpcservice",
            "daemon",
            "agent",
            "service",
            "monitor",
            "updater",
            "sync",
            "backup",
            "cache",
            "log",
        ]
    ):
        return False

    # 只包含用户应用程序
    user_app_indicators = ["/applications/", "/users/", "~/", ".app/contents/macos/"]

    return any(indicator in command_lower for indicator in user_app_indicators)


def _extract_app_name(comm: str, command: str) -> str:
    """从进程信息中提取应用程序名称.

    Args:
        comm: 进程名称
        command: 完整命令

    Returns:
        str: 应用程序名称
    """
    # 尝试从命令路径中提取.app名称
    if ".app/Contents/MacOS/" in command:
        try:
            app_path = command.split(".app/Contents/MacOS/")[0] + ".app"
            app_name = Path(app_path).name.replace(".app", "")
            return app_name
        except (IndexError, AttributeError):
            pass

    # 尝试从/Applications/路径提取
    if "/Applications/" in command:
        try:
            parts = command.split("/Applications/")[1].split("/")[0]
            if parts.endswith(".app"):
                return parts.replace(".app", "")
        except (IndexError, AttributeError):
            pass

    # 使用进程名称
    return comm if comm else "Unknown"


def _clean_app_name(name: str) -> str:
    """清理应用程序名称，移除版本号和特殊字符.

    Args:
        name: 原始名称

    Returns:
        str: 清理后的名称
    """
    if not name:
        return ""

    # 移除常见的版本号模式
    import re

    # 移除版本号 (如 "App 1.0", "App v2.1", "App (2023)")
    name = re.sub(r"\s+v?\d+[\.\d]*", "", name)
    name = re.sub(r"\s*\(\d+\)", "", name)
    name = re.sub(r"\s*\[.*?\]", "", name)

    # 移除多余的空格
    name = " ".join(name.split())

    return name.strip()
