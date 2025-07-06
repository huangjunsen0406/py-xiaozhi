"""应用程序启动器.

提供跨平台打开应用程序的功能
"""

import asyncio
import os
import platform
import subprocess
from typing import Any, Dict, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


async def launch_application(args: Dict[str, Any]) -> bool:
    """
    启动应用程序.
    
    Args:
        args: 包含应用程序名称的参数字典
            - app_name: 应用程序名称
    
    Returns:
        bool: 启动是否成功
    """
    try:
        app_name = args["app_name"]
        logger.info(f"[AppLauncher] 尝试启动应用程序: {app_name}")
        
        # 首先尝试通过扫描找到精确匹配的应用程序
        matched_app = await _find_matching_application(app_name)
        if matched_app:
            logger.info(f"[AppLauncher] 找到匹配的应用程序: {matched_app['display_name']}")
            # 根据应用程序类型使用不同的启动方法
            app_type = matched_app.get('type', 'unknown')
            app_path = matched_app.get('path', matched_app['name'])
            
            if app_type == 'uwp':
                # UWP应用使用特殊的启动方法
                success = await asyncio.to_thread(_launch_uwp_app_by_path, app_path)
            elif app_type == 'shortcut' and app_path.endswith('.lnk'):
                # 快捷方式文件
                success = await asyncio.to_thread(_launch_shortcut, app_path)
            else:
                # 常规应用程序
                success = await asyncio.to_thread(_launch_app_sync, app_path, platform.system())
        else:
            # 如果没有找到匹配，使用原来的方法
            logger.info(f"[AppLauncher] 未找到精确匹配，使用原始名称: {app_name}")
            success = await asyncio.to_thread(_launch_app_sync, app_name, platform.system())
        
        if success:
            logger.info(f"[AppLauncher] 成功启动应用程序: {app_name}")
        else:
            logger.warning(f"[AppLauncher] 启动应用程序失败: {app_name}")
            
        return success
        
    except KeyError:
        logger.error("[AppLauncher] 缺少app_name参数")
        return False
    except Exception as e:
        logger.error(f"[AppLauncher] 启动应用程序失败: {e}", exc_info=True)
        return False


async def _find_matching_application(app_name: str) -> Optional[Dict[str, str]]:
    """
    通过扫描找到匹配的应用程序.
    
    Args:
        app_name: 要查找的应用程序名称
    
    Returns:
        匹配的应用程序信息，如果没找到则返回None
    """
    try:
        from .app_utils import find_best_matching_app

        # 使用统一的匹配逻辑
        matched_app = await find_best_matching_app(app_name, "installed")
        
        if matched_app:
            logger.info(f"[AppLauncher] 通过统一匹配找到应用: {matched_app.get('display_name', matched_app.get('name', ''))}")
        
        return matched_app
        
    except Exception as e:
        logger.warning(f"[AppLauncher] 查找匹配应用程序时出错: {e}")
        return None


def _launch_app_sync(app_name: str, system: str) -> bool:
    """
    同步启动应用程序.
    
    Args:
        app_name: 应用程序名称
        system: 操作系统类型
    
    Returns:
        bool: 启动是否成功
    """
    try:
        if system == "Windows":
            return _launch_windows_app(app_name)
        elif system == "Darwin":  # macOS
            return _launch_macos_app(app_name)
        else:  # Linux和其他Unix系统
            return _launch_linux_app(app_name)
    except Exception as e:
        logger.error(f"[AppLauncher] 同步启动失败: {e}", exc_info=True)
        return False


