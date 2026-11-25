# MCP External Plugins

For **packaged apps (exe / dmg)** and dev installs: plugin authors ship a **self-contained Python plugin package** (dependencies vendored). End users import a ZIP or folder directly in Settings—**no `pip install`**, no changes to the main repo.

For **built-in** tools, see the [MCP Development Guide](./index.md). Built-ins and external plugins coexist.

## In one line

**Author builds package (`plugin.py` + `manifest.json` + `lib/`) → user imports ZIP/folder in Settings → MCP Tools → hot-reloaded immediately.**

## Built-in vs external

| | Built-in | External |
|--|----------|----------|
| Location | `src/mcp/tools/<name>/` | `{user data}/mcp_plugins/<id>/` |
| Entry | `register.py` → `register_*_tools` | `plugin.py` → `register(host)` |
| Dependencies | App dependencies | Vendored under plugin `lib/` |
| Data directory | App shared data dir | Isolated `{user data}/mcp_plugins_data/<id>/` |
| Release | With the app | Independent plugin version |
| User action | Upgrade app | Import / uninstall in Settings |

## Install directory & configuration

| Platform | Default plugins path |
|----------|----------------|
| macOS | `~/Library/Application Support/py-xiaozhi/mcp_plugins/` |
| Windows | `%LOCALAPPDATA%\py-xiaozhi\mcp_plugins\` |
| Linux | `~/.local/share/py-xiaozhi/mcp_plugins/` |

To relocate the entire user data directory (config, logs, plugins, and plugin data), set the `XIAOZHI_DATA_DIR` environment variable before launch.

Config (`config.json`):

```json
"MCP_PLUGINS": {
  "ENABLED": true,
  "DIR": null,
  "ENABLED_IDS": [],
  "DISABLED_IDS": [],
  "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir"]
}
```

- `DIR: null` → default path above.
- `DISABLED_IDS` → plugin **not loaded**.
- `ALLOW_HOST_GET` → whitelist for `host.get`. In-app playback (`media_player`) is opt-in and can be toggled in **Settings → MCP Tools** ("Allow external plugins to use in-app playback").

## Package layout

```text
demo_media_plugin/
  manifest.json     # identity, runtime & entry
  plugin.py         # def register(host)
  lib/              # optional vendored deps
  native/           # optional per-platform binaries
  README.md         # optional
