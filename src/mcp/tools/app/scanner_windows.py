"""Windows应用程序扫描器.

专门用于Windows系统的应用程序扫描和管理
"""

import json
import os
import platform
import subprocess
from typing import Dict, List, Optional

from src.logging import get_logger

from .utils import clean_app_name

logger = get_logger()


def scan_installed_applications() -> List[Dict[str, str]]:
    """扫描Windows系统中已安装的应用程序.

    Returns:
        List[Dict[str, str]]: 应用程序列表
    """
    if platform.system() != "Windows":
        return []

    apps = []

    # 1. 扫描开始菜单中的主要应用程序（最直接的方法）
    try:
        logger.info("[WindowsScanner] 开始扫描开始菜单主要应用")
        start_menu_apps = _scan_main_start_menu_apps()
        apps.extend(start_menu_apps)
        logger.info(
            f"[WindowsScanner] 从开始菜单扫描到 {len(start_menu_apps)} 个主要应用"
        )
    except Exception as e:
        logger.warning(f"[WindowsScanner] 开始菜单扫描失败: {e}", exc_info=True)

    # 2. 扫描注册表中的主要第三方应用（过滤系统组件）
    try:
        logger.info("[WindowsScanner] 开始扫描已安装的主要应用程序")
        registry_apps = _scan_main_registry_apps()
        # 去重：避免重复添加开始菜单中的应用
        existing_names = {app["display_name"].lower() for app in apps}
        for app in registry_apps:
            if app["display_name"].lower() not in existing_names:
                apps.append(app)
        logger.info(
            f"[WindowsScanner] 从注册表扫描到 {len([a for a in registry_apps if a['display_name'].lower() not in existing_names])} 个新的主要应用"
        )
    except Exception as e:
        logger.warning(f"[WindowsScanner] 注册表扫描失败: {e}", exc_info=True)

    # 3. 添加常见的系统应用（只保留用户常用的）
    system_apps = [
        {
            "name": "Calculator",
            "display_name": "计算器",
            "path": "calc",
            "type": "system",
        },
        {
            "name": "Notepad",
            "display_name": "记事本",
            "path": "notepad",
            "type": "system",
        },
        {"name": "Paint", "display_name": "画图", "path": "mspaint", "type": "system"},
        {
            "name": "File Explorer",
            "display_name": "文件资源管理器",
            "path": "explorer",
            "type": "system",
        },
        {
            "name": "Task Manager",
            "display_name": "任务管理器",
            "path": "taskmgr",
            "type": "system",
        },
        {
            "name": "Control Panel",
            "display_name": "控制面板",
            "path": "control",
            "type": "system",
        },
        {
            "name": "Settings",
            "display_name": "设置",
            "path": "ms-settings:",
            "type": "system",
        },
    ]
    apps.extend(system_apps)

    logger.info(
        f"[WindowsScanner] Windows应用扫描完成，总共找到 {len(apps)} 个主要应用程序"
    )
    return apps


def _build_shortcut_app(root: str, filename: str) -> dict[str, str] | None:
    if not filename.lower().endswith(".lnk"):
        return None
    display_name = filename[:-4]
    if not _should_include_app(display_name):
        return None
    shortcut_path = os.path.join(root, filename)
    target_path = _resolve_shortcut_target(shortcut_path)
    return {
        "name": clean_app_name(display_name),
        "display_name": display_name,
        "path": target_path or shortcut_path,
        "type": "shortcut",
    }


def _scan_start_menu_dir(start_path: str) -> list[dict[str, str]]:
    apps: list[dict[str, str]] = []
    for root, _dirs, files in os.walk(start_path):
        for file in files:
            try:
                app = _build_shortcut_app(root, file)
                if app is not None:
                    apps.append(app)
            except Exception as e:
                logger.debug(f"[WindowsScanner] 处理快捷方式失败 {file}: {e}")
    return apps


def _scan_main_start_menu_apps() -> List[Dict[str, str]]:
    """
    扫描开始菜单中的主要应用程序（过滤系统组件和辅助工具）.
    """
    apps: list[dict[str, str]] = []
    start_menu_paths = (
        os.path.join(
            os.environ.get("PROGRAMDATA", ""),
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
        ),
        os.path.join(
            os.environ.get("APPDATA", ""),
            "Microsoft",
            "Windows",
            "Start Menu",
            "Programs",
        ),
    )

    for start_path in start_menu_paths:
        if not os.path.exists(start_path):
            continue
        try:
            apps.extend(_scan_start_menu_dir(start_path))
        except Exception as e:
            logger.debug(f"[WindowsScanner] 扫描开始菜单失败 {start_path}: {e}")

    return apps


