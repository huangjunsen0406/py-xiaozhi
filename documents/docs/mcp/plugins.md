# MCP External Plugins

For **packaged apps (exe / dmg)** and dev installs: plugin authors ship a **self-contained Python plugin package** (dependencies vendored). End users drop it into a fixed directory—**no `pip install`**, no changes to the main repo.

For **built-in** tools, see the [MCP Development Guide](./index.md). Built-ins and external plugins coexist.

## In one line

**Author builds package (`plugin.py` + `manifest.json` + `lib/`) → user copies into `mcp_plugins` → restart app.**

## Built-in vs external

| | Built-in | External |
|--|----------|----------|
| Location | `src/mcp/tools/<name>/` | `{user data}/mcp_plugins/<id>/` |
| Entry | `register.py` → `register_*_tools` | `plugin.py` → `register(host)` |
| Dependencies | App dependencies | Vendored under plugin `lib/` |
| Release | With the app | Independent plugin version |
| User action | Upgrade app | Install / remove plugin folder |

## Install directory

| Platform | Default path |
|----------|----------------|
| macOS | `~/Library/Application Support/py-xiaozhi/mcp_plugins/` |
| Windows | `%LOCALAPPDATA%\py-xiaozhi\mcp_plugins\` |
| Linux | `~/.local/share/py-xiaozhi/mcp_plugins/` |

Config override:

```json
"MCP_PLUGINS": {
  "ENABLED": true,
  "DIR": null,
  "ENABLED_IDS": [],
  "DISABLED_IDS": [],
  "ALLOW_HOST_GET": ["config_readonly", "logger"]
}
```

- `DIR: null` → default path above.  
- `DISABLED_IDS` → plugin **not loaded** at startup.  
- `ALLOW_HOST_GET` → whitelist for `host.get` (`music_player` must be listed explicitly).

## Package layout

```text
com.example.hello/
  manifest.json
  plugin.py           # def register(host)
  lib/                # optional vendored deps
  native/             # optional per-platform binaries
  README.txt
```

### manifest.json

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

| Field | Meaning |
|-------|---------|
| `id` | Unique id for enable/disable |
| `api_version` | Must not exceed host plugin API (currently 1) |
| `min_host_version` | Optional; skip if host is older |
| `platforms` | Optional; skip if OS/arch mismatch |
| `python_abi` | Optional; e.g. `cp310` |
| `entry` | `module:attr`, default `plugin:register` |
| `runtime` | Currently only `python-inprocess` |
| `tool_name_prefix` | Recommended for tool names |

Optional strict flags (default off): `ENFORCE_PREFIX`, `REQUIRE_PYTHON_ABI`, `REQUIRE_PLATFORMS`.

### Minimal plugin.py

```python
def register(host):
    @host.tool(
        name="example.hello",
        description="Say hello. Optional arg: name.",
        props=[{"name": "name", "type": "string", "default": "world"}],
    )
    async def hello(args):
        name = (args or {}).get("name") or "world"
        return f"Hello, {name}!"
