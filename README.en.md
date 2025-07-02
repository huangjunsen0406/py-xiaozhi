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
    <img alt="Usage Docs" src="https://img.shields.io/badge/Usage Docs-View-blue?labelColor=2d2d2d" />
  </a>
</p>

English | [简体中文](README.md)

## Project Introduction

py-xiaozhi is a Python-based Xiaozhi voice client, designed to learn coding and experience AI voice interaction without hardware requirements. This repository is ported from [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32).

## Demo

- [Bilibili Demo Video](https://www.bilibili.com/video/BV1HmPjeSED2/#reply255921347937)

![Image](./documents/docs/guide/images/系统界面.png)

## Features

- **AI Voice Interaction**: Supports voice input and recognition, enabling smart human-computer interaction with natural conversation flow.
- **Visual Multimodal**: Supports image recognition and processing, providing multimodal interaction capabilities and image content understanding.
- **IoT Device Integration**:
  - Supports smart home device control including lights, volume, temperature sensors, etc.
  - Integrates with Home Assistant smart home platform to control lights, switches, number controllers, and buttons
  - Provides countdown timer functionality for delayed command execution
  - Features built-in virtual devices and physical device drivers, easily extensible
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

## Read This First

- Carefully read [项目文档](https://huangjunsen0406.github.io/py-xiaozhi/) for startup tutorials and file descriptions
- The main branch has the latest code; manually reinstall pip dependencies after each update to ensure you have new dependencies

[Zero to Xiaozhi Client (Video Tutorial)](https://www.bilibili.com/video/BV1dWQhYEEmq/?vd_source=2065ec11f7577e7107a55bbdc3d12fce)

## Configuration System

The project uses a layered configuration system, including:

1. **Basic Configuration**: Sets basic runtime parameters, located in `config/config.json`
2. **Device Activation**: Device identity information, stored in `config/efuse.json`
3. **Wake Word Settings**: Voice wake-up related configuration
4. **IoT Devices**: Configuration for various IoT devices, including temperature sensors and Home Assistant integration

For detailed configuration instructions, please refer to [Configuration Documentation](./documents/docs/guide/02_配置说明.md)

## IoT Functionality

py-xiaozhi provides rich IoT device control features:

- **Virtual Devices**: Light control, volume adjustment, countdown timers, etc.
- **Physical Device Integration**: Temperature sensors, cameras, etc.
- **Home Assistant Integration**: Connect to smart home systems via HTTP API
- **Custom Device Extension**: Complete framework for device definition and registration

For supported device types and usage examples, please refer to [IoT Functionality Guide](./documents/docs/guide/05_IoT功能说明.md)

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
- **IoT devices not responding**: Check if the corresponding device configuration information is correct, such as Home Assistant URL and Token.

## Related Third-party Open Source Projects

[Xiaozhi Mobile Client](https://github.com/TOM88812/xiaozhi-android-client)

[xiaozhi-esp32-server (Open source server)](https://github.com/xinnan-tech/xiaozhi-esp32-server)

[XiaoZhiAI_server32_Unity(Unity Development)](https://gitee.com/vw112266/XiaoZhiAI_server32_Unity)

[IntelliConnect(Aiot Middleware)](https://github.com/ruanrongman/IntelliConnect)

[open-xiaoai(Xiaoai Audio Access Xiaozhi)](https://github.com/idootop/open-xiaoai.git)

## Project Structure

```
├── .github                 # GitHub related configurations
├── assets                  # Resource files (emotion animations, etc.)
├── cache                   # Cache directory (music and temporary files)
├── config                  # Configuration directory
├── documents               # Documentation directory
├── hooks                   # PyInstaller hooks directory
├── libs                    # Dependencies directory
├── scripts                 # Utility scripts directory
├── src                     # Source code directory
│   ├── audio_codecs        # Audio encoding/decoding module
│   ├── audio_processing    # Audio processing module
│   ├── constants           # Constants definition
│   ├── display             # Display interface module
│   ├── iot                 # IoT device related module
│   │   └── things          # Specific device implementation directory
│   ├── network             # Network communication module
│   ├── protocols           # Communication protocol module
│   └── utils               # Utility classes module
```

## Contribution Guidelines

We welcome issue reports and code contributions. Please ensure you follow these specifications:

1. Code style complies with PEP8 standards
2. PR submissions include appropriate tests
3. Update relevant documentation

## Community and Support

### Thanks to the Following Open Source Contributors
>
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
  
  <a href="https://huangjunsen0406.github.io/py-xiaozhi/sponsors/" target="_blank">
    <img src="https://img.shields.io/badge/View-Sponsors-brightgreen?style=for-the-badge&logo=github" alt="View Sponsors">
  </a>
  <a href="https://huangjunsen0406.github.io/py-xiaozhi/sponsors/" target="_blank">
    <img src="https://img.shields.io/badge/Become-Sponsor-orange?style=for-the-badge&logo=heart" alt="Become a Sponsor">
  </a>
</div>

## Project Statistics

[![Star History Chart](https://api.star-history.com/svg?repos=huangjunsen0406/py-xiaozhi&type=Date)](https://www.star-history.com/#huangjunsen0406/py-xiaozhi&Date)

## License

[MIT License](LICENSE)
