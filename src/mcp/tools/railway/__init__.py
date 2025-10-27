"""12306铁路购票查询工具模块.

提供火车票查询、车次查询、经停站查询等功能.
"""

from .manager import RailwayToolsManager, get_railway_manager

# 全局工具管理器实例
_railway_tools_manager = None


def get_railway_tools_manager() -> RailwayToolsManager:
    """
    获取Railway工具管理器实例 - 新版本智能工具接口.
    """
    global _railway_tools_manager
    if _railway_tools_manager is None:
        _railway_tools_manager = RailwayToolsManager()
    return _railway_tools_manager


__all__ = [
    "get_railway_manager",  # 兼容性接口
    "get_railway_tools_manager",  # 新版本智能工具接口
    "RailwayToolsManager",
]
