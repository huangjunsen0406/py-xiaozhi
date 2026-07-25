"""天气工具 MCP.

- register_weather_tools: 显式注册（当前 mock，待接真 API）
"""

from .weather_tools import register_weather_tools

__all__ = ["register_weather_tools"]
