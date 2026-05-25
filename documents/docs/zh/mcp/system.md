# 系统工具 (System Tools)

系统工具面向桌面端的音量控制与应用管理场景，封装了 MCP 可调用的音量设置/查询能力，以及跨平台的应用扫描、启动、列出与关闭流程。

### 常见使用场景

**音量调节与查询:**

- "把音量调成 40"
- "静音一下"
- "现在的音量是多少"
- "扬声器可用吗"

**应用启动:**

- "打开微信"
- "启动记事本"
- "帮我开一下浏览器"
- "运行 VS Code"

**应用发现与列表:**

- "系统里有什么应用"
- "列一下正在运行的程序"
- "有哪些播放器可以用"
- "判断 QQ 是否正在运行"

**应用关闭:**

- "退出 QQ 音乐"
- "强制关闭 Chrome"
- "把播放器关掉"
- "结束所有叫 XXX 的进程"

### 使用提示

1. **音量值范围**: 所有音量调整以 0-100 的整数为单位，0 代表静音
2. **跨平台能力**: 应用管理工具会自动识别 Windows/macOS/Linux，并调用对应实现
3. **名称匹配**: 建议使用 `self.application.scan_installed` 提供的 `name` 字段去启动或关闭应用以减少模糊匹配误差
4. **结果解析**: `get_volume_status`、`scan_installed`、`list_running` 均返回 JSON 字符串，使用方需自行 `json.loads`

AI 助手会根据需求自动选择合适的系统工具，以便在语音 / 文本会话中完成音量与应用相关操作。

## 功能概览

### 音量与音频控制

- **绝对音量设置**: 直接把扬声器音量设置到目标值
- **音量查询**: 获取当前音量百分比
- **状态诊断**: 查询静音标记、依赖可用性等状态、用于排查音频能力

### 应用管理

- **启动应用**: 通过统一入口打开桌面应用、工具或游戏
- **扫描应用**: 获取可启动的应用清单，支持中英文名称
- **列出运行中应用**: 查看实时运行进程，支持名称过滤
- **关闭应用**: 正常退出或强制结束指定应用

### 状态透明

- **结构化响应**: 所有查询类工具都以结构化 JSON 返回，包含 `success`、`message` 等字段
- **线程隔离**: 实际操作（扫描/启动/关闭）在后台线程或子进程执行，不阻塞 MCP 主循环

## 工具列表

### 1. 音量与音频工具

#### self.audio_speaker.set_volume - 设置系统音量

把系统扬声器音量设为绝对值，内部直接调用 `VolumeController`。

**参数:**

- `volume` (必需): 0-100 的整数，0 表示静音

**使用场景:**

- 精确调节音量
- 执行静音/解除静音
- 用户指定“调大/调小到具体数值”

**返回:**

- `True/False` 布尔值表示操作是否成功

#### self.audio_speaker.get_volume - 查询当前音量

返回当前扬声器音量 (0-100)。当依赖缺失时返回默认值。

**参数:**
无

**使用场景:**

- 回答“当前音量是多少”
- 在调节前先读出旧值
- 检查是否处于静音

**返回:**

- 整型音量值，依赖不可用时为 `VolumeController.DEFAULT_VOLUME`

#### self.audio_speaker.get_volume_status - 获取音量状态

提供包含音量、静音标记、依赖可用性的详细 JSON。

**参数:**
无

**使用场景:**

- 排查音量控制依赖是否齐全
- 判断音频是否静音
- 在 UI 中展示更丰富的状态

**返回:**

- JSON 字符串，字段包括 `volume`、`muted`、`available`、`reason/error`

### 2. 应用生命周期工具

#### self.application.launch - 启动应用

跨平台启动应用：支持桌面软件、系统工具、浏览器、游戏等。

**参数:**

- `app_name` (必需): 应用名称/路径，可为中英混合

**使用场景:**

- 打开 QQ、微信、浏览器、VS Code 等
- 调用系统自带应用（计算器、记事本等）
- 启动安装在 PATH 或已扫描到的程序

#### self.application.scan_installed - 扫描已安装应用

列出可启动的应用清单，并提供匹配所需的 `name`、`display_name`、`path`、`type` 等字段。

**参数:**

- `force_refresh` (可选): 是否强制重新扫描，默认 `false`

**使用场景:**

- 不确定应用名称时先查询
- 提示用户当前系统可用的软件
- 调用 `self.application.launch` 失败时排查名称

**返回:**

- JSON 字符串，包含 `success`、`total_count`、`applications[]`

#### self.application.list_running - 列出正在运行的应用

实时列出当前运行中的应用进程，可按名称过滤。

**参数:**

- `filter_name` (可选): 字符串包含匹配，默认空

**使用场景:**

- 回答“哪些程序正在运行”
- 在关闭应用前确认是否在运行
- 排查占用资源的进程

**返回:**

- JSON 字符串，字段含 `success`、`total_count`、`applications[]`

#### self.application.kill - 关闭/强制结束应用

根据名称关闭一个或多个匹配的运行程序，Windows 下支持分组关闭和强制 kill。

**参数:**

- `app_name` (必需): 需要关闭的应用名
- `force` (可选): `true` 时启用强制 kill，默认 `false`

