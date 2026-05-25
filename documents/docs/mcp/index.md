# MCP Tool Development Guide

This document explains how to develop built-in MCP tools for py-xiaozhi. For external MCP service integration, refer to the [External MCP Integration Guide](xiaozhi-mcp.md).

## How It Works

1. On startup, `McpServer.add_common_tools()` calls `discover_tool_modules()` to automatically scan all sub-packages under `src/mcp/tools/`
2. Scanning imports each sub-package's `__init__.py`, as well as the sub-package's `_tools.py` (if it exists)
3. During import, the `@mcp_tool` decorator registers tool functions into a global registry
4. After registration, tools are exposed externally via the JSON-RPC 2.0 protocol

**You only need to write tool functions and add decorators -- no modification to `mcp_server.py` required.**

## Quick Start: Developing a Light Control Tool

### Step 1: Create the Directory

```
src/mcp/tools/light/
├── __init__.py      # Imports _tools to trigger decorator registration
├── _tools.py        # Tool registration (@mcp_tool decorator)
└── light_manager.py # Business logic (optional; simple tools can be written directly in _tools.py)
```

### Step 2: Write Business Logic (`light_manager.py`)

```python
"""Light control business logic."""

from src.logging import get_logger

logger = get_logger()


class LightManager:
    def __init__(self):
        self._on = False
        self._brightness = 100

    def turn_on(self) -> str:
        self._on = True
        logger.info("[Light] Light turned on")
        return "Light turned on"

    def turn_off(self) -> str:
        self._on = False
        logger.info("[Light] Light turned off")
        return "Light turned off"

    def set_brightness(self, level: int) -> str:
        self._brightness = max(0, min(100, level))
        logger.info(f"[Light] Brightness set to {self._brightness}%")
        return f"Brightness set to {self._brightness}%"

    def get_status(self) -> str:
        state = "on" if self._on else "off"
        return f"Light status: {state}, brightness: {self._brightness}%"


_light = LightManager()


def get_light_manager() -> LightManager:
    return _light
```

### Step 3: Register MCP Tools (`_tools.py`)

```python
"""Light MCP tool registration."""

from src.mcp.decorators import Prop, PropType, mcp_tool

from .light_manager import get_light_manager


@mcp_tool(
    name="self.light.turn_on",
    description="Turn on the light. Call when user says 'turn on the light', 'switch on the light'.",
)
async def tool_light_on(args):
    return get_light_manager().turn_on()


@mcp_tool(
    name="self.light.turn_off",
    description="Turn off the light. Call when user says 'turn off the light', 'switch off the light'.",
)
async def tool_light_off(args):
    return get_light_manager().turn_off()


@mcp_tool(
    name="self.light.set_brightness",
    description="Set the light brightness. Parameter: brightness (0-100).",
    props=[Prop("brightness", PropType.INT, min_val=0, max_val=100)],
)
async def tool_set_brightness(args):
    brightness = args.get("brightness", 100)
    return get_light_manager().set_brightness(brightness)


@mcp_tool(
    name="self.light.get_status",
    description="View the current state of the light (on/off, brightness).",
)
async def tool_light_status(args):
    return get_light_manager().get_status()
```

### Step 4: Write `__init__.py`

```python
"""Light control tools."""

# Import _tools to trigger @mcp_tool decorator registration
from . import _tools  # noqa: F401
```

**Done.** After restarting the application, all 4 light control tools are automatically available.

## API Reference

### `@mcp_tool` Decorator

```python
from src.mcp.decorators import Prop, PropType, mcp_tool

@mcp_tool(
    name="self.module.action",   # Tool name (globally unique)
    description="Tool description; the AI uses this to decide when to call",
    props=[                      # Parameter list (optional; omit if no parameters)
        Prop("city", PropType.STR),                              # Required string
        Prop("days", PropType.INT, default=3, min_val=1, max_val=7),  # Optional integer with range
        Prop("verbose", PropType.BOOL, default=False),           # Optional boolean
    ],
)
async def tool_function(args: dict) -> str:
    city = args.get("city", "")
    days = args.get("days", 3)
    return json.dumps({"city": city, "days": days}, ensure_ascii=False)
```

### Parameter Types

| Type | Usage | Description |
|------|------|------|
| `PropType.STR` | `Prop("name", PropType.STR)` | String |
| `PropType.INT` | `Prop("count", PropType.INT, min_val=0, max_val=100)` | Integer, with optional range limit |
| `PropType.BOOL` | `Prop("flag", PropType.BOOL, default=False)` | Boolean |

- Parameters without `default` are **required**
- Parameters with `default` are **optional**
- `min_val` / `max_val` only apply to `INT`

### Return Values

Tool functions must return a **`str`** type. Use `json.dumps()` when returning structured data:

```python
# Simple text
return "Operation successful"

# Structured JSON
return json.dumps({"status": "success", "data": result}, ensure_ascii=False)
```

**Do not return `dict`**; the MCP protocol requires text content.

## Auto-Discovery Rules

`discover_tool_modules()` scan order:

1. `src/mcp/tools/*.py` -- standalone files in the root directory (skips files starting with `_`)
2. `src/mcp/tools/<name>/` -- `__init__.py` of each sub-package
3. `src/mcp/tools/<name>/_tools.py` -- `_tools.py` inside the sub-package (if it exists)

**Key Points**:
- `__init__.py` must import `_tools` or tool modules, otherwise the decorator will not trigger
- Files starting with `_` are skipped (`_tools.py` is the only exception; it is explicitly loaded)
- A single module import failure only produces a warning and does not affect loading of other tools

## Development Conventions

| Rule | Description |
|------|------|
| Naming | Tool name format: `self.module.action`, globally unique |
| Async | Tool functions use `async def`; wrap blocking operations with `asyncio.to_thread()` |
| Timeout | External API calls must set a `timeout` |
| Logging | Use `from src.logging import get_logger`, prefix with `[ToolName]` |
| Error Handling | Catch exceptions with try/except, return user-readable error messages, log stack traces with `logger.error(..., exc_info=True)` |

## Existing Tool Modules

| Module | Path | Function | Detailed Docs |
|------|------|------|----------|
| Volume Control | `src/mcp/tools/volume/` | Volume set/query/status diagnostics | [system.md](system.md) |
| App Management | `src/mcp/tools/app/` | App launch/kill/scan, running process query | [system.md](system.md) |
| Camera | `src/mcp/tools/camera/` | Photo capture, visual Q&A | [camera.md](camera.md) |
| Screenshot | `src/mcp/tools/screenshot/` | Desktop screenshot, screen OCR, multi-monitor support | — |
| Music | `src/mcp/tools/music/` | Search & play, pause/resume/stop, lyrics, local playlist | [music.md](music.md) |
| Weather | `src/mcp/tools/weather/` | Weather query, weather forecast (example tool) | — |
