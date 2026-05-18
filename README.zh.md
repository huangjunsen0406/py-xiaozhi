<p align="center" class="trendshift">
  <a href="https://trendshift.io/repositories/14130" target="_blank">
    <img src="https://trendshift.io/api/badge/repositories/14130" alt="Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
  </a>
</p>
<p align="center">
  <a href="https://github.com/huangjunsen0406/py-xiaozhi/releases/latest">
    <img src="https://img.shields.io/github/v/release/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github&color=blue" alt="Release"/>
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License: MIT"/>
  </a>
  <a href="https://github.com/huangjunsen0406/py-xiaozhi/stargazers">
    <img src="https://img.shields.io/github/stars/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github" alt="Stars"/>
  </a>
  <a href="https://github.com/huangjunsen0406/py-xiaozhi/releases/latest">
    <img src="https://img.shields.io/github/downloads/huangjunsen0406/py-xiaozhi/total?style=flat-square&logo=github&color=52c41a1&maxAge=86400" alt="Download"/>
  </a>
  <a href="https://gitee.com/huang-jun-sen/py-xiaozhi">
    <img src="https://img.shields.io/badge/Gitee-FF5722?style=flat-square&logo=gitee" alt="Gitee"/>
  </a>
  <a href="https://huangjunsen0406.github.io/py-xiaozhi/guide/00_%E6%96%87%E6%A1%A3%E7%9B%AE%E5%BD%95.html">
    <img alt="使用文档" src="https://img.shields.io/badge/使用文档-点击查看-blue?labelColor=2d2d2d" />
  </a>
  <a href="https://atomgit.com/huangjunsen0406/py-xiaozhi">
    <img src="./assets/AtomGit.svg" alt="AtomGit" height="20"/>
  </a>
</p>

简体中文 | [English](README.md)

## 项目简介

py-xiaozhi 是一个轻量级、跨平台的多模态 AI 交互主控框架，基于 Python 异步架构，支持实时语音、视觉识别和 IoT 设备控制。可部署于 Windows / macOS / Linux 桌面以及 Raspberry Pi、RDK 等 ARM 嵌入式平台，向下对接具身智能硬件，向上接入大语言模型，开箱即用。

