# MCP 外挂扩展

面向 **已打包安装版（exe / dmg）** 与开发环境：由插件开发者打好 **自带依赖的 Python 插件包**，普通用户安装到约定目录后即可扩展 MCP 工具，**无需** `pip install`，也无需改主工程源码。

内置工具开发请见 [MCP 开发指南](./index.md)。外挂与内置 **双轨并存**。

## 一句话

**开发者构建插件包（`plugin.py` + `manifest.json` + `lib/`）→ 用户拷贝到 `mcp_plugins` → 重启应用加载。**

## 与内置工具的区别

| | 内置 | 外挂 |
|--|------|------|
| 位置 | `src/mcp/tools/<name>/` | `{用户数据}/mcp_plugins/<id>/` |
| 入口 | `register.py` → `register_*_tools` | `plugin.py` → `register(host)` |
| 依赖 | 主程序依赖 | 插件目录 `lib/` 自带（vendored） |
| 发版 | 跟主程序 | 插件独立版本 |
| 用户操作 | 升级应用 | 安装/删除插件目录 |

## 安装目录

| 平台 | 默认路径 |
|------|----------|
| macOS | `~/Library/Application Support/py-xiaozhi/mcp_plugins/` |
| Windows | `%LOCALAPPDATA%\py-xiaozhi\mcp_plugins\` |
| Linux | `~/.local/share/py-xiaozhi/mcp_plugins/` |

可用配置覆盖：

```json
"MCP_PLUGINS": {
  "ENABLED": true,
  "DIR": null,
  "ENABLED_IDS": [],
  "DISABLED_IDS": [],
  "ALLOW_HOST_GET": ["config_readonly", "logger"]
}
```

- `DIR` 为 `null` 时使用上表默认路径。  
- `DISABLED_IDS` 含插件 `id` → **启动时不加载**。  
- `ALLOW_HOST_GET` 控制 `host.get` 白名单；`music_player` 需显式加入。

## 插件包结构

```text
com.example.hello/
  manifest.json     # 身份与入口
  plugin.py         # def register(host)
  lib/              # 可选：pip install --target lib/ 打进去的依赖
  native/           # 可选：按平台分子目录的二进制扩展
  README.txt        # 可选
