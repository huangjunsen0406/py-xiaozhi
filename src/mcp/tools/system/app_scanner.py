"""应用程序扫描器.

扫描并获取系统中所有已安装的应用程序信息
"""

import asyncio
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 全局缓存变量
_app_cache: Optional[Dict[str, Any]] = None
_cache_timestamp: float = 0
_cache_duration = 300  # 缓存5分钟


async def scan_installed_applications(args: Dict[str, Any]) -> str:
    """
    扫描系统中所有已安装的应用程序.
    
    Args:
        args: 包含扫描参数的字典
            - force_refresh: 是否强制重新扫描（可选，默认False）
    
    Returns:
        str: JSON格式的应用程序列表
    """
    global _app_cache, _cache_timestamp
    
    try:
        force_refresh = args.get("force_refresh", False)
        current_time = time.time()
        
        # 检查是否需要使用缓存
        if not force_refresh and _app_cache and (current_time - _cache_timestamp) < _cache_duration:
            logger.info(f"[AppScanner] 使用内存缓存，缓存时间: {int(current_time - _cache_timestamp)}秒前")
            return json.dumps(_app_cache, ensure_ascii=False, indent=2)
        
        # 尝试从文件缓存加载
        if not force_refresh:
            file_cache = await _load_file_cache()
            if file_cache:
                _app_cache = file_cache
                _cache_timestamp = current_time
                logger.info("[AppScanner] 使用文件缓存")
                return json.dumps(_app_cache, ensure_ascii=False, indent=2)
        
        logger.info(f"[AppScanner] 开始扫描已安装应用程序，强制刷新: {force_refresh}")
        
        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(_scan_applications_sync, force_refresh)
        
        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"成功扫描到 {len(apps)} 个已安装应用程序",
            "scan_time": current_time,
            "cache_duration": _cache_duration
        }
        
        # 更新缓存
        _app_cache = result
        _cache_timestamp = current_time
        
        # 异步保存到文件缓存
        asyncio.create_task(_save_file_cache(result))
        
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


async def _load_file_cache() -> Optional[Dict[str, Any]]:
    """
    从文件加载缓存.
    """
    try:
        cache_file = _get_cache_file_path()
        if not cache_file.exists():
            return None
        
        # 检查文件缓存是否过期
        file_mtime = cache_file.stat().st_mtime
        if time.time() - file_mtime > _cache_duration:
            logger.debug("[AppScanner] 文件缓存已过期")
            return None
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 验证缓存数据结构
        if (isinstance(cache_data, dict) and
                "applications" in cache_data and
                "scan_time" in cache_data):
            logger.debug(f"[AppScanner] 加载文件缓存成功，包含 {len(cache_data['applications'])} 个应用")
            return cache_data
        
    except Exception as e:
        logger.debug(f"[AppScanner] 加载文件缓存失败: {e}")
    
    return None


async def _save_file_cache(cache_data: Dict[str, Any]) -> None:
    """
    保存缓存到文件.
    """
    try:
        cache_file = _get_cache_file_path()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"[AppScanner] 缓存已保存到文件: {cache_file}")
        
    except Exception as e:
        logger.warning(f"[AppScanner] 保存文件缓存失败: {e}")


def _get_cache_file_path() -> Path:
    """
    获取缓存文件路径.
    """
    cache_dir = Path("cache")
    return cache_dir / "installed_apps.json"


def clear_app_cache() -> None:
    """
    清空应用程序缓存.
    """
    global _app_cache, _cache_timestamp
    
    _app_cache = None
    _cache_timestamp = 0
    
    # 删除文件缓存
    try:
        cache_file = _get_cache_file_path()
        if cache_file.exists():
            cache_file.unlink()
            logger.info("[AppScanner] 已清空应用程序缓存")
    except Exception as e:
        logger.warning(f"[AppScanner] 清空文件缓存失败: {e}")


