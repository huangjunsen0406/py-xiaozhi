"""应用程序管理模块.

提供跨平台的应用程序扫描、启动和关闭功能。
"""

from .killer import kill_application, list_running_applications
from .process_manager import kill_application_by_name
from .process_manager import list_running_applications as list_running_apps_sync
from .scanner import scan_installed_applications
from .utils import AppMatcher, find_best_matching_app, get_cached_applications

__all__ = [
    "AppMatcher",
    "find_best_matching_app",
    "get_cached_applications",
    "kill_application",
    "kill_application_by_name",
    "list_running_applications",
    "list_running_apps_sync",
    "scan_installed_applications",
]