```

### manifest.json 示例

```json
{
  "id": "com.example.hello",
  "name": "Hello Demo",
  "version": "1.0.0",
  "api_version": 1,
  "entry": "plugin:register",
  "runtime": "python-inprocess",
  "tool_name_prefix": "example.",
  "enabled_by_default": true
}
```

| 字段 | 说明 |
|------|------|
| `id` | 全局唯一，用于启用/禁用 |
| `api_version` | 不得高于宿主支持的插件 API（当前为 1） |
| `min_host_version` | 可选；宿主版本过低则跳过 |
| `platforms` | 可选；声明后与当前 OS/ARCH 不符则跳过 |
| `python_abi` | 可选；如 `cp310`，与宿主不一致则跳过 |
| `entry` | `模块:属性`，默认 `plugin:register` |
| `runtime` | 当前仅支持 `python-inprocess` |
| `tool_name_prefix` | 建议填写；工具名宜带此前缀 |

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

## 宿主 API（host）

| 方法 | 说明 |
|------|------|
| `host.add_tool(tool)` | 注册 `McpTool` |
| `host.tool(name, description, props=None)` | 装饰器糖，**不写**全局 registry |
| `host.get(name)` | 白名单能力；未授权返回 `None` |

默认 `get` 白名单：`config_readonly`、`logger`。  
`music_player` 等需在配置 `ALLOW_HOST_GET` 中显式允许。

**禁止**依赖已删除的全局 `@mcp_tool` 或 `get_instance` 单例。

## 自带依赖与分平台发布

### 原则

| 依赖类型 | 能否一份包三端通用 | 做法 |
|----------|-------------------|------|
| 纯 Python（如 `markdown`） | 通常可以 | 一个 `lib/` + 一个 zip 即可 |
| 带原生扩展（`.so` / `.pyd` / `.dylib`） | **否** | **按系统 + 架构分别构建、分别发布** |
| 系统/机器人环境 SDK（ROS2、`rclpy`、厂商 SDK） | **一般不能塞进 `lib/`** | 见下文「环境依赖」 |

### 推荐发布命名（有原生库时最合适）

```text
com.example.foo-1.0.0-macos-arm64.zip
com.example.foo-1.0.0-windows-amd64.zip
com.example.foo-1.0.0-linux-x86_64.zip
```

每个 zip 内为完整插件目录；`manifest.platforms` 建议只写当前平台，`python_abi` 与构建用的宿主 Python 一致（如 `cp310`）。

用户只下载**自己系统**那一份，解压到 `mcp_plugins/`。

### 构建命令（开发者）

在**目标平台**、与宿主**相同的 Python 小版本**上：

```bash
# 在插件目录内
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# 或: python -m pip install -r requirements.txt -t lib/
```

- 用 `--target lib/` / `-t lib/`，**不要** `pip install` 进主程序环境。  
- 含二进制的包必须在对应 OS/ARCH 的机器或 CI 上执行上述命令。  
- 打 zip 时带上整个目录（含 `lib/`）。

### 环境依赖（ROS2 / 宇树 Python SDK 等）

这类依赖**通常安装在机器人系统环境**里（如 `source /opt/ros/humble/setup.bash`、厂商提供的 site-packages），**不是**普通 PyPI 小 wheel，也**很难**完整 vendored 进 `lib/` 后在任意 PC 上跑通。

推荐约定：

| 做法 | 说明 |
|------|------|
| **插件声明环境要求** | 在 `README` / 发布页写清：需已安装 ROS2 发行版、宇树 SDK、Python 版本、架构（如 `linux-aarch64`） |
| **`lib/` 只打可搬运的 PyPI 依赖** | HTTP、工具库等可 `--target lib/` |
| **import 环境包时写清失败信息** | `import rclpy` 失败 → 返回「请先 source ROS 并安装 xxx」 |
| **分平台发布** | 机器人插件多为 `linux-aarch64` / `linux-x86_64` 专用包，不要发「三端通用」误导用户 |
| **不要**假设桌面 exe/dmg 用户能跑 ROS 插件 | 桌面安装版与工控机/宇树镜像是不同运行环境 |

示例（插件内）：

```python
def register(host):
    try:
        import rclpy  # 来自系统 ROS，而非 lib/
    except ImportError as e:
        raise RuntimeError(
            "需要 ROS2 Python 环境（rclpy）。"
            "请在已 source ROS 的环境中运行宿主，或安装对应发行版。"
        ) from e
    # 可搬运依赖仍从 lib/ 提供
    ...
```

同进程加载下，`lib/` 只解决「免用户 pip」；**不是**进程级隔离。ROS/重型 native 冲突时，后续可考虑子进程运行时。

## 用户安装步骤

1. 取得插件包（目录或 zip）。  
2. 解压/复制到上文 `mcp_plugins` 目录（保证存在 `manifest.json` 与入口文件）。  
3. **完全退出并重启** 应用。  
4. 日志中应出现：`[MCP插件] 已加载 <id> (N 工具)`。  
5. 通过对话或 MCP `tools/list` 确认工具名。

仓库示例（无第三方依赖，可直接拷贝）：

```text
examples/mcp_plugins/com.example.hello/
```

## 开发者检查

```bash
python scripts/check_mcp_plugin.py /path/to/com.example.hello
python scripts/check_mcp_plugin.py /path/to/plugin --strict
```

`--strict` 会要求 `api_version`、`python_abi`、`platforms`、`tool_name_prefix`。

## 命名与冲突

- 工具名建议使用 `manifest.tool_name_prefix` 前缀（如 `example.`）。  
- 与**已有工具同名**时：宿主 **拒绝重复注册**（不覆盖内置）。  
- 关闭插件：`MCP_PLUGINS.DISABLED_IDS` 加入 `id` 后重启；或删除目录。

## 运行时 API（程序侧）

| API | 说明 |
|-----|------|
| 启动加载 | `McpServer.add_common_tools` 末尾调用 `load_mcp_plugins_from_config` |
| `server.unload_plugin(plugin_id)` | 移除该插件已注册工具 |
| `server.reload_external_plugins(...)` | 卸掉外挂后按配置重新扫描 |

设置 UI、列表变更推送、子进程隔离、签名等为后续能力。

## 安全提示

插件与主程序**同进程**，权限等同本机任意代码。请只安装**可信来源**插件；可用 `MCP_PLUGINS.ENABLED=false` 一键关闭全部外挂。

## 相关文档

- [MCP 内置工具开发指南](./index.md)  
- 示例目录：`examples/mcp_plugins/`  
- 实现：`src/mcp/plugins/`（`host.py`、`loader.py`、`registry.py`）
