# MCP 外挂扩展

面向 **已打包安装版（exe / dmg）** 与开发环境：由插件开发者打好 **自带依赖的 Python 插件包**，普通用户在设置页一键导入 ZIP / 文件夹即可扩展 MCP 工具，**无需** `pip install`，也无需改主工程源码。

内置工具开发请见 [MCP 开发指南](./index.md)。外挂与内置 **双轨并存**。

## 一句话

**开发者构建插件包（`plugin.py` + `manifest.json` + `lib/`）→ 用户在「参数设置 → MCP 工具」导入 ZIP / 文件夹 → 立即热加载生效。**

## 与内置工具的区别

| | 内置 | 外挂 |
|--|------|------|
| 位置 | `src/mcp/tools/<name>/` | `{用户数据}/mcp_plugins/<id>/` |
| 入口 | `register.py` → `register_*_tools` | `plugin.py` → `register(host)` |
| 依赖 | 主程序依赖 | 插件目录 `lib/` 自带（vendored） |
| 数据目录 | 宿主共享数据目录 | 专属隔离目录 `{用户数据}/mcp_plugins_data/<id>/` |
| 发版 | 跟主程序 | 插件独立版本 |
| 用户操作 | 升级应用 | 在设置页一键导入 / 卸载 |

## 安装目录与配置

| 平台 | 默认插件代码目录 |
|------|----------|
| macOS | `~/Library/Application Support/py-xiaozhi/mcp_plugins/` |
| Windows | `%LOCALAPPDATA%\py-xiaozhi\mcp_plugins\` |
| Linux | `~/.local/share/py-xiaozhi/mcp_plugins/` |

如需整体迁移用户数据目录（含配置、日志、插件与插件数据），可在启动前设置环境变量 `XIAOZHI_DATA_DIR`。

配置项（`config.json`）：

```json
"MCP_PLUGINS": {
  "ENABLED": true,
  "DIR": null,
  "ENABLED_IDS": [],
  "DISABLED_IDS": [],
  "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir"]
}
```

- `DIR` 为 `null` 时使用上表默认路径。
- `DISABLED_IDS` 含插件 `id` → **不加载该插件**。
- `ALLOW_HOST_GET` 控制 `host.get` 白名单；音频/媒体播放能力 `media_player` 默认关闭，可在「参数设置 → MCP 工具」打开「**允许外挂使用应用内播放**」开关启用。

## 插件包结构

```text
demo_media_plugin/
  manifest.json     # 身份、runtime 与入口
  plugin.py         # def register(host)
  lib/              # 可选：pip install --target lib/ 打进去的依赖
  native/           # 可选：按平台分子目录的二进制扩展
  README.md         # 可选
