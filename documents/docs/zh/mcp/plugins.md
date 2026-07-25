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

## 自带依赖（给 exe/dmg 用）

开发者在与宿主一致的 Python/平台上构建：

```bash
# 在插件目录内
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# 或: python -m pip install -r requirements.txt -t lib/
```

然后将**整个插件目录**打成 zip 分发。用户只需解压到 `mcp_plugins/`，**不要**再 pip。

说明：同进程加载下，`lib/` 是「自带依赖、免用户安装」，**不是**完美进程级隔离。重型冲突栈需后续子进程方案。

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
