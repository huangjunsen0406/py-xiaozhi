# py-xiaozhi

## 项目简介
py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
本仓库是基于zhh827的[py-xiaozhi](https://github.com/zhh827/py-xiaozhi/tree/main)优化再新增功能

临时体验（windows）:https://wwny.lanzoub.com/iU3oO2pgij8j 密码:9gm3

## 项目背景
- 原始硬件项目：[xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
- 参考 Python 实现：[py-xiaozhi](https://github.com/zhh827/py-xiaozhi/tree/main)

## 演示
- [Bilibili 演示视频](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](https://github.com/user-attachments/assets/dd6ad32c-89ef-4d43-ad4d-63b1c9517923)

## 使用websocket连接小智同学服务器

- 小智官方服务端接口：wss://api.tenclass.net/xiaozhi/v1/
- 开源服务端(需自建)：[xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)

## 功能特点
- 按照虾哥1.1.2固件移植（向上兼容新的client_id）
- 语音交互
- 图形化界面
- 音量控制
- 会话管理
- 加密音频传输
- cli模式
- 第一次使用会自动复制验证码和打开浏览器

## 虾哥后台
[后台管理](https://xiaozhi.me/)

## 环境要求
- Python 3.8+（推荐 3.12）
- Windows/Linux/macOS

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
   - 从 https://opus-codec.org/downloads/ 下载
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
brew install portaudio opus python-tk ffmpeg
```


## 通用 Python 依赖（所有平台）

```bash
# 安装项目所需的 Python 包
pip3 install -r requirements.txt
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

## 已实现功能

- [x] 优化了 goodbye 后无法重连问题
- [x] 新增 GUI 页面，无需在控制台一直按空格
- [x] 拆分代码，封装为类，各司其职
- [x] 控制windows音量大小（mac/linux需要自行实现）
- [x] MAC_ADDR 自动获取（解决mac地址冲突问题）
- [x] wss协议的支持
- [x] 修复mac和linux的运行异常（原先使用pycaw来处理音频音量大小） 
- [x] GUI新增小智表情、文本显示
- [x] 修复按住说话按钮不明显问题
- [x] 新增了命令行的操控方案（方便linux嵌入式使用） 
- [x] 自动对话


## 待测试通过（不够稳定）
- [x] 新增webrtcvad处理aec消音问题 （未接入但已实现demo）
- [x] 新增实时打断 （未接入但已实现demo）
- [x] 唤醒词 （状态流转有点问题）
- [x] 实时对话 （未接入但已实现demo）
- [x] 联网音乐 （未接入但已实现demo,需要移植thing过来才行）

## 待实现功能
- [ ] 新 GUI （Electron）

## 贡献
欢迎提交 Issues 和 Pull Requests！

## 免责声明
本项目仅用于学习和研究目的，不得用于商业用途。

## 感谢以下开源人员-排名不分前后
[Xiaoxia](https://github.com/78)
[zhh827](https://github.com/zhh827)
[四博智联-李洪刚](https://github.com/SmartArduino)
[HonestQiao](https://github.com/HonestQiao)