```

### manifest.json

```json
{
  "id": "demo_media_plugin",
  "name": "Demo Media Plugin",
  "version": "1.0.0",
  "description": "Play audio streams or local files via host media_player",
  "api_version": 1,
  "entry": "plugin:register",
  "runtime": "python-subprocess",
  "tool_name_prefix": "demo_media.",
  "enabled_by_default": true,
  "tools": [
    { "name": "demo_media.play_url", "title": "Play audio URL" }
  ]
}
```

| Field | Meaning |
|-------|---------|
| `id` | Unique id (`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`) for install, data isolation, enable/disable |
| `name` / `version` / `description` | Optional metadata shown in Settings plugin cards |
| `api_version` | Must not exceed host plugin API (currently 1) |
| `min_host_version` | Optional; skip if host is older |
| `platforms` | Optional; skip if OS/arch mismatch |
| `python_abi` | Optional; e.g. `cp310` |
| `entry` | `module:attr`, default `plugin:register` |
| `runtime` | **`python-inprocess` (default, same process)** or **`python-subprocess` (recommended, child process)** |
| `call_timeout` | Optional; `python-subprocess` only — per-call timeout in seconds (default 60) |
| `tool_name_prefix` | Recommended for tool names |
| `tools` | Optional tool list for offline display in Settings |

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

## Host API (`host`)

| Method | Role |
|--------|------|
| `host.add_tool(tool)` | Register an `McpTool` |
| `host.tool(name, description, props=None)` | Decorator sugar (**no** global registry) |
| `host.get(name)` | Whitelisted capabilities; otherwise `None` |

### Capabilities

| Capability | Default | Description |
|------------|---------|-------------|
| `logger` | Allowed | Logger (worker stderr is routed into host logs in subprocess mode) |
| `config_readonly` | Allowed | Redacted, recursively read-only config snapshot with `get_config(path, default=None)` |
| `data_dir` | Allowed | Isolated writable `Path` (`{user data}/mcp_plugins_data/<id>/`), lazily created on first `host.get("data_dir")`; survives plugin code upgrades |
| `media_player` | Opt-in | Scoped `MediaPlayerFacade` for in-app audio playback; works identically in both `inprocess` and `subprocess` modes |

> Setting `ALLOW_HOST_GET` explicitly to `[]` denies all host capabilities.

`config_readonly` exposes only these paths (URLs strip credentials, query strings and fragments; all tokens/API keys return defaults):

- `CONFIG_VERSION`
- `SYSTEM_OPTIONS.WINDOW_SIZE_MODE`
- `SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL`
- `SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL`
- `SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION`

Do **not** rely on removed global `@mcp_tool` or `get_instance` singletons.

## Audio / Media Plugins (`media_player`)

The app removed built-in third-party music scraping and instead provides a **source-agnostic audio playback foundation** (`AudioMixer` + `AudioDecoder` + `MediaPlayer`). Music, radio, podcast, audiobook, and ambient-sound plugins only need to resolve audio URLs or local files and delegate playback to `host.get("media_player")`:

- **Host audio benefits for free**: AEC echo cancellation, automatic TTS ducking (when AEC is active) or transient pause/resume (half-duplex), bundled FFmpeg decoding, audio device hot-swapping, and main-window `mediaLine` display.
- **No duplicate transport tools needed**: Whenever `media_player` is authorized and at least one external plugin is loaded, the host conditionally registers `media.pause`, `media.resume`, `media.stop`, `media.seek`, and `media.get_status`. Plugins only register their own domain tools (e.g. search/play, next track, playlists).
- **Lifecycle & ownership safety**: Each plugin gets its own `MediaPlayerFacade` bound to a `PluginLifecycle`. Unloading the plugin immediately revokes its handle and stops any playback owned by that plugin.

### `media_player` API reference

| Method | Description |
|--------|-------------|
| `await player.play_url(url, *, title="", start_position=0.0, headers=None)` | Play an `http/https` stream or an existing local **absolute** file path |
| `await player.pause()` | Pause active playback |
| `await player.resume()` | Resume paused playback |
| `await player.stop()` | Stop playback |
| `await player.seek(*, position=None, percent=None)` | Seek by seconds or percentage (`0~100`) |
| `await player.get_status()` | Returns structured dict (`status`, `state`, `title`, `position`, `duration`, `progress`, `owner_id`, `message`) |
| `await player.set_subtitle(text)` | Update the main-window `mediaLine` subtitle / lyric text |

**Security validation:**

- `url` allows only valid `http://` / `https://` URLs or existing absolute local file paths (e.g. `str(data_dir / "track.mp3")`). Relative paths and dangerous FFmpeg schemes (`file:`, `pipe:`, `concat:`) are rejected.
- `headers` whitelists `User-Agent`, `Referer`, `Origin`, `Cookie`, `Authorization`, `Accept`, `Accept-Language`, and `Range`, rejecting CRLF injection.

### Audio plugin example

See the complete runnable template in `examples/mcp_plugins/demo_media_plugin/`:

