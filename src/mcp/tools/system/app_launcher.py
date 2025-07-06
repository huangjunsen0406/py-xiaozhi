"""应用程序启动器.

提供跨平台打开应用程序的功能
"""

import asyncio
import json
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
            # 使用匹配到的应用程序路径或名称
            target_name = matched_app.get('path', matched_app['name'])
            success = await asyncio.to_thread(_launch_app_sync, target_name, platform.system())
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
        from .app_scanner import scan_installed_applications

        # 扫描已安装的应用程序
        result_json = await scan_installed_applications({"force_refresh": False})
        result = json.loads(result_json)
        
        if not result.get("success", False):
            return None
        
        applications = result.get("applications", [])
        app_name_lower = app_name.lower()
        
        # 1. 精确匹配（忽略大小写）
        for app in applications:
            if app["name"].lower() == app_name_lower:
                return app
            if app["display_name"].lower() == app_name_lower:
                return app
        
        # 2. 部分匹配（包含关系）
        for app in applications:
            if app_name_lower in app["name"].lower():
                return app
            if app_name_lower in app["display_name"].lower():
                return app
        
        # 3. 模糊匹配（移除空格和特殊字符）
        import re
        clean_app_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', app_name_lower)
        
        for app in applications:
            clean_name = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', app["name"].lower())
            clean_display = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]', '', app["display_name"].lower())
            
            if clean_app_name == clean_name or clean_app_name == clean_display:
                return app
        
        return None
        
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
        # 方法1: 直接使用应用程序名称
        try:
            subprocess.Popen([app_name], shell=True)
            return True
        except (OSError, subprocess.SubprocessError):
            pass
        
        # 方法2: 使用os.startfile
        try:
            os.startfile(app_name)
            return True
        except OSError:
            pass
        
        # 方法3: 尝试常见的应用程序路径
        common_paths = [
            f"C:\\Program Files\\{app_name}\\{app_name}.exe",
            f"C:\\Program Files (x86)\\{app_name}\\{app_name}.exe",
            f"C:\\Users\\{os.getenv('USERNAME')}\\AppData\\Local\\Programs\\{app_name}\\{app_name}.exe",
        ]
        
        for path in common_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                return True
        
        # 方法4: 使用start命令
        subprocess.Popen(f"start {app_name}", shell=True)
        return True
        
    except Exception as e:
        logger.error(f"[AppLauncher] Windows启动失败: {e}")
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