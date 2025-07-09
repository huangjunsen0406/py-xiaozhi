# 八字命理工具 (Bazi Tools)

八字命理工具是基于中国传统命理学的 MCP 工具集，提供了全面的八字分析、婚姻合婚、黄历查询等功能。

### 常见使用场景

**个人八字分析:**
- "帮我算一下我的八字，我是1990年3月15日下午3点出生的"
- "我的农历生日是1985年二月十五，性别女，算一下八字"
- "分析一下我的命格特点"

**婚姻合婚:**
- "我和我对象八字合不合，我是1990年3月15日生，他是1988年10月20日生"
- "帮我们算一下婚姻是否般配"
- "分析一下我们的婚姻时机"

**黄历查询:**
- "今天日子好不好"
- "2025年7月9日的黄历信息"
- "查一下明天适合做什么事情"

**时间反推:**
- "我的八字是甲子年丙寅月戊申日甲寅时，有哪些可能的出生时间"

### 使用提示

1. **提供准确时间**: 包含年、月、日、时信息，可以是公历或农历
2. **明确性别**: 对于婚姻分析，请说明双方性别
3. **自然描述**: 用日常语言描述您的需求，AI 会自动调用相应的命理工具
4. **理性对待**: 命理分析仅供参考，不应完全依赖于此做重要决定

AI 助手会根据您的需求自动选择合适的命理工具，为您提供专业的八字分析服务。

## 功能概览

### 基础八字分析
- **八字排盘**: 根据出生时间计算完整的八字信息
- **五行分析**: 分析五行强弱和喜忌
- **十神分析**: 分析命格中的十神关系
- **大运流年**: 分析人生运势走向

### 婚姻分析
- **合婚分析**: 分析两人八字是否相配
- **婚姻时机**: 分析最佳结婚时间
- **配偶特征**: 分析配偶的可能特征
- **婚姻运势**: 分析婚姻生活的吉凶

### 黄历服务
- **每日宜忌**: 查询某日的宜忌事项
- **节气信息**: 提供二十四节气信息
- **农历信息**: 提供农历日期和相关信息

## 工具列表

### 1. 基础八字工具

#### get_bazi_detail - 获取八字详情
根据出生时间（公历或农历）和性别计算完整的八字信息。

**参数:**
- `solar_datetime` (可选): 公历时间，格式如 "1990-03-15 15:30"
- `lunar_datetime` (可选): 农历时间，格式如 "1990-02-15 15:30"
- `gender` (可选): 性别，1=男，0=女，默认为1
- `eight_char_provider_sect` (可选): 八字流派，默认为2

**使用场景:**
- 个人八字分析
- 命理咨询
- 运势预测基础

#### get_solar_times - 八字反推时间
根据八字信息反推可能的公历出生时间。

**参数:**
- `bazi` (必需): 八字信息，格式如 "甲子年丙寅月戊申日甲寅时"

**使用场景:**
- 时间验证
- 多种可能性分析
- 八字校对

#### get_chinese_calendar - 黄历查询
查询指定日期的黄历信息，包括宜忌、节气等。

**参数:**
- `solar_datetime` (可选): 公历时间，默认为当前时间

**使用场景:**
- 择日选时
- 日常宜忌查询
- 传统节日信息

### 2. 婚姻分析工具

#### analyze_marriage_timing - 婚姻时机分析
分析个人的婚姻时机和配偶信息。

**参数:**
- `solar_datetime` (可选): 公历时间
- `lunar_datetime` (可选): 农历时间
- `gender` (可选): 性别，1=男，0=女
- `eight_char_provider_sect` (可选): 八字流派

**使用场景:**
- 婚姻时机预测
- 配偶特征分析
- 感情运势分析

#### analyze_marriage_compatibility - 合婚分析
分析两人八字的婚姻匹配度。

**参数:**
- `male_solar_datetime` (可选): 男方公历时间
- `male_lunar_datetime` (可选): 男方农历时间
- `female_solar_datetime` (可选): 女方公历时间
- `female_lunar_datetime` (可选): 女方农历时间

**使用场景:**
- 婚前合婚
- 婚姻咨询
- 配对分析

## 使用示例

### 基础八字分析示例

```python
# 公历时间八字分析
result = await mcp_server.call_tool("get_bazi_detail", {
    "solar_datetime": "1990-03-15 15:30",
    "gender": 1
})

# 农历时间八字分析
result = await mcp_server.call_tool("get_bazi_detail", {
    "lunar_datetime": "1990-02-15 15:30",
    "gender": 0
})

# 八字反推时间
result = await mcp_server.call_tool("get_solar_times", {
    "bazi": "甲子年丙寅月戊申日甲寅时"
})

# 黄历查询
result = await mcp_server.call_tool("get_chinese_calendar", {
    "solar_datetime": "2024-01-01"
})
```