> 本项目从 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) 移植演进而来，已被 [D-Robotics 官方生态 (xiaozhi-in-rdk)](https://github.com/D-Robotics/xiaozhi-in-rdk) 深度适配。

> **重要提示**
>
> - 请先阅读 [项目文档](https://huangjunsen0406.github.io/py-xiaozhi/)，启动教程和配置说明都在里面
> - main 是最新代码，每次更新后请重新安装 pip 依赖
> - **如果你已经基于本项目进行了二次开发，请不要直接合并最新代码**，新版本架构已大幅重构，强行合并会导致大量冲突。建议以旧版本为基础继续维护，或参考新架构重新适配
> - [从零开始使用小智客户端（视频教程）](https://www.bilibili.com/video/BV1dWQhYEEmq/)

## 演示

- [Bilibili 演示视频](https://www.bilibili.com/video/BV1HmPjeSED2/)

![系统界面](./documents/docs/guide/images/系统界面.png)

## 功能特点

- **AI 语音交互** — 语音输入与识别，自然流畅的对话体验
- **视觉多模态** — 图像识别和处理，理解图像内容
- **智能唤醒** — 多种唤醒词激活，免手动操作（可配置）
- **自动对话模式** — 连续对话，提升交互流畅度
- **MCP 工具生态** — 音乐播放、摄像头、截图、应用管理、天气查询、音量控制
- **Opus 编解码** — 音频编解码和实时重采样
- **唤醒词检测** — 基于 Sherpa-ONNX 离线识别，支持多唤醒词和拼音匹配
- **多界面模式** — GUI（PySide6 + QML）/ CLI / GPIO，适应不同环境
- **系统托盘 & 全局快捷键** — 后台运行，快捷操作
- **WebSocket / MQTT** — 双协议通信，支持 WSS 加密传输
- **设备激活** — v1/v2 双协议，自动验证码和设备指纹
- **跨平台** — Windows 10+ / macOS 10.15+ / Linux

## 相关项目

- [xiaozhi-desktop](https://xiaozhi.junsen.online) — Electron 桌面版，支持 AEC 回声消除、Live2D、悬浮窗等显示模式，提供 Windows / macOS 安装包

## 快速开始

**环境要求**：Python >= 3.10，麦克风和扬声器，稳定网络连接

```bash
# 克隆项目
git clone https://github.com/huangjunsen0406/py-xiaozhi.git
cd py-xiaozhi

# 基础安装（CLI / GPIO 模式）
uv sync                        # 推荐
# 或: pip install -e .

# GUI 模式（额外安装 PySide6 + qasync）
uv sync --extra gui            # 推荐
# 或: pip install -e '.[gui]'

# 运行
python main.py                 # GUI 模式（默认）
python main.py --mode cli      # CLI 模式
python main.py --protocol mqtt # MQTT 协议
```

## 项目结构

```
py-xiaozhi/
├── main.py                     # 应用程序主入口
├── src/
│   ├── bootstrap/              # 应用引导与依赖注入
│   ├── core/                   # 核心基础设施（事件总线、状态管理等）
│   ├── plugins/                # 插件系统（音频、UI、MCP、唤醒词、快捷键）
│   ├── protocols/              # 通信协议（WebSocket / MQTT）
│   ├── audio_codecs/           # 音频编解码
│   ├── audio_processing/       # 唤醒词检测
│   ├── activation/             # 设备激活
│   ├── mcp/                    # MCP 工具系统
│   │   └── tools/              # 工具模块（music/camera/screenshot/app/weather/volume）
│   ├── ui/                     # 用户界面
│   │   ├── gui/                # PySide6 + QML 图形界面
│   │   ├── cli/                # 命令行界面
│   │   └── gpio/               # GPIO 嵌入式界面
│   └── utils/                  # 工具函数
├── libs/                       # 第三方原生库（libopus / webrtc_apm）
├── models/                     # 语音唤醒模型
├── documents/                  # VitePress 文档站
└── pyproject.toml              # 项目配置
```

## 状态流转

```
                    +----------------+
                    |                |
                    v                |
+------+  唤醒/按钮  +------------+  |   +------------+
| IDLE | ---------> | CONNECTING | -+-> | LISTENING  |
+------+            +------------+      +------------+
   ^                                          |
   |                                          | 语音识别完成
   |        +------------+                    v
   +------- |  SPEAKING  | <-----------------+
    完成播放 +------------+
```

## 贡献指南

欢迎提交 Issue 和 PR，请确保：

1. 代码风格符合 PEP8 规范
2. PR 包含适当的测试
3. 更新相关文档

## 感谢

> 排名不分前后

[Xiaoxia](https://github.com/78)
[zhh827](https://github.com/zhh827)
[四博智联-李洪刚](https://github.com/SmartArduino)
[HonestQiao](https://github.com/HonestQiao)
[vonweller](https://github.com/vonweller)
[孙卫公](https://space.bilibili.com/416954647)
[isamu2025](https://github.com/isamu2025)
[Rain120](https://github.com/Rain120)
[kejily](https://github.com/kejily)
[电波bilibili君](https://space.bilibili.com/119751)
[赛搏智能](https://shop115087494.m.taobao.com/?refer=https%3A%2F%2Fm.tb.cn%2F)

## 赞助支持

<div align="center">
  <p>感谢所有赞助者的支持，无论是接口资源、设备兼容测试还是资金支持，每一份帮助都让项目更加完善</p>
  <a href="https://huangjunsen0406.github.io/py-xiaozhi/sponsors/" target="_blank">
    <img src="https://img.shields.io/badge/查看-赞助者名单-brightgreen?style=for-the-badge&logo=github" alt="赞助者名单">
  </a>
  <a href="https://huangjunsen0406.github.io/py-xiaozhi/sponsors/" target="_blank">
    <img src="https://img.shields.io/badge/成为-项目赞助者-orange?style=for-the-badge&logo=heart" alt="成为赞助者">
  </a>
</div>

## 项目统计

[![Star History Chart](https://api.star-history.com/svg?repos=huangjunsen0406/py-xiaozhi&type=Date)](https://www.star-history.com/#huangjunsen0406/py-xiaozhi&Date)

## 许可证

[MIT License](LICENSE)
