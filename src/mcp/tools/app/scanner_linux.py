"""Linux应用程序扫描器.

专门用于Linux系统的应用程序扫描和管理
"""

import platform
from pathlib import Path

from src.logging import get_logger

from .utils import clean_app_name

logger = get_logger()


def scan_installed_applications() -> list[dict[str, str]]:
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


def _parse_desktop_file(desktop_file: Path) -> dict[str, str]:
    """解析.desktop文件.

    Args:
        desktop_file: .desktop文件路径

    Returns:
        Dict[str, str]: 应用程序信息
    """
    try:
        with open(desktop_file, encoding="utf-8") as f:
            content = f.read()

        # 解析 .desktop 文件
        name = ""
        display_name = ""
        exec_cmd = ""

        in_entry = False
        localized_name = ""
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("["):
                in_entry = line == "[Desktop Entry]"
                continue
            if not in_entry:
                continue
            if line.startswith("Name="):
                display_name = line.split("=", 1)[1]
            elif line.startswith("Name[zh_CN]="):
                localized_name = line.split("=", 1)[1]
            elif line.startswith("Exec="):
                exec_cmd = line.split("=", 1)[1]

        display_name = localized_name or display_name
        if display_name and exec_cmd:
            name = clean_app_name(display_name)
            return {
                "name": name,
                "display_name": display_name,
                "path": str(desktop_file),
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
