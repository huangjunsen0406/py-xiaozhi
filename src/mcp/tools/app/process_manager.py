"""跨平台进程管理（基于 psutil）.

用 psutil 替代所有平台特定的 subprocess 进程列表和终止逻辑，
消除命令注入风险。
"""

import sys

import psutil

from src.logging import get_logger

from .utils import AppMatcher

logger = get_logger()

# Electron/Chromium 子进程后缀，这些是主应用的内部子进程
_HELPER_SUFFIXES = (
    " helper",
    " helper (gpu)",
    " helper (renderer)",
    " helper (plugin)",
    "_crashpad_handler",
)

# macOS 系统路径前缀，这些路径下的进程都是系统守护进程
_MACOS_SYSTEM_PREFIXES = (
    "/usr/libexec/",
    "/usr/sbin/",
    "/System/Library/",
    "/Library/Apple/",
)

# Windows 系统进程名（小写，不含 .exe）
_WINDOWS_SYSTEM_NAMES: set[str] = {
    "dwm",
    "winlogon",
    "csrss",
    "smss",
    "wininit",
    "services",
    "lsass",
    "svchost",
    "spoolsv",
    "taskhostw",
    "fontdrvhost",
    "dllhost",
    "ctfmon",
    "audiodg",
    "conhost",
    "sihost",
    "shellexperiencehost",
    "startmenuexperiencehost",
    "runtimebroker",
    "applicationframehost",
    "searchui",
    "lockapp",
    "explorer",
}


def _is_user_application(name: str, exe: str) -> bool:
    """判断进程是否为用户可见的应用程序."""
    name_lower = name.lower()
    exe_lower = exe.lower()

    # Electron/Chromium 子进程（Helper、Renderer、GPU）排除
    if any(name_lower.endswith(suffix) for suffix in _HELPER_SUFFIXES):
        return False

    if sys.platform == "darwin":
        # macOS: 只保留 /Applications/ 下的 .app 主进程
        if "/Applications/" in exe and ".app/" in exe:
            # 排除 .app 内部的子 .app（如 Framework/Helpers/）
            app_path = exe[: exe.index(".app/") + 5]
            remaining = exe[len(app_path) :]
            if ".app/" in remaining:
                return False
            return True
        # 非 /Applications 但也不是系统路径的（如 ~/Library/Application Support 下的工具）
        if any(exe_lower.startswith(p) for p in _MACOS_SYSTEM_PREFIXES):
            return False
        # /Library/Application Support 下的用户工具（如安全软件、VPN）
        if "/Library/Application Support/" in exe and ".app" not in exe:
            return False
        # 其他已知系统进程路径
        if exe_lower.startswith("/system/") or exe_lower.startswith("/library/"):
            return False
        return False

    elif sys.platform == "win32":
        if name_lower.replace(".exe", "") in _WINDOWS_SYSTEM_NAMES:
            return False
        # Windows 系统目录进程排除
        if "\\windows\\system32\\" in exe_lower:
            return False
        if "\\windows\\syswow64\\" in exe_lower:
            return False
        return True

    else:
        # Linux: 排除系统守护进程
        if exe_lower.startswith(("/usr/libexec/", "/usr/sbin/")):
            return False
        if exe_lower.startswith("/usr/bin/") and name_lower in {
            "dbus-daemon",
            "dbus-broker",
            "at-spi-bus-launcher",
            "pulseaudio",
            "pipewire",
            "systemd",
        }:
            return False
        return True


