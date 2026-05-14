"""
天气工具 MCP 示例

使用 @mcp_tool 装饰器注册工具，自动发现并加载。
"""

# 导入以触发装饰器注册
from .weather_tools import get_forecast, get_weather

__all__ = ["get_weather", "get_forecast"]
