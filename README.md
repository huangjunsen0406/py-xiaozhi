# py-xiaozhi

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
</p>

简体中文 | [English](README.en.md)

## 项目简介

py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
本仓库是基于[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)移植

## 演示

- [Bilibili 演示视频](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](./documents/docs/guide/images/系统界面.png)

## 功能特点

- **AI语音交互**：支持语音输入与识别，实现智能人机交互，提供自然流畅的对话体验。
- **视觉多模态**：支持图像识别和处理，提供多模态交互能力，理解图像内容。
- **IoT 设备集成**：
  - 支持智能家居设备控制，包括灯光、音量、温度传感器等
  - 集成Home Assistant智能家居平台，控制灯具、开关、数值控制器和按钮设备
  - 提供倒计时器功能，支持延时执行命令
  - 内置多种虚拟设备和物理设备驱动，可轻松扩展
- **联网音乐播放**：基于pygame实现的高性能音乐播放器，支持播放／暂停／停止、进度控制、歌词显示和本地缓存，提供更稳定的音乐播放体验。
- **语音唤醒**：支持唤醒词激活交互，免去手动操作的烦恼（默认关闭需要手动开启）。
- **自动对话模式**：实现连续对话体验，提升用户交互流畅度。
- **图形化界面**：提供直观易用的 GUI，支持小智表情与文本显示，增强视觉体验。
- **命令行模式**：支持 CLI 运行，适用于嵌入式设备或无 GUI 环境。
- **跨平台支持**：兼容 Windows 10+、macOS 10.15+ 和 Linux 系统，随时随地使用。
- **音量控制**：支持音量调节，适应不同环境需求，统一声音控制接口。
- **会话管理**：有效管理多轮对话，保持交互的连续性。
- **加密音频传输**：支持 WSS 协议，保障音频数据的安全性，防止信息泄露。
- **自动验证码处理**：首次使用时，程序自动复制验证码并打开浏览器，简化用户操作。
- **自动获取 MAC 地址**：避免 MAC 地址冲突，提高连接稳定性。
- **代码模块化**：拆分代码并封装为类，职责分明，便于二次开发。
- **稳定性优化**：修复多项问题，包括断线重连、跨平台兼容等。

## 系统要求

- 3.9 >= Python版本 <= 3.12
- 支持的操作系统：Windows 10+、macOS 10.15+、Linux
- 麦克风和扬声器设备

## 请先看这里

- 仔细阅读 [项目文档](https://huangjunsen0406.github.io/py-xiaozhi/) 启动教程和文件说明都在里面了
- main是最新代码，每次更新都需要手动重新安装一次pip依赖防止我新增依赖后你们本地没有

[从零开始使用小智客户端（视频教程）](https://www.bilibili.com/video/BV1dWQhYEEmq/?vd_source=2065ec11f7577e7107a55bbdc3d12fce)

## 配置系统

项目使用分层配置系统，主要包括：

1. **基础配置**：设置基本运行参数，位于`config/config.json`
2. **设备激活**：设备身份信息，存储在`config/efuse.json`
3. **唤醒词配置**：语音唤醒相关设置
4. **物联网设备**：支持各种IoT设备的配置，包括温度传感器和Home Assistant集成

详细配置说明请参考 [配置说明文档](./documents/docs/guide/02_配置说明.md)

## IoT功能

py-xiaozhi提供丰富的IoT设备控制功能：

- **虚拟设备**：灯光控制、音量调节、倒计时器等
- **物理设备集成**：温度传感器、摄像头等
- **Home Assistant集成**：通过HTTP API接入智能家居系统
- **自定义设备扩展**：提供完整的设备定义和注册框架

支持的设备类型和使用示例请参考 [IoT功能说明](./documents/docs/guide/05_IoT功能说明.md)

## 状态流转图

```
                        +----------------+
                        |                |
                        v                |
+------+  唤醒词/按钮  +------------+   |   +------------+
| IDLE | -----------> | CONNECTING | --+-> | LISTENING  |
+------+              +------------+       +------------+
   ^                                            |
   |                                            | 语音识别完成
   |          +------------+                    v
   +--------- |  SPEAKING  | <-----------------+
     完成播放 +------------+
```

## 待实现功能

- [ ] **新 GUI（Electron）**：提供更现代、美观的用户界面，优化交互体验。

## 常见问题

- **找不到音频设备**：请检查麦克风和扬声器是否正常连接和启用。
- **唤醒词不响应**：请检查`config.json`中的`USE_WAKE_WORD`设置是否为`true`，以及模型路径是否正确。
- **网络连接失败**：请检查网络设置和防火墙配置，确保WebSocket或MQTT通信未被阻止。
- **打包失败**：确保已安装PyInstaller (`pip install pyinstaller`)，并且所有依赖项都已安装。然后重新执行`python scripts/build.py`
- **IoT设备不响应**：检查对应设备的配置信息是否正确，如Home Assistant的URL和Token。

## 相关第三方开源项目

[小智手机端](https://github.com/TOM88812/xiaozhi-android-client)

[xiaozhi-esp32-server（开源服务端）](https://github.com/xinnan-tech/xiaozhi-esp32-server)

[XiaoZhiAI_server32_Unity(Unity开发)](https://gitee.com/vw112266/XiaoZhiAI_server32_Unity)

[IntelliConnect(Aiot中间件)](https://github.com/ruanrongman/IntelliConnect)

[open-xiaoai(小爱音响接入小智)](https://github.com/idootop/open-xiaoai.git)

## 项目结构

```
├── .github                 # GitHub 相关配置
├── assets                  # 资源文件（表情动画等）
├── cache                   # 缓存目录（音乐等临时文件）
├── config                  # 配置文件目录
├── documents               # 文档目录
├── hooks                   # PyInstaller钩子目录
├── libs                    # 依赖库目录
├── scripts                 # 实用脚本目录
├── src                     # 源代码目录
│   ├── audio_codecs        # 音频编解码模块
│   ├── audio_processing    # 音频处理模块
│   ├── constants           # 常量定义
│   ├── display             # 显示界面模块
│   ├── iot                 # IoT设备相关模块
│   │   └── things          # 具体设备实现目录
│   ├── network             # 网络通信模块
│   ├── protocols           # 通信协议模块
│   └── utils               # 工具类模块
```

## 贡献指南

欢迎提交问题报告和代码贡献。请确保遵循以下规范：

1. 代码风格符合PEP8规范
2. 提交的PR包含适当的测试
3. 更新相关文档

## 社区与支持

### 感谢以下开源人员
>
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

### 赞助支持

<div align="center">
  <h3>感谢所有赞助者的支持 ❤️</h3>
  <p>无论是接口资源、设备兼容测试还是资金支持，每一份帮助都让项目更加完善</p>
  
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
