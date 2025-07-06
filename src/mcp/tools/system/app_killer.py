"""应用程序关闭器.

提供跨平台关闭应用程序的功能
"""

import asyncio
import json
import platform
import subprocess
from typing import Any, Dict, List

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


async def kill_application(args: Dict[str, Any]) -> bool:
    """
    关闭应用程序.
    
    Args:
        args: 包含应用程序名称的参数字典
            - app_name: 应用程序名称
            - force: 是否强制关闭（可选，默认False）
    
    Returns:
        bool: 关闭是否成功
    """
    try:
        app_name = args["app_name"]
        force = args.get("force", False)
        logger.info(f"[AppKiller] 尝试关闭应用程序: {app_name}, 强制关闭: {force}")
        
        # 首先尝试通过扫描找到正在运行的应用程序
        running_apps = await _find_running_applications(app_name)
        
        if not running_apps:
            logger.warning(f"[AppKiller] 未找到正在运行的应用程序: {app_name}")
            return False
        
        # 尝试关闭找到的应用程序
        success_count = 0
        for app in running_apps:
            success = await asyncio.to_thread(_kill_app_sync, app, force, platform.system())
            if success:
                success_count += 1
                logger.info(f"[AppKiller] 成功关闭应用程序: {app['name']} (PID: {app.get('pid', 'N/A')})")
            else:
                logger.warning(f"[AppKiller] 关闭应用程序失败: {app['name']} (PID: {app.get('pid', 'N/A')})")
        
        overall_success = success_count > 0
        logger.info(f"[AppKiller] 关闭操作完成，成功关闭 {success_count}/{len(running_apps)} 个进程")
        return overall_success
        
    except Exception as e:
        logger.error(f"[AppKiller] 关闭应用程序时出错: {e}", exc_info=True)
        return False


