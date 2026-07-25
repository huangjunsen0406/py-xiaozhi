"""天气数据（当前 mock；待接真 API）."""

from __future__ import annotations

import json
from typing import Any

from src.logging import get_logger

logger = get_logger()


def get_weather_payload(args: dict[str, Any]) -> str:
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


def get_forecast_payload(args: dict[str, Any]) -> str:
    city = args.get("city", "北京")
    days = args.get("days", 3)
    logger.info(f"[WeatherTool] 获取 {city} 的 {days} 天天气预报")
    forecast = [
        {"date": "今天", "high": 28, "low": 18, "condition": "晴"},
        {"date": "明天", "high": 26, "low": 17, "condition": "多云"},
        {"date": "后天", "high": 24, "low": 15, "condition": "小雨"},
    ]
    return json.dumps({"city": city, "forecast": forecast[:days]}, ensure_ascii=False)
