# 小智MCP外挂接入指南

本文档介绍如何将外部MCP服务接入小智系统，实现功能扩展和第三方工具集成。

## 概述

小智系统除了内置的MCP工具外，还支持接入外部MCP服务器，实现：
- 第三方工具集成
- 远程服务调用
- 分布式工具部署
- 社区工具共享

## 架构说明

### 外挂式MCP架构
```
小智AI平台        xiaozhi-mcphub        外部MCP服务器        第三方工具
┌─────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌─────────────┐
│             │   │                 │   │                 │   │             │
│ MCP客户端   │◄──┤ MCP服务器/代理   │◄──┤ MCP服务器       │◄──┤ 实际工具    │
│             │   │                 │   │                 │   │             │
└─────────────┘   └─────────────────┘   └─────────────────┘   └─────────────┘
```

### 连接方式
1. **标准输入输出 (stdio)**: 启动子进程，通过stdin/stdout管道进行进程间通信，适用于本地CLI工具如Playwright、高德地图等
2. **服务器推送事件 (SSE)**: 基于HTTP长连接的事件流通信，提供类似WebSocket的实时双向通信能力
3. **流式HTTP (streamable-http)**: 基于TCP的HTTP协议封装，支持流式数据传输，适用于远程API服务和微服务
4. **OpenAPI**: 基于标准REST API规范的连接方式，自动解析OpenAPI规范并生成工具接口，适用于标准化的第三方API服务

## 相关开源项目
社区开发的小智客户端项目，提供不同平台的接入方式

### xiaozhi-mcphub （本项目配套）

**小智MCP Hub** 是专为小智AI平台优化的智能MCP工具桥接系统，基于优秀的MCPHub项目开发，增加了小智平台集成和智能工具同步功能。

- **项目地址**: [xiaozhi-mcphub](https://huangjunsen0406.github.io/xiaozhi-mcphub/)
- **GitHub**: [xiaozhi-mcphub](https://github.com/huangjunsen0406/xiaozhi-mcphub)
- **核心功能**: 
  - **小智AI平台集成**: WebSocket自动工具同步，实时状态更新，协议桥接
  - **增强的MCP管理**: 支持stdio、SSE、HTTP协议，热插拔配置，集中控制台
  - **智能工具路由**: 基于向量的智能工具搜索和分组管理
  - **安全认证机制**: JWT+bcrypt用户管理，角色权限控制
  - **内置mcp商店**: 多种mcp工具在线安装无需重启支持热更新 
  
### xiaozhi-client
- **项目地址**: [xiaozhi-client](https://github.com/shenjingnan/xiaozhi-client)
- **功能**: 小智 AI 客户端，专门用于 MCP 的对接和聚合
- **核心特性**: 
  - **多接入点支持**: 可配置多个小智接入点，实现多设备共享一个MCP配置
  - **MCP Server聚合**: 通过标准方式聚合多个MCP Server，统一管理
  - **动态工具控制**: 控制MCP Server工具的可见性，避免工具过多导致的异常
  - **多种集成方式**: 支持作为普通MCP Server集成到Cursor/Cherry Studio等客户端
  - **Web可视化配置**: 现代化的Web UI界面，支持远程配置和管理
  - **ModelScope集成**: 支持ModelScope托管的远程MCP服务

### HyperChat
- **项目地址**: [HyperChat](https://github.com/BigSweetPotatoStudio/HyperChat)
- **功能**: 下一代 AI 工作空间，首创"AI as Code"理念的多平台智能协作平台
- **核心特性**: 
  - **AI as Code**: 配置驱动的AI能力管理，支持版本控制和团队协作
  - **工作区驱动**: 以项目为核心的AI环境隔离和管理
  - **MCP生态深度集成**: 完整支持MCP协议，丰富的内置工具和动态加载
  - **多平台统一**: Web应用、Electron桌面、CLI命令行、VSCode插件
- **技术亮点**:
  - 配置化AI智能体系统，支持专业化Agent定制
  - 多模型并行对比测试（Claude、OpenAI、Gemini等）
  - 智能内容渲染（Artifacts、Mermaid、数学公式）
  - 定时任务和工作流自动化