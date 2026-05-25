# XiaoZhi External MCP Integration Guide

This document describes how to integrate external MCP services into the XiaoZhi system for feature extension and third-party tool integration.

## Overview

In addition to built-in MCP tools, the XiaoZhi system also supports connecting to external MCP servers, enabling:
- Third-party tool integration
- Remote service invocation
- Distributed tool deployment
- Community tool sharing

## Architecture

### External MCP Architecture
```
XiaoZhi AI Platform     xiaozhi-mcphub          External MCP Server       Third-Party Tools
┌─────────────┐        ┌─────────────────┐      ┌─────────────────┐      ┌─────────────┐
│             │        │                 │      │                 │      │             │
│ MCP Client  │◄───────┤ MCP Server/Proxy│◄─────┤ MCP Server      │◄─────┤ Actual Tools│
│             │        │                 │      │                 │      │             │
└─────────────┘        └─────────────────┘      └─────────────────┘      └─────────────┘
```

### Connection Methods
1. **Standard Input/Output (stdio)**: Launches a subprocess and communicates via stdin/stdout pipes for inter-process communication. Suitable for local CLI tools such as Playwright, Amap, etc.
2. **Server-Sent Events (SSE)**: HTTP long-connection based event stream communication, providing real-time bidirectional communication similar to WebSocket
3. **Streamable HTTP (streamable-http)**: HTTP protocol encapsulation over TCP, supporting streaming data transmission. Suitable for remote API services and microservices
4. **OpenAPI**: Connection based on standard REST API specifications, automatically parsing OpenAPI specifications and generating tool interfaces. Suitable for standardized third-party API services

## Related Open-Source Projects
Community-developed XiaoZhi client projects providing integration methods for different platforms

### xiaozhi-mcphub (Companion Project)

**XiaoZhi MCP Hub** is an intelligent MCP tool bridge system optimized for the XiaoZhi AI platform, built on the excellent MCPHub project with added XiaoZhi platform integration and intelligent tool synchronization features.

- **Project Site**: [xiaozhi-mcphub](https://huangjunsen0406.github.io/xiaozhi-mcphub/)
- **GitHub**: [xiaozhi-mcphub](https://github.com/huangjunsen0406/xiaozhi-mcphub)
- **Core Features**: 
  - **XiaoZhi AI Platform Integration**: WebSocket automatic tool synchronization, real-time status updates, protocol bridging
  - **Enhanced MCP Management**: Supports stdio, SSE, HTTP protocols, hot-swap configuration, centralized console
  - **Smart Tool Routing**: Vector-based intelligent tool search and group management
  - **Security Authentication**: JWT + bcrypt user management, role-based access control
  - **Built-in MCP Store**: Various MCP tools available for online installation with hot updates, no restart required

### xiaozhi-client
- **Project Repository**: [xiaozhi-client](https://github.com/shenjingnan/xiaozhi-client)
- **Function**: XiaoZhi AI client, specifically designed for MCP integration and aggregation
- **Core Features**: 
  - **Multi-Endpoint Support**: Configurable multiple XiaoZhi endpoints, enabling multiple devices to share a single MCP configuration
  - **MCP Server Aggregation**: Aggregates multiple MCP Servers through standard methods for unified management
  - **Dynamic Tool Control**: Controls MCP Server tool visibility to avoid issues caused by too many tools
  - **Multiple Integration Methods**: Supports integration as a regular MCP Server into clients like Cursor/Cherry Studio
  - **Web Visual Configuration**: Modern web UI interface supporting remote configuration and management
  - **ModelScope Integration**: Supports ModelScope-hosted remote MCP services

### HyperChat
- **Project Site**: [HyperChat](https://github.com/BigSweetPotatoStudio/HyperChat)
- **Function**: Next-generation AI workspace, pioneering the "AI as Code" concept for a multi-platform intelligent collaboration platform
- **Core Features**: 
  - **AI as Code**: Configuration-driven AI capability management, supporting version control and team collaboration
  - **Workspace-Driven**: Project-centric AI environment isolation and management
  - **MCP Ecosystem Deep Integration**: Full MCP protocol support, rich built-in tools, and dynamic loading
  - **Multi-Platform Unified**: Web application, Electron desktop, CLI command-line, VSCode extension
- **Technical Highlights**:
  - Configurable AI agent system with specialized Agent customization
  - Multi-model parallel comparison testing (Claude, OpenAI, Gemini, etc.)
  - Intelligent content rendering (Artifacts, Mermaid, mathematical formulas)
  - Scheduled tasks and workflow automation
