# System Tools

System tools provide desktop-oriented volume control and application management capabilities, encapsulating MCP-callable volume setting/querying functionality, as well as cross-platform application scanning, launching, listing, and closing workflows.

### Common Use Cases

**Volume Adjustment and Query:**

- "Set the volume to 40"
- "Mute the sound"
- "What is the current volume"
- "Is the speaker available"

**Application Launching:**

- "Open WeChat"
- "Launch Notepad"
- "Help me open the browser"
- "Run VS Code"

**Application Discovery and Listing:**

- "What applications are on the system"
- "List the running programs"
- "Which media players are available"
- "Check if QQ is running"

**Application Closing:**

- "Quit QQ Music"
- "Force close Chrome"
- "Close the media player"
- "End all processes named XXX"

### Usage Tips

1. **Volume Range**: All volume adjustments use integers from 0-100, with 0 representing mute
2. **Cross-Platform Capability**: Application management tools automatically detect Windows/macOS/Linux and call the corresponding implementation
3. **Name Matching**: It is recommended to use the `name` field provided by `self.application.scan_installed` to launch or close applications, reducing fuzzy matching errors
4. **Result Parsing**: `get_volume_status`, `scan_installed`, and `list_running` all return JSON strings; callers need to parse them with `json.loads`

The AI assistant will automatically select the appropriate system tools based on needs, enabling volume and application-related operations in voice/text sessions.

## Feature Overview

### Volume and Audio Control

- **Absolute Volume Setting**: Directly set the speaker volume to a target value
- **Volume Query**: Get the current volume percentage
- **Status Diagnostics**: Query mute flag, dependency availability, and other status information for troubleshooting audio capabilities

### Application Management

- **Launch Application**: Open desktop applications, tools, or games through a unified entry point
- **Scan Applications**: Get a list of launchable applications, supporting both Chinese and English names
- **List Running Applications**: View real-time running processes, with name filtering support
- **Close Application**: Gracefully exit or force-terminate specified applications

### Status Transparency

- **Structured Responses**: All query-type tools return structured JSON, including fields like `success` and `message`
- **Thread Isolation**: Actual operations (scanning/launching/closing) execute in background threads or subprocesses, not blocking the MCP main loop

## Tool List

### 1. Volume and Audio Tools

#### self.audio_speaker.set_volume - Set System Volume

Sets the system speaker volume to an absolute value, internally calling `VolumeController` directly.

**Parameters:**

- `volume` (required): Integer from 0-100, where 0 represents mute

**Use Cases:**

- Precisely adjust volume
- Execute mute/unmute
- User specifies "turn up/down to a specific value"

**Returns:**

- `True/False` boolean indicating whether the operation was successful

#### self.audio_speaker.get_volume - Query Current Volume

Returns the current speaker volume (0-100). Returns a default value when dependencies are missing.

**Parameters:**
None

**Use Cases:**

- Answer "what is the current volume"
- Read the old value before adjusting
- Check if muted

**Returns:**

- Integer volume value; `VolumeController.DEFAULT_VOLUME` when dependencies are unavailable

#### self.audio_speaker.get_volume_status - Get Volume Status

Provides detailed JSON including volume, mute flag, and dependency availability.

**Parameters:**
None

**Use Cases:**

- Troubleshoot whether volume control dependencies are complete
- Determine if audio is muted
- Display richer status in the UI

**Returns:**

- JSON string with fields including `volume`, `muted`, `available`, `reason/error`

### 2. Application Lifecycle Tools

#### self.application.launch - Launch Application

Cross-platform application launching: supports desktop software, system tools, browsers, games, etc.

**Parameters:**

- `app_name` (required): Application name/path, can be a mix of Chinese and English

**Use Cases:**

- Open QQ, WeChat, browser, VS Code, etc.
- Invoke system built-in applications (calculator, notepad, etc.)
- Launch programs installed in PATH or already scanned

#### self.application.scan_installed - Scan Installed Applications

Lists launchable applications, providing fields like `name`, `display_name`, `path`, `type` for matching.

**Parameters:**

- `force_refresh` (optional): Whether to force a re-scan, default `false`

**Use Cases:**

- Query first when unsure of the application name
- Prompt the user about available software on the current system
- Troubleshoot names when `self.application.launch` fails

**Returns:**

- JSON string containing `success`, `total_count`, `applications[]`

#### self.application.list_running - List Running Applications

Real-time listing of currently running application processes, with name-based filtering.

**Parameters:**

- `filter_name` (optional): String contains match, default empty

**Use Cases:**

- Answer "which programs are running"
- Confirm if an application is running before closing it
- Troubleshoot resource-consuming processes

**Returns:**

- JSON string with fields `success`, `total_count`, `applications[]`

#### self.application.kill - Close/Force-Terminate Application

Closes one or more matching running programs by name. On Windows, supports grouped closing and forced kill.

**Parameters:**

- `app_name` (required): The name of the application to close
- `force` (optional): When `true`, enables forced kill; default `false`

**Use Cases:**

