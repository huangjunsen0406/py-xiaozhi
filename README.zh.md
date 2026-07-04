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

## ❤️赞助商

> [想出现在这里？](mailto:huangjunsen0406@gmail.com)

<details open>
<summary>点击折叠</summary>

[**GitDo.net**](https://gitdo.net/)

感谢 GitDo.net 赞助了本项目！GitDo.net 是一个 AI API 聚合中转平台，一个 API Key 即可调用 **Claude、Gemini、GPT** 等主流模型，国内直连、无需魔法、稳定高效，是企业级 AI 编程和应用的理想选择。**[点击访问 GitDo.net](https://gitdo.net/)**

---

| | |
|---|---|
| [**Token能量站**](https://factory.pub/register?aff=3rXc) | 感谢 Token能量站 赞助了本项目！提供 **GPT、Grok、Claude** 等主流模型的 API 中转服务，稳定可靠，价格实惠。**[点击注册](https://factory.pub/register?aff=3rXc)** |
| [**良心AI**](https://www.openailaozu.com/register?aff=5Y7JEH5HBTXS) | 感谢 良心AI 赞助了本项目！提供 **GPT、Claude、Gemini** 等主流模型的 API 中转服务，国内直连，稳定高速。**[点击注册](https://www.openailaozu.com/register?aff=5Y7JEH5HBTXS)** |

</details>

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

## 参与贡献

- 仓库贡献入口请先阅读 [CONTRIBUTING.md](./CONTRIBUTING.md)
- 中文版本请查看 [CONTRIBUTING_ZH.md](./CONTRIBUTING_ZH.md)
- 详细文档请查看 [贡献指南](https://huangjunsen0406.github.io/py-xiaozhi/contributing)

## Maintainer Workflow

- 先将新提交归类为 `bug`、`feature`、`docs`、`refactor` 或 `maintenance`
- 优先审核范围清晰、验证步骤明确、上下文完整的 Pull Request
- 影响行为、配置或公共接口的改动需要同步更新文档
- 在 CI 通过且审核意见处理完成后再合并
- 合并后按正常发布流程进入版本，不承诺立即发布

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

## 项目统计

[![Star History Chart](https://api.star-history.com/svg?repos=huangjunsen0406/py-xiaozhi&type=Date)](https://www.star-history.com/#huangjunsen0406/py-xiaozhi&Date)

## 许可证

[MIT License](LICENSE)
