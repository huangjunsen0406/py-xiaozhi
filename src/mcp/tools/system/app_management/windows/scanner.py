"""Windows应用程序扫描器.

专门用于Windows系统的应用程序扫描和管理
"""

import json
import os
import platform
import subprocess
from typing import Dict, List, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


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
        logger.warning(f"[WindowsScanner] 开始菜单扫描失败: {e}")

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
        logger.warning(f"[WindowsScanner] 注册表扫描失败: {e}")

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


def scan_running_applications() -> List[Dict[str, str]]:
    """扫描Windows系统中正在运行的应用程序.

    Returns:
        List[Dict[str, str]]: 正在运行的应用程序列表
    """
    if platform.system() != "Windows":
        return []

    apps = []

    try:
        # 使用tasklist命令获取进程信息
        result = subprocess.run(
            ["tasklist", "/fo", "csv", "/v"], capture_output=True, text=True, timeout=10
        )

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # 跳过标题行

            for line in lines:
                try:
                    # 解析CSV格式
                    parts = [part.strip('"') for part in line.split('","')]
                    if len(parts) >= 8:
                        image_name = parts[0].strip('"')
                        pid = parts[1]
                        window_title = parts[8] if len(parts) > 8 else ""

                        # 过滤掉不需要的进程
                        if _should_include_process(image_name, window_title):
                            display_name = _extract_app_name(image_name, window_title)
                            clean_name = _clean_app_name(display_name)

                            apps.append(
                                {
                                    "pid": int(pid),
                                    "name": clean_name,
                                    "display_name": display_name,
                                    "command": image_name,
                                    "window_title": window_title,
                                    "type": "application",
                                }
                            )
                except (ValueError, IndexError):
                    continue

        logger.info(f"[WindowsScanner] 找到 {len(apps)} 个正在运行的应用程序")
        return apps

    except Exception as e:
        logger.error(f"[WindowsScanner] 扫描运行应用失败: {e}")
        return []


def _scan_main_start_menu_apps() -> List[Dict[str, str]]:
    """
    扫描开始菜单中的主要应用程序（过滤系统组件和辅助工具）.
    """
    apps = []

    # 开始菜单目录
    start_menu_paths = [
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
    ]

    for start_path in start_menu_paths:
        if os.path.exists(start_path):
            try:
                for root, dirs, files in os.walk(start_path):
                    for file in files:
                        if file.lower().endswith(".lnk"):
                            try:
                                shortcut_path = os.path.join(root, file)
                                display_name = file[:-4]  # 移除.lnk扩展名

                                # 过滤掉不需要的应用程序
                                if _should_include_app(display_name):
                                    clean_name = _clean_app_name(display_name)
                                    target_path = _resolve_shortcut_target(
                                        shortcut_path
                                    )

                                    apps.append(
                                        {
                                            "name": clean_name,
                                            "display_name": display_name,
                                            "path": target_path or shortcut_path,
                                            "type": "shortcut",
                                        }
                                    )

                            except Exception as e:
                                logger.debug(
                                    f"[WindowsScanner] 处理快捷方式失败 {file}: {e}"
                                )

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
                        clean_name = _clean_app_name(display_name)
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
        logger.warning(f"[WindowsScanner] PowerShell扫描失败: {e}")

    return apps


def _should_include_app(display_name: str, publisher: str = "") -> bool:
    """判断是否应该包含该应用程序.

    Args:
        display_name: 应用程序显示名称
        publisher: 发布者（可选）

    Returns:
        bool: 是否应该包含
    """
    name_lower = display_name.lower()

    # 明确排除的系统组件和运行库
    exclude_keywords = [
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
    ]

    # 检查是否包含排除关键词
    for keyword in exclude_keywords:
        if keyword in name_lower:
            return False

    # 明确包含的知名应用程序
    include_keywords = [
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
    ]

    # 检查是否包含明确包含的关键词
    for keyword in include_keywords:
        if keyword in name_lower:
            return True

    # 如果有发布者信息，排除Microsoft发布的系统组件
    if publisher:
        publisher_lower = publisher.lower()
        if "microsoft corporation" in publisher_lower and any(
            x in name_lower
            for x in [
                "visual c++",
                ".net",
                "redistributable",
                "runtime",
                "framework",
                "update",
            ]
        ):
            return False

    # 默认包含其他应用程序（假设是用户安装的）
    # 但排除明显的系统组件
    system_indicators = ["(x64)", "(x86)", "redistributable", "runtime", "framework"]
    if any(indicator in name_lower for indicator in system_indicators):
        return False

    return True


def _should_include_process(image_name: str, window_title: str) -> bool:
    """判断是否应该包含该进程.

    Args:
        image_name: 进程映像名称
        window_title: 窗口标题

    Returns:
        bool: 是否包含
    """
    # 排除系统进程
    system_processes = {
        "dwm.exe",
        "winlogon.exe",
        "csrss.exe",
        "smss.exe",
        "lsass.exe",
        "services.exe",
        "svchost.exe",
        "explorer.exe",
        "taskhostw.exe",
        "conhost.exe",
        "dllhost.exe",
        "rundll32.exe",
        "msiexec.exe",
        "wininit.exe",
        "lsm.exe",
        "spoolsv.exe",
        "audiodg.exe",
    }

    image_lower = image_name.lower()

    # 排除系统进程
    if image_lower in system_processes:
        return False

    # 排除无窗口标题的进程（通常是后台服务）
    if not window_title or window_title == "N/A":
        return False

    # 只包含有意义的窗口标题
    if len(window_title.strip()) < 3:
        return False

    return True


def _extract_app_name(image_name: str, window_title: str) -> str:
    """从进程信息中提取应用程序名称.

    Args:
        image_name: 进程映像名称
        window_title: 窗口标题

    Returns:
        str: 应用程序名称
    """
    # 优先使用窗口标题
    if window_title and window_title != "N/A" and len(window_title.strip()) > 0:
        return window_title.strip()

    # 使用进程名称（去掉.exe后缀）
    if image_name.lower().endswith(".exe"):
        return image_name[:-4]

    return image_name


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
