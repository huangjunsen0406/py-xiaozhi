# MCP 工具开发指南

## 什么是 MCP？

MCP（Model Context Protocol）是让 AI 调用外部工具的协议。基于 JSON-RPC 2.0。

## 快速开始：创建一个 MCP 工具

以天气工具为例，只需 2 个文件：

### 1. 工具实现 (`weather_tools.py`)

```python
import json
from typing import Any, Dict

async def get_weather(args: Dict[str, Any]) -> str:
    """获取当前天气"""
    city = args.get("city", "北京")

    # TODO: 调用真实天气API
    weather_data = {
        "city": city,
        "temperature": 25,
        "condition": "晴朗",
    }

    return json.dumps(weather_data, ensure_ascii=False)
```

### 2. 在 `mcp_server.py` 注册

```python
from src.mcp.tools.weather import get_weather

# 定义参数
weather_props = PropertyList([Property("city", PropertyType.STRING)])

# 注册工具
self.add_tool(
    McpTool(
        "get_weather",                          # 工具名
        "获取天气。参数: city-城市名称",           # 描述（AI根据这个决定何时调用）
        weather_props,                          # 参数定义
        get_weather,                            # 回调函数
    )
)
```

## 核心概念

### PropertyType（参数类型）

| 类型 | 说明 |
|------|------|
| `STRING` | 字符串 |
| `INTEGER` | 整数，可设置 min/max |
| `BOOLEAN` | 布尔值 |

### Property（参数定义）

```python
Property("city", PropertyType.STRING)  # 必需参数
Property("days", PropertyType.INTEGER, default_value=3, min_value=1, max_value=7)  # 可选参数
```

### McpTool（工具定义）

```python
McpTool(
    name="工具名",
    description="工具描述，AI根据这个决定何时调用",
    properties=PropertyList([...]),
    callback=async_function,  # 支持同步/异步函数
)
```

## 返回值格式

工具函数返回 JSON 字符串，会被包装成：

```json
{
  "content": [{"type": "text", "text": "你的返回值"}],
  "isError": false
}
```

## 实际运行日志

### 工具调用: get_weather

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 7,
  "params": {
    "name": "get_weather",
    "arguments": {"city": "广州市"}
  }
}
```

```
[MCP] 收到工具调用请求! ID=7, 参数={'name': 'get_weather', 'arguments': {'city': '广州市'}}
[MCP] 尝试调用工具: get_weather
[MCP] 开始执行工具 get_weather, 参数: {'city': '广州市'}
[WeatherTool] 获取 广州市 的当前天气
[MCP] 工具 get_weather 执行成功，结果: {"city": "广州市", "temperature": 25, "condition": "晴朗", "humidity": 45, "wind": "东北风 3级", "aqi": 52}
[MCP] 发送成功响应: ID=7, 结果长度=222
```

### 工具调用: get_forecast

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "id": 8,
  "params": {
    "name": "get_forecast",
    "arguments": {"city": "广州市", "days": 2}
  }
}
```

```
[MCP] 收到工具调用请求! ID=8, 参数={'name': 'get_forecast', 'arguments': {'city': '广州市', 'days': 2}}
[MCP] 尝试调用工具: get_forecast
[MCP] 开始执行工具 get_forecast, 参数: {'city': '广州市', 'days': 2}
[WeatherTool] 获取 广州市 的 2 天天气预报
[MCP] 工具 get_forecast 执行成功，结果: {"city": "广州市", "forecast": [{"date": "今天", "high": 28, "low": 18, "condition": "晴"}, {"date": "明天", "high": 26, "low": 17, "condition": "多云"}]}
[MCP] 发送成功响应: ID=8, 结果长度=285
```

## 现有工具参考

| 工具 | 文件 | 说明 |
|------|------|------|
| 截图 | [screenshot/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/screenshot) | 简洁示例 |
| 天气 | [weather/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/weather) | 简洁示例 |
| 音乐 | [music/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/music) | 带管理器 |
| 日程 | [calendar/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/calendar) | 带数据库 |