def _scan_main_registry_apps() -> List[Dict[str, str]]:
    """
    扫描注册表中的主要应用程序（过滤系统组件）.
    """
    apps = []

    try:
        powershell_cmd = [
            "powershell",
            "-Command",
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
            "Select-Object DisplayName, InstallLocation, Publisher | "
            "Where-Object {$_.DisplayName -ne $null} | "
            "ConvertTo-Json",
        ]

        result = subprocess.run(
            powershell_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            try:
                installed_apps = json.loads(result.stdout)
                if isinstance(installed_apps, dict):
                    installed_apps = [installed_apps]

                for app in installed_apps:
                    display_name = app.get("DisplayName", "")
                    publisher = app.get("Publisher", "")

                    if display_name and _should_include_app(display_name, publisher):
                        clean_name = clean_app_name(display_name)
                        apps.append(
                            {
                                "name": clean_name,
                                "display_name": display_name,
                                "path": app.get("InstallLocation", ""),
                                "type": "installed",
                            }
                        )

            except json.JSONDecodeError:
                logger.warning("[WindowsScanner] 无法解析PowerShell输出")

    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[WindowsScanner] PowerShell扫描失败: {e}", exc_info=True)

    return apps


_EXCLUDE_KEYWORDS = (
    # Microsoft系统组件
    "microsoft visual c++",
    "microsoft .net",
    "microsoft office",
    "microsoft edge webview",
    "microsoft visual studio",
    "microsoft redistributable",
    "microsoft windows sdk",
    # 系统工具和驱动
    "uninstall",
    "卸载",
    "readme",
    "help",
    "帮助",
    "documentation",
    "文档",
    "driver",
    "驱动",
    "update",
    "更新",
    "hotfix",
    "patch",
    "补丁",
    # 开发工具组件
    "development",
    "sdk",
    "runtime",
    "redistributable",
    "framework",
    "python documentation",
    "python test suite",
    "python executables",
    "java update",
    "java development kit",
    # 系统服务
    "service pack",
    "security update",
    "language pack",
    # 无用的快捷方式
    "website",
    "web site",
    "网站",
    "online",
    "在线",
    "report",
    "报告",
    "feedback",
    "反馈",
)

_INCLUDE_KEYWORDS = (
    # 浏览器
    "chrome",
    "firefox",
    "edge",
    "safari",
    "opera",
    "brave",
    # 办公软件
    "office",
    "word",
    "excel",
    "powerpoint",
    "outlook",
    "onenote",
    "wps",
    "typora",
    "notion",
    "obsidian",
    # 开发工具
    "visual studio code",
    "vscode",
    "pycharm",
    "idea",
    "eclipse",
    "git",
    "docker",
    "nodejs",
    "android studio",
    # 通信软件
    "qq",
    "微信",
    "wechat",
    "skype",
    "zoom",
    "teams",
    "飞书",
    "feishu",
    "discord",
    "slack",
    "telegram",
    # 媒体软件
    "vlc",
    "potplayer",
    "网易云音乐",
    "spotify",
    "itunes",
    "photoshop",
    "premiere",
    "after effects",
    "illustrator",
    # 游戏平台
    "steam",
    "epic",
    "origin",
    "uplay",
    "battlenet",
    # 实用工具
    "7-zip",
    "winrar",
    "bandizip",
    "everything",
    "listary",
    "notepad++",
    "sublime",
    "atom",
)

_MS_SYSTEM_KEYWORDS = ("visual c++", ".net")
_SYSTEM_INDICATORS = ("(x64)", "(x86)")


def _should_include_app(display_name: str, publisher: str = "") -> bool:
    """判断是否应该包含该应用程序.

    Args:
        display_name: 应用程序显示名称
        publisher: 发布者（可选）

    Returns:
        bool: 是否应该包含
    """
    name_lower = display_name.lower()

    if any(keyword in name_lower for keyword in _EXCLUDE_KEYWORDS):
        return False

    if any(keyword in name_lower for keyword in _INCLUDE_KEYWORDS):
        return True

    if publisher and "microsoft corporation" in publisher.lower():
        if any(k in name_lower for k in _MS_SYSTEM_KEYWORDS):
            return False

    return not any(indicator in name_lower for indicator in _SYSTEM_INDICATORS)


def _resolve_shortcut_target(shortcut_path: str) -> Optional[str]:
    """解析Windows快捷方式的目标路径.

    Args:
        shortcut_path: 快捷方式文件路径

    Returns:
        目标路径，如果解析失败则返回None
    """
    try:
        import win32com.client

        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        target_path = shortcut.Targetpath

        if target_path and os.path.exists(target_path):
            return target_path

    except ImportError:
        logger.debug("[WindowsScanner] win32com模块不可用，无法解析快捷方式")
    except Exception as e:
        logger.debug(f"[WindowsScanner] 解析快捷方式失败: {e}")

    return None