### 婚姻分析示例

```python
# 个人婚姻时机分析
result = await mcp_server.call_tool("analyze_marriage_timing", {
    "solar_datetime": "1990-03-15 15:30",
    "gender": 1
})

# 两人合婚分析
result = await mcp_server.call_tool("analyze_marriage_compatibility", {
    "male_solar_datetime": "1990-03-15 15:30",
    "female_solar_datetime": "1992-08-20 10:00"
})
```

## 数据结构

### 八字信息 (BaziInfo)
```python
@dataclass
class BaziInfo:
    bazi: str              # 完整八字
    year_pillar: dict      # 年柱信息
    month_pillar: dict     # 月柱信息
    day_pillar: dict       # 日柱信息
    hour_pillar: dict      # 时柱信息
    day_master: str        # 日主
    zodiac: str            # 生肖
    wuxing_analysis: dict  # 五行分析
    shishen_analysis: dict # 十神分析
```

### 婚姻分析结果 (MarriageAnalysis)
```python
@dataclass
class MarriageAnalysis:
    overall_score: float        # 综合评分
    overall_level: str          # 婚配等级
    element_analysis: dict      # 五行分析
    zodiac_analysis: dict       # 生肖分析
    pillar_analysis: dict       # 日柱分析
    branch_analysis: dict       # 地支分析
    complement_analysis: dict   # 互补分析
    suggestions: list          # 专业建议
```

### 黄历信息 (ChineseCalendar)
```python
@dataclass
class ChineseCalendar:
    solar_date: str        # 公历日期
    lunar_date: str        # 农历日期
    zodiac_year: str       # 生肖年
    gan_zhi_year: str      # 干支年
    gan_zhi_month: str     # 干支月
    gan_zhi_day: str       # 干支日
    yi_events: list        # 宜事
    ji_events: list        # 忌事
    festival: str          # 节日
    jieqi: str            # 节气
```

## 专业术语说明

### 基础概念
- **八字**: 由出生年、月、日、时的天干地支组成的八个字
- **五行**: 金、木、水、火、土五种基本元素
- **十神**: 比肩、劫财、食神、伤官、偏财、正财、七杀、正官、偏印、正印
- **大运**: 人生各阶段的运势周期
- **流年**: 每年的运势变化

### 婚姻术语
- **合婚**: 分析两人八字是否相配
- **六合**: 地支间的最佳组合关系
- **三合**: 地支间的良好组合关系
- **相冲**: 地支间的对立关系
- **相刑**: 地支间的刑克关系
- **相害**: 地支间的伤害关系

### 黄历术语
- **宜**: 适合进行的活动
- **忌**: 不宜进行的活动
- **节气**: 二十四节气，反映季节变化
- **干支**: 天干地支纪年法

## 注意事项

1. **时间准确性**: 提供准确的出生时间对分析结果至关重要
2. **理性对待**: 命理分析仅供参考，不应完全依赖
3. **文化背景**: 基于中国传统文化，理解时需要文化背景知识
4. **隐私保护**: 个人出生信息属于隐私，请谨慎分享

## 最佳实践

### 1. 时间格式
- 公历时间: "YYYY-MM-DD HH:MM" (如 "1990-03-15 15:30")
- 农历时间: "YYYY-MM-DD HH:MM" (如 "1990-02-15 15:30")
- 确保时间的准确性，特别是小时信息

### 2. 性别参数
- 男性: gender=1
- 女性: gender=0
- 对于婚姻分析，性别信息很重要

### 3. 结果解读
- 综合分析多个方面，不要只看单一指标
- 重视专业建议和综合评分
- 理性对待分析结果

### 4. 隐私保护
- 不要在公共场合分享详细的出生信息
- 注意保护个人隐私和敏感信息

## 故障排除

### 常见问题
1. **时间格式错误**: 确保时间格式正确
2. **参数缺失**: 检查必需参数是否提供
3. **结果解读**: 参考术语说明理解结果
4. **文化差异**: 理解传统文化背景

### 调试方法
1. 检查时间参数格式
2. 验证性别参数设置
3. 查看返回的错误信息
4. 参考使用示例调整参数

通过八字命理工具，您可以获得专业的命理分析服务，但请理性对待分析结果，将其作为人生参考而非绝对指导。