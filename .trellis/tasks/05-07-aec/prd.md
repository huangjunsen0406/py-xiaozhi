# PRD: 去除 AEC 功能(第一步:清理死代码)

## 背景

当前仓库存在 `src/audio_codecs/aec_processor.py` (461 行) 和 `scripts/webrtc_aec_demo.py` (700+ 行)。代码扫描结果:

- `AECProcessor` 类**没有任何被实例化或 import 的位置**(grep `AECProcessor`、`aec_processor`、`from libs.webrtc_apm import` 全仓库,只有 aec_processor.py 自己 + 独立 demo 脚本)。
- `audio_codec.py` 主类内部**完全不引用 AEC**(grep `aec/AEC` 0 命中);整条 `_input_callback` → 转换 → opus 编码 → listener 分发 的链路上没有 AEC 介入点。
- `AECProcessor.process_audio(capture_audio)` 这个入口方法在 src/ 下 0 个 caller。
- `AudioListener` 协议要求 `on_audio_data(...)`,而 `AECProcessor` 没实现该方法,即便有人想把它当 listener 接也接不上,签名不对。

也就是说,`audio_codecs/aec_processor.py` 的 BlackHole + WebRTC APM 客户端 AEC 实现是 **写了一半但从未接到主链路** 的孤岛代码。

### 关于 `ListeningMode.REALTIME` 与 `AEC_OPTIONS.ENABLED` 的真实语义

为避免误删,先澄清这两个东西当前到底在做什么:

- **`ListeningMode.REALTIME` 是协议层的双工合约**: 通过 `protocol.py:124` 序列化为字符串 `"realtime"` 发给服务器,声明"客户端音频通道支持边说边听"。服务器侧据此走双向实时流。这是与服务器之间的契约,**与 `aec_processor.py` 这套客户端实现无关**。
- **`AEC_OPTIONS.ENABLED=true` 当前的实际作用**: 让 `StateManager` 默认选 `REALTIME`、让 3 个 plugin 在自动监听时上报 REALTIME 协议参数。它声明的是"本设备具备 AEC 能力(系统级 / 操作系统提供 / 后续重接的客户端实现)",不是"启动 Python 端 WebRTC APM 处理"。
- **设备自带 AEC**(如 macOS AVAudioSession voice processing、Linux/Windows 系统级回声消除)在 `ENABLED=true` + `REALTIME` 模式下,经由操作系统在 sounddevice 层就把回声去掉了 —— 客户端 Python 代码无需介入,服务器仍能拿到干净音频。

因此本任务删除 `aec_processor.py` 之后:
- `REALTIME` 协议合约保留
- 设备具备系统级 AEC 时,实时双工对话功能 **不变**
- 后续重构若要接回客户端 Python AEC,从 git 历史还原或重新设计

## 目标

第一步只做**最小、零风险的清理**: 删除 `audio_codecs/aec_processor.py` 这套孤岛实现及其独立 demo 脚本,为后续音频路径重构清出空间。

不在本任务范围:
- `AEC_OPTIONS` 配置项(留;声明设备 AEC 能力)
- `StateManager.aec_enabled` 字段(留;影响监听模式选择)
- `ListeningMode.REALTIME` 枚举值(留;协议双工合约,服务器侧使用)
- 各 plugin 内 `if AEC_OPTIONS.ENABLED ...` 分支(留)
- 设置页面 AEC 开关(留)

## 范围(精确文件清单)

### 删除

| 文件 | 行数 | 说明 |
|---|---|---|
| `src/audio_codecs/aec_processor.py` | 461 | `AECProcessor` 类,无任何 caller |
| `scripts/webrtc_aec_demo.py` | 700+ | 独立 demo 脚本,与运行时无关 |

### 顺手清理(若存在)

- `src/audio_codecs/__init__.py` 若 re-export 了 `AECProcessor` / `aec_processor`,删除该 export。
- `src/audio_codecs/__pycache__/aec_processor.cpython-*.pyc`(由 Python 自动重建,可不动)。

### 不动

- `AEC_OPTIONS` 默认配置(`src/utils/config_manager.py`)
- `config/config.json` 中 `AEC_OPTIONS` 段
- `StateManager` 中所有 `aec_enabled` / `_aec_enabled` 相关字段、方法、`should_capture_audio` 中的 SPEAKING 分支
- `ServiceContainer` 中 `aec_enabled` 读取 + 传参
- `src/plugins/wake_word.py:120-125`、`src/plugins/ui.py:251-255`、`src/plugins/shortcuts/__init__.py:80-85` 中的 `REALTIME if AEC else AUTO_STOP` 三处
- `src/ui/shared/models/settings_model.py` 中 `aecEnabled` Property
- `src/ui/gui/qml/windows/settings/SystemOptionsTab.qml` 中 AEC 开关 UI

这些保留是为了让后续重构有现成的接入点;现在动会扩大本次任务的影响面,且当前用户 `ENABLED=false`,代码路径不走。

### 用户已有 config.json 中的 AEC_OPTIONS 字段

被动忽略。`ConfigManager` 在合并默认值时会保留未知字段(见 `config_manager.py` 实际行为),不主动写迁移逻辑。

## 验证

完成后跑通以下三条路径,确认无回归:

1. **启动**: `uv run python main.py`
   - 无 `ImportError` / `ModuleNotFoundError`
   - 启动日志中不出现 `AECProcessor`/`AEC处理器` 字样(因为已删)
   - 启动总耗时不变或略快(<5% 浮动属正常)

2. **`AEC_OPTIONS.ENABLED=false` (当前默认) 路径**:
   - 唤醒词 → 自动对话 → 走 `ListeningMode.AUTO_STOP`
   - 行为与删除前一致

3. **`AEC_OPTIONS.ENABLED=true` 路径(双工实时对话验证)**:
   - 设置页面切到 ENABLED=true,重启
   - 唤醒词 → 自动对话 → 走 `ListeningMode.REALTIME` → 协议发 `"realtime"`
   - 服务器侧双向实时流仍正常工作(macOS 上依赖系统级 voice processing)
   - 这一步是关键: 验证删 `aec_processor.py` 不影响"设备自带 AEC + REALTIME"的实时对话能力

4. **手动对话 + 设置**:
   - 手动模式快捷键(ctrl+j)正常录音
   - 设置页面打开,AEC 开关仍然显示(因为本任务不动 UI)
   - 切换 AEC 开关不报错(配置写入 OK,影响下次启动的监听模式选择)

## 已知风险与回滚

**风险**: 极低。`grep -rn "AECProcessor\|aec_processor"` 全仓库无 caller,删除后任何运行时路径都不应该到达。

**回滚**: 一次性 commit,问题时直接 `git revert`。删除文件可从 git 历史还原。

## 实施顺序

1. `git rm src/audio_codecs/aec_processor.py`
2. `git rm scripts/webrtc_aec_demo.py`
3. `grep -rn "aec_processor\|AECProcessor" src/` 确认无残留引用
4. 检查 `src/audio_codecs/__init__.py` 是否 re-export,有则删
5. 启动应用走完三条验证路径
6. 提交: `chore: 移除未使用的 AEC processor 实现与 demo`

## 产出

- `src/audio_codecs/aec_processor.py` 删除
- `scripts/webrtc_aec_demo.py` 删除
- 必要时 `src/audio_codecs/__init__.py` 清理 export
- 单个 commit,描述上述内容
- 启动日志附在 PR 描述里(对比删除前后)
