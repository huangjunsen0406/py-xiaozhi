# py-xiaozhi
<p align="center">

[![Release](https://img.shields.io/github/v/release/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github&color=blue)](https://github.com/huangjunsen0406/py-xiaozhi/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg?style=flat-square)](https://opensource.org/licenses/MIT)
[![Stars](https://img.shields.io/github/stars/huangjunsen0406/py-xiaozhi?style=flat-square&logo=github)](https://github.com/huangjunsen0406/py-xiaozhi/stargazers)
[![Download](https://img.shields.io/github/downloads/huangjunsen0406/py-xiaozhi/total?style=flat-square&logo=github&color=52c41a1&maxAge=86400)](https://github.com/huangjunsen0406/py-xiaozhi/releases/latest)

</p>

English | [简体中文](README.md)

## Project Introduction
py-xiaozhi is a Python-based Xiaozhi voice client, designed to learn coding and experience AI voice interaction without hardware requirements. This repository is ported from [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32).

## Demo
- [Bilibili Demo Video](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](https://github.com/user-attachments/assets/df8bd5d2-a8e6-4203-8084-46789fc8e9ad)

## Features
- **AI Voice Interaction**: Supports voice input and recognition, enabling smart human-computer interaction with natural conversation flow.
- **Visual Multimodal**: Supports image recognition and processing, providing multimodal interaction capabilities and image content understanding.
- **IoT Device Integration**: Supports smart home device control, enabling more IoT functions and building a smart home ecosystem.
- **Online Music Playback**: Advanced Music Player: A high-performance music player built on Pygame, supporting play/pause/stop, progress control, lyric display, and local caching, delivering a more stable and smooth listening experience.
- **Voice Wake-up**: Supports wake word activation, eliminating manual operation (disabled by default, manual activation required).
- **Auto Dialogue Mode**: Implements continuous dialogue experience, enhancing user interaction fluidity.
- **Graphical Interface**: Provides intuitive GUI with Xiaozhi expressions and text display, enhancing visual experience.
- **Command Line Mode**: Supports CLI operation, suitable for embedded devices or environments without GUI.
- **Cross-platform Support**: Compatible with Windows 10+, macOS 10.15+, and Linux systems for use anywhere.
- **Volume Control**: Supports volume adjustment to adapt to different environmental requirements with unified sound control interface.
- **Session Management**: Effectively manages multi-turn dialogues to maintain interaction continuity.
- **Encrypted Audio Transmission**: Supports WSS protocol to ensure audio data security and prevent information leakage.
- **Automatic Verification Code Handling**: Automatically copies verification codes and opens browsers during first use, simplifying user operations.
- **Automatic MAC Address Acquisition**: Avoids MAC address conflicts and improves connection stability.
- **Modular Code**: Code is split and encapsulated into classes with clear responsibilities, facilitating secondary development.
- **Stability Optimization**: Fixes multiple issues including reconnection and cross-platform compatibility.

## System Requirements
- Python version: 3.9 >= version <= 3.12
- Supported operating systems: Windows 10+, macOS 10.15+, Linux
- Microphone and speaker devices

## Read This First!
- Carefully read /docs/使用文档.md for startup tutorials and file descriptions
- The main branch has the latest code; manually reinstall pip dependencies after each update to ensure you have new dependencies

[Zero to Xiaozhi Client (Video Tutorial)](https://www.bilibili.com/video/BV1dWQhYEEmq/?vd_source=2065ec11f7577e7107a55bbdc3d12fce)

## State Transition Diagram

```
                        +----------------+
                        |                |
                        v                |
+------+  Wake/Button  +------------+   |   +------------+
| IDLE | -----------> | CONNECTING | --+-> | LISTENING  |
+------+              +------------+       +------------+
   ^                                            |
   |                                            | Voice Recognition Complete
   |          +------------+                    v
   +--------- |  SPEAKING  | <-----------------+
     Playback +------------+
     Complete
```

## Upcoming Features
- [ ] **New GUI (Electron)**: Provides a more modern and beautiful user interface, optimizing the interaction experience.

## FAQ
- **Can't find audio device**: Please check if your microphone and speakers are properly connected and enabled.
- **Wake word not responding**: Check if the `USE_WAKE_WORD` setting in `config.json` is set to `true` and the model path is correct.
- **Network connection failure**: Check network settings and firewall configuration to ensure WebSocket or MQTT communication is not blocked.
- **Packaging failure**: Make sure PyInstaller is installed (`pip install pyinstaller`) and all dependencies are installed. Then re-execute `python scripts/build.py`

## Related Third-party Open Source Projects
[Xiaozhi Mobile Client](https://github.com/TOM88812/xiaozhi-android-client)

[xiaozhi-esp32-server (Open source server)](https://github.com/xinnan-tech/xiaozhi-esp32-server)

[XiaoZhiAI_server32_Unity(Unity Development)](https://gitee.com/vw112266/XiaoZhiAI_server32_Unity)

[IntelliConnect(Aiot Middleware)](https://github.com/ruanrongman/IntelliConnect)

[open-xiaoai(Xiaoai Audio Access Xiaozhi)](https://github.com/idootop/open-xiaoai.git)

## Related Branches
- main: Main branch
- feature/v1: First version
- feature/visual: Visual branch

## Project Structure

```
├── .github                          # GitHub related configurations
│   └── ISSUE_TEMPLATE               # Issue template directory
│       ├── bug_report.md            # Bug report template
│       ├── code_improvement.md      # Code improvement suggestion template
│       ├── documentation_improvement.md  # Documentation improvement template
│       └── feature_request.md       # Feature request template
├── config                           # Configuration directory
│   └── config.json                  # Application configuration file
├── docs                             # Documentation directory
│   ├── images                       # Documentation image resources
│   │   ├── 唤醒词.png               # Wake word setting example image
│   │   └── 群聊.jpg                 # Community chat group image
│   ├── 使用文档.md                  # User guide
│   └── 异常汇总.md                  # Common errors and solutions
├── hooks                            # PyInstaller hooks directory
│   ├── hook-opuslib.py              # opuslib hook
│   ├── hook-vosk.py                 # vosk hook
│   └── runtime_hook.py              # Runtime hook
├── libs                             # Dependencies directory
│   └── windows                      # Windows platform-specific libraries
│       └── opus.dll                 # Opus audio codec library
├── resources                        # Resource files directory
├── scripts                          # Utility scripts directory
│   ├── build.py                     # Packaging build script
│   ├── dir_tree.py                  # Generate directory tree structure script
│   └── py_audio_scanner.py          # Audio device scanning tool
├── src                              # Source code directory
│   ├── audio_codecs                 # Audio encoding/decoding module
│   │   └── audio_codec.py           # Audio codec implementation
│   ├── audio_processing             # Audio processing module
│   │   ├── vad_detector.py          # Voice activity detection (for real-time interruption)
│   │   └── wake_word_detect.py      # Wake word detection implementation
│   ├── constants                    # Constants definition
│   │   └── constants.py             # Application constants (states, event types, etc.)
│   ├── display                      # Display interface module
│   │   ├── base_display.py          # Display interface base class
│   │   ├── cli_display.py           # Command line interface implementation
│   │   └── gui_display.py           # Graphical user interface implementation
│   ├── iot                          # IoT device related module
│   │   ├── things                   # Specific device implementation directory
│   │   │   ├── CameraVL             # Camera and visual recognition module
│   │   │   │   ├── Camera.py        # Camera control implementation
│   │   │   │   └── VL.py            # Visual recognition implementation
│   │   │   ├── lamp.py              # Smart light control implementation
│   │   │   ├── music_player.py      # Music player implementation
│   │   │   ├── query_bridge_rag.py  # RAG query bridge implementation
│   │   │   ├── speaker.py           # volume controller
│   │   │   └── temperature_sensor.py # Temperature sensor implementation
│   │   ├── thing.py                 # IoT device base class definition
│   │   └── thing_manager.py         # IoT device manager (unified management)
│   ├── protocols                    # Communication protocol module
│   │   ├── mqtt_protocol.py         # MQTT protocol implementation (for device communication)
│   │   ├── protocol.py              # Protocol base class
│   │   └── websocket_protocol.py    # WebSocket protocol implementation
│   ├── utils                        # Utility classes module
│   │   ├── config_manager.py        # Configuration manager (singleton pattern)
│   │   ├── logging_config.py        # Logging configuration
│   │   ├── system_info.py           # System information tool (handling opus.dll loading, etc.)
│   │   └── volume_controller.py     # Volume control tool (cross-platform volume adjustment)
│   └── application.py               # Application main class (core business logic)
├── .gitignore                       # Git ignore file configuration
├── LICENSE                          # Project license
├── README.md                        # Project documentation (Chinese)
├── README.en.md                     # Project documentation (English)
├── main.py                          # Program entry point
├── requirements.txt                 # Python dependency package list (general)
├── requirements_mac.txt             # macOS specific dependency package list
```

## Contribution Guidelines
We welcome issue reports and code contributions. Please ensure you follow these specifications:

1. Code style complies with PEP8 standards
2. PR submissions include appropriate tests
3. Update relevant documentation

## Community and Support

### Thanks to the Following Open Source Contributors
> In no particular order

[Xiaoxia](https://github.com/78)
[zhh827](https://github.com/zhh827)
[SmartArduino-Li Honggang](https://github.com/SmartArduino)
[HonestQiao](https://github.com/HonestQiao)
[vonweller](https://github.com/vonweller)
[Sun Weigong](https://space.bilibili.com/416954647)
[isamu2025](https://github.com/isamu2025)
[Rain120](https://github.com/Rain120)
[kejily](https://github.com/kejily)
[Radio bilibili Jun](https://space.bilibili.com/119751)

### Sponsorship Support

<div align="center">
  <h3>Thanks to All Sponsors ❤️</h3>
  <p>Whether it's API resources, device compatibility testing, or financial support, every contribution makes the project more complete</p>
  
  <a href="https://py-xiaozhi.vercel.app/sponsors.html" target="_blank">
    <img src="https://img.shields.io/badge/View-Sponsors-brightgreen?style=for-the-badge&logo=github" alt="View Sponsors">
  </a>
  <a href="https://py-xiaozhi.vercel.app/sponsors.html" target="_blank">
    <img src="https://img.shields.io/badge/Become-Sponsor-orange?style=for-the-badge&logo=heart" alt="Become a Sponsor">
  </a>
</div>

## Project Statistics
[![Star History Chart](https://api.star-history.com/svg?repos=huangjunsen0406/py-xiaozhi&type=Date)](https://www.star-history.com/#huangjunsen0406/py-xiaozhi&Date)

## License
[MIT License](LICENSE) 