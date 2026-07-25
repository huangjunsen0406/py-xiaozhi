# MCP 工具开发指南

本文档说明如何为 py-xiaozhi 开发**内置** MCP 工具。外部 MCP 服务接入请参考 [外挂 MCP 接入指南](xiaozhi-mcp.md)。

## 工作原理

1. `McpPlugin.setup` 创建摄像头等运行时对象，并调用 `register_camera_tools` / `register_screenshot_tools`
2. `McpServer.add_common_tools()` **显式**调用各包的 `register_*_tools(add_tool, …)`
3. 每个 `register_*` 用闭包持有依赖（如 `MusicPlayer`、`VolumeController`），构造 `McpTool` 并 `add_tool`
4. 工具通过 JSON-RPC 2.0 对外暴露

**内置工具不使用 `@mcp_tool` 全局装饰器，也不做目录自动发现。** 新增工具包时：实现 `register_*_tools`，并在 `add_common_tools`（或 `McpPlugin`）中挂上一次。

需要运行时对象时，由容器 / `McpPlugin` 创建后注入 `register`，**不要**写模块级 `get_instance` 单例。

## 快速上手：开发一个灯控工具

### 第 1 步：创建目录

```
src/mcp/tools/light/
├── __init__.py          # 导出 register_light_tools
├── register.py            # register_light_tools 实现
└── light_manager.py     # 业务逻辑（可选）
```

### 第 2 步：业务逻辑（`light_manager.py`）

```python
"""灯光控制业务逻辑."""

from src.logging import get_logger

logger = get_logger()


class LightManager:
    def __init__(self):
        self._on = False
        self._brightness = 100

    def turn_on(self) -> str:
        self._on = True
        logger.info("[Light] 灯已打开")
        return "灯已打开"

    def turn_off(self) -> str:
        self._on = False
        logger.info("[Light] 灯已关闭")
        return "灯已关闭"

    def set_brightness(self, level: int) -> str:
        self._brightness = max(0, min(100, level))
        logger.info(f"[Light] 亮度设为 {self._brightness}%")
        return f"亮度已设为 {self._brightness}%"

    def get_status(self) -> str:
        state = "开" if self._on else "关"
        return f"灯状态: {state}, 亮度: {self._brightness}%"
```

### 第 3 步：`register_light_tools`（`register.py`）

```python
"""灯光 MCP 工具注册."""

from collections.abc import Callable
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .light_manager import LightManager

logger = get_logger()


def register_light_tools(
    add_tool: Callable[[McpTool], None],
    manager: LightManager | None = None,
) -> None:
    light = manager or LightManager()

    async def turn_on(args: dict[str, Any]) -> str:
        return light.turn_on()

    async def turn_off(args: dict[str, Any]) -> str:
        return light.turn_off()

    async def set_brightness(args: dict[str, Any]) -> str:
        brightness = int(args.get("brightness", 100))
        return light.set_brightness(brightness)

    async def get_status(args: dict[str, Any]) -> str:
        return light.get_status()

    tools = [
        McpTool(
            "self.light.turn_on",
            "打开灯。当用户说'开灯'、'打开灯'时调用。",
            PropertyList(),
            turn_on,
        ),
        McpTool(
            "self.light.turn_off",
            "关闭灯。当用户说'关灯'、'把灯关了'时调用。",
            PropertyList(),
            turn_off,
        ),
        McpTool(
            "self.light.set_brightness",
            "设置灯的亮度。参数: brightness (0-100)。",
            PropertyList(
                [
                    Property(
                        "brightness",
                        PropertyType.INTEGER,
                        min_value=0,
                        max_value=100,
                    )
                ]
            ),
            set_brightness,
        ),
        McpTool(
            "self.light.get_status",
            "查看灯的当前状态（开/关、亮度）。",
            PropertyList(),
            get_status,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("已注册 %d 个灯光 MCP 工具", len(tools))
```

### 第 4 步：`__init__.py`

```python
"""灯光控制工具."""

from .register import register_light_tools

__all__ = ["register_light_tools"]
```

### 第 5 步：挂到宿主

在 `src/mcp/mcp_server.py` 的 `add_common_tools` 中增加：

```python
from src.mcp.tools.light import register_light_tools

register_light_tools(self.add_tool)
```

若工具依赖容器对象，在 `McpPlugin.setup` 中创建后传入 `register_light_tools(server.add_tool, manager)`。

**完成。** 重启应用后灯控工具可用。

## API 参考

### `McpTool` / `Property`

```python
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

McpTool(
    name="self.module.action",  # 全局唯一
    description="AI 据此决定何时调用",
    properties=PropertyList(
        [
            Property("city", PropertyType.STRING),
            Property(
                "days",
                PropertyType.INTEGER,
                default_value=3,
                min_value=1,
                max_value=7,
            ),
            Property("verbose", PropertyType.BOOLEAN, default_value=False),
        ]
    ),
    callback=async_handler,  # async def handler(args: dict) -> str | int | bool
)
```

### 参数类型

| 类型 | 用法 | 说明 |
|------|------|------|
| `PropertyType.STRING` | `Property("name", PropertyType.STRING)` | 字符串 |
| `PropertyType.INTEGER` | `Property("n", PropertyType.INTEGER, min_value=0, max_value=100)` | 整数，可选范围 |
| `PropertyType.BOOLEAN` | `Property("flag", PropertyType.BOOLEAN, default_value=False)` | 布尔 |

- 不带 `default_value` 的一般为**必填**（由协议侧校验）
- `min_value` / `max_value` 仅对 `INTEGER` 有效

### 返回值

回调宜返回 **`str`**（或 bool/int）。结构化数据用 `json.dumps(..., ensure_ascii=False)`。

**不要直接返回 `dict`** 作为协议 body 的主形态时需按现有 `McpTool` 封装约定处理。

## 注册约定

| 规则 | 说明 |
|------|------|
| 入口 | 包导出 `register_*_tools(add_tool, ...)` |
| 挂载 | 在 `add_common_tools` 或 `McpPlugin.setup` 中**显式**调用一次 |
| 依赖 | 有状态对象用参数注入闭包；禁止模块级全局 `get_instance` |
| 命名 | 工具名 `self.module.action` 或业务约定名，全局唯一 |
| 异步 | `async def`；阻塞 IO 用 `asyncio.to_thread` |
| 超时 | 外部 API 必须设 `timeout` |
| 日志 | `get_logger()`，前缀 `[ToolName]` |
| 错误 | try/except，用户可读信息 + `logger.error(..., exc_info=True)` |

## 现有工具模块

| 模块 | 路径 | 注册方式 | 详细文档 |
|------|------|----------|----------|
| 音量 | `volume/` | `register_volume_tools` | [system.md](system.md) |
| 应用 | `app/` | `register_app_tools` | [system.md](system.md) |
| 相机 | `camera/` | `register_camera_tools`（McpPlugin） | [camera.md](camera.md) |
| 截图 | `screenshot/` | `register_screenshot_tools`（McpPlugin） | — |
| 音乐 | `music/` | `register_music_tools`（注入 MusicPlayer） | [music.md](music.md) |
| 天气 | `weather/` | `register_weather_tools`（当前 mock） | — |

用户目录下的**外挂** Python 插件（`mcp_plugins`）见仓库内《MCP工具扩展方案》；与内置 `register_*` 并存，不恢复全局装饰器发现。