```

You may also use `host.add_tool(McpTool(...))` with the same types as built-ins (`src.mcp.tooling`).

## Host API

| Method | Role |
|--------|------|
| `host.add_tool(tool)` | Register an `McpTool` |
| `host.tool(name, description, props=None)` | Decorator sugar (**no** global registry) |
| `host.get(name)` | Whitelisted capabilities; otherwise `None` |

Default whitelist: `config_readonly`, `logger`.  
Do **not** rely on removed global `@mcp_tool` or `get_instance` singletons.

## Vendoring dependencies and multi-platform releases

### Rules of thumb

| Dependency type | One zip for all OSes? | What to do |
|-----------------|----------------------|------------|
| Pure Python (e.g. `markdown`) | Often yes | Single `lib/` is fine |
| Native wheels (`.so` / `.pyd` / `.dylib`) | **No** | **Build and publish per OS + arch** |
| Environment SDKs (ROS2, `rclpy`, vendor SDKs) | **Usually cannot vendor fully** | See “Environment dependencies” below |

### Recommended artifact names (best when natives are involved)

```text
com.example.foo-1.0.0-macos-arm64.zip
com.example.foo-1.0.0-windows-amd64.zip
com.example.foo-1.0.0-linux-x86_64.zip
```

Each zip contains a full plugin folder; set `manifest.platforms` to that platform and `python_abi` to the host Python tag used at build time (e.g. `cp310`).

Users download **only their platform** and extract into `mcp_plugins/`.

### Build commands (authors)

On the **target OS/arch**, with the **same Python minor** as the host:

```bash
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# or: python -m pip install -r requirements.txt -t lib/
```

- Use `--target` / `-t` into **plugin `lib/`** — do **not** install into the app venv.  
- Native wheels must be built on matching CI/runners.  
- Zip the entire plugin directory including `lib/`.

### Environment dependencies (ROS2 / Unitree Python SDK, etc.)

These usually live in the **robot system environment** (e.g. `source /opt/ros/humble/setup.bash`, vendor site-packages). They are **not** typical portable PyPI trees and often **cannot** be fully vendored into `lib/` for arbitrary PCs.

Recommended practice:

| Practice | Notes |
|----------|--------|
| Document runtime requirements | ROS distro, vendor SDK, Python, arch (e.g. `linux-aarch64`) in README / release notes |
| Vendor only portable PyPI deps in `lib/` | HTTP clients, small pure-Python helpers, etc. |
| Fail clearly on missing env imports | e.g. `import rclpy` → “source ROS / install SDK first” |
| Ship per-platform packages | Robot plugins are often `linux-aarch64` / `linux-x86_64` only — do not market as universal desktop zips |
| Desktop exe/dmg ≠ robot image | A Unitree/ROS plugin is not expected to run on a stock desktop install |

Example:

```python
def register(host):
    try:
        import rclpy  # from system ROS, not lib/
    except ImportError as e:
        raise RuntimeError(
            "ROS2 Python (rclpy) is required. "
            "Run the host in a sourced ROS environment or install the distro."
        ) from e
    ...
```

Vendored `lib/` avoids end-user pip; it is **not** full process isolation. For heavy native conflicts, a future subprocess runtime may be needed.

## User install steps

1. Get the plugin folder or zip.  
2. Copy/extract under `mcp_plugins` so `manifest.json` is present.  
3. **Fully quit and restart** the app.  
4. Logs should show: `[MCP插件] 已加载 <id> (N 工具)`.  
5. Confirm tools via chat or MCP `tools/list`.

Repo sample (stdlib only):

```text
examples/mcp_plugins/com.example.hello/
```

## Developer check

```bash
python scripts/check_mcp_plugin.py /path/to/com.example.hello
python scripts/check_mcp_plugin.py /path/to/plugin --strict
```

## Naming and conflicts

- Prefer `tool_name_prefix` (e.g. `example.`).  
- **Duplicate tool names are rejected** (built-ins are not overwritten).  
- Disable: add id to `DISABLED_IDS` and restart, or delete the folder.

## Runtime APIs (host)

| API | Role |
|-----|------|
| Startup | `add_common_tools` → `load_mcp_plugins_from_config` |
| `server.unload_plugin(plugin_id)` | Remove that plugin’s tools |
| `server.reload_external_plugins(...)` | Unload externals and rescan |

Settings UI, list-change notifications, subprocess isolation, and signing are future work.

## Security

Plugins run **in-process** with the same privileges as the app. Install only trusted packages. Set `MCP_PLUGINS.ENABLED=false` to disable all external plugins.

## See also

- [Built-in MCP guide](./index.md)  
- Samples: `examples/mcp_plugins/`  
- Code: `src/mcp/plugins/` (`host.py`, `loader.py`, `registry.py`)
