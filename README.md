# py-xiaozhi

## 请先看这里！
- 仔细阅读/docs/使用文档.md 启动教程和文件说明都在里面了
- main是最新代码，每次更新都需要手动重新安装一次pip依赖防止我新增依赖后你们本地没有

[从零开始使用小智客户端（视频教程）](https://www.bilibili.com/video/BV1dWQhYEEmq/?vd_source=2065ec11f7577e7107a55bbdc3d12fce)

## 项目简介
py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
本仓库是基于[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)移植


## 环境要求
- Python 3.9.13+（推荐 3.12）最大支持版本3.12
- Windows/Linux/macOS

## 相关分支
- main 主分支
- feature/v1 第一个版本
- feature/visual 视觉分支


## 相关第三方开源项目
[小智手机端](https://github.com/TOM88812/xiaozhi-android-client)

[xiaozhi-esp32-server（第三方服务端）](https://github.com/xinnan-tech/xiaozhi-esp32-server)


## 演示
- [Bilibili 演示视频](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](https://github.com/user-attachments/assets/df8bd5d2-a8e6-4203-8084-46789fc8e9ad)
## 功能特点
- **语音交互**：支持语音输入与识别，实现智能人机交互。  
- **图形化界面**：提供直观易用的 GUI，方便用户操作。  
- **音量控制**：支持音量调节，适应不同环境需求。  
- **会话管理**：有效管理多轮对话，保持交互的连续性。  
- **加密音频传输**：保障音频数据的安全性，防止信息泄露。  
- **CLI 模式**：支持命令行运行，适用于嵌入式设备或无 GUI 环境。  
- **自动验证码处理**：首次使用时，程序自动复制验证码并打开浏览器，简化用户操作。  
- **唤醒词**：支持语音唤醒，免去手动操作的烦恼。  
- **键盘按键**：监听可以最小化视口

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
│   ├── 使用文档.md                  # 用户使用指南
│   └── 异常汇总.md                  # 常见错误及解决方案
├── libs                             # 依赖库目录
│   └── windows                      # Windows 平台特定库
│       └── opus.dll                 # Opus 音频编解码库
├── models                           # 语音模型目录（用于语音唤醒）
├── src                              # 源代码目录
│   ├── audio_codecs                 # 音频编解码模块
│   │   └── audio_codec.py           # 音频编解码器实现
│   ├── audio_processing             # 音频处理模块
│   │   └── wake_word_detect.py      # 语音唤醒词检测实现
│   ├── constants                    # 常量定义
│   │   └── constants.py             # 应用程序常量（状态、事件类型等）
│   ├── display                      # 显示界面模块
│   │   ├── base_display.py          # 显示界面基类
│   │   ├── cli_display.py           # 命令行界面实现
│   │   └── gui_display.py           # 图形用户界面实现
│   ├── iot                          # IoT设备相关模块
│   │   ├── things                   # 具体设备实现目录
│   │   │   ├── lamp.py              # 智能灯具控制实现
│   │   │   ├── music_player.py      # 音乐播放器实现
│   │   │   └── speaker.py           # 智能音箱控制实现
│   │   ├── thing.py                 # IoT设备基类定义
│   │   └── thing_manager.py         # IoT设备管理器（统一管理各类设备）
│   ├── protocols                    # 通信协议模块
│   │   ├── mqtt_protocol.py         # MQTT 协议实现（用于设备通信）
│   │   ├── protocol.py              # 协议基类
│   │   └── websocket_protocol.py    # WebSocket 协议实现
│   ├── utils                        # 工具类模块
│   │   ├── config_manager.py        # 配置管理器（单例模式）
│   │   ├── logging_config.py        # 日志配置
│   │   └── system_info.py           # 系统信息工具（处理 opus.dll 加载等）
│   └── application.py               # 应用程序主类（核心业务逻辑）
├── .gitignore                       # Git 忽略文件配置
├── LICENSE                          # 项目许可证
├── README.md                        # 项目说明文档
├── main.py                          # 程序入口点
├── requirements.txt                 # Python 依赖包列表（通用）
├── requirements_mac.txt             # macOS 特定依赖包列表
└── xiaozhi.spec                     # PyInstaller 打包配置文件
```

## 已实现功能

- [x] **新增 GUI 页面**，无需在控制台一直按空格  
- [x] **代码模块化**，拆分代码并封装为类，职责分明  
- [x] **音量调节**，可手动调整音量大小  
- [x] **自动获取 MAC 地址**，避免 MAC 地址冲突  
- [x] **支持 WSS 协议**，提升安全性和兼容性  
- [x] **GUI 新增小智表情与文本显示**，增强交互体验  
- [x] **新增命令行操控方案**，适用于 Linux 嵌入式设备  
- [x] **自动对话模式**，实现更自然的交互  
- [x] **语音唤醒**，支持唤醒词激活交互 (默认关闭需要手动开启)
- [x] **IoT 设备集成**，实现更多物联网功能  
- [x] **联网音乐播放**
- [x] **新增 Volume控制类统一声音改变**

## 待测试功能（不够稳定）

- [x] **WebRTC VAD 处理 AEC 消音问题**（未集成，但已实现 demo）  
- [x] **实时打断功能**（未集成，但已实现 demo）  
- [x] **实时对话模式**（未集成，但已实现 demo）  


## 优化

- [x] 修复 **goodbye 后无法重连** 的问题  
- [x] 解决 **macOS 和 Linux 运行异常**（原先使用 pycaw 处理音量导致）  
- [x] **优化“按住说话”按钮**，使其更明显  
- [x] **修复 Stream not open 错误**（目前 Windows 不再触发，其他系统待确认）  
- [x] 修复 **没有找到该设备的版本信息，请正确配置 OTA 地址提示**
- [x] 修复 **cli模式update_volume缺失问题**

## 待实现功能

- [ ] **新 GUI（Electron）**，提供更现代的用户界面

## 贡献
欢迎提交 Issues 和 Pull Requests！

## 感谢以下开源人员-排名不分前后
[Xiaoxia](https://github.com/78)

[zhh827](https://github.com/zhh827)

[四博智联-李洪刚](https://github.com/SmartArduino)

[HonestQiao](https://github.com/HonestQiao)

[vonweller](https://github.com/vonweller)

[孙卫公](https://space.bilibili.com/416954647)

[isamu2025](https://github.com/isamu2025)

[Rain120](https://github.com/Rain120)


## Star History
[![Star History Chart](https://api.star-history.com/svg?repos=Huang-junsen/py-xiaozhi&type=Date)](https://www.star-history.com/#Huang-junsen/py-xiaozhi&Date)