- User requests to quit/close an application
- Program is frozen and needs forced termination
- Batch cleanup of identically named program instances

**Returns:**

- `True/False` boolean indicating whether at least one matching process was successfully closed

> It is recommended to use `self.application.list_running` to get PID/name first, then call `self.application.kill` to avoid accidentally killing the wrong process.

## Usage Examples

### Volume Control Examples

```python
# Set volume to 50
await mcp_server.call_tool("self.audio_speaker.set_volume", {"volume": 50})

# Query current volume
current_volume = await mcp_server.call_tool("self.audio_speaker.get_volume", {})

# Get detailed volume status (JSON string requires manual parsing)
import json
status_json = await mcp_server.call_tool("self.audio_speaker.get_volume_status", {})
status = json.loads(status_json)
```

### Application Management Examples

```python
import json

# Scan installed applications
scan_raw = await mcp_server.call_tool("self.application.scan_installed", {"force_refresh": False})
scan_result = json.loads(scan_raw)

# Launch the first scan result
first_app = scan_result["applications"][0]["name"]
await mcp_server.call_tool("self.application.launch", {"app_name": first_app})

# List running applications
running_raw = await mcp_server.call_tool("self.application.list_running", {"filter_name": "QQ"})
running = json.loads(running_raw)

# Close all applications containing "QQ" in their name
await mcp_server.call_tool("self.application.kill", {
    "app_name": "QQ",
    "force": False
})
```

## Technical Architecture

### Volume Control (`src/mcp/tools/volume/`)

- **VolumeController**: Cross-platform volume control (Windows: pycaw, macOS: applescript, Linux: pactl/wpctl/amixer)
- **Async Wrapper**: Moves blocking calls to the thread pool via `asyncio.to_thread`
- **Fault Tolerance Strategy**: Returns default volume and marks `available=False` in the status interface when dependencies are missing

### Application Management (`src/mcp/tools/app/`)

- **Process Management**: `process_manager.py` based on psutil, unifying process listing and termination across three platforms
- **Application Scanning**: `scanner.py` + platform files (`scanner_mac.py` / `scanner_windows.py` / `scanner_linux.py`)
- **Application Launching**: `launcher.py` + platform files (`launcher_mac.py` / `launcher_windows.py` / `launcher_linux.py`)
- **Unified Matching**: `AppMatcher` in `utils.py` handles fuzzy matching (Chinese, English, case-insensitive, aliases)

## Data Structures

### Volume Status

```python
{
    "volume": 42,
    "muted": false,
    "available": true
}
```

### Installed Application Scan Results

```python
{
    "success": true,
    "total_count": 128,
    "applications": [
        {
            "name": "QQ",
            "display_name": "QQ Music",
            "path": "C:/Program Files/QQMusic/QQMusic.exe",
            "type": "exe"
        },
        {
            "name": "WeChat",
            "display_name": "WeChat",
            "path": "/Applications/WeChat.app",
            "type": "app"
        }
    ],
    "message": "Successfully scanned 128 installed applications"
}
```

### Running Application List

```python
{
    "success": true,
    "total_count": 2,
    "applications": [
        {
            "pid": 1234,
            "name": "WeChat",
            "display_name": "WeChat",
            "command": "/Applications/WeChat.app/Contents/MacOS/WeChat"
        },
        {
            "pid": 4321,
            "name": "QQMusic",
            "display_name": "QQ Music",
            "command": "C:/Program Files/QQMusic/QQMusic.exe"
        }
    ],
    "message": "Found 2 running applications"
}
```

## Best Practices

### Volume Management

- Call `get_volume` first to get the old value, then provide a statement like "adjusted from X to Y"
- Mute can be set directly to 0; when unmuting, restore the volume to the previously recorded value
- When dependencies are missing, prompt the user to install/grant audio control permissions

### Application Management

- Before launching/closing, verify the name using `scan_installed` or `list_running` to reduce misoperations
- Before force-closing (`force=true`), try a normal close first to avoid data corruption
- For multi-instance programs, list running instances first and inform the user by PID

## Troubleshooting

1. **Volume Setting Failed**: Check `available`/`reason` in `get_volume_status`
2. **Application Launch Failed**: Confirm the application exists in scan results, or provide the full path
3. **Application Close Failed**: Use `list_running` to verify it is actually running; enable `force` if necessary
4. **Scan Timeout**: Scanning many applications may take longer; prompt the user to wait or limit the scan scope

## Security Considerations

### Permissions and Access Control

- Volume control depends on system-level permissions; first-time calls may require user authorization
- Operations like launching and closing applications should only be executed after explicit user commands to avoid misoperation on sensitive programs
- `force` close will directly kill the process; inform the user that data loss may occur before calling

### Data Protection

- Scan/running lists may contain user-installed software names; display with caution externally
- When persisting logs, it is recommended to sanitize sensitive data and keep only necessary fields
- Do not record or report specific command-line arguments to protect privacy

With these system tools, the AI assistant can safely adjust volume, launch, or manage desktop applications in a multi-platform environment, providing end users with a natural language-driven system control experience.