def get_cache_status() -> Dict[str, Any]:
    """
    获取缓存状态信息.
    """
    global _app_cache, _cache_timestamp
    
    current_time = time.time()
    cache_age = current_time - _cache_timestamp if _cache_timestamp > 0 else -1
    cache_file = _get_cache_file_path()
    
    return {
        "memory_cache_exists": _app_cache is not None,
        "memory_cache_age_seconds": int(cache_age) if cache_age >= 0 else None,
        "memory_cache_valid": cache_age >= 0 and cache_age < _cache_duration,
        "file_cache_exists": cache_file.exists(),
        "file_cache_size": cache_file.stat().st_size if cache_file.exists() else 0,
        "cache_duration_seconds": _cache_duration,
        "cached_app_count": len(_app_cache["applications"]) if _app_cache else 0
    }


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
    扫描Windows系统中的应用程序（只保留主要应用）.
    """
    apps = []
    
    # 1. 扫描开始菜单中的主要应用程序（最直接的方法）
    try:
        logger.info("[AppScanner] 开始扫描开始菜单主要应用")
        start_menu_apps = _scan_main_start_menu_apps()
        apps.extend(start_menu_apps)
        logger.info(f"[AppScanner] 从开始菜单扫描到 {len(start_menu_apps)} 个主要应用")
    except Exception as e:
        logger.warning(f"[AppScanner] 开始菜单扫描失败: {e}")
    
    # 2. 扫描注册表中的主要第三方应用（过滤系统组件）
    try:
        logger.info("[AppScanner] 开始扫描已安装的主要应用程序")
        registry_apps = _scan_main_registry_apps()
        # 去重：避免重复添加开始菜单中的应用
        existing_names = {app['display_name'].lower() for app in apps}
        for app in registry_apps:
            if app['display_name'].lower() not in existing_names:
                apps.append(app)
        logger.info(f"[AppScanner] 从注册表扫描到 {len([a for a in registry_apps if a['display_name'].lower() not in existing_names])} 个新的主要应用")
    except Exception as e:
        logger.warning(f"[AppScanner] 注册表扫描失败: {e}")
    
    # 3. 添加常见的系统应用（只保留用户常用的）
    system_apps = [
        {"name": "Calculator", "display_name": "计算器", "path": "calc", "type": "system"},
        {"name": "Notepad", "display_name": "记事本", "path": "notepad", "type": "system"},
        {"name": "Paint", "display_name": "画图", "path": "mspaint", "type": "system"},
        {"name": "File Explorer", "display_name": "文件资源管理器", "path": "explorer", "type": "system"},
        {"name": "Task Manager", "display_name": "任务管理器", "path": "taskmgr", "type": "system"},
        {"name": "Control Panel", "display_name": "控制面板", "path": "control", "type": "system"},
        {"name": "Settings", "display_name": "设置", "path": "ms-settings:", "type": "system"},
    ]
    apps.extend(system_apps)
    
    logger.info(f"[AppScanner] Windows应用扫描完成，总共找到 {len(apps)} 个主要应用程序")
    return apps


def _scan_main_start_menu_apps() -> List[Dict[str, str]]:
    """
    扫描开始菜单中的主要应用程序（过滤系统组件和辅助工具）.
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
                                
                                # 过滤掉不需要的应用程序
                                if _should_include_app(display_name):
                                    clean_name = _clean_app_name(display_name)
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


def _scan_main_registry_apps() -> List[Dict[str, str]]:
    """
    扫描注册表中的主要应用程序（过滤系统组件）.
    """
    apps = []
    
    try:
        powershell_cmd = [
            "powershell", "-Command",
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* | "
            "Select-Object DisplayName, InstallLocation, Publisher | "
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
                    publisher = app.get("Publisher", "")
                    
                    if display_name and _should_include_app(display_name, publisher):
                        clean_name = _clean_app_name(display_name)
                        apps.append({
                            "name": clean_name,
                            "display_name": display_name,
                            "path": app.get("InstallLocation", ""),
                            "type": "installed"
                        })
                        
            except json.JSONDecodeError:
                logger.warning("[AppScanner] 无法解析PowerShell输出")
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppScanner] PowerShell扫描失败: {e}")
    
    return apps


def _should_include_app(display_name: str, publisher: str = "") -> bool:
    """
    判断是否应该包含该应用程序.
    
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
        'microsoft visual c++', 'microsoft .net', 'microsoft office', 'microsoft edge webview',
        'microsoft visual studio', 'microsoft redistributable', 'microsoft windows sdk',
        
        # 系统工具和驱动
        'uninstall', '卸载', 'readme', 'help', '帮助', 'documentation', '文档',
        'driver', '驱动', 'update', '更新', 'hotfix', 'patch', '补丁',
        
        # 开发工具组件
        'development', 'sdk', 'runtime', 'redistributable', 'framework',
        'python documentation', 'python test suite', 'python executables',
        'java update', 'java development kit',
        
        # 系统服务
        'service pack', 'security update', 'language pack',
        
        # 无用的快捷方式
        'website', 'web site', '网站', 'online', '在线',
        'report', '报告', 'feedback', '反馈',
    ]
    
    # 检查是否包含排除关键词
    for keyword in exclude_keywords:
        if keyword in name_lower:
            return False
    
    # 明确包含的知名应用程序
    include_keywords = [
        # 浏览器
        'chrome', 'firefox', 'edge', 'safari', 'opera', 'brave',
        
        # 办公软件
        'office', 'word', 'excel', 'powerpoint', 'outlook', 'onenote',
        'wps', 'typora', 'notion', 'obsidian',
        
        # 开发工具
        'visual studio code', 'vscode', 'pycharm', 'idea', 'eclipse',
        'git', 'docker', 'nodejs', 'android studio',
        
        # 通信软件
        'qq', '微信', 'wechat', 'skype', 'zoom', 'teams', '飞书', 'feishu',
        'discord', 'slack', 'telegram',
        
        # 媒体软件
        'vlc', 'potplayer', '网易云音乐', 'spotify', 'itunes',
        'photoshop', 'premiere', 'after effects', 'illustrator',
        
        # 游戏平台
        'steam', 'epic', 'origin', 'uplay', 'battlenet',
        
        # 实用工具
        '7-zip', 'winrar', 'bandizip', 'everything', 'listary',
        'notepad++', 'sublime', 'atom',
    ]
    
    # 检查是否包含明确包含的关键词
    for keyword in include_keywords:
        if keyword in name_lower:
            return True
    
    # 如果有发布者信息，排除Microsoft发布的系统组件
    if publisher:
        publisher_lower = publisher.lower()
        if ('microsoft corporation' in publisher_lower and 
                any(x in name_lower for x in ['visual c++', '.net', 'redistributable', 'runtime', 'framework', 'update'])):
            return False
    
    # 默认包含其他应用程序（假设是用户安装的）
    # 但排除明显的系统组件
    system_indicators = ['(x64)', '(x86)', 'redistributable', 'runtime', 'framework']
    if any(indicator in name_lower for indicator in system_indicators):
        return False
    
    return True


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