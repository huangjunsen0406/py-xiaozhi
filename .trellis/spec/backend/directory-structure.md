# 目录结构

> Python 单仓库项目,所有运行时代码在 `src/`,以 hatchling 打 wheel(`pyproject.toml` → `[tool.hatch.build.targets.wheel] packages = ["src"]`)。

---

## 顶层布局

```
py-xiaozhi/
├── main.py                # 入口,解析 --mode/--protocol,初始化日志,启动 ServiceContainer
├── pyproject.toml         # 依赖 + ruff/black/isort/pytest 配置
├── requirements.txt
├── src/                   # 全部应用代码
├── scripts/               # 独立 CLI 脚本(音频扫描、目录树等)
├── config/                # 默认配置模板
├── models/                # ML 模型资源(sherpa-onnx、唤醒词)
├── libs/                  # 原生 / 二进制库
├── assets/                # 图标、字体、QML 资源
├── documents/             # 用户面向文档
└── logs/                  # 本地运行日志(已 gitignore)
```

---

## `src/` 子模块

每个顶层子包对应一个域。跨域 import **统一使用绝对路径**: `from src.<package>.<module> import X`。**禁止** 跨域使用相对 import。

| 子包 | 职责 | 关键文件 |
|---|---|---|
| `src/bootstrap/` | 应用装配,`ServiceContainer` 持有生命周期 | `container.py`、`protocols.py` |
| `src/core/` | 跨域基础设施 | `event_bus.py`、`state_manager.py`、`task_manager.py`、`protocol_manager.py` |
| `src/protocols/` | 与后端的传输层协议 | `protocol.py`、`mqtt_protocol.py`、`websocket_protocol.py` |
| `src/plugins/` | 接到 `ServiceContainer` 的插件子系统 | `base.py` (Plugin 基类)、`manager.py`、`audio.py`、`mcp.py`、`ui.py`、`wake_word.py`、`shortcuts/` |
| `src/audio_codecs/` | 音频编解码 / AEC | `audio_codec.py`、`opus_codec.py`、`aec_processor.py`、`music_decoder.py`、`audio_buffer.py`、`stream_manager.py`、`audio_converter.py` |
| `src/audio_processing/` | 唤醒词检测 + 关键词转换 | `wake_word_detect.py`、`keyword_converters/` |
| `src/mcp/` | MCP(Model Context Protocol)服务端 + 工具 | `mcp_server.py`、`tooling.py`、`decorators.py`、`tools/<name>/` |
| `src/iot/` | IoT 设备抽象 | `things/` |
| `src/activation/` | 设备激活流程 | `service.py` |
| `src/ui/` | UI 实现 | `gui/`(PySide6 + QML)、`cli/`、`gpio/`、`shared/`(事件桥、ViewModel) |
| `src/views/` | GUI 视图组件 | `main/`、`components/` |
| `src/logging/` | 基于 stdlib `logging` 的内部日志模块 | `__init__.py`(导出 `setup_logging`、`get_logger`)、`log_config.py`、`formatters.py`、`filters.py`、`log_handlers.py`、`context.py` |
| `src/utils/` | 进程级辅助 | `config_manager.py`、`resource_finder.py`、`audio_device.py`、`volume_controller.py`、`opus_loader.py`、`common_utils.py` |
| `src/constants/` | 枚举与冻结常量 | `constants.py`(`DeviceState`、`ListeningMode`、`AbortReason`)、`system.py`(`SystemConstants`、`InitializationStage`) |

---

## 新代码落在哪里

- **新插件 / 子系统** → 在 `src/plugins/` 下新文件,继承 `Plugin`(`src/plugins/base.py`)。在 `src/bootstrap/container.py` 注册。
- **新 MCP 工具** → `src/mcp/tools/<name>/` 下新包,`__init__.py` 里 import 工具模块,触发 `@mcp_tool` 注册。详见 `mcp-tool-pattern.md`。
- **新协议传输** → `src/protocols/` 下新文件,实现 `protocol.py` 中的 `Protocol` 接口。
- **跨域辅助函数** → `src/utils/`。**先搜后写** —— 已经存在不少助手(`resource_finder` 处理路径、`config_manager` 读配置、`audio_device` 查设备)。
- **常量 / 枚举** → `src/constants/`。不要在模块里散落字面量字符串。
- **配置 schema 变更** → 扩展 `src/utils/config_manager.py` 中的 `ConfigManager.DEFAULT_CONFIG`。单例访问: `ConfigManager.get_instance()`。

---

## 模块约定

- 每个包都有 `__init__.py`。子包在 `__init__.py` 里 re-export 公共 API(参考 `src/ui/cli/__init__.py`、`src/logging/__init__.py`)。
- 函数内的延迟 import 用于打破循环依赖或推迟重型 import(例如 `main.py` 中 `handle_activation` 内部 `from src.activation import ActivationService`)。当顶层 import 会循环或会过早拉入 PySide6 时,沿用此模式。
- 单例使用 class-method 风格: `ClassName.get_instance()`(见 `ConfigManager`、`LoggingConfigManager`、`McpServer`)。**不要** 引入其他单例风格。