**使用场景:**

- 用户要求退出/关闭某应用
- 程序卡死需要强制结束
- 批量清理同名程序实例

**返回:**

- `True/False` 布尔值表示是否至少成功关闭一个匹配进程

> 建议配合 `self.application.list_running` 获取 PID/名称，再调用 `self.application.kill` 以避免误杀。

## 使用示例

### 音量控制示例

```python
# 把音量设置为 50
await mcp_server.call_tool("self.audio_speaker.set_volume", {"volume": 50})

# 查询当前音量
current_volume = await mcp_server.call_tool("self.audio_speaker.get_volume", {})

# 获取详细音量状态（JSON 字符串需自行解析）
import json
status_json = await mcp_server.call_tool("self.audio_speaker.get_volume_status", {})
status = json.loads(status_json)
```

### 应用管理示例

```python
import json

# 扫描已安装应用
scan_raw = await mcp_server.call_tool("self.application.scan_installed", {"force_refresh": False})
scan_result = json.loads(scan_raw)

# 启动第一个扫描结果
first_app = scan_result["applications"][0]["name"]
await mcp_server.call_tool("self.application.launch", {"app_name": first_app})

# 列出运行中的应用
running_raw = await mcp_server.call_tool("self.application.list_running", {"filter_name": "QQ"})
running = json.loads(running_raw)

# 关闭所有名称里包含 QQ 的应用
await mcp_server.call_tool("self.application.kill", {
    "app_name": "QQ",
    "force": False
})
```

## 技术架构

### 音量控制 (`src/mcp/tools/volume/`)

- **VolumeController**: 跨平台音量控制（Windows: pycaw, macOS: applescript, Linux: pactl/wpctl/amixer）
- **异步封装**: 通过 `asyncio.to_thread` 把阻塞调用移到线程池
- **容错策略**: 依赖缺失时返回默认音量并在状态接口中标记 `available=False`

### 应用管理 (`src/mcp/tools/app/`)

- **进程管理**: `process_manager.py` 基于 psutil，统一三平台进程列表和终止
- **应用扫描**: `scanner.py` + 平台文件（`scanner_mac.py` / `scanner_windows.py` / `scanner_linux.py`）
- **应用启动**: `launcher.py` + 平台文件（`launcher_mac.py` / `launcher_windows.py` / `launcher_linux.py`）
- **统一匹配**: `utils.py` 中 `AppMatcher` 负责模糊匹配（中文、英文、大小写、别名）

## 数据结构

### 音量状态

```python
{
    "volume": 42,
    "muted": false,
    "available": true
}
```

### 已安装应用扫描结果

```python
{
    "success": true,
    "total_count": 128,
    "applications": [
        {
            "name": "QQ",
            "display_name": "QQ 音乐",
            "path": "C:/Program Files/QQMusic/QQMusic.exe",
            "type": "exe"
        },
        {
            "name": "WeChat",
            "display_name": "微信",
            "path": "/Applications/WeChat.app",
            "type": "app"
        }
    ],
    "message": "成功扫描到 128 个已安装应用程序"
}
```

### 正在运行的应用列表

```python
{
    "success": true,
    "total_count": 2,
    "applications": [
        {
            "pid": 1234,
            "name": "WeChat",
            "display_name": "微信",
            "command": "/Applications/WeChat.app/Contents/MacOS/WeChat"
        },
        {
            "pid": 4321,
            "name": "QQMusic",
            "display_name": "QQ 音乐",
            "command": "C:/Program Files/QQMusic/QQMusic.exe"
        }
    ],
    "message": "找到 2 个正在运行的应用程序"
}
```

## 最佳实践

### 音量管理

- 先调用 `get_volume` 获取旧值，再据此给出“从 X 调到 Y”的语句
- 静音可直接设置为 0，取消静音时把音量恢复到上次记录值
- 依赖缺失时提示用户安装/授予音频控制权限

### 应用管理

- 在启动/关闭前先用 `scan_installed` 或 `list_running` 核实名称，减少误操作
- 需要强制关闭（`force=true`）前先尝试正常关闭，避免数据损坏
- 对于多实例程序，可以先列出运行列表并按 PID 告知用户

## 故障排除

1. **音量设置失败**: 检查 `get_volume_status` 中的 `available`/`reason`
2. **启动应用失败**: 确认扫描结果中存在该应用，或提供完整路径
3. **关闭应用失败**: 使用 `list_running` 验证是否真的在运行，必要时开启 `force`
4. **扫描超时**: 大量应用时耗时较长，可提示稍候或限制扫描范围

## 安全考虑

### 权限与访问控制

- 音量控制依赖系统级权限，首次调用可能需要用户授权
- 启动、关闭应用等操作应在用户明确指令后执行，避免敏感程序被误操作
- `force` 关闭会直接杀死进程，调用前需告知用户可能导致数据丢失

### 数据保护

- 扫描/运行列表可能包含用户安装的软件名称，应谨慎对外展示
- 需要持久化日志时建议脱敏处理，只保留必要字段
- 不记录或上报具体命令行参数，保护隐私

通过这些系统工具，AI 助手可以在多平台环境下安全地调整音量、启动或管理桌面应用，为终端用户提供自然语言驱动的系统控制体验。
