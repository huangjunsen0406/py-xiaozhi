"""
高德地图 MCP 工具模块.
"""

from .client import AmapClient
from .manager import AmapManager, AmapToolsManager, get_amap_tools_manager
from .models import *
from .tools import AmapTools

# 硬编码的API Key (临时解决方案)
AMAP_API_KEY = "your_api_key_here"

# 全局管理器实例
_amap_manager = None


def get_amap_manager():
    """
    获取高德地图管理器实例 (兼容性保持).
    """
    return get_amap_tools_manager()


__all__ = [
    "AmapTools",
    "AmapManager",
    "AmapClient",
    "AmapToolsManager",
    "get_amap_manager",
    "get_amap_tools_manager",
    "Location",
    "AddressComponent",
    "GeocodeResult",
    "POI",
    "RouteStep",
    "RoutePath",
    "RouteResult",
    "WeatherInfo",
    "WeatherForecast",
    "DistanceResult",
    "IPLocationResult",
    "BusLine",
    "TransitSegment",
    "TransitRoute",
    "TransitResult",
    "SearchSuggestion",
    "SearchResult",
]
