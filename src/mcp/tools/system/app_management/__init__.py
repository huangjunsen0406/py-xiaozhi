"""应用程序管理模块.

提供跨平台的应用程序扫描、启动和关闭功能
"""

from .scanner import list_running_applications, scan_installed_applications
from .utils import AppMatcher, find_best_matching_app, get_cached_applications

__all__ = [
    "scan_installed_applications",
    "list_running_applications",
    "AppMatcher",
    "find_best_matching_app",
    "get_cached_applications",
]
