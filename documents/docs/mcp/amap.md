# 高德地图工具 (Amap Tools)

高德地图工具是基于高德地图 Web API 的 MCP 工具集，提供了丰富的地理位置服务功能。

## 自然语言使用方式

### 路线规划
- "从云升科学园到科学城地铁站怎么走"
- "去天河城的路线"
- "开车从A到B要多久"

### 最近地点查询
- "最近的奶茶店怎么走"
- "最近的餐厅在哪里"
- "最近的地铁站"
- "最近的银行"

### 附近地点搜索
- "附近有哪些奶茶店"
- "附近的餐厅"
- "周边的超市"
- "附近2公里内的银行"

### 智能导航
- "去天河城"
- "导航到广州塔"
- "怎么去白云机场"

### 出行方式对比
- "从A到B，开车和坐地铁哪个快"
- "比较一下去机场的各种方式"
- "哪种方式最快"

## MCP 工具介绍

### 智能工具（推荐使用）

#### 1. route_planning - 智能路线规划
支持自然语言地址输入的路线规划，自动处理地址转换和坐标解析。

**参数:**
- `origin` (必需): 起点地址名称
- `destination` (必需): 终点地址名称
- `city` (可选): 所在城市，默认广州
- `travel_mode` (可选): 出行方式，walking(步行)、driving(驾车)、bicycling(骑行)、transit(公交)，默认步行

#### 2. find_nearest - 最近地点查找
找到最近的某类地点并提供详细的步行路线。

**参数:**
- `keywords` (必需): 搜索关键词，如"奶茶店"、"餐厅"、"地铁站"、"银行"
- `radius` (可选): 搜索半径（米），默认5000米
- `user_location` (可选): 用户位置，不提供则自动定位

#### 3. find_nearby - 附近地点搜索
搜索附近的多个地点，按距离排序展示。

**参数:**
- `keywords` (必需): 搜索关键词，如"奶茶店"、"餐厅"、"超市"
- `radius` (可选): 搜索半径（米），默认2000米
- `user_location` (可选): 用户位置，不提供则自动定位

#### 4. navigation - 智能导航
提供到目的地的多种出行方式对比和推荐。

**参数:**
- `destination` (必需): 目的地名称
- `city` (可选): 所在城市，默认广州
- `user_location` (可选): 用户位置，不提供则自动定位

#### 5. get_location - 当前位置获取
基于IP地址的智能定位服务。

**参数:**
- `user_ip` (可选): 用户IP地址，不提供则自动获取

#### 6. compare_routes - 路线对比
比较不同出行方式的时间、距离和适用性。

**参数:**
- `origin` (必需): 起点地址名称
- `destination` (必需): 终点地址名称
- `city` (可选): 所在城市，默认广州

### 基础工具（二次开发使用）

#### 地理编码工具
- `maps_geo` - 地址转坐标
- `maps_regeocode` - 坐标转地址
- `maps_ip_location` - IP定位

#### 路径规划工具
- `maps_direction_walking` - 步行路径规划
- `maps_direction_driving` - 驾车路径规划
- `maps_bicycling` - 骑行路径规划
- `maps_direction_transit_integrated` - 公交路径规划

#### 搜索工具
- `maps_text_search` - 关键词搜索
- `maps_around_search` - 周边搜索
- `maps_search_detail` - POI详情查询

#### 其他工具
- `maps_weather` - 天气查询
- `maps_distance` - 距离测量

## 使用示例

### 智能工具示例

```python
# 智能路线规划
result = await mcp_server.call_tool("route_planning", {
    "origin": "云升科学园",
    "destination": "科学城地铁站",
    "travel_mode": "walking"
})

# 最近地点查找
result = await mcp_server.call_tool("find_nearest", {
    "keywords": "奶茶店",
    "radius": "5000"
})

# 附近地点搜索
result = await mcp_server.call_tool("find_nearby", {
    "keywords": "餐厅",
    "radius": "2000"
})
```