def _launch_windows_app(app_name: str) -> bool:
    """
    在Windows上启动应用程序.
    
    Args:
        app_name: 应用程序名称
    
    Returns:
        bool: 启动是否成功
    """
    try:
        logger.info(f"[AppLauncher] Windows启动应用程序: {app_name}")
        
        # 按优先级尝试不同的启动方法
        launch_methods = [
            ("PowerShell Start-Process", _try_powershell_start),
            ("start命令", _try_start_command),
            ("os.startfile", _try_os_startfile),
            ("注册表查找", _try_registry_launch),
            ("常见路径", _try_common_paths),
            ("where命令", _try_where_command),
            ("UWP应用", _try_uwp_launch)
        ]
        
        for method_name, method_func in launch_methods:
            try:
                if method_func(app_name):
                    logger.info(f"[AppLauncher] {method_name}成功启动: {app_name}")
                    return True
                else:
                    logger.debug(f"[AppLauncher] {method_name}启动失败: {app_name}")
            except Exception as e:
                logger.debug(f"[AppLauncher] {method_name}异常: {e}")
        
        logger.warning(f"[AppLauncher] 所有Windows启动方法都失败了: {app_name}")
        return False
        
    except Exception as e:
        logger.error(f"[AppLauncher] Windows启动异常: {e}", exc_info=True)
        return False


