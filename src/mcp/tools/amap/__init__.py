"""
高德地图 MCP 工具模块.
"""

from .client import AmapClient
from .manager import AmapManager
from .models import *
from .tools import AmapTools

# 硬编码的API Key (临时解决方案)
AMAP_API_KEY = "ce2a3951c9f3b82dea64ce37eeac4bdd"

# 全局管理器实例
_amap_manager = None


def get_amap_manager():
    """
    获取高德地图管理器实例.
    """
    global _amap_manager
    if _amap_manager is None:
        _amap_manager = AmapToolsManager()
    return _amap_manager


class AmapToolsManager:
    """高德地图工具管理器 - 适配MCP服务器"""

    def __init__(self):
        self.amap_tools = AmapTools(AMAP_API_KEY)

    def init_tools(self, add_tool_func, PropertyList, Property, PropertyType):
        """
        初始化高德地图工具.
        """
        # 获取所有工具定义
        tools = self.amap_tools.get_tools()

        for tool_def in tools:
            # 创建属性列表
            properties = PropertyList()

            # 转换工具定义为MCP格式
            input_schema = tool_def.get("inputSchema", {})
            schema_props = input_schema.get("properties", {})
            required_props = input_schema.get("required", [])

            for prop_name, prop_def in schema_props.items():
                prop_type = prop_def.get("type", "string")

                # 转换类型
                if prop_type == "string":
                    mcp_type = PropertyType.STRING
                elif prop_type == "integer":
                    mcp_type = PropertyType.INTEGER
                elif prop_type == "boolean":
                    mcp_type = PropertyType.BOOLEAN
                else:
                    mcp_type = PropertyType.STRING

                # 创建属性
                prop = Property(
                    name=prop_name,
                    type=mcp_type,
                    default_value=None if prop_name in required_props else "",
                )
                properties.add_property(prop)

            # 创建工具回调函数
            def make_tool_callback(tool_name):
                async def tool_callback(arguments):
                    try:
                        result = await self.amap_tools.execute_tool(
                            tool_name, arguments
                        )
                        if result.get("success", False):
                            return str(result.get("data", ""))
                        else:
                            return f"Error: {result.get('error', 'Unknown error')}"
                    except Exception as e:
                        return f"Error: {str(e)}"

                return tool_callback

            # 添加工具
            add_tool_func(
                (
                    tool_def["name"],
                    tool_def["description"],
                    properties,
                    make_tool_callback(tool_def["name"]),
                )
            )


__all__ = [
    "AmapTools",
    "AmapManager",
    "AmapClient",
    "AmapToolsManager",
    "get_amap_manager",
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
