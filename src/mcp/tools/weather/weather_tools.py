"""
天气工具 MCP 示例

一个简洁的 MCP Tools 实现示例，展示如何创建工具供 AI 调用。
"""

import json
from typing import Any, Dict

from src.logging import get_logger

logger = get_logger()


async def get_weather(args: Dict[str, Any]) -> str:
    """获取当前天气。

    Args:
        args: {"city": "城市名称"}

    Returns:
        JSON 格式的天气数据
    """
    city = args.get("city", "北京")
    logger.info(f"[WeatherTool] 获取 {city} 的当前天气")

    # TODO: 实际项目中应调用天气API
    weather_data = {
        "city": city,
        "temperature": 25,
        "condition": "晴朗",
        "humidity": 45,
        "wind": "东北风 3级",
        "aqi": 52,
    }

    return json.dumps(weather_data, ensure_ascii=False)


async def get_forecast(args: Dict[str, Any]) -> str:
    """获取天气预报。

    Args:
        args: {"city": "城市名称", "days": 天数(1-7)}

    Returns:
        JSON 格式的天气预报
    """
    city = args.get("city", "北京")
    days = args.get("days", 3)
    logger.info(f"[WeatherTool] 获取 {city} 的 {days} 天天气预报")

    forecast = [
        {"date": "今天", "high": 28, "low": 18, "condition": "晴"},
        {"date": "明天", "high": 26, "low": 17, "condition": "多云"},
        {"date": "后天", "high": 24, "low": 15, "condition": "小雨"},
    ]

    return json.dumps({"city": city, "forecast": forecast[:days]}, ensure_ascii=False)
