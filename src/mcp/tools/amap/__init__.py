"""高德地图MCP工具模块.

提供高德地图API功能的MCP工具集，包括地理编码、路径规划、POI搜索、天气查询等
"""

from .manager import get_amap_manager

__all__ = ["get_amap_manager"]