```

### manifest.json 示例

```json
{
  "id": "demo_media_plugin",
  "name": "示例媒体播放插件",
  "version": "1.0.0",
  "description": "通过宿主 media_player 播放音频流或本地文件",
  "api_version": 1,
  "entry": "plugin:register",
  "runtime": "python-subprocess",
  "tool_name_prefix": "demo_media.",
  "enabled_by_default": true,
  "tools": [
    { "name": "demo_media.play_url", "title": "播放音频地址" }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `id` | 全局唯一（`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`），用于安装、数据隔离与启停 |
| `name` / `version` / `description` | 可选；展示在「参数设置 → MCP 工具」的已安装插件卡片中 |
| `api_version` | 不得高于宿主支持的插件 API（当前为 1） |
| `min_host_version` | 可选；宿主版本过低则跳过 |
| `platforms` | 可选；声明后与当前 OS/ARCH 不符则跳过 |
| `python_abi` | 可选；如 `cp310`，与宿主不一致则跳过 |
| `entry` | `模块:属性`，默认 `plugin:register` |
| `runtime` | **`python-inprocess`（默认，同进程）** 或 **`python-subprocess`（推荐，独立子进程）** |
| `call_timeout` | 可选；仅 `python-subprocess`，单次工具调用超时秒数（默认 60） |
| `tool_name_prefix` | 建议填写；工具名宜带此前缀 |
| `tools` | 可选；声明工具清单，供设置页离线展示工具名与中文标题 |

可选严格配置（默认关）：`ENFORCE_PREFIX`、`REQUIRE_PYTHON_ABI`、`REQUIRE_PLATFORMS`。

### plugin.py 最小示例

```python
def register(host):
    @host.tool(
        name="example.hello",
        description="打招呼。参数 name 可选。",
        props=[{"name": "name", "type": "string", "default": "世界"}],
    )
    async def hello(args):
        name = (args or {}).get("name") or "世界"
        return f"你好, {name}！"
```

也可用 `host.add_tool(McpTool(...))`（与内置相同的 `src.mcp.tooling` 类型）。

## 宿主 API（`host`）

| 方法 | 说明 |
|------|------|
| `host.add_tool(tool)` | 注册 `McpTool` |
| `host.tool(name, description, props=None)` | 装饰器糖，**不写**全局 registry |
| `host.get(name)` | 按白名单获取宿主能力；未授权返回 `None` |

### 可用能力一览

| 能力名 | 默认放行 | 说明 |
|--------|----------|------|
| `logger` | 是 | 日志记录器（子进程模式下输出到宿主日志通道） |
| `config_readonly` | 是 | 脱敏递归只读配置快照（仅含公开字段，无写入方法） |
| `data_dir` | 是 | 插件专属隔离可写目录 `Path`（`{用户数据}/mcp_plugins_data/<id>/`），首次调用 `host.get("data_dir")` 时延迟创建；更新或覆盖插件代码不会丢失数据 |
| `media_player` | 否（需用户开启授权） | 受控的 `MediaPlayerFacade` 句柄，支持 `inprocess` 与 `subprocess` 两种模式 |

> 显式将 `MCP_PLUGINS.ALLOW_HOST_GET` 设为 `[]` 会禁用全部宿主能力。

`config_readonly` 仅公开以下字段（URL 已移除用户信息、查询串和片段，其余凭据/API Key 一律不可见）：

- `CONFIG_VERSION`
- `SYSTEM_OPTIONS.WINDOW_SIZE_MODE`
- `SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL`
- `SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL`
- `SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION`

**禁止**依赖已删除的全局 `@mcp_tool` 或 `get_instance` 单例。

## 音频 / 媒体类外挂开发（`media_player`）

主程序已移除易失效的内置音乐音源，改为提供**无音源依赖的通用音频底座**（基于 `AudioMixer` + `AudioDecoder` + `MediaPlayer`）。音乐、电台、播客、有声书、白噪音等插件只需负责“检索音源 / 获取直链或本地文件”，播放直接交由 `host.get("media_player")`：

- **自动享有宿主音频基础设施**：AEC 回声消除、TTS 说话时自动闪避（并行模式）或临时暂停/播完恢复（半双工模式）、内置 FFmpeg 解码、蓝牙/外置声卡热切换、主界面底部 `mediaLine` 展示。
- **无需重复注册通用播控工具**：当用户开启「允许外挂使用应用内播放」且至少成功加载 1 个外挂时，宿主会自动注册全局唯一的 `media.pause`、`media.resume`、`media.stop`、`media.seek`、`media.get_status`，避免多款音频插件互相冲突。插件只需注册自己独有的工具（如“搜索播放”“下一首”“歌单管理”）。
- **生命周期与安全保护**：每个插件持有独立的 `MediaPlayerFacade` 句柄；插件卸载后句柄立即失效，且正在播放的归属音频流会自动停止。

### `media_player` 方法参考

| 方法 | 说明 |
|------|------|
| `await player.play_url(url, *, title="", start_position=0.0, headers=None)` | 播放 `http/https` 音频流或本地文件**绝对路径** |
| `await player.pause()` | 手动暂停当前播放 |
| `await player.resume()` | 恢复播放 |
| `await player.stop()` | 停止播放 |
| `await player.seek(*, position=None, percent=None)` | 按秒数或百分比（`0~100`）跳转 |
| `await player.get_status()` | 返回结构化字典（`status` / `state` / `title` / `position` / `duration` / `progress` / `owner_id` / `message`） |
| `await player.set_subtitle(text)` | 刷新主界面 `mediaLine` 副标题或歌词行 |

**输入安全约束：**

- `url` 仅允许合法的 `http://` / `https://` 地址或**已存在的本地文件绝对路径**（例如将解密/缓存后的音频写入 `data_dir` 后传入 `str(data_dir / "track.mp3")`）；拒绝相对路径与 `file:` / `pipe:` / `concat:` 等非法协议。
- `headers` 白名单放行 `User-Agent`、`Referer`、`Origin`、`Cookie`、`Authorization`、`Accept`、`Accept-Language`、`Range`，并拦截 CRLF 注入。

### 音频插件完整示例

仓库内置完整模板见 `examples/mcp_plugins/demo_media_plugin/`：

```python
import json
from pathlib import Path

def register(host):
    player = host.get("media_player")
    data_dir = host.get("data_dir")

    @host.tool(
        "demo_media.play_url",
        "通过宿主应用内播放器播放指定的 HTTP(S) 音频直链或本地音频绝对路径。",
        [
            {"name": "url", "type": "string"},
            {"name": "title", "type": "string", "default": ""},
        ],
    )
    async def play_url(args):
        if player is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": "请在「参数设置 → MCP 工具」中开启「允许外挂使用应用内播放」。",
                },
                ensure_ascii=False,
            )
        res = await player.play_url(
            str(args.get("url") or "").strip(),
            title=str(args.get("title") or "").strip(),
            headers={"User-Agent": "py-xiaozhi-plugin/1.0"},
        )
        return json.dumps(res, ensure_ascii=False)
```

## 自带依赖与分平台发布

### 原则

| 依赖类型 | 能否一份包三端通用 | 做法 |
|----------|-------------------|------|
| 纯 Python（如 `httpx`、`markdown`） | 通常可以 | 一个 `lib/` + 一个 zip 即可 |
| 带原生扩展（`.so` / `.pyd` / `.dylib`） | **否** | **按系统 + 架构分别构建、分别发布** |
| 系统/机器人环境 SDK（ROS2、`rclpy`、厂商 SDK） | **一般不能塞进 `lib/`** | 见下文「环境依赖」 |

### 推荐发布命名（有原生库时最合适）

```text
com.example.foo-1.0.0-macos-arm64.zip
com.example.foo-1.0.0-windows-amd64.zip
com.example.foo-1.0.0-linux-x86_64.zip
```

每个 zip 内为完整插件目录；`manifest.platforms` 建议只写当前平台，`python_abi` 与构建用的宿主 Python 一致（如 `cp310`）。

### 构建命令（开发者）

在**目标平台**、与宿主**相同的 Python 小版本**上：

```bash
# 在插件目录内
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# 或: python -m pip install -r requirements.txt -t lib/
```

- 用 `--target lib/` / `-t lib/`，**不要** `pip install` 进主程序环境。
- 含二进制的包必须在对应 OS/ARCH 的机器或 CI 上执行上述命令。
- 打 zip 时带上整个目录（含 `lib/`），导入器会自动剥离单一顶层目录并校验防路径穿越与符号链接。

### 环境依赖（ROS2 / 宇树 Python SDK 等）

这类依赖通常安装在机器人系统环境里（如 `source /opt/ros/humble/setup.bash`），很难完整 vendored 进 `lib/`。建议：

- 在 `README` 中明确声明系统环境要求与目标平台（如 `linux-aarch64`）；
- `lib/` 仅打包可搬运的纯 Python 依赖；
- `import` 系统 SDK 失败时给出清晰指引。

## 运行时：`python-inprocess` 与 `python-subprocess`

未写 `runtime` 时默认 `python-inprocess`；**带第三方依赖或网络 IO 的插件（特别是音频/爬虫类）推荐显式使用 `python-subprocess`**。

| | `python-inprocess`（默认） | `python-subprocess`（推荐） |
|--|---------------------------|---------------------|
| 进程 | 与宿主同进程 | 独立 worker 进程（stdin/stdout 双向 JSON 行协议） |
| 崩溃/堵死隔离 | 差（可拖垮宿主） | 较好（单次调用超时可终止子进程） |
| `host.get("logger")` | 宿主 logger | 子进程本地 logger（stderr 汇入宿主日志） |
| `host.get("config_readonly")` | 脱敏只读快照 | 相同只读接口（由脱敏 JSON 快照构造） |
| `host.get("data_dir")` | 延迟创建的 `Path` | **完全支持**（经 `host_call` RPC 延迟获取 `Path`） |
| `host.get("media_player")` | 受控 `MediaPlayerFacade` | **完全支持**（经双向 `host_call` RPC 代理，API 100% 一致） |
| 适用 | 极轻量、完全可信插件 | 第三方依赖、音频/网络爬虫、需隔离风险的插件 |

仓库示例：

```text
examples/mcp_plugins/com.example.hello/          # inprocess
examples/mcp_plugins/com.example.hello_sub/      # subprocess
examples/mcp_plugins/demo_media_plugin/          # subprocess + media_player + data_dir
```

说明：子进程隔离**不是** OS 级沙箱，仍是本机同用户权限；只隔离解释器、依赖路径与内存空间。

## 用户安装与管理（设置页）

应用内 **参数设置 → MCP 工具** 已内置完整的插件管理能力：

1. **导入 ZIP / 导入文件夹**：点击顶部「导入 ZIP」或「导入文件夹」，宿主会执行安全解压/复制、校验 `manifest.json`（同 ID 覆盖时自动备份并在失败时回滚）并立即热重载。
2. **开启应用内播放权限**：若使用音频类插件，打开「**允许外挂使用应用内播放**」开关并保存。
3. **查看与卸载**：卡片展示已安装插件的名称、版本、`runtime` 及加载报错；点击「卸载」会自动停播该插件归属的媒体、移除工具、结束子进程并删除插件代码目录（隔离数据目录 `mcp_plugins_data/<id>/` 默认保留）。
4. **打开目录 / 刷新**：一键打开 `mcp_plugins` 目录或手动触发重新扫描。

## 按工具启停（`MCP_TOOLS`）

在 **参数设置 → MCP 工具** 下方可按分组或单个工具开关暴露状态：

- 配置键：`MCP_TOOLS.DISABLED`（工具全名黑名单；默认 `[]` 全开）。
- 内置工具目录扫描自 `src/mcp/tools/*/register.py`（分组 = 目录名，如 `media` / `app` / `camera`）。
- **关闭后**：不出现在 MCP `tools/list`，`tools/call` 也会被拒绝。
- **保存后**：若已连接服务端，会自动断开重连以刷新工具列表（重连后保持空闲）。

与 `MCP_PLUGINS.DISABLED_IDS` 的区别：后者是**整包不加载**；前者是已注册工具的**暴露面裁剪**。

## 开发者检查

```bash
python scripts/check_mcp_plugin.py /path/to/demo_media_plugin
python scripts/check_mcp_plugin.py /path/to/plugin --strict
```

`--strict` 会要求 `api_version`、`python_abi`、`platforms`、`tool_name_prefix`。

## 命名、冲突与生命周期

- 工具名建议使用 `manifest.tool_name_prefix` 前缀（如 `demo_media.`）。
- 与**已有工具同名**时，宿主会拒绝该插件的整批注册并保留原工具归属；注册窗口关闭后不能再通过缓存的 `host` 注册新工具。
- 卸载、重载和应用退出时，宿主会先 `revoke` 插件生命周期令牌（令所有受控能力句柄失效并自动停播归属媒体流），再移除工具并终止子进程 worker。
- 子进程 JSON 协议使用 UTF-8，插件 `print`/stdout 重定向到日志通道，不污染协议流。

## 运行时 API（程序侧）

| API | 说明 |
|-----|------|
| 启动加载 | `McpPlugin.setup` 调用 `server.register_builtin_tools()` 与 `server.reload_external_plugins(media_player=...)` |
| `server.unload_plugin(plugin_id)` | 撤销插件生命周期、停播归属媒体、移除工具、结束子进程并重新同步条件 `media.*` 工具 |
| `server.reload_external_plugins(media_player=...)` | 卸载全部外挂、按配置重新扫描并按授权条件同步宿主通用播控工具 |

## 安全提示

- **`python-inprocess`**：与主程序同进程，权限等同本机任意代码。
- **`python-subprocess`**：工具逻辑在独立子进程，崩溃与依赖隔离更好，但仍是本机同用户权限，**不是**安全沙箱。
- 请只安装**可信来源**插件；`media_player` 默认关闭，按需开启；可用 `MCP_PLUGINS.ENABLED=false` 一键关闭全部外挂。

## 相关文档

- [MCP 内置工具开发指南](./index.md)
- 示例目录：`examples/mcp_plugins/`（含 `demo_media_plugin`）
- 实现：`src/mcp/plugins/`（`host.py`、`media_facade.py`、`installer.py`、`loader.py`、`registry.py`、`subprocess_runtime.py`、`subprocess_worker.py`）与 `src/media/`
