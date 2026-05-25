# Home Assistant MCP 集成

为提升架构灵活性与稳定性，py-xiaozhi 已移除内置的 Home Assistant（HA）。现可通过基于 WSS 的 Home Assistant MCP 外挂插件接入 HA，与小智 AI 服务器通过 MCP 协议直连，无需任何中转。该插件由 c1pher-cn 开源维护，完整支持设备状态查询、实体控制与自动化管理。

项目地址：[ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)

## 插件特性

### 核心能力

1. **直连小智服务器**: Home Assistant 作为 MCP server，通过 WebSocket 协议直接对接小智服务器，无需中转
2. **多API组代理**: 在一个实体中同时选择多个API组（Home Assistant 自带控制API、用户自定义MCP Server）
3. **多实体支持**: 支持同时配置多个实体实例
4. **HACS集成**: 通过 HACS 商店一键安装，方便管理和更新

### 技术优势

- **低延迟**: 直连架构，减少网络中转延迟
- **高可靠**: 基于WebSocket长连接，稳定性更佳
- **易扩展**: 支持代理其他MCP Server，扩展性强
- **易维护**: HACS管理，自动更新

## 常见使用场景

**设备状态查询:**

- "客厅灯现在是什么状态"
- "查看所有灯的状态"
- "温度传感器显示多少度"
- "空调现在开着吗"

**设备控制:**

- "打开客厅灯"
- "关闭所有灯"
- "把空调温度设置到25度"
- "调节客厅灯亮度到80%"

**场景控制:**

- "开启睡眠模式"
- "激活回家场景"
- "执行晚安场景"
- "启动派对模式"

**高级控制:**

- "通过script控制电视"
- "执行自定义自动化"
- "控制多媒体设备"
- "管理安防系统"

## 安装指南

### 前置要求

- Home Assistant 已安装并运行
- 已安装 HACS（Home Assistant Community Store）
- 小智AI账号及MCP接入点地址

### 安装步骤

#### 1. 通过HACS安装

1. 打开 HACS，搜索 `xiaozhi` 或 `ha-mcp-for-xiaozhi`

<img width="700" alt="HACS搜索界面" src="https://github.com/user-attachments/assets/fa49ee7c-b503-49fa-ad63-512499fa3885" />

2. 点击下载并安装插件

<img width="500" alt="插件下载界面" src="https://github.com/user-attachments/assets/1ee75d6f-e1b0-4073-a2c7-ee0d72d002ca" />

3. 重启 Home Assistant

#### 2. 手动安装

如果无法通过HACS安装，可以手动下载：

1. 从 [GitHub Releases](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/releases) 下载最新版本
2. 解压到 `custom_components` 目录
3. 重启 Home Assistant

### 配置步骤

#### 1. 添加集成

1. 进入 **设置 > 设备与服务 > 添加集成**
2. 搜索 "Mcp" 或 "MCP Server for Xiaozhi"

<img width="600" alt="添加集成界面" src="https://github.com/user-attachments/assets/07a70fe1-8c6e-4679-84df-1ea05114b271" />

3. 选择并点击添加

#### 2. 配置参数

配置界面需要填写以下信息：

**基本配置:**

- **小智MCP接入点地址**: 从小智AI后台获取的MCP接入地址
- **设备名称**: 为该Home Assistant实例设置一个识别名称

**API组选择:**

- **Assist**: Home Assistant自带的控制功能
- **其他MCP Server**: 如果你在Home Assistant中配置了其他MCP服务器，可以选择一并代理给小智

<img width="600" alt="配置界面" src="https://github.com/user-attachments/assets/38e98fde-8a6c-4434-932c-840c25dc6e28" />

#### 3. 实体公开设置

为了让小智能够控制设备，需要公开相应实体：

1. 进入 **设置 > 语音助手 > 公开**
2. 选择需要被小智控制的设备和实体
3. 保存设置

#### 4. 验证连接

1. 配置完成后等待约1分钟
2. 登录小智AI后台，进入MCP接入点页面
3. 点击刷新，检查连接状态是否正常

<img width="600" alt="连接状态检查" src="https://github.com/user-attachments/assets/ace79a44-6197-4e94-8c49-ab9048ed4502" />

## 使用示例

### 基础设备控制

```
用户: "打开客厅灯"
小智: "好的，已为您打开客厅灯"

用户: "把空调温度调到26度"  
小智: "已将空调温度设置为26度"

用户: "关闭所有灯"
小智: "已为您关闭所有灯光"
```

### 状态查询

```
用户: "客厅现在的温度是多少"
小智: "客厅温度传感器显示当前温度为23.5度"

用户: "哪些灯现在是开着的"
小智: "目前开启的灯有：客厅灯、卧室床头灯"
```

### 场景控制

```
用户: "执行睡眠模式"
小智: "已为您执行睡眠模式场景，所有灯光已关闭，窗帘已拉上"

用户: "开启回家场景"  
小智: "欢迎回家！已为您开启客厅灯和玄关灯，空调已调至舒适温度"
```

## 调试说明

### 1. 实体暴露检查

暴露的工具数量取决于您公开给Home Assistant语音助手的实体种类：

- 进入 **设置 > 语音助手 > 公开**
- 确保需要控制的设备已添加到公开列表

### 2. 版本要求

建议使用最新版本的Home Assistant：

- 新版本提供的工具和API更加完善
- 5月版本相比3月版本在工具支持上有明显改进

### 3. 调试方法

当控制效果未达到预期时：

**查看小智聊天记录:**

1. 检查小智如何理解和处理指令
2. 确认是否调用了Home Assistant工具
3. 分析调用参数是否正确

**已知问题:**

- 灯光控制可能与内置屏幕控制冲突
- 音乐控制可能与内置音乐功能冲突
- 这些问题将在下个月小智服务器支持内置工具选择后解决

### 4. 调试日志

如果Home Assistant function调用正确但执行异常：

1. 在Home Assistant中开启本插件的调试日志
2. 重现问题操作
3. 查看日志中的详细执行情况

## 演示视频

为了更好地了解插件功能，可以观看以下演示视频：

- [接入演示视频](https://www.bilibili.com/video/BV1XdjJzeEwe) - 基础安装和配置流程
- [控制电视演示](https://www.bilibili.com/video/BV18DM8zuEYV) - 通过自定义script实现电视控制
- [进阶教程](https://www.bilibili.com/video/BV1SruXzqEW5) - Home Assistant、LLM、MCP、小智的详细教程

## 故障排除

### 常见问题

**1. 连接失败**

- 检查小智MCP接入点地址是否正确
- 确认Home Assistant网络连接正常
- 检查防火墙设置

**2. 设备无法控制**

- 确认设备已在语音助手中公开
- 检查设备实体状态是否正常
- 验证设备是否支持相应操作

**3. 部分功能冲突**

- 临时禁用内置功能
- 调整设备命名避免冲突
- 等待小智服务器工具选择功能更新

**4. 响应延迟**

- 检查网络连接质量
- 优化Home Assistant性能
- 减少不必要的实体公开

### 调试技巧

1. 启用详细日志记录
2. 逐步测试基础功能
3. 对比正常工作的设备配置
4. 参考社区讨论和issues

## 社区支持

### 项目链接

- **GitHub仓库**: [ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)
- **问题反馈**: [GitHub Issues](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/issues)
- **功能请求**: [GitHub Discussions](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/discussions)
