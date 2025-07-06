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
        
        # 按应用分组并关闭
        system = platform.system()
        if system == "Windows":
            success = await asyncio.to_thread(_kill_windows_app_group, running_apps, app_name, force)
        else:
            # macOS和Linux保持原有逻辑
            success_count = 0
            for app in running_apps:
                success = await asyncio.to_thread(_kill_app_sync, app, force, system)
                if success:
                    success_count += 1
                    logger.info(f"[AppKiller] 成功关闭应用程序: {app['name']} (PID: {app.get('pid', 'N/A')})")
                else:
                    logger.warning(f"[AppKiller] 关闭应用程序失败: {app['name']} (PID: {app.get('pid', 'N/A')})")
            
            success = success_count > 0
            logger.info(f"[AppKiller] 关闭操作完成，成功关闭 {success_count}/{len(running_apps)} 个进程")
        
        return success
        
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
        from .app_utils import AppMatcher

        # 获取所有正在运行的应用程序
        all_apps = await asyncio.to_thread(_list_running_apps_sync, "")
        
        # 使用统一匹配器找到最佳匹配
        matched_apps = []
        
        for app in all_apps:
            score = AppMatcher.match_application(app_name, app)
            if score >= 50:  # 匹配度阈值
                matched_apps.append(app)
        
        # 按匹配度排序
        matched_apps.sort(key=lambda x: AppMatcher.match_application(app_name, x), reverse=True)
        
        logger.info(f"[AppKiller] 找到 {len(matched_apps)} 个匹配的运行应用")
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
    
    # 方法1: 使用优化的PowerShell扫描（优先选择，最快最准确）
    try:
        logger.debug("[AppKiller] 使用优化的PowerShell扫描进程")
        # 更简洁高效的PowerShell脚本
        powershell_script = """
        Get-Process | Where-Object {
            $_.ProcessName -notmatch '^(dwm|winlogon|csrss|smss|wininit|services|lsass|svchost|spoolsv|taskhostw|explorer|fontdrvhost|dllhost|conhost|sihost|runtimebroker)$' -and
            ($_.MainWindowTitle -or $_.ProcessName -match '(chrome|firefox|edge|qq|wechat|notepad|calc|typora|vscode|pycharm|feishu|qqmusic)')
        } | Select-Object Id, ProcessName, MainWindowTitle, Path | ConvertTo-Json
        """
        
        result = subprocess.run(
            ["powershell", "-Command", powershell_script],
            capture_output=True, text=True, timeout=8
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
                    exe_path = proc.get("Path", "")
                    
                    if proc_name and pid:
                        # 应用过滤条件
                        if not filter_name or _matches_process_name(filter_name, proc_name, window_title, exe_path):
                            apps.append({
                                "pid": int(pid),
                                "name": proc_name,
                                "display_name": f"{proc_name}.exe",
                                "command": exe_path or f"{proc_name}.exe",
                                "window_title": window_title,
                                "type": "application"
                            })
                
                if apps:
                    logger.info(f"[AppKiller] PowerShell扫描成功，找到 {len(apps)} 个进程")
                    return _deduplicate_and_sort_apps(apps)
                    
            except json.JSONDecodeError as e:
                logger.debug(f"[AppKiller] PowerShell JSON解析失败: {e}")
                
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        logger.warning(f"[AppKiller] PowerShell进程扫描失败: {e}")
    
    # 方法2: 使用简化的tasklist命令（备选方案）
    if not apps:
        try:
            logger.debug("[AppKiller] 使用简化tasklist命令")
            result = subprocess.run(
                ["tasklist", "/fo", "csv"],
                capture_output=True, text=True, timeout=5, encoding='gbk'
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
                            
                            # 基本过滤
                            if not image_name.lower().endswith('.exe'):
                                continue
                            
                            app_name = image_name.replace('.exe', '')
                            
                            # 过滤系统进程
                            if _is_system_process(app_name):
                                continue
                            
                            # 应用过滤条件
                            if not filter_name or _matches_process_name(filter_name, app_name, "", image_name):
                                apps.append({
                                    "pid": int(pid),
                                    "name": app_name,
                                    "display_name": image_name,
                                    "command": image_name,
                                    "type": "application"
                                })
                    except (ValueError, IndexError):
                        continue
                        
            if apps:
                logger.info(f"[AppKiller] tasklist扫描成功，找到 {len(apps)} 个进程")
                return _deduplicate_and_sort_apps(apps)
        
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.warning(f"[AppKiller] tasklist命令失败: {e}")
    
    # 方法3: 使用wmic作为最后备选
    if not apps:
        try:
            logger.debug("[AppKiller] 使用wmic命令")
            result = subprocess.run(
                ["wmic", "process", "get", "ProcessId,Name,ExecutablePath", "/format:csv"],
                capture_output=True, text=True, timeout=5
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
                
                for line in lines:
                    parts = line.split(',')
                    if len(parts) >= 3:
                        try:
                            exe_path = parts[1].strip() if len(parts) > 1 else ""
                            name = parts[2].strip() if len(parts) > 2 else ""
                            pid = parts[3].strip() if len(parts) > 3 else ""
                            
                            if name.lower().endswith('.exe') and pid.isdigit():
                                app_name = name.replace('.exe', '')
                                
                                if _is_system_process(app_name):
                                    continue
                                
                                # 应用过滤条件
                                if not filter_name or _matches_process_name(filter_name, app_name, "", exe_path):
                                    apps.append({
                                        "pid": int(pid),
                                        "name": app_name,
                                        "display_name": name,
                                        "command": exe_path or name,
                                        "type": "application"
                                    })
                        except (ValueError, IndexError):
                            continue
                            
        except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
            logger.warning(f"[AppKiller] wmic进程扫描失败: {e}")
    
    return _deduplicate_and_sort_apps(apps)


def _matches_process_name(filter_name: str, proc_name: str, window_title: str = "", exe_path: str = "") -> bool:
    """
    智能匹配进程名称.
    
    Args:
        filter_name: 要匹配的应用名称
        proc_name: 进程名称
        window_title: 窗口标题
        exe_path: 可执行文件路径
    
    Returns:
        bool: 是否匹配
    """
    try:
        from .app_utils import AppMatcher

        # 构造应用信息对象
        app_info = {
            'name': proc_name,
            'display_name': proc_name,
            'window_title': window_title,
            'command': exe_path
        }
        
        # 使用统一匹配器，匹配度大于30即认为匹配
        score = AppMatcher.match_application(filter_name, app_info)
        return score >= 30
        
    except ImportError:
        # 兜底简化实现
        filter_lower = filter_name.lower()
        proc_lower = proc_name.lower()
        
        return (filter_lower == proc_lower or 
                filter_lower in proc_lower or
                (window_title and filter_lower in window_title.lower()))


def _is_system_process(proc_name: str) -> bool:
    """
    判断是否为系统进程.
    """
    system_processes = {
        'dwm', 'winlogon', 'csrss', 'smss', 'wininit', 'services', 
        'lsass', 'svchost', 'spoolsv', 'explorer', 'taskhostw', 
        'fontdrvhost', 'dllhost', 'ctfmon', 'audiodg', 'conhost',
        'sihost', 'shellexperiencehost', 'startmenuexperiencehost',
        'runtimebroker', 'applicationframehost', 'searchui',
        'cortana', 'useroobebroker', 'lockapp'
    }
    
    return proc_name.lower() in system_processes


def _deduplicate_and_sort_apps(apps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    去重并排序应用程序列表.
    """
    # 按PID去重
    seen_pids = set()
    unique_apps = []
    for app in apps:
        if app["pid"] not in seen_pids:
            seen_pids.add(app["pid"])
            unique_apps.append(app)
    
    # 按名称排序
    unique_apps.sort(key=lambda x: x["name"].lower())
    
    logger.info(f"[AppKiller] 进程扫描完成，去重后找到 {len(unique_apps)} 个应用程序")
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


def _kill_windows_app_group(apps: List[Dict[str, Any]], app_name: str, force: bool) -> bool:
    """
    按分组关闭Windows应用程序.
    
    Args:
        apps: 匹配的应用程序进程列表
        app_name: 应用程序名称
        force: 是否强制关闭
    
    Returns:
        bool: 关闭是否成功
    """
    try:
        logger.info(f"[AppKiller] 开始分组关闭Windows应用: {app_name}, 找到 {len(apps)} 个相关进程")
        
        # 1. 首先尝试按应用名称整体关闭（推荐方法）
        success = _kill_by_image_name(apps, force)
        if success:
            logger.info(f"[AppKiller] 成功通过应用名称整体关闭: {app_name}")
            return True
        
        # 2. 如果整体关闭失败，尝试智能分组关闭
        success = _kill_by_process_groups(apps, force)
        if success:
            logger.info(f"[AppKiller] 成功通过进程分组关闭: {app_name}")
            return True
        
        # 3. 最后尝试逐个关闭（兜底方案）
        success = _kill_individual_processes(apps, force)
        logger.info(f"[AppKiller] 通过逐个关闭完成: {app_name}, 成功: {success}")
        return success
        
    except Exception as e:
        logger.error(f"[AppKiller] Windows分组关闭失败: {e}")
        return False


def _kill_by_image_name(apps: List[Dict[str, Any]], force: bool) -> bool:
    """
    通过镜像名称整体关闭应用程序.
    """
    try:
        # 获取主要的进程名称
        image_names = set()
        for app in apps:
            name = app.get("name", "")
            if name:
                # 统一添加.exe后缀
                if not name.lower().endswith('.exe'):
                    name += '.exe'
                image_names.add(name)
        
        if not image_names:
            return False
        
        logger.info(f"[AppKiller] 尝试通过镜像名称关闭: {list(image_names)}")
        
        # 按镜像名称关闭
        success_count = 0
        for image_name in image_names:
            try:
                if force:
                    cmd = ["taskkill", "/IM", image_name, "/F", "/T"]  # /T关闭子进程树
                else:
                    cmd = ["taskkill", "/IM", image_name, "/T"]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    success_count += 1
                    logger.info(f"[AppKiller] 成功关闭镜像: {image_name}")
                else:
                    logger.debug(f"[AppKiller] 关闭镜像失败: {image_name}, 错误: {result.stderr}")
                    
            except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
                logger.debug(f"[AppKiller] 关闭镜像异常: {image_name}, 错误: {e}")
        
        return success_count > 0
        
    except Exception as e:
        logger.debug(f"[AppKiller] 镜像名称关闭异常: {e}")
        return False


def _kill_by_process_groups(apps: List[Dict[str, Any]], force: bool) -> bool:
    """
    按进程组智能关闭应用程序.
    """
    try:
        # 按进程名称分组
        process_groups = {}
        for app in apps:
            name = app.get("name", "")
            if name:
                base_name = _get_base_process_name(name)
                if base_name not in process_groups:
                    process_groups[base_name] = []
                process_groups[base_name].append(app)
        
        logger.info(f"[AppKiller] 识别出 {len(process_groups)} 个进程组: {list(process_groups.keys())}")
        
        # 为每个组识别主进程并关闭
        success_count = 0
        for group_name, group_apps in process_groups.items():
            try:
                # 找到主进程（通常是PPID最小的或者有窗口标题的）
                main_process = _find_main_process(group_apps)
                
                if main_process:
                    # 关闭主进程（会带动子进程）
                    pid = main_process.get("pid")
                    if pid:
                        success = _kill_windows_app(pid, force)
                        if success:
                            success_count += 1
                            logger.info(f"[AppKiller] 成功关闭进程组 {group_name} 的主进程 (PID: {pid})")
                        else:
                            # 如果主进程关闭失败，尝试关闭组内所有进程
                            for app in group_apps:
                                if _kill_windows_app(app.get("pid"), force):
                                    success_count += 1
                
            except Exception as e:
                logger.debug(f"[AppKiller] 关闭进程组失败: {group_name}, 错误: {e}")
        
        return success_count > 0
        
    except Exception as e:
        logger.debug(f"[AppKiller] 进程组关闭异常: {e}")
        return False


def _kill_individual_processes(apps: List[Dict[str, Any]], force: bool) -> bool:
    """
    逐个关闭进程（兜底方案）.
    """
    try:
        logger.info(f"[AppKiller] 开始逐个关闭 {len(apps)} 个进程")
        
        success_count = 0
        for app in apps:
            pid = app.get("pid")
            if pid:
                success = _kill_windows_app(pid, force)
                if success:
                    success_count += 1
                    logger.debug(f"[AppKiller] 成功关闭进程: {app.get('name')} (PID: {pid})")
        
        logger.info(f"[AppKiller] 逐个关闭完成，成功关闭 {success_count}/{len(apps)} 个进程")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"[AppKiller] 逐个关闭异常: {e}")
        return False


def _get_base_process_name(process_name: str) -> str:
    """
    获取基础进程名称（用于分组）.
    """
    try:
        from .app_utils import AppMatcher
        return AppMatcher.get_process_group(process_name)
    except ImportError:
        # 兜底实现
        name = process_name.lower().replace('.exe', '')
        if 'chrome' in name:
            return 'chrome'
        elif 'qq' in name and 'music' not in name:
            return 'qq'
        return name


def _find_main_process(processes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    在进程组中找到主进程.
    
    Args:
        processes: 进程列表
    
    Returns:
        主进程信息，如果找不到则返回第一个进程
    """
    if not processes:
        return {}
    
    # 策略1: 有窗口标题的进程通常是主进程
    for proc in processes:
        window_title = proc.get("window_title", "")
        if window_title and window_title.strip():
            return proc
    
    # 策略2: PPID最小的进程（通常是父进程）
    try:
        main_proc = min(processes, key=lambda p: p.get("ppid", p.get("pid", 999999)))
        return main_proc
    except (ValueError, TypeError):
        pass
    
    # 策略3: PID最小的进程
    try:
        main_proc = min(processes, key=lambda p: p.get("pid", 999999))
        return main_proc
    except (ValueError, TypeError):
        pass
    
    # 兜底：返回第一个进程
    return processes[0] 