def list_running_applications(filter_name: str = "") -> list[dict]:
    """列出运行中的用户应用程序.

    只返回用户可见的桌面应用，不包含系统守护进程、Electron 子进程等。

    Args:
        filter_name: 可选的名称过滤关键词，传入时放宽过滤（用于 kill 匹配）
    """
    apps: list[dict] = []
    filter_lower = filter_name.lower() if filter_name else ""

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "status"]):
        try:
            info = proc.info
            name = info.get("name") or ""
            exe = info.get("exe") or ""
            pid = info.get("pid", 0)
            if not name or pid <= 4:
                continue

            # 有过滤词时放宽条件（用于 kill 匹配场景，需要匹配子进程）
            if filter_lower:
                name_lower = name.lower()
                exe_lower = exe.lower()
                cmd = " ".join(info.get("cmdline") or [])
                cmd_lower = cmd.lower()
                if (
                    filter_lower not in name_lower
                    and filter_lower not in exe_lower
                    and filter_lower not in cmd_lower
                ):
                    continue
                apps.append(
                    {
                        "pid": pid,
                        "name": name,
                        "display_name": name,
                        "exe": exe,
                        "command": cmd,
                        "type": "application",
                    }
                )
            else:
                # 无过滤词：严格只返回用户应用
                if not _is_user_application(name, exe):
                    continue
                apps.append(
                    {
                        "pid": pid,
                        "name": name,
                        "display_name": name,
                        "exe": exe,
                        "command": " ".join(info.get("cmdline") or []),
                        "type": "application",
                    }
                )

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    # 按名称排序去重
    seen_pids: set[int] = set()
    unique_apps: list[dict] = []
    for app in sorted(apps, key=lambda x: x["name"].lower()):
        if app["pid"] not in seen_pids:
            seen_pids.add(app["pid"])
            unique_apps.append(app)

    return unique_apps


def kill_process(pid: int, force: bool = False) -> bool:
    """终止指定 PID 的进程.

    Args:
        pid: 进程 ID
        force: True 使用 SIGKILL/TerminateProcess，False 使用 SIGTERM

    Returns:
        是否成功终止
    """
    try:
        proc = psutil.Process(pid)
        if force:
            proc.kill()
        else:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                logger.warning(f"[ProcessManager] 进程 {pid} 未在超时内退出，强制终止")
                proc.kill()
        return True
    except psutil.NoSuchProcess:
        logger.warning(f"[ProcessManager] 进程不存在: {pid}")
        return False
    except psutil.AccessDenied as e:
        logger.warning(f"[ProcessManager] 无权终止进程 {pid}: {e}")
        return False


def find_matching_processes(app_name: str) -> list[dict]:
    """查找与应用名匹配的运行中进程.

    使用 AppMatcher 进行智能匹配（包含特殊映射、模糊匹配等）。

    Args:
        app_name: 目标应用名称

    Returns:
        匹配的进程信息列表，按匹配度降序排列
    """
    all_apps = list_running_applications()
    matched: list[tuple[int, dict]] = []

    for app in all_apps:
        score = AppMatcher.match_application(app_name, app)
        if score >= 50:
            matched.append((score, app))

    matched.sort(key=lambda x: x[0], reverse=True)
    return [app for _, app in matched]


def kill_application_by_name(app_name: str, force: bool = False) -> bool:
    """按名称终止应用（匹配所有相关进程）.

    Args:
        app_name: 应用名称
        force: 是否强制终止

    Returns:
        是否至少终止了一个进程
    """
    matched = find_matching_processes(app_name)
    if not matched:
        logger.info(f"[ProcessManager] 未找到匹配的运行进程: {app_name}")
        return False

    logger.info(f"[ProcessManager] 找到 {len(matched)} 个匹配进程: {app_name}")

    # 按进程组分组，尝试先终止子进程再终止父进程
    success_count = 0
    for app in matched:
        pid = app["pid"]
        try:
            proc = psutil.Process(pid)
            # 先终止子进程
            children = proc.children(recursive=True)
            for child in children:
                try:
                    if force:
                        child.kill()
                    else:
                        child.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 终止主进程
            if kill_process(pid, force):
                success_count += 1
                logger.info(f"[ProcessManager] 已终止进程: {app['name']} (PID={pid})")
        except psutil.NoSuchProcess:
            logger.debug(f"[ProcessManager] 进程已退出: PID={pid}")
        except psutil.AccessDenied as e:
            logger.warning(f"[ProcessManager] 无权操作进程 PID={pid}: {e}")

    logger.info(
        f"[ProcessManager] 终止操作完成，成功 {success_count}/{len(matched)} 个进程"
    )
    return success_count > 0
