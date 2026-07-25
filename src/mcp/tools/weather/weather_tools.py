"""天气 MCP 工具：显式 register；数据仍为占位 mock，待接真 API."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()


def _get_weather(args: dict[str, Any]) -> str:
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


def _get_forecast(args: dict[str, Any]) -> str:
    city = args.get("city", "北京")
    days = args.get("days", 3)
    logger.info(f"[WeatherTool] 获取 {city} 的 {days} 天天气预报")
    forecast = [
        {"date": "今天", "high": 28, "low": 18, "condition": "晴"},
        {"date": "明天", "high": 26, "low": 17, "condition": "多云"},
        {"date": "后天", "high": 24, "low": 15, "condition": "小雨"},
    ]
    return json.dumps({"city": city, "forecast": forecast[:days]}, ensure_ascii=False)


def register_weather_tools(add_tool: Callable[[McpTool], None]) -> None:
    """向 McpServer 注册天气工具（当前为 mock 数据）."""

    tools: list[McpTool] = [
        McpTool(
            "get_weather",
            (
                "获取指定城市的当前天气。"
                "参数: city - 城市名称（如：北京、上海、广州）"
            ),
            PropertyList(
                [Property("city", PropertyType.STRING, default_value="北京")]
            ),
            _get_weather,
        ),
        McpTool(
            "get_forecast",
            (
                "获取指定城市的天气预报。"
                "参数: city - 城市名称, days - 预报天数(1-7天)"
            ),
            PropertyList(
                [
                    Property("city", PropertyType.STRING, default_value="北京"),
                    Property(
                        "days",
                        PropertyType.INTEGER,
                        default_value=3,
                        min_value=1,
                        max_value=7,
                    ),
                ]
            ),
            _get_forecast,
        ),
    ]

    for tool in tools:
        add_tool(tool)
    logger.info("已注册 %d 个天气 MCP 工具（register_weather_tools, mock）", len(tools))