```python
import json

def register(host):
    player = host.get("media_player")
    data_dir = host.get("data_dir")

    @host.tool(
        "demo_media.play_url",
        "Play an HTTP(S) audio URL or absolute local audio file via the host player.",
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
                    "message": "Enable 'Allow external plugins to use in-app playback' in Settings -> MCP Tools.",
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

## Vendoring dependencies and multi-platform releases

### Rules of thumb

| Dependency type | One zip for all OSes? | What to do |
|-----------------|----------------------|------------|
| Pure Python (e.g. `httpx`, `markdown`) | Often yes | Single `lib/` is fine |
| Native wheels (`.so` / `.pyd` / `.dylib`) | **No** | **Build and publish per OS + arch** |
| Environment SDKs (ROS2, `rclpy`, vendor SDKs) | **Usually cannot vendor fully** | Document OS/SDK requirements; fail clearly on missing imports |

### Build commands (authors)

On the **target OS/arch**, with the **same Python minor** as the host:

```bash
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# or: python -m pip install -r requirements.txt -t lib/
```

Zip the entire plugin directory including `lib/`. The built-in installer automatically strips a single wrapper directory and blocks Zip Slip / symlinks.

## Runtimes: `python-inprocess` vs `python-subprocess`

Omitting `runtime` defaults to `python-inprocess`; **plugins with third-party dependencies or network/audio workflows should prefer `python-subprocess`**.

| | `python-inprocess` (default) | `python-subprocess` (recommended) |
|--|------------------------------|---------------------|
| Process | Same as host | Dedicated worker (bidirectional JSON lines over stdin/stdout) |
| Crash / hang isolation | Poor (can take down the app) | Better (timeout can kill the child) |
| `host.get("logger")` | Host logger | Local logger in worker (stderr routed to host logs) |
| `host.get("config_readonly")` | Redacted read-only snapshot | Same interface from redacted JSON snapshot |
| `host.get("data_dir")` | Lazily created `Path` | **Supported** (lazily resolved via `host_call` RPC) |
| `host.get("media_player")` | Scoped `MediaPlayerFacade` | **Supported** (bidirectional `host_call` RPC, identical async API) |
| Best for | Minimal trusted utilities | Heavy deps, audio/crawler plugins, crash isolation |

Samples in the repo:

```text
examples/mcp_plugins/com.example.hello/        # in-process
examples/mcp_plugins/com.example.hello_sub/    # subprocess
examples/mcp_plugins/demo_media_plugin/        # subprocess + media_player + data_dir
```

Note: subprocess isolation is **not** an OS security sandbox — same OS user privileges, separate interpreter and memory space.

## User install & management (Settings UI)

Open **Settings → MCP Tools**:

1. **Import ZIP / Import Folder**: Validates `manifest.json`, protects against path traversal/symlinks, backs up and rolls back on overwrite failures, and hot-reloads plugins immediately.
2. **In-app playback authorization**: Toggle **"Allow external plugins to use in-app playback"** and save.
3. **Inspect & Uninstall**: View installed plugins, versions, runtimes, and load errors; click **Uninstall** to revoke handles, auto-stop owned media, remove tools, and delete the plugin folder (plugin `data_dir` is preserved by default).
4. **Open Folder / Refresh**: Open `mcp_plugins/` in the OS file manager or trigger a rescan.

## Per-tool enable/disable (`MCP_TOOLS`)

Below the plugin manager in **Settings → MCP Tools**, toggle individual tools or entire groups:

- Config key: `MCP_TOOLS.DISABLED` (array of full tool names; default `[]` = all on).
- Built-in catalog is scanned from `src/mcp/tools/*/register.py` (group = folder name, e.g. `media` / `app` / `camera`).
- **When disabled**: omitted from MCP `tools/list`; `tools/call` is rejected.
- **After save**: if connected, the client reconnects in idle state so the server refreshes the tool list.

## Developer check

```bash
python scripts/check_mcp_plugin.py /path/to/demo_media_plugin
python scripts/check_mcp_plugin.py /path/to/plugin --strict
```

## Naming, conflicts & lifecycle

- Prefer `tool_name_prefix` (e.g. `demo_media.`).
- A duplicate tool name rejects the entire plugin registration and preserves existing tools and ownership. Cached hosts cannot register tools after the registration window closes.
- Unload, reload, and shutdown first revoke the plugin's `PluginLifecycle` (invalidating handles and stopping any media playback owned by that plugin), then remove tools and terminate subprocess workers.
- Worker JSON uses UTF-8; plugin stdout is redirected to the logging channel.

## Runtime APIs (host)

| API | Role |
|-----|------|
| Startup | `McpPlugin.setup` calls `server.register_builtin_tools()` and `server.reload_external_plugins(media_player=...)` |
| `server.unload_plugin(plugin_id)` | Revokes lifecycle, stops owned media, removes tools, kills subprocess workers, and re-syncs conditional `media.*` tools |
| `server.reload_external_plugins(media_player=...)` | Unloads externals, rescans plugins, and syncs conditional transport tools |

## Security

- **`python-inprocess`**: same process and privileges as the app.
- **`python-subprocess`**: better crash/dependency isolation; still same OS user — **not** a security sandbox.
- Install only trusted packages. Keep `media_player` disabled unless needed; set `MCP_PLUGINS.ENABLED=false` to disable all external plugins.

## See also

- [Built-in MCP guide](./index.md)
- Samples: `examples/mcp_plugins/` (including `demo_media_plugin`)
- Code: `src/mcp/plugins/` (`host.py`, `media_facade.py`, `installer.py`, `loader.py`, `registry.py`, `subprocess_runtime.py`, `subprocess_worker.py`) and `src/media/`
