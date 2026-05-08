# MCP 工具模式

> 新增 MCP 工具的标准做法。当前模式: `@mcp_tool` 装饰器 + 自动发现。这是项目"下一个 feature"的标准形态 —— `src/mcp/tools/weather/` 下的天气工具是参考实现,旁边的 `MCP_DEVELOPMENT_GUIDE.md` 是面向开发者的速查文档。

---

## 工具放在哪里

```
src/mcp/tools/<your_tool>/
├── __init__.py            # import 工具模块以触发 @mcp_tool 装饰器
└── <your_tool>_tools.py   # 一个或多个 @mcp_tool 函数
```

可选的同级文件(`bazi`、`music`、`system`、`weather` 用过):

- `_tools.py` —— 单独的工具注册模块,把工具函数与 manager 逻辑解耦。自动发现会 **显式** 拉取这个名字(见 `src/mcp/decorators.py` 的 `discover_tool_modules()`)。
- 业务模块(如 `weather_tools.py`、`music_player.py`)—— 纯逻辑,可独立 import。

`src/mcp/decorators.py` 中的发现循环:

1. import 直接放在 `src/mcp/tools/` 下的每个 `*.py`(跳过 `_*`)。
2. import `src/mcp/tools/` 下每个子包(跳过 `_*`)。
3. 子包内若有 `_tools.py`,**额外** import 一遍。

两个推论:

- 工具定义在 `src/mcp/tools/foo/foo_tools.py` 时,只有 `src/mcp/tools/foo/__init__.py` 显式 import 它,装饰器才会触发(发现步骤只 import 子包,不会展开内部文件,除非文件名叫 `_tools.py`)。
- `_` 开头的文件名会被包级扫描跳过,**只有** 子包内的 `_tools.py` 是显式拉取的例外。

---

## 最小可用工具

```python
# src/mcp/tools/<name>/<name>_tools.py
"""<Name> 工具 MCP 实现."""

import json
from typing import Any, Dict

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool

logger = get_logger()


@mcp_tool(
    name="<name>_action",                              # 全局唯一
    description="一句话描述工具用途及参数。AI 用它判断何时调用。",
    props=[
        Prop("city", PropType.STR, default="北京"),
        Prop("days", PropType.INT, default=3, min_val=1, max_val=7),
    ],
)
def name_action(args: Dict[str, Any]) -> str:
    city = args.get("city", "北京")
    days = args.get("days", 3)
    logger.info(f"[NameTool] 调用 city={city} days={days}")
    result = {...}
    return json.dumps(result, ensure_ascii=False)
```

```python
# src/mcp/tools/<name>/__init__.py
"""<Name> 工具 MCP 入口."""

# 触发 @mcp_tool 注册
from .name_tools import name_action

__all__ = ["name_action"]
```

注册到此结束。`McpPlugin.setup()`(`src/plugins/mcp.py`)调用 `McpServer.add_common_tools()`,后者迭代 `iter_registered_mcp_tools()`,新工具自动暴露。

---

## 锚定在现有代码的规则

- **工具函数签名固定为 `def fn(args: Dict[str, Any]) -> str`**,返回 JSON 字符串(`json.dumps(..., ensure_ascii=False)` 构造)。**不要** 返回 dict —— MCP 服务器要求字符串作为文本内容块。
- **属性类型** 仅 `PropType.STR`、`PropType.INT`、`PropType.BOOL`(见 `src/mcp/decorators.py`)。其他类型用字符串编解码,在函数内自行校验。
- **`Prop` 默认值** 让参数变可选。不带 `default=...` 即为必需。
- **`min_val` / `max_val`** 仅对 `PropType.INT` 有效。
- **工具名唯一性**: 同名重复注册会打 warning 并覆盖。用域前缀(`get_weather`、`get_forecast`)避免误覆。
- **日志** 加 `[ToolName]` 前缀,与 `[WeatherTool]` 风格保持一致,便于 grep。
- **不要** 在工具模块里 import MCP 服务器内部。工具只依赖 `src.mcp.decorators` 与 stdlib;服务器侧消费它们。

---

## 不要做

- **不要** 在功能代码里手动调 `McpServer.add_tool(...)`。装饰器 + 自动发现是 **唯一** 注册路径。早期手工实例化 `McpTool` 的写法已经过时。
- **async 工具函数**：需要 I/O 操作（网络请求、文件读写、硬件访问）时使用 `async def` + `asyncio.to_thread()` 将阻塞操作卸载到线程池，避免阻塞事件循环。参考 `src/mcp/tools/camera/__init__.py` 和 `src/mcp/tools/screenshot/__init__.py`。
- **外部 API 客户端必须设超时**：`requests.post(timeout=N)`、`OpenAI(timeout=httpx.Timeout(...))`。无超时的阻塞调用会在线程池中永久挂起，耗尽线程池资源。
- **不要** 返回 Python 富对象、dataclass、pydantic model —— 返回 JSON 字符串。
- **不要** 用 `_` 开头的文件名(除非按 `_tools.py` 约定)。会被自动发现静默跳过。

---

## 参考文件

- `src/mcp/decorators.py` —— 注册表、`@mcp_tool`、`Prop`、`PropType`、`discover_tool_modules`、`iter_registered_mcp_tools`。
- `src/mcp/tools/weather/weather_tools.py` —— 最小参考实现。
- `src/mcp/tools/weather/MCP_DEVELOPMENT_GUIDE.md` —— 团队开发者速查文档,关于返回格式有更多示例。
- `src/plugins/mcp.py` —— 插件层把已注册工具接到运行中的 server 的方式。
