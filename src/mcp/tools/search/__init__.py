"""
搜索工具模块 - 提供必应搜索和网页内容获取功能
"""

from .manager import cleanup_search_manager, get_search_manager

__all__ = ["get_search_manager", "cleanup_search_manager"]
