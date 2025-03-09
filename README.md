# py-xiaozhi

## 项目简介
py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
本仓库是基于[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)移植

临时体验（windows）:https://wwny.lanzoub.com/iU3oO2pgij8j 密码:9gm3


## 注意点：
- **如若使用xiaozhi-esp32-server作为服务端该项目只能自动对话才有反应**
- 使用第三方服务端时tts选TTS302AI就可以使用小智同款湾湾小何了
- windows系统无需挪动opus.dll，项目默认会自动引入
- 使用conda环境时安装ffmpeg和Opus
  - conda install conda-forge::libopus
  - conda install conda-forge::ffmpeg
## 环境要求
- Python 3.9.13+（推荐 3.12）
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

![Image](https://github.com/user-attachments/assets/dd6ad32c-89ef-4d43-ad4d-63b1c9517923)

## 功能特点
- **语音交互**：支持语音输入与识别，实现智能人机交互。  
- **图形化界面**：提供直观易用的 GUI，方便用户操作。  
- **音量控制**：支持音量调节，适应不同环境需求。  
- **会话管理**：有效管理多轮对话，保持交互的连续性。  
- **加密音频传输**：保障音频数据的安全性，防止信息泄露。  
- **CLI 模式**：支持命令行运行，适用于嵌入式设备或无 GUI 环境。  
- **自动验证码处理**：首次使用时，程序自动复制验证码并打开浏览器，简化用户操作。  
- **唤醒词**：支持语音唤醒，免去手动操作的烦恼。  
- **键盘按键**监听可以最小化视口

## 完整状态流转图

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

## 安装依赖

### Windows

1. 下载 FFmpeg：
   - 访问 https://ffmpeg.org/download.html
   - 将 bin 目录添加到系统 PATH

2. 如果 opus.dll 缺失：
   - 将 /libs/windows的 opus.dll 复制到应用程序目录或 C:\Windows\System32


### Linux (Debian/Ubuntu)

```bash
# 安装系统依赖
sudo apt-get update
sudo apt-get install python3-pyaudio portaudio19-dev ffmpeg libopus0 libopus-dev

# 安装 Python 包
pip install opuslib
```


## macOS

```bash
# 安装系统依赖
brew install portaudio opus python-tk ffmpeg gfortran
```

## 使用虚拟环境进行依赖安装

```bash
# 创建虚拟环境：
python3 -m venv .venv
# 激活虚拟环境：
source .venv/bin/activate
pip3 install -r requirements.txt
```

## 唤醒词模型
- [唤醒词模型下载](https://alphacephei.com/vosk/models)
- 下载完成后放至根目录/models
- 默认读取vosk-model-small-cn-0.22小模型
- ![Image](https://github.com/user-attachments/assets/ed534f03-ccdb-418d-88b4-ff5b4ceb5f9e)

## 通用 Python 依赖（所有平台）

```bash
# 安装项目所需的 Python 包 
pip install -r requirements.txt
# mac
pip install -r requirements_mac.txt
```

## GUI模式运行
```bash
python main.py
```


## CLI模式运行
```bash
python main.py --mode cli
```

## 使用说明
- 启动应用程序后，GUI 界面会自动连接
- 点击并按住 "按住说话" 按钮开始语音交互
- 松开按钮结束语音输入
- 自动模式点击开始对话即可
- gui模式-f2长按说话-f3打断
- cli模式-f2按一次自动对话-f3打断

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

## 待测试功能（不够稳定）

- [x] **WebRTC VAD 处理 AEC 消音问题**（未集成，但已实现 demo）  
- [x] **实时打断功能**（未集成，但已实现 demo）  
- [x] **实时对话模式**（未集成，但已实现 demo）  
- [x] **联网音乐播放**（未集成，但已实现 demo，需要移植 thing 组件）  

## 优化

- [x] 修复 **goodbye 后无法重连** 的问题  
- [x] 解决 **macOS 和 Linux 运行异常**（原先使用 pycaw 处理音量导致）  
- [x] **优化“按住说话”按钮**，使其更明显  
- [x] **修复 Stream not open 错误**（目前 Windows 不再触发，其他系统待确认）  
- [x] 修复 **没有找到该设备的版本信息，请正确配置 OTA 地址提示**
- [x] 修复 **cli模式update_volume缺失问题**

## 待实现功能

- [ ] **新 GUI（Electron）**，提供更现代的用户界面  
- [ ] **IoT 设备集成**，实现更多物联网功能  

## 贡献
欢迎提交 Issues 和 Pull Requests！

## 免责声明
本项目仅用于学习和研究目的，不得用于商业用途。

## 感谢以下开源人员-排名不分前后
[Xiaoxia](https://github.com/78)

[zhh827](https://github.com/zhh827)

[四博智联-李洪刚](https://github.com/SmartArduino)

[HonestQiao](https://github.com/HonestQiao)

[vonweller](https://github.com/vonweller)


## Star History
<a href="https://star-history.com/#Huang-junsen/py-xiaozhi&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Huang-junsen/py-xiaozhi&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Huang-junsen/py-xiaozhi&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Huang-junsen/py-xiaozhi&type=Date" />
 </picture>
</a>