async def list_running_applications(args: Dict[str, Any]) -> str:
    """
    列出所有正在运行的应用程序.
    
    Args:
        args: 包含列出参数的字典
            - filter_name: 过滤应用程序名称（可选）
    
    Returns:
        str: JSON格式的运行中应用程序列表
    """
    try:
        filter_name = args.get("filter_name", "")
        logger.info(f"[AppKiller] 开始列出正在运行的应用程序，过滤条件: {filter_name}")
        
        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(_list_running_apps_sync, filter_name)
        
        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"找到 {len(apps)} 个正在运行的应用程序"
        }
        
        logger.info(f"[AppKiller] 列出完成，找到 {len(apps)} 个正在运行的应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        error_msg = f"列出运行中应用程序失败: {str(e)}"
        logger.error(f"[AppKiller] {error_msg}", exc_info=True)
        return json.dumps({
            "success": False,
            "total_count": 0,
            "applications": [],
            "message": error_msg
        }, ensure_ascii=False)


async def _find_running_applications(app_name: str) -> List[Dict[str, Any]]:
    """
    查找正在运行的匹配应用程序.
    
    Args:
        app_name: 要查找的应用程序名称
    
    Returns:
        匹配的正在运行应用程序列表
    """
    try:
        # 获取所有正在运行的应用程序
        all_apps = await asyncio.to_thread(_list_running_apps_sync, "")
        
        # 匹配应用程序名称
        matched_apps = []
        app_name_lower = app_name.lower()
        
        for app in all_apps:
            # 多种匹配方式
            if (app_name_lower in app["name"].lower() or
                    app_name_lower in app.get("display_name", "").lower() or
                    app_name_lower in app.get("command", "").lower()):
                matched_apps.append(app)
        
        return matched_apps
        
    except Exception as e:
        logger.warning(f"[AppKiller] 查找运行中应用程序时出错: {e}")
        return []


def _list_running_apps_sync(filter_name: str = "") -> List[Dict[str, Any]]:
    """
    同步列出正在运行的应用程序.
    
    Args:
        filter_name: 过滤应用程序名称
    
    Returns:
        正在运行的应用程序列表
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return _list_macos_running_apps(filter_name)
    elif system == "Windows":  # Windows
        return _list_windows_running_apps(filter_name)
    else:  # Linux
        return _list_linux_running_apps(filter_name)


def _list_macos_running_apps(filter_name: str = "") -> List[Dict[str, Any]]:
    """
    列出macOS上正在运行的应用程序.
    """
    apps = []
    
    try:
        # 使用ps命令获取进程信息
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,comm,command"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            
            for line in lines:
                parts = line.strip().split(None, 3)
                if len(parts) >= 4:
                    pid, ppid, comm, command = parts
                    
                    # 过滤应用程序
                    is_app = (".app" in command or 
                              not command.startswith("/") or 
                              any(name in command.lower() for name in ["chrome", "firefox", "qq", "wechat", "music"]))
                    
                    if is_app:
                        app_name = comm.split('/')[-1]
                        
                        # 应用过滤条件
                        if not filter_name or filter_name.lower() in app_name.lower():
                            apps.append({
                                "pid": int(pid),
                                "ppid": int(ppid),
                                "name": app_name,
                                "display_name": app_name,
                                "command": command,
                                "type": "application"
                            })
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppKiller] macOS进程扫描失败: {e}")
    
    return apps


def _list_windows_running_apps(filter_name: str = "") -> List[Dict[str, Any]]:
    """
    列出Windows上正在运行的应用程序.
    """
    apps = []
    
    # 方法1: 使用简化的tasklist命令（更快）
    try:
        logger.debug("[AppKiller] 尝试使用简化tasklist命令")
        result = subprocess.run(
            ["tasklist", "/fo", "csv"],  # 移除/v参数以提高速度
            capture_output=True, text=True, timeout=10, encoding='gbk'
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            
            for line in lines:
                try:
                    # 解析CSV格式
                    parts = [p.strip('"') for p in line.split('","')]
                    if len(parts) >= 2:
                        image_name = parts[0]
                        pid = parts[1]
                        
                        # 过滤系统进程和服务
                        if not image_name.lower().endswith('.exe'):
                            continue
                        
                        # 排除常见的系统进程
                        system_processes = {
                            'dwm.exe', 'winlogon.exe', 'csrss.exe', 'smss.exe',
                            'wininit.exe', 'services.exe', 'lsass.exe', 'svchost.exe',
                            'spoolsv.exe', 'explorer.exe', 'taskhostw.exe', 'winlogon.exe'
                        }
                        
                        if image_name.lower() in system_processes:
                            continue
                        
                        app_name = image_name.replace('.exe', '')
                        
                        # 应用过滤条件
                        if not filter_name or filter_name.lower() in app_name.lower():
                            apps.append({
                                "pid": int(pid),
                                "name": app_name,
                                "display_name": image_name,
                                "command": image_name,
                                "type": "application"
                            })
                except (ValueError, IndexError) as e:
                    logger.debug(f"[AppKiller] 解析tasklist行失败: {e}")
                    continue
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppKiller] tasklist命令失败: {e}")
    
    # 方法2: 如果tasklist失败，使用PowerShell作为备选
    if not apps:
        try:
            logger.debug("[AppKiller] 尝试使用PowerShell扫描进程")
            powershell_script = """
            Get-Process | Where-Object {
                $_.ProcessName -notmatch '^(dwm|winlogon|csrss|smss|wininit|services|lsass|svchost|spoolsv|taskhostw)$' -and
                $_.MainWindowTitle -ne '' -and
                $_.ProcessName -ne 'explorer'
            } | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json
            """
            
            result = subprocess.run(
                ["powershell", "-Command", powershell_script],
                capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0 and result.stdout.strip():
                try:
                    process_data = json.loads(result.stdout)
                    if isinstance(process_data, dict):
                        process_data = [process_data]
                    
                    for proc in process_data:
                        proc_name = proc.get("ProcessName", "")
                        pid = proc.get("Id", 0)
                        window_title = proc.get("MainWindowTitle", "")
                        
                        if proc_name and pid:
                            # 应用过滤条件
                            if not filter_name or filter_name.lower() in proc_name.lower():
                                apps.append({
                                    "pid": int(pid),
                                    "name": proc_name,
                                    "display_name": f"{proc_name}.exe",
                                    "command": f"{proc_name}.exe",
                                    "window_title": window_title,
                                    "type": "application"
                                })
                                
                except json.JSONDecodeError as e:
                    logger.debug(f"[AppKiller] PowerShell JSON解析失败: {e}")
                    
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.warning(f"[AppKiller] PowerShell进程扫描失败: {e}")
    
    # 方法3: 使用wmic作为最后备选（如果前两种方法都失败）
    if not apps:
        try:
            logger.debug("[AppKiller] 尝试使用wmic扫描进程")
            result = subprocess.run(
                ["wmic", "process", "get", "ProcessId,Name", "/format:csv"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        try:
                            name = parts[1].strip()
                            pid = parts[2].strip()
                            
                            if name.lower().endswith('.exe') and pid.isdigit():
                                app_name = name.replace('.exe', '')
                                
                                # 应用过滤条件
                                if not filter_name or filter_name.lower() in app_name.lower():
                                    apps.append({
                                        "pid": int(pid),
                                        "name": app_name,
                                        "display_name": name,
                                        "command": name,
                                        "type": "application"
                                    })
                        except (ValueError, IndexError):
                            continue
                            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.warning(f"[AppKiller] wmic进程扫描失败: {e}")
    
    # 去重并按名称排序
    seen_pids = set()
    unique_apps = []
    for app in apps:
        if app["pid"] not in seen_pids:
            seen_pids.add(app["pid"])
            unique_apps.append(app)
    
    unique_apps.sort(key=lambda x: x["name"].lower())
    
    logger.info(f"[AppKiller] Windows进程扫描完成，找到 {len(unique_apps)} 个应用程序")
    return unique_apps


def _list_linux_running_apps(filter_name: str = "") -> List[Dict[str, Any]]:
    """
    列出Linux上正在运行的应用程序.
    """
    apps = []
    
    try:
        # 使用ps命令获取进程信息
        result = subprocess.run(
            ["ps", "-eo", "pid,ppid,comm,command", "--no-headers"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                parts = line.strip().split(None, 3)
                if len(parts) >= 4:
                    pid, ppid, comm, command = parts
                    
                    # 过滤GUI应用程序
                    is_gui_app = (not command.startswith('/usr/bin/') and 
                                  not command.startswith('/bin/') and
                                  not command.startswith('[') and  # 内核线程
                                  len(comm) > 2)
                    
                    if is_gui_app:
                        app_name = comm
                        
                        # 应用过滤条件
                        if not filter_name or filter_name.lower() in app_name.lower():
                            apps.append({
                                "pid": int(pid),
                                "ppid": int(ppid),
                                "name": app_name,
                                "display_name": app_name,
                                "command": command,
                                "type": "application"
                            })
    
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppKiller] Linux进程扫描失败: {e}")
    
    return apps


def _kill_app_sync(app: Dict[str, Any], force: bool, system: str) -> bool:
    """
    同步关闭应用程序.
    
    Args:
        app: 应用程序信息
        force: 是否强制关闭
        system: 操作系统类型
    
    Returns:
        bool: 关闭是否成功
    """
    try:
        pid = app.get("pid")
        if not pid:
            return False
        
        if system == "Windows":
            return _kill_windows_app(pid, force)
        elif system == "Darwin":  # macOS
            return _kill_macos_app(pid, force)
        else:  # Linux
            return _kill_linux_app(pid, force)
            
    except Exception as e:
        logger.error(f"[AppKiller] 同步关闭应用程序失败: {e}")
        return False


def _kill_windows_app(pid: int, force: bool) -> bool:
    """
    在Windows上关闭应用程序.
    """
    try:
        logger.info(f"[AppKiller] 尝试关闭Windows应用程序，PID: {pid}, 强制关闭: {force}")
        
        if force:
            # 强制关闭
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"], 
                capture_output=True, text=True, timeout=10
            )
        else:
            # 正常关闭
            result = subprocess.run(
                ["taskkill", "/PID", str(pid)], 
                capture_output=True, text=True, timeout=10
            )
        
        success = result.returncode == 0
        
        if success:
            logger.info(f"[AppKiller] 成功关闭应用程序，PID: {pid}")
        else:
            logger.warning(f"[AppKiller] 关闭应用程序失败，PID: {pid}, 错误信息: {result.stderr}")
            
        return success
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.error(f"[AppKiller] Windows关闭应用程序异常，PID: {pid}, 错误: {e}")
        return False


def _kill_macos_app(pid: int, force: bool) -> bool:
    """
    在macOS上关闭应用程序.
    """
    try:
        if force:
            # 强制关闭 (SIGKILL)
            result = subprocess.run(
                ["kill", "-9", str(pid)], 
                capture_output=True, timeout=5
            )
        else:
            # 正常关闭 (SIGTERM)
            result = subprocess.run(
                ["kill", "-15", str(pid)], 
                capture_output=True, timeout=5
            )
        
        return result.returncode == 0
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.error(f"[AppKiller] macOS关闭应用程序失败: {e}")
        return False


def _kill_linux_app(pid: int, force: bool) -> bool:
    """
    在Linux上关闭应用程序.
    """
    try:
        if force:
            # 强制关闭 (SIGKILL)
            result = subprocess.run(
                ["kill", "-9", str(pid)], 
                capture_output=True, timeout=5
            )
        else:
            # 正常关闭 (SIGTERM)
            result = subprocess.run(
                ["kill", "-15", str(pid)], 
                capture_output=True, timeout=5
            )
        
        return result.returncode == 0
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.error(f"[AppKiller] Linux关闭应用程序失败: {e}")
        return False 