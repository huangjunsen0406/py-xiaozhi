# MCP 工具开发指南

## 什么是 MCP？

MCP（Model Context Protocol）是让 AI 调用外部工具的协议。基于 JSON-RPC 2.0。

## 快速开始：创建一个 MCP 工具

以天气工具为例，使用 `@mcp_tool` 装饰器快速注册工具：

### 工具实现 (`weather_tools.py`)

```python
import json
from typing import Any, Dict

from src.mcp.decorators import Prop, PropType, mcp_tool

@mcp_tool(
    name="get_weather",
    description="获取指定城市的当前天气。参数: city - 城市名称",
    props=[
        Prop("city", PropType.STR, default="北京"),
    ],
)
def get_weather(args: Dict[str, Any]) -> str:
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

> [!TIP]
> 使用装饰器后，工具会自动注册到 MCP 服务器，无需手动在 `mcp_server.py` 中添加代码。

## 核心概念

### PropType（参数类型）

| 类型 | 说明 |
|------|------|
| `STR` | 字符串 |
| `INT` | 整数，可设置 min_val/max_val |
| `BOOL` | 布尔值 |

### Prop（参数定义）

```python
Prop("city", PropType.STR)                                    # 必需参数
Prop("city", PropType.STR, default="北京")                     # 可选参数，带默认值
Prop("days", PropType.INT, default=3, min_val=1, max_val=7)   # 整数参数，带范围限制
```

### @mcp_tool 装饰器

```python
@mcp_tool(
    name="工具名称",                    # AI 调用时使用的名称
    description="工具描述",              # AI 根据这个决定何时调用
    props=[                             # 参数列表
        Prop("param1", PropType.STR),
        Prop("param2", PropType.INT, default=10),
    ],
)
def my_tool(args: Dict[str, Any]) -> str:
    # 工具实现
    return json.dumps(result)
```

## 返回值格式

工具函数返回 JSON 字符串，会被包装成：

```json
{
  "content": [{"type": "text", "text": "你的返回值"}],
  "isError": false
}
```

## 完整示例

```python
from src.mcp.decorators import Prop, PropType, mcp_tool

@mcp_tool(
    name="get_forecast",
    description="获取指定城市的天气预报。参数: city - 城市名称, days - 预报天数(1-7天)",
    props=[
        Prop("city", PropType.STR, default="北京"),
        Prop("days", PropType.INT, default=3, min_val=1, max_val=7),
    ],
)
def get_forecast(args: Dict[str, Any]) -> str:
    city = args.get("city", "北京")
    days = args.get("days", 3)

    forecast = [
        {"date": "今天", "high": 28, "low": 18, "condition": "晴"},
        {"date": "明天", "high": 26, "low": 17, "condition": "多云"},
        {"date": "后天", "high": 24, "low": 15, "condition": "小雨"},
    ]

    return json.dumps({"city": city, "forecast": forecast[:days]}, ensure_ascii=False)
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

## 现有工具参考

| 工具 | 文件 | 说明 |
|------|------|------|
| 截图 | [screenshot/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/screenshot) | 简洁示例 |
| 天气 | [weather/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/weather) | 装饰器示例 |
| 音乐 | [music/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/music) | 带管理器 |
| 系统 | [system/](file:///Users/junsen/Desktop/workspace/py-xiaozhi/src/mcp/tools/system) | 多工具示例 |
