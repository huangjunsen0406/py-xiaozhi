"""Linux应用程序扫描器.

专门用于Linux系统的应用程序扫描和管理
"""

import platform
import subprocess
from pathlib import Path
from typing import Dict, List

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def scan_installed_applications() -> List[Dict[str, str]]:
    """扫描Linux系统中已安装的应用程序.

    Returns:
        List[Dict[str, str]]: 应用程序列表
    """
    if platform.system() != "Linux":
        return []

    apps = []

    # 扫描 .desktop 文件
    desktop_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        Path.home() / ".local/share/applications",
    ]

    for desktop_dir in desktop_dirs:
        desktop_path = Path(desktop_dir)
        if desktop_path.exists():
            for desktop_file in desktop_path.glob("*.desktop"):
                try:
                    app_info = _parse_desktop_file(desktop_file)
                    if app_info and _should_include_app(app_info["display_name"]):
                        apps.append(app_info)
                except Exception as e:
                    logger.debug(
                        f"[LinuxScanner] 解析desktop文件失败 {desktop_file}: {e}"
                    )

    # 添加常见的Linux系统应用
    system_apps = [
        {
            "name": "gedit",
            "display_name": "文本编辑器",
            "path": "gedit",
            "type": "system",
        },
        {
            "name": "firefox",
            "display_name": "Firefox浏览器",
            "path": "firefox",
            "type": "system",
        },
        {
            "name": "gnome-calculator",
            "display_name": "计算器",
            "path": "gnome-calculator",
            "type": "system",
        },
        {
            "name": "nautilus",
            "display_name": "文件管理器",
            "path": "nautilus",
            "type": "system",
        },
        {
            "name": "gnome-terminal",
            "display_name": "终端",
            "path": "gnome-terminal",
            "type": "system",
        },
        {
            "name": "gnome-control-center",
            "display_name": "设置",
            "path": "gnome-control-center",
            "type": "system",
        },
    ]
    apps.extend(system_apps)

    logger.info(f"[LinuxScanner] 扫描完成，找到 {len(apps)} 个应用程序")
    return apps


def scan_running_applications() -> List[Dict[str, str]]:
    """扫描Linux系统中正在运行的应用程序.

    Returns:
        List[Dict[str, str]]: 正在运行的应用程序列表
    """
    if platform.system() != "Linux":
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

        logger.info(f"[LinuxScanner] 找到 {len(apps)} 个正在运行的应用程序")
        return apps

    except Exception as e:
        logger.error(f"[LinuxScanner] 扫描运行应用失败: {e}")
        return []


def _parse_desktop_file(desktop_file: Path) -> Dict[str, str]:
    """解析.desktop文件.

    Args:
        desktop_file: .desktop文件路径

    Returns:
        Dict[str, str]: 应用程序信息
    """
    try:
        with open(desktop_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 解析 .desktop 文件
        name = ""
        display_name = ""
        exec_cmd = ""

        for line in content.split("\n"):
            if line.startswith("Name="):
                display_name = line.split("=", 1)[1]
            elif line.startswith("Name[zh_CN]="):
                display_name = line.split("=", 1)[1]  # 优先使用中文名
            elif line.startswith("Exec="):
                exec_cmd = line.split("=", 1)[1].split()[0]  # 取第一个命令

        if display_name and exec_cmd:
            name = _clean_app_name(display_name)
            return {
                "name": name,
                "display_name": display_name,
                "path": exec_cmd,
                "type": "desktop",
            }

        return None

    except Exception:
        return None


def _should_include_app(display_name: str) -> bool:
    """判断是否应该包含该应用程序.

    Args:
        display_name: 应用程序显示名称

    Returns:
        bool: 是否包含
    """
    if not display_name:
        return False

    # 排除的应用程序模式
    exclude_patterns = [
        # 系统组件
        "gnome-",
        "kde-",
        "xfce-",
        "unity-",
        # 开发工具组件
        "gdb",
        "valgrind",
        "strace",
        "ltrace",
        # 系统工具
        "dconf",
        "gsettings",
        "xdg-",
        "desktop-file-",
        # 其他系统组件
        "help",
        "about",
        "preferences",
        "settings",
    ]

    display_lower = display_name.lower()

    # 检查排除模式
    for pattern in exclude_patterns:
        if pattern in display_lower:
            return False

    return True


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
        # 内核和核心进程
        "kthreadd",
        "ksoftirqd",
        "migration",
        "rcu_",
        "watchdog",
        "systemd",
        "init",
        "kernel",
        "kworker",
        "kcompactd",
        # 系统服务
        "dbus",
        "networkd",
        "resolved",
        "logind",
        "udevd",
        "cron",
        "rsyslog",
        "ssh",
        "avahi",
        "cups",
        # 桌面环境服务
        "gnome-",
        "kde-",
        "xfce-",
        "unity-",
        "compiz",
        "pulseaudio",
        "pipewire",
        "wireplumber",
        # X11/Wayland
        "Xorg",
        "wayland",
        "weston",
        "mutter",
        "kwin",
    }

    # 检查是否是系统进程
    comm_lower = comm.lower()
    command_lower = command.lower()

    # 排除空名称或系统进程
    if not comm or any(proc in comm_lower for proc in system_processes):
        return False

    # 排除系统路径下的进程
    if any(
        path in command_lower
        for path in [
            "/usr/libexec/",
            "/usr/lib/",
            "/lib/",
            "/sbin/",
            "/usr/sbin/",
            "/bin/systemd",
            "/usr/bin/dbus",
        ]
    ):
        return False

    # 排除明显的系统服务
    if any(
        keyword in command_lower
        for keyword in ["daemon", "service", "helper", "agent", "monitor"]
    ):
        return False

    # 只包含用户应用程序
    user_app_indicators = [
        "/usr/bin/",
        "/usr/local/bin/",
        "/opt/",
        "/home/",
        "/snap/",
        "/flatpak/",
    ]

    return any(indicator in command_lower for indicator in user_app_indicators)


def _extract_app_name(comm: str, command: str) -> str:
    """从进程信息中提取应用程序名称.

    Args:
        comm: 进程名称
        command: 完整命令

    Returns:
        str: 应用程序名称
    """
    # 尝试从命令路径中提取应用名称
    if "/" in command:
        try:
            # 获取可执行文件名
            exec_path = command.split()[0]
            app_name = Path(exec_path).name

            # 移除常见后缀
            if app_name.endswith(".py"):
                app_name = app_name[:-3]
            elif app_name.endswith(".sh"):
                app_name = app_name[:-3]

            return app_name
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
