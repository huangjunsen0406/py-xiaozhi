"""应用程序扫描器.

扫描并获取系统中所有已安装的应用程序信息
"""

import asyncio
import json
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


async def scan_installed_applications(args: Dict[str, Any]) -> str:
    """
    扫描系统中所有已安装的应用程序.
    
    Args:
        args: 包含扫描参数的字典
            - force_refresh: 是否强制重新扫描（可选，默认False）
    
    Returns:
        str: JSON格式的应用程序列表
    """
    try:
        force_refresh = args.get("force_refresh", False)
        logger.info(f"[AppScanner] 开始扫描已安装应用程序，强制刷新: {force_refresh}")
        
        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(_scan_applications_sync, force_refresh)
        
        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"成功扫描到 {len(apps)} 个已安装应用程序"
        }
        
        logger.info(f"[AppScanner] 扫描完成，找到 {len(apps)} 个应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        error_msg = f"扫描应用程序失败: {str(e)}"
        logger.error(f"[AppScanner] {error_msg}", exc_info=True)
        return json.dumps({
            "success": False,
            "total_count": 0,
            "applications": [],
            "message": error_msg
        }, ensure_ascii=False)


def _scan_applications_sync(force_refresh: bool = False) -> List[Dict[str, str]]:
    """
    同步扫描应用程序的实现.
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return _scan_macos_applications()
    elif system == "Windows":  # Windows
        return _scan_windows_applications()
    else:  # Linux
        return _scan_linux_applications()


def _scan_macos_applications() -> List[Dict[str, str]]:
    """
    扫描macOS系统中的应用程序.
    """
    apps = []
    
    # 扫描 /Applications 目录
    applications_dir = Path("/Applications")
    if applications_dir.exists():
        for app_path in applications_dir.glob("*.app"):
            app_name = app_path.stem
            # 移除常见的版本号后缀
            clean_name = _clean_app_name(app_name)
            apps.append({
                "name": clean_name,
                "display_name": app_name,
                "path": str(app_path),
                "type": "application"
            })
    
    # 扫描用户应用程序目录
    user_apps_dir = Path.home() / "Applications"
    if user_apps_dir.exists():
        for app_path in user_apps_dir.glob("*.app"):
            app_name = app_path.stem
            clean_name = _clean_app_name(app_name)
            apps.append({
                "name": clean_name,
                "display_name": app_name,
                "path": str(app_path),
                "type": "user_application"
            })
    
    # 添加系统工具
    system_apps = [
        {"name": "Calculator", "display_name": "计算器", "path": "Calculator", "type": "system"},
        {"name": "TextEdit", "display_name": "文本编辑", "path": "TextEdit", "type": "system"},
        {"name": "Preview", "display_name": "预览", "path": "Preview", "type": "system"},
        {"name": "Safari", "display_name": "Safari浏览器", "path": "Safari", "type": "system"},
        {"name": "Finder", "display_name": "访达", "path": "Finder", "type": "system"},
        {"name": "Terminal", "display_name": "终端", "path": "Terminal", "type": "system"},
    ]
    apps.extend(system_apps)
    
    return apps


def _scan_windows_applications() -> List[Dict[str, str]]:
    """
    扫描Windows系统中的应用程序.
    """
    apps = []
    
    # 1. 使用PowerShell获取已安装的程序（注册表方式）
    try:
        logger.info("[AppScanner] 开始扫描注册表中的已安装程序")
        powershell_cmd = [
            "powershell", "-Command",
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
            "Select-Object DisplayName, InstallLocation | "
            "Where-Object {$_.DisplayName -ne $null} | "
            "ConvertTo-Json"
        ]
        
        result = subprocess.run(powershell_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout:
            try:
                installed_apps = json.loads(result.stdout)
                if isinstance(installed_apps, dict):
                    installed_apps = [installed_apps]
                
                for app in installed_apps:
                    display_name = app.get("DisplayName", "")
                    if display_name:
                        clean_name = _clean_app_name(display_name)
                        apps.append({
                            "name": clean_name,
                            "display_name": display_name,
                            "path": app.get("InstallLocation", ""),
                            "type": "installed"
                        })
                        
                logger.info(f"[AppScanner] 从注册表扫描到 {len([a for a in apps if a['type'] == 'installed'])} 个已安装程序")
            except json.JSONDecodeError:
                logger.warning("[AppScanner] 无法解析PowerShell输出")
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppScanner] PowerShell扫描失败: {e}")
    
    # 2. 扫描UWP应用（Windows Store应用）
    try:
        logger.info("[AppScanner] 开始扫描UWP应用")
        uwp_apps = _scan_uwp_applications()
        apps.extend(uwp_apps)
        logger.info(f"[AppScanner] 扫描到 {len(uwp_apps)} 个UWP应用")
    except Exception as e:
        logger.warning(f"[AppScanner] UWP应用扫描失败: {e}")
    
    # 3. 扫描开始菜单快捷方式
    try:
        logger.info("[AppScanner] 开始扫描开始菜单快捷方式")
        start_menu_apps = _scan_start_menu_shortcuts()
        # 去重：避免重复添加已经从注册表扫描到的应用
        existing_names = {app['display_name'].lower() for app in apps}
        for app in start_menu_apps:
            if app['display_name'].lower() not in existing_names:
                apps.append(app)
        logger.info(f"[AppScanner] 从开始菜单扫描到 {len([a for a in start_menu_apps if a['display_name'].lower() not in existing_names])} 个新应用")
    except Exception as e:
        logger.warning(f"[AppScanner] 开始菜单扫描失败: {e}")
    
    # 4. 添加常见的Windows系统应用
    system_apps = [
        {"name": "Calculator", "display_name": "计算器", "path": "calc", "type": "system"},
        {"name": "Notepad", "display_name": "记事本", "path": "notepad", "type": "system"},
        {"name": "Paint", "display_name": "画图", "path": "mspaint", "type": "system"},
        {"name": "Command Prompt", "display_name": "命令提示符", "path": "cmd", "type": "system"},
        {"name": "PowerShell", "display_name": "PowerShell", "path": "powershell", "type": "system"},
        {"name": "File Explorer", "display_name": "文件资源管理器", "path": "explorer", "type": "system"},
        {"name": "Task Manager", "display_name": "任务管理器", "path": "taskmgr", "type": "system"},
        {"name": "Registry Editor", "display_name": "注册表编辑器", "path": "regedit", "type": "system"},
        {"name": "Control Panel", "display_name": "控制面板", "path": "control", "type": "system"},
        {"name": "Device Manager", "display_name": "设备管理器", "path": "devmgmt.msc", "type": "system"},
    ]
    apps.extend(system_apps)
    
    return apps


def _scan_uwp_applications() -> List[Dict[str, str]]:
    """
    扫描UWP（Windows Store）应用程序.
    """
    apps = []
    
    try:
        # 使用PowerShell获取UWP应用
        powershell_script = """
        Get-AppxPackage | Where-Object {$_.Name -notlike "*Microsoft.Windows*" -and $_.Name -notlike "*Microsoft.NET*" -and $_.Name -notlike "*Microsoft.VCLibs*"} | 
        ForEach-Object {
            try {
                $manifest = Get-AppxPackageManifest $_.PackageFullName -ErrorAction SilentlyContinue
                if ($manifest -and $manifest.Package.Applications.Application) {
                    $app = $manifest.Package.Applications.Application | Select-Object -First 1
                    if ($app.Id) {
                        $displayName = if ($manifest.Package.Properties.DisplayName -match '^ms-resource:') {
                            $_.Name
                        } else {
                            $manifest.Package.Properties.DisplayName
                        }
                        [PSCustomObject]@{
                            Name = $_.Name
                            DisplayName = $displayName
                            PackageFullName = $_.PackageFullName
                            AppId = $app.Id
                        }
                    }
                }
            } catch {
                # 忽略错误，继续处理下一个
            }
        } | ConvertTo-Json
        """
        
        result = subprocess.run(
            ["powershell", "-Command", powershell_script],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0 and result.stdout.strip():
            try:
                uwp_data = json.loads(result.stdout)
                if isinstance(uwp_data, dict):
                    uwp_data = [uwp_data]
                
                for app in uwp_data:
                    display_name = app.get("DisplayName", app.get("Name", ""))
                    if display_name:
                        clean_name = _clean_app_name(display_name)
                        # 使用特殊的UWP启动路径格式
                        uwp_path = f"shell:AppsFolder\\{app['PackageFullName']}!{app['AppId']}"
                        apps.append({
                            "name": clean_name,
                            "display_name": display_name,
                            "path": uwp_path,
                            "type": "uwp"
                        })
                        
            except json.JSONDecodeError as e:
                logger.debug(f"[AppScanner] UWP JSON解析失败: {e}")
                
    except Exception as e:
        logger.debug(f"[AppScanner] UWP扫描异常: {e}")
    
    return apps


def _scan_start_menu_shortcuts() -> List[Dict[str, str]]:
    """
    扫描开始菜单中的快捷方式.
    """
    apps = []
    
    # 开始菜单目录
    start_menu_paths = [
        os.path.join(os.environ.get('PROGRAMDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
        os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
    ]
    
    for start_path in start_menu_paths:
        if os.path.exists(start_path):
            try:
                for root, dirs, files in os.walk(start_path):
                    for file in files:
                        if file.lower().endswith('.lnk'):
                            try:
                                shortcut_path = os.path.join(root, file)
                                display_name = file[:-4]  # 移除.lnk扩展名
                                clean_name = _clean_app_name(display_name)
                                
                                # 尝试解析快捷方式目标
                                target_path = _resolve_shortcut_target(shortcut_path)
                                
                                apps.append({
                                    "name": clean_name,
                                    "display_name": display_name,
                                    "path": target_path or shortcut_path,
                                    "type": "shortcut"
                                })
                                
                            except Exception as e:
                                logger.debug(f"[AppScanner] 处理快捷方式失败 {file}: {e}")
                                
            except Exception as e:
                logger.debug(f"[AppScanner] 扫描开始菜单失败 {start_path}: {e}")
    
    return apps


def _resolve_shortcut_target(shortcut_path: str) -> Optional[str]:
    """
    解析Windows快捷方式的目标路径.
    
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
        logger.debug("[AppScanner] win32com模块不可用，无法解析快捷方式")
    except Exception as e:
        logger.debug(f"[AppScanner] 解析快捷方式失败: {e}")
    
    return None


def _scan_linux_applications() -> List[Dict[str, str]]:
    """
    扫描Linux系统中的应用程序.
    """
    apps = []
    
    # 扫描 .desktop 文件
    desktop_dirs = [
        "/usr/share/applications",
        "/usr/local/share/applications",
        Path.home() / ".local/share/applications"
    ]
    
    for desktop_dir in desktop_dirs:
        desktop_path = Path(desktop_dir)
        if desktop_path.exists():
            for desktop_file in desktop_path.glob("*.desktop"):
                try:
                    with open(desktop_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 解析 .desktop 文件
                    name = ""
                    display_name = ""
                    exec_cmd = ""
                    
                    for line in content.split('\n'):
                        if line.startswith('Name='):
                            display_name = line.split('=', 1)[1]
                        elif line.startswith('Name[zh_CN]='):
                            display_name = line.split('=', 1)[1]  # 优先使用中文名
                        elif line.startswith('Exec='):
                            exec_cmd = line.split('=', 1)[1].split()[0]  # 取第一个命令
                    
                    if display_name and exec_cmd:
                        name = _clean_app_name(display_name)
                        apps.append({
                            "name": name,
                            "display_name": display_name,
                            "path": exec_cmd,
                            "type": "desktop"
                        })
                
                except Exception as e:
                    logger.debug(f"[AppScanner] 解析desktop文件失败 {desktop_file}: {e}")
    
    # 添加常见的Linux系统应用
    system_apps = [
        {"name": "gedit", "display_name": "文本编辑器", "path": "gedit", "type": "system"},
        {"name": "firefox", "display_name": "Firefox浏览器", "path": "firefox", "type": "system"},
        {"name": "gnome-calculator", "display_name": "计算器", "path": "gnome-calculator", "type": "system"},
        {"name": "nautilus", "display_name": "文件管理器", "path": "nautilus", "type": "system"},
        {"name": "gnome-terminal", "display_name": "终端", "path": "gnome-terminal", "type": "system"},
    ]
    apps.extend(system_apps)
    
    return apps


def _clean_app_name(name: str) -> str:
    """
    清理应用程序名称，移除版本号和特殊字符.
    """
    # 移除常见的版本号模式
    import re

    # 移除版本号 (如 "App 1.0", "App v2.1", "App (2023)")
    name = re.sub(r'\s+v?\d+[\.\d]*', '', name)
    name = re.sub(r'\s*\(\d+\)', '', name)
    name = re.sub(r'\s*\[.*?\]', '', name)
    
    # 移除多余的空格
    name = ' '.join(name.split())
    
    return name.strip() 