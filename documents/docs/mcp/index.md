# MCP 工具开发指南

本文档说明如何为 py-xiaozhi 开发内置 MCP 工具。外部 MCP 服务接入请参考 [外挂 MCP 接入指南](xiaozhi-mcp.md)。

## 工作原理

1. 启动时，`McpServer.add_common_tools()` 调用 `discover_tool_modules()` 自动扫描 `src/mcp/tools/` 下的所有子包
2. 扫描会 import 每个子包的 `__init__.py`，以及子包内的 `_tools.py`（如果存在）
3. import 过程中，`@mcp_tool` 装饰器将工具函数注册到全局注册表
4. 注册完成后，工具通过 JSON-RPC 2.0 协议对外暴露

**你只需要写工具函数并加装饰器，不需要修改 `mcp_server.py`。**

## 快速上手：开发一个灯控工具

### 第 1 步：创建目录

```
src/mcp/tools/light/
├── __init__.py      # 导入 _tools 触发装饰器注册
├── _tools.py        # 工具注册（@mcp_tool 装饰器）
└── light_manager.py # 业务逻辑（可选，简单工具可直接写在 _tools.py）
```

### 第 2 步：编写业务逻辑 (`light_manager.py`)

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


_light = LightManager()


def get_light_manager() -> LightManager:
    return _light
```

### 第 3 步：注册 MCP 工具 (`_tools.py`)

```python
"""灯光 MCP 工具注册."""

from src.mcp.decorators import Prop, PropType, mcp_tool

from .light_manager import get_light_manager


@mcp_tool(
    name="self.light.turn_on",
    description="打开灯。当用户说'开灯'、'打开灯'时调用。",
)
async def tool_light_on(args):
    return get_light_manager().turn_on()


@mcp_tool(
    name="self.light.turn_off",
    description="关闭灯。当用户说'关灯'、'把灯关了'时调用。",
)
async def tool_light_off(args):
    return get_light_manager().turn_off()


@mcp_tool(
    name="self.light.set_brightness",
    description="设置灯的亮度。参数: brightness (0-100)。",
    props=[Prop("brightness", PropType.INT, min_val=0, max_val=100)],
)
async def tool_set_brightness(args):
    brightness = args.get("brightness", 100)
    return get_light_manager().set_brightness(brightness)


@mcp_tool(
    name="self.light.get_status",
    description="查看灯的当前状态（开/关、亮度）。",
)
async def tool_light_status(args):
    return get_light_manager().get_status()
```

### 第 4 步：编写 `__init__.py`

```python
"""灯光控制工具."""

# 导入 _tools 触发 @mcp_tool 装饰器注册
from . import _tools  # noqa: F401
```

**完成。** 重启应用后，4 个灯控工具自动可用。

## API 参考

### `@mcp_tool` 装饰器

```python
from src.mcp.decorators import Prop, PropType, mcp_tool

@mcp_tool(
    name="self.module.action",   # 工具名称（全局唯一）
    description="工具描述，AI 根据此判断何时调用",
    props=[                      # 参数列表（可选，无参数时省略）
        Prop("city", PropType.STR),                              # 必填字符串
        Prop("days", PropType.INT, default=3, min_val=1, max_val=7),  # 可选整数，带范围
        Prop("verbose", PropType.BOOL, default=False),           # 可选布尔值
    ],
)
async def tool_function(args: dict) -> str:
    city = args.get("city", "")
    days = args.get("days", 3)
    return json.dumps({"city": city, "days": days}, ensure_ascii=False)
```

### 参数类型

| 类型 | 用法 | 说明 |
|------|------|------|
| `PropType.STR` | `Prop("name", PropType.STR)` | 字符串 |
| `PropType.INT` | `Prop("count", PropType.INT, min_val=0, max_val=100)` | 整数，可选范围限制 |
| `PropType.BOOL` | `Prop("flag", PropType.BOOL, default=False)` | 布尔值 |

- 不带 `default` 的参数为**必填**
- 带 `default` 的参数为**可选**
- `min_val` / `max_val` 仅对 `INT` 有效

### 返回值

工具函数必须返回 **`str`** 类型。返回结构化数据时使用 `json.dumps()`：

```python
# 简单文本
return "操作成功"

# 结构化 JSON
return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
```

**不要返回 `dict`**，MCP 协议要求文本内容。

## 自动发现规则

`discover_tool_modules()` 的扫描顺序：

1. `src/mcp/tools/*.py` — 根目录下的独立文件（跳过 `_` 开头的）
2. `src/mcp/tools/<name>/` — 每个子包的 `__init__.py`
3. `src/mcp/tools/<name>/_tools.py` — 子包内的 `_tools.py`（如果存在）

**关键点**：
- `__init__.py` 必须 import `_tools` 或工具模块，否则装饰器不会触发
- `_` 开头的文件名会被跳过（`_tools.py` 是唯一例外，会被显式拉取）
- 单个模块 import 失败只会 warning，不影响其他工具加载

## 开发规范

| 规则 | 说明 |
|------|------|
| 命名 | 工具名格式 `self.module.action`，全局唯一 |
| 异步 | 工具函数用 `async def`；阻塞操作用 `asyncio.to_thread()` 包裹 |
| 超时 | 外部 API 调用必须设 `timeout` |
| 日志 | 用 `from src.logging import get_logger`，加 `[ToolName]` 前缀 |
| 错误处理 | try/except 捕获异常，返回用户可读的错误信息，`logger.error(..., exc_info=True)` 记录堆栈 |

## 现有工具模块

| 模块 | 路径 | 功能 | 详细文档 |
|------|------|------|----------|
| 音量控制 | `src/mcp/tools/volume/` | 音量设置/查询/状态诊断 | [system.md](system.md) |
| 应用管理 | `src/mcp/tools/app/` | 应用启动/终止/扫描、运行进程查询 | [system.md](system.md) |
| 相机 | `src/mcp/tools/camera/` | 拍照、视觉问答 | [camera.md](camera.md) |
| 截图 | `src/mcp/tools/screenshot/` | 桌面截图、屏幕 OCR、多屏支持 | — |
| 音乐 | `src/mcp/tools/music/` | 搜索播放、暂停/恢复/停止、歌词、本地歌单 | [music.md](music.md) |
| 天气 | `src/mcp/tools/weather/` | 天气查询、天气预报（示例工具） | — |
