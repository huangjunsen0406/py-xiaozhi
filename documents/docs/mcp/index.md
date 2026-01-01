# MCP 开发指南

MCP (Model Context Protocol) 是一个用于AI工具扩展的开放标准协议。本项目基于 MCP 实现了一个强大的工具系统，支持多种功能模块的无缝集成。

## 📖 文档导航

- **[🔧 内置MCP开发指南](#系统架构)** - 本文档：开发和使用内置MCP工具
- **[🔌 外挂MCP接入指南](xiaozhi-mcp.md)** - 外部MCP服务接入和社区项目集成

> 💡 **选择指南**: 如果你想开发新的内置工具，请参考本文档；如果你想接入外部MCP服务或了解社区项目，请查看[外挂接入指南](xiaozhi-mcp.md)。

## 系统架构

### 核心组件

#### 1. MCP 服务器 (`src/mcp/mcp_server.py`)

- **基于 JSON-RPC 2.0 协议**: 符合 MCP 标准规范
- **单例模式**: 全局统一的服务器实例管理
- **工具注册系统**: 支持动态添加和管理工具
- **参数验证**: 完整的类型检查和参数验证机制
- **错误处理**: 标准化的错误响应和异常处理

#### 2. 工具属性系统

```python
# 属性类型定义
class PropertyType(Enum):
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"

# 属性定义
@dataclass
class Property:
    name: str
    type: PropertyType
    default_value: Optional[Any] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
```

#### 3. 工具定义结构

```python
@dataclass
class McpTool:
    name: str                  # 工具名称
    description: str           # 工具描述
    properties: PropertyList   # 参数列表
    callback: Callable         # 回调函数
```

### 工具管理器架构

每个功能模块都有对应的管理器类，负责：

- 工具的初始化和注册
- 业务逻辑的封装
- 与底层服务的交互

#### 现有工具模块

1. **系统工具 (`src/mcp/tools/system/`)**
   - 设备状态监控
   - 应用程序管理（启动、终止、扫描）
   - 系统信息查询

2. **日程管理 (`src/mcp/tools/calendar/`)**
   - 日程的增删改查
   - 智能时间解析
   - 冲突检测
   - 提醒服务

3. **系统工具 (`src/mcp/tools/system/`)**
   - 音量控制、音量状态查询
   - 桌面应用启动/关闭/扫描
   - 运行进程信息

4. **相机/截图 (`src/mcp/tools/camera/`, `src/mcp/tools/screenshot/`)**
   - 拍照、视觉问答
   - 桌面截图、屏幕 OCR、主/副屏选择

5. **音乐播放 (`src/mcp/tools/music/`)**
   - 搜索播放、暂停/恢复/停止、跳转
   - 歌词获取、本地歌单管理

6. **八字命理 (`src/mcp/tools/bazi/`)**
   - 八字计算、反推公历
   - 黄历查询
   - 婚姻时机与合婚分析

## 工具开发指南：模拟一盏灯

#### 1. 目录结构

```bash
mkdir -p src/mcp/tools/light
touch src/mcp/tools/light/__init__.py
touch src/mcp/tools/light/_tools.py   # 注册入口
touch src/mcp/tools/light/state.py    # 业务逻辑（模拟灯）
```

#### 2. 业务逻辑（`state.py`）

```python
# 一个最简单的“灯”状态
class Light:
    def __init__(self):
        self._on = False

    def turn_on(self):
        self._on = True
        return "灯已打开"

    def turn_off(self):
        self._on = False
        return "灯已关闭"

    def status(self):
        return "灯亮着" if self._on else "灯是关的"

_LIGHT = Light()
```

#### 3. 注册 MCP 工具（`_tools.py`）

```python
from src.mcp.decorators import mcp_tool
from .state import _LIGHT

@mcp_tool(name="self.light.turn_on", description="开启模拟灯")
async def light_on(args):
    return _LIGHT.turn_on()

@mcp_tool(name="self.light.turn_off", description="关闭模拟灯")
async def light_off(args):
    return _LIGHT.turn_off()

@mcp_tool(name="self.light.get_status", description="查看灯的状态")
async def light_status(args):
    return _LIGHT.status()
```

完成！无需修改 `mcp_server.py`，服务器会在 `add_common_tools()` 时自动扫描 `_tools.py` 并加载这三个工具。

### 最佳实践速记

1. 工具命名统一 `self.module.action`
2. 必填参数不设默认值；可选参数提供合理默认
3. 优先 `async/await`，同步逻辑可 `asyncio.to_thread`
4. 捕获异常并返回可读信息（`logger.error` + 字符串消息）