### 基础工具示例

```python
# 地址转坐标
result = await mcp_server.call_tool("maps_geo", {
    "address": "北京市天安门广场",
    "city": "北京"
})

# 步行路径规划
result = await mcp_server.call_tool("maps_direction_walking", {
    "origin": "116.397428,39.90923",
    "destination": "116.390813,39.904368"
})
```

## 二次开发说明

### 工具架构

高德地图工具采用分层架构设计：

#### 1. 智能工具层 (MCP 适配)
- **AmapToolsManager**: 适配 MCP 服务器的管理器
- **智能工具注册**: 自动注册用户友好的智能工具
- **参数验证**: 完整的参数类型和格式验证
- **结果格式化**: 用户友好的结果展示

#### 2. 业务逻辑层 (AmapManager)
- **智能路线规划**: 支持自然语言地址输入
- **自动定位**: 多策略IP定位和城市识别
- **组合功能**: 将多个API调用组合成高级功能
- **错误处理**: 完善的异常处理和容错机制

#### 3. API 客户端层 (AmapClient)
- **HTTP 客户端**: 基于 aiohttp 的异步HTTP客户端
- **API 封装**: 所有高德地图API的完整封装
- **响应解析**: 自动解析API响应并转换为数据模型
- **错误处理**: API级别的错误处理和重试

#### 4. 数据模型层 (Models)
- **结构化数据**: 使用 dataclass 定义的数据结构
- **类型安全**: 完整的类型注解和验证
- **格式转换**: 坐标、地址等格式的自动转换
- **数据一致性**: 统一的数据格式和命名规范

### 智能功能特性

#### 自动定位策略
1. 优先使用高德API自动IP识别
2. 如果失败，尝试第三方IP服务
3. 验证定位结果的有效性
4. 回退到城市中心坐标

#### 地址智能解析
- 支持自然语言地址输入: "天安门广场"
- 支持坐标格式: "116.397428,39.90923"
- 支持复合地址: "北京市东城区天安门广场1号"

#### 结果智能格式化
- 用户友好的输出格式
- 多种出行方式对比展示
- 详细的步行路线指引

### 配置说明

#### API 密钥配置
高德地图工具需要配置 API 密钥才能正常使用。

**获取 API 密钥:**
1. 访问 [高德开放平台](https://lbs.amap.com/)
2. 注册开发者账号
3. 创建应用，获取 API Key

**配置方式:**
目前 API 密钥在 `src/mcp/tools/amap/__init__.py` 中硬编码：

```python
AMAP_API_KEY = "your_api_key_here"
```

**建议配置方式:**
将 API 密钥配置到 `config/config.json` 中：

```json
{
  "amap": {
    "api_key": "your_api_key_here"
  }
}
```

### 扩展开发

#### 添加新的智能工具
1. 在 `AmapManager` 中实现业务逻辑
2. 在 `AmapToolsManager` 中注册新工具
3. 在 `AmapTools` 中添加工具定义
4. 更新测试用例

#### 添加新的基础工具
1. 在 `AmapClient` 中封装API调用
2. 在 `AmapManager` 中实现业务逻辑
3. 在 `AmapTools` 中添加工具定义
4. 更新数据模型（如需要）

### 数据结构

```python
@dataclass
class Location:
    longitude: float  # 经度
    latitude: float   # 纬度

@dataclass
class POI:
    id: str              # POI ID
    name: str            # 名称
    address: str         # 地址
    location: Location   # 坐标
    type_code: str       # 类型代码
```

### 最佳实践

1. **优先使用智能工具**: 自动处理复杂逻辑，用户友好
2. **合理设置参数**: 指定城市、半径等参数提高精度
3. **错误处理**: 处理网络异常和API错误
4. **缓存策略**: 对频繁查询的结果进行缓存
5. **异步调用**: 使用异步方式提高性能

通过高德地图工具，您可以轻松地为应用添加强大的地理位置服务功能，提供更好的用户体验。