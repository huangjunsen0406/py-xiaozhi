# py-xiaozhi
<p align="center">

[![Release](https://img.shields.io/github/v/release/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github&color=blue)](https://github.com/huangjunsen0406/py-xiaozhi/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github)](https://github.com/huangjunsen0406/py-xiaozhi/stargazers)
[![Download](https://img.shields.io/github/downloads/huangjunsen0406/py-xiaozhi/total?style=flat-square&logo=github&color=52c41a1&maxAge=86400)](https://github.com/huangjunsen0406/py-xiaozhi/releases/latest)
</p>


简体中文 | [English](README.en.md)

## 项目简介
py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
本仓库是基于[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)移植

## 演示
- [Bilibili 演示视频](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](https://github.com/user-attachments/assets/df8bd5d2-a8e6-4203-8084-46789fc8e9ad)

## 功能特点
- **AI语音交互**：支持语音输入与识别，实现智能人机交互，提供自然流畅的对话体验。
- **视觉多模态**：支持图像识别和处理，提供多模态交互能力，理解图像内容。
- **IoT 设备集成**：支持智能家居设备控制，实现更多物联网功能，打造智能家居生态。
- **联网音乐播放**：基于pygame实现的高性能音乐播放器，支持歌词显示和本地缓存，支持播放／暂停／停止、进度控制、歌词显示和本地缓存，提供更稳定的音乐播放体验。
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

## 请先看这里！
- 仔细阅读/docs/使用文档.md 启动教程和文件说明都在里面了
- main是最新代码，每次更新都需要手动重新安装一次pip依赖防止我新增依赖后你们本地没有

[从零开始使用小智客户端（视频教程）](https://www.bilibili.com/video/BV1dWQhYEEmq/?vd_source=2065ec11f7577e7107a55bbdc3d12fce)

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

## 相关第三方开源项目
[小智手机端](https://github.com/TOM88812/xiaozhi-android-client)

[xiaozhi-esp32-server（开源服务端）](https://github.com/xinnan-tech/xiaozhi-esp32-server)

[XiaoZhiAI_server32_Unity(Unity开发)](https://gitee.com/vw112266/XiaoZhiAI_server32_Unity)

[IntelliConnect(Aiot中间件)](https://github.com/ruanrongman/IntelliConnect)

[open-xiaoai(小爱音响接入小智)](https://github.com/idootop/open-xiaoai.git)

## 相关分支
- main 主分支
- feature/v1 第一个版本
- feature/visual 视觉分支

## 项目结构

```
├── .github                          # GitHub 相关配置
│   └── ISSUE_TEMPLATE               # Issue 模板目录
│       ├── bug_report.md            # Bug 报告模板
│       ├── code_improvement.md      # 代码改进建议模板
│       ├── documentation_improvement.md  # 文档改进建议模板
│       └── feature_request.md       # 功能请求模板
├── config                           # 配置文件目录
│   └── config.json                  # 应用程序配置文件
├── docs                             # 文档目录
│   ├── images                       # 文档图片资源
│   │   ├── 唤醒词.png               # 唤醒词设置示例图
│   │   └── 群聊.jpg                 # 社区交流群图片
│   ├── 使用文档.md                  # 用户使用指南
│   └── 异常汇总.md                  # 常见错误及解决方案
├── hooks                            # PyInstaller钩子目录
│   ├── hook-opuslib.py              # opuslib钩子
│   ├── hook-vosk.py                 # vosk钩子
│   └── runtime_hook.py              # 运行时钩子
├── libs                             # 依赖库目录
│   └── windows                      # Windows 平台特定库
│       └── opus.dll                 # Opus 音频编解码库
├── resources                        # 资源文件目录
├── scripts                          # 实用脚本目录
│   ├── build.py                     # 打包构建脚本
│   ├── dir_tree.py                  # 生成目录树结构脚本
│   └── py_audio_scanner.py          # 音频设备扫描工具
├── src                              # 源代码目录
│   ├── audio_codecs                 # 音频编解码模块
│   │   └── audio_codec.py           # 音频编解码器实现
│   ├── audio_processing             # 音频处理模块
│   │   ├── vad_detector.py          # 语音活动检测实现（用于实时打断）
│   │   └── wake_word_detect.py      # 语音唤醒词检测实现
│   ├── constants                    # 常量定义
│   │   └── constants.py             # 应用程序常量（状态、事件类型等）
│   ├── display                      # 显示界面模块
│   │   ├── base_display.py          # 显示界面基类
│   │   ├── cli_display.py           # 命令行界面实现
│   │   └── gui_display.py           # 图形用户界面实现
│   ├── iot                          # IoT设备相关模块
│   │   ├── things                   # 具体设备实现目录
│   │   │   ├── CameraVL             # 摄像头与视觉识别模块
│   │   │   │   ├── Camera.py        # 摄像头控制实现
│   │   │   │   └── VL.py            # 视觉识别实现
│   │   │   ├── lamp.py              # 智能灯具控制实现
│   │   │   ├── music_player.py      # 音乐播放器实现
│   │   │   ├── query_bridge_rag.py  # RAG查询桥接实现
│   │   │   ├── speaker.py           # 音量控制器
│   │   │   └── temperature_sensor.py # 温度传感器实现
│   │   ├── thing.py                 # IoT设备基类定义
│   │   └── thing_manager.py         # IoT设备管理器（统一管理各类设备）
│   ├── protocols                    # 通信协议模块
│   │   ├── mqtt_protocol.py         # MQTT 协议实现（用于设备通信）
│   │   ├── protocol.py              # 协议基类
│   │   └── websocket_protocol.py    # WebSocket 协议实现
│   ├── utils                        # 工具类模块
│   │   ├── config_manager.py        # 配置管理器（单例模式）
│   │   ├── logging_config.py        # 日志配置
│   │   ├── system_info.py           # 系统信息工具（处理 opus.dll 加载等）
│   │   └── volume_controller.py     # 音量控制工具（跨平台音量调节）
│   └── application.py               # 应用程序主类（核心业务逻辑）
├── .gitignore                       # Git 忽略文件配置
├── LICENSE                          # 项目许可证
├── README.md                        # 项目说明文档
├── main.py                          # 程序入口点
├── requirements.txt                 # Python 依赖包列表（通用）
├── requirements_mac.txt             # macOS 特定依赖包列表
```

## 贡献指南
欢迎提交问题报告和代码贡献。请确保遵循以下规范：

1. 代码风格符合PEP8规范
2. 提交的PR包含适当的测试
3. 更新相关文档

## 社区与支持

### 感谢以下开源人员
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
  
  <a href="https://py-xiaozhi.vercel.app/sponsors.html" target="_blank">
    <img src="https://img.shields.io/badge/查看-赞助者名单-brightgreen?style=for-the-badge&logo=github" alt="赞助者名单">
  </a>
  <a href="https://py-xiaozhi.vercel.app/sponsors.html" target="_blank">
    <img src="https://img.shields.io/badge/成为-项目赞助者-orange?style=for-the-badge&logo=heart" alt="成为赞助者">
  </a>
</div>

## 项目统计
[![Star History Chart](https://api.star-history.com/svg?repos=huangjunsen0406/py-xiaozhi&type=Date)](https://www.star-history.com/#huangjunsen0406/py-xiaozhi&Date)

## 许可证
[MIT License](LICENSE)