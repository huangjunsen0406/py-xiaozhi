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

3. **定时器 (`src/mcp/tools/timer/`)**
   - 倒计时器管理
   - 任务调度
   - 时间提醒

4. **音乐播放 (`src/mcp/tools/music/`)**
   - 音乐播放控制
   - 播放列表管理
   - 音量控制

5. **铁路查询 (`src/mcp/tools/railway/`)**
   - 12306 车次查询
   - 车站信息查询
   - 票价查询

6. **搜索工具 (`src/mcp/tools/search/`)**
   - 网络搜索
   - 信息检索
   - 结果过滤

7. **菜谱工具 (`src/mcp/tools/recipe/`)**
   - 菜谱查询
   - 食谱推荐
   - 营养信息

8. **相机工具 (`src/mcp/tools/camera/`)**
   - 拍照功能
   - 视觉问答
   - 图像分析

9. **地图工具 (`src/mcp/tools/amap/`)**
   - 地理编码/逆地理编码
   - 路径规划
   - 天气查询
   - POI 搜索

10. **八字命理 (`src/mcp/tools/bazi/`)**
    - 八字计算
    - 命理分析
    - 合婚分析
    - 黄历查询

## 工具开发指南

### 1. 创建新工具模块

创建新的工具模块需要以下步骤：

#### 步骤 1: 创建模块目录
```bash
mkdir src/mcp/tools/your_tool_name
cd src/mcp/tools/your_tool_name
```

#### 步骤 2: 创建必要文件
```bash
touch __init__.py
touch manager.py      # 管理器类
touch tools.py        # 工具函数实现
touch models.py       # 数据模型（可选）
touch client.py       # 客户端类（可选）
```

#### 步骤 3: 实现管理器类
```python
# manager.py
class YourToolManager:
    def __init__(self):
        # 初始化代码
        pass
    
    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册工具
        """
        # 定义工具属性
        tool_props = PropertyList([
            Property("param1", PropertyType.STRING),
            Property("param2", PropertyType.INTEGER, default_value=0)
        ])
        
        # 注册工具
        add_tool((
            "tool_name",
            "工具描述",
            tool_props,
            your_tool_function
        ))

# 全局管理器实例
_manager = None

def get_your_tool_manager():
    global _manager
    if _manager is None:
        _manager = YourToolManager()
    return _manager
```

#### 步骤 4: 实现工具函数
```python
# tools.py
async def your_tool_function(args: dict) -> str:
    """
    工具函数实现
    """
    param1 = args.get("param1")
    param2 = args.get("param2", 0)
    
    # 业务逻辑
    result = perform_operation(param1, param2)
    
    return f"操作结果: {result}"
```

#### 步骤 5: 注册到主服务器
在 `src/mcp/mcp_server.py` 的 `add_common_tools` 方法中添加：
```python
# 添加你的工具
from src.mcp.tools.your_tool_name import get_your_tool_manager

your_tool_manager = get_your_tool_manager()
your_tool_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)
```

### 2. 最佳实践

#### 工具命名规范
- 使用 `self.module.action` 格式
- 例如：`self.calendar.create_event`、`self.music.play`

#### 参数设计
- 必需参数不设默认值
- 可选参数设置合理的默认值
- 使用合适的参数类型（STRING、INTEGER、BOOLEAN）

#### 错误处理
```python
async def your_tool_function(args: dict) -> str:
    try:
        # 业务逻辑
        result = await perform_operation(args)
        return f"成功: {result}"
    except Exception as e:
        logger.error(f"工具执行失败: {e}")
        return f"错误: {str(e)}"
```

#### 异步支持
- 优先使用 async/await
- 支持同步函数的自动包装
- 合理使用 asyncio 工具

### 3. 工具描述编写

工具描述应包含：
- 功能简介
- 使用场景
- 参数说明
- 返回格式
- 注意事项

示例：
```python
description = """
创建新的日程事件，支持智能时间设置和冲突检测。
使用场景：
1. 安排会议或约会
2. 设置提醒事项
3. 时间管理规划

参数：
  title: 事件标题（必需）
  start_time: 开始时间，ISO格式（必需）
  end_time: 结束时间，可自动计算
  description: 事件描述
  category: 事件分类
  reminder_minutes: 提醒时间（分钟）

返回：创建成功或失败的消息
"""
```

## 使用示例

### 日程管理
```python
# 创建日程
await mcp_server.call_tool("self.calendar.create_event", {
    "title": "团队会议",
    "start_time": "2024-01-01T10:00:00",
    "category": "会议",
    "reminder_minutes": 15
})

# 查询今日日程
await mcp_server.call_tool("self.calendar.get_events", {
    "date_type": "today"
})
```

### 地图功能
```python
# 地址转经纬度
await mcp_server.call_tool("self.amap.geocode", {
    "address": "北京市天安门广场"
})

# 路径规划
await mcp_server.call_tool("self.amap.direction_walking", {
    "origin": "116.397428,39.90923",
    "destination": "116.390813,39.904368"
})
```

### 八字命理
```python
# 获取八字分析
await mcp_server.call_tool("self.bazi.get_bazi_detail", {
    "solar_datetime": "2008-03-01T13:00:00+08:00",
    "gender": 1
})

# 合婚分析
await mcp_server.call_tool("self.bazi.analyze_marriage_compatibility", {
    "male_solar_datetime": "1990-01-01T10:00:00+08:00",
    "female_solar_datetime": "1992-05-15T14:30:00+08:00"
})
```

## 高级特性

### 1. 参数验证
系统提供完整的参数验证机制：
- 类型检查
- 范围验证
- 必需参数检查
- 默认值处理

### 2. 工具发现
支持动态工具发现和列表获取：
- 分页支持
- 大小限制
- 游标遍历

### 3. 视觉能力
支持视觉相关功能：
- 图像分析
- 视觉问答
- 配置外部视觉服务

### 4. 并发处理
- 异步工具执行
- 任务调度
- 资源管理

## 调试和测试

### 日志系统
```python
from src.utils.logging_config import get_logger
logger = get_logger(__name__)

logger.info("工具执行开始")
logger.error("执行失败", exc_info=True)
```

### 测试工具
```python
# 测试工具注册
server = McpServer.get_instance()
server.add_common_tools()

# 测试工具调用
result = await server.parse_message({
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
        "name": "your_tool_name",
        "arguments": {"param1": "value1"}
    },
    "id": 1
})
```

## 部署和配置

### 环境要求
- Python 3.8+
- 异步支持
- 相关依赖库

### 配置文件
工具配置通过 `config/config.json` 进行管理，支持：
- API 密钥配置
- 服务端点设置
- 功能开关控制

### 性能优化
- 连接池管理
- 缓存策略
- 并发控制
- 资源回收

## 故障排除

### 常见问题
1. **工具注册失败**: 检查管理器单例和导入路径
2. **参数验证错误**: 确认参数类型和必需性
3. **异步调用问题**: 确保正确使用 async/await
4. **依赖缺失**: 检查模块导入和依赖安装

### 调试技巧
- 启用详细日志
- 使用调试工具
- 单元测试验证
- 性能分析工具