def _try_powershell_start(app_name: str) -> bool:
    """尝试使用PowerShell Start-Process启动应用程序"""
    try:
        escaped_name = app_name.replace('"', '""').replace("'", "''")
        powershell_cmd = f'powershell -Command "Start-Process \'{escaped_name}\'"'
        result = subprocess.run(powershell_cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _try_start_command(app_name: str) -> bool:
    """尝试使用start命令启动应用程序"""
    try:
        start_cmd = f'start "" "{app_name}"'
        result = subprocess.run(start_cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _try_os_startfile(app_name: str) -> bool:
    """尝试使用os.startfile启动应用程序"""
    try:
        os.startfile(app_name)
        return True
    except OSError:
        return False


def _try_registry_launch(app_name: str) -> bool:
    """尝试通过注册表查找并启动应用程序"""
    try:
        executable_path = _find_executable_in_registry(app_name)
        if executable_path:
            subprocess.Popen([executable_path])
            return True
    except Exception:
        pass
    return False


def _try_common_paths(app_name: str) -> bool:
    """尝试常见的应用程序路径"""
    common_paths = [
        f"C:\\Program Files\\{app_name}\\{app_name}.exe",
        f"C:\\Program Files (x86)\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local\\Programs\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local\\{app_name}\\{app_name}.exe",
        f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Roaming\\{app_name}\\{app_name}.exe",
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path])
                return True
            except Exception:
                continue
    return False


def _try_where_command(app_name: str) -> bool:
    """尝试使用where命令查找并启动应用程序"""
    try:
        result = subprocess.run(f"where {app_name}", shell=True, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            exe_path = result.stdout.strip().split('\n')[0]  # 取第一个结果
            if exe_path and os.path.exists(exe_path):
                subprocess.Popen([exe_path])
                return True
    except Exception:
        pass
    return False


def _try_uwp_launch(app_name: str) -> bool:
    """尝试启动UWP应用程序"""
    try:
        return _launch_uwp_app(app_name)
    except Exception:
        return False


def _find_executable_in_registry(app_name: str) -> Optional[str]:
    """
    通过注册表查找应用程序的可执行文件路径.
    
    Args:
        app_name: 应用程序名称
    
    Returns:
        应用程序路径，如果没找到则返回None
    """
    try:
        import winreg

        # 查找注册表中的卸载信息
        registry_paths = [
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
        ]
        
        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as subkey:
                                try:
                                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if app_name.lower() in display_name.lower():
                                        try:
                                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                            if install_location and os.path.exists(install_location):
                                                # 查找主执行文件
                                                for root, dirs, files in os.walk(install_location):
                                                    for file in files:
                                                        if file.lower().endswith('.exe') and app_name.lower() in file.lower():
                                                            return os.path.join(root, file)
                                        except FileNotFoundError:
                                            pass
                                        
                                        try:
                                            display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                                            if display_icon and display_icon.endswith('.exe') and os.path.exists(display_icon):
                                                return display_icon
                                        except FileNotFoundError:
                                            pass
                                            
                                except FileNotFoundError:
                                    continue
                        except Exception:
                            continue
            except Exception:
                continue
        
        return None
        
    except ImportError:
        logger.debug("[AppLauncher] winreg模块不可用，跳过注册表查找")
        return None
    except Exception as e:
        logger.debug(f"[AppLauncher] 注册表查找失败: {e}")
        return None


def _launch_uwp_app(app_name: str) -> bool:
    """
    尝试启动UWP（Windows Store）应用程序.
    
    Args:
        app_name: 应用程序名称
    
    Returns:
        bool: 启动是否成功
    """
    try:
        # 使用PowerShell查找和启动UWP应用
        powershell_script = f"""
        $app = Get-AppxPackage | Where-Object {{$_.Name -like "*{app_name}*" -or $_.PackageFullName -like "*{app_name}*"}} | Select-Object -First 1
        if ($app) {{
            $manifest = Get-AppxPackageManifest $app.PackageFullName
            $appId = $manifest.Package.Applications.Application.Id
            if ($appId) {{
                Start-Process "shell:AppsFolder\\$($app.PackageFullName)!$appId"
                Write-Output "Success"
            }}
        }}
        """
        
        result = subprocess.run(
            ["powershell", "-Command", powershell_script],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and "Success" in result.stdout:
            return True
            
    except Exception as e:
        logger.debug(f"[AppLauncher] UWP启动异常: {e}")
    
    return False


def _launch_macos_app(app_name: str) -> bool:
    """
    在macOS上启动应用程序.
    
    Args:
        app_name: 应用程序名称
    
    Returns:
        bool: 启动是否成功
    """
    try:
        # 方法1: 使用open -a命令
        try:
            subprocess.Popen(["open", "-a", app_name])
            return True
        except (OSError, subprocess.SubprocessError):
            pass
        
        # 方法2: 直接使用应用程序名称
        try:
            subprocess.Popen([app_name])
            return True
        except (OSError, subprocess.SubprocessError):
            pass
        
        # 方法3: 尝试Applications目录
        app_path = f"/Applications/{app_name}.app"
        if os.path.exists(app_path):
            subprocess.Popen(["open", app_path])
            return True
        
        # 方法4: 使用osascript启动
        script = f'tell application "{app_name}" to activate'
        subprocess.Popen(["osascript", "-e", script])
        return True
        
    except Exception as e:
        logger.error(f"[AppLauncher] macOS启动失败: {e}")
        return False


def _launch_linux_app(app_name: str) -> bool:
    """
    在Linux上启动应用程序.
    
    Args:
        app_name: 应用程序名称
    
    Returns:
        bool: 启动是否成功
    """
    try:
        # 方法1: 直接使用应用程序名称
        try:
            subprocess.Popen([app_name])
            return True
        except (OSError, subprocess.SubprocessError):
            pass
        
        # 方法2: 使用which查找应用程序路径
        try:
            result = subprocess.run(["which", app_name], capture_output=True, text=True)
            if result.returncode == 0:
                app_path = result.stdout.strip()
                subprocess.Popen([app_path])
                return True
        except (OSError, subprocess.SubprocessError):
            pass
        
        # 方法3: 使用xdg-open（适用于桌面环境）
        try:
            subprocess.Popen(["xdg-open", app_name])
            return True
        except (OSError, subprocess.SubprocessError):
            pass
        
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
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"[AppLauncher] Linux启动失败: {e}")
        return False


def _launch_uwp_app_by_path(uwp_path: str) -> bool:
    """
    通过UWP路径启动应用程序.
    
    Args:
        uwp_path: UWP应用程序路径（shell:AppsFolder\\...格式）
    
    Returns:
        bool: 启动是否成功
    """
    try:
        if uwp_path.startswith("shell:AppsFolder\\"):
            # 使用explorer启动UWP应用
            subprocess.Popen(["explorer.exe", uwp_path])
            logger.info(f"[AppLauncher] UWP应用启动成功: {uwp_path}")
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"[AppLauncher] UWP应用启动失败: {e}")
        return False


def _launch_shortcut(shortcut_path: str) -> bool:
    """
    启动快捷方式文件.
    
    Args:
        shortcut_path: 快捷方式文件路径
    
    Returns:
        bool: 启动是否成功
    """
    try:
        os.startfile(shortcut_path)
        logger.info(f"[AppLauncher] 快捷方式启动成功: {shortcut_path}")
        return True
    except Exception as e:
        logger.error(f"[AppLauncher] 快捷方式启动失败: {e}")
        return False 