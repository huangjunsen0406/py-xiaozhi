# MCP Tool Development Guide

This document explains how to develop **built-in** MCP tools for py-xiaozhi. For external MCP services, see the [External MCP Integration Guide](xiaozhi-mcp.md).

## How It Works

1. `McpPlugin.setup` creates runtime objects (e.g. camera) and calls `register_camera_tools` / `register_screenshot_tools`
2. `McpServer.add_common_tools()` **explicitly** calls each package’s `register_*_tools(add_tool, …)`
3. Each `register_*` holds dependencies in a closure (e.g. `MusicPlayer`, `VolumeController`), builds `McpTool` instances, and calls `add_tool`
4. Tools are exposed over JSON-RPC 2.0

**Built-in tools do not use a global `@mcp_tool` decorator or filesystem auto-discovery.** To add a package: implement `register_*_tools` and wire it once in `add_common_tools` (or `McpPlugin`).

Inject runtime objects from the container / plugin — **do not** use module-level `get_instance` singletons.

## Quick Start: Light Control Tool

### Step 1: Directory

```
src/mcp/tools/light/
├── __init__.py          # export register_light_tools
├── _tools.py            # register_light_tools
└── light_manager.py     # optional business logic
```

### Step 2: Business logic (`light_manager.py`)

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
```

### Step 3: `register_light_tools` (`_tools.py`)

```python
"""Light MCP tool registration."""

from collections.abc import Callable
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .light_manager import LightManager

logger = get_logger()


def register_light_tools(
    add_tool: Callable[[McpTool], None],
    manager: LightManager | None = None,
) -> None:
    light = manager or LightManager()

    async def turn_on(args: dict[str, Any]) -> str:
        return light.turn_on()

    async def turn_off(args: dict[str, Any]) -> str:
        return light.turn_off()

    async def set_brightness(args: dict[str, Any]) -> str:
        brightness = int(args.get("brightness", 100))
        return light.set_brightness(brightness)

    async def get_status(args: dict[str, Any]) -> str:
        return light.get_status()

    tools = [
        McpTool(
            "self.light.turn_on",
            "Turn on the light. Call when user says 'turn on the light'.",
            PropertyList(),
            turn_on,
        ),
        McpTool(
            "self.light.turn_off",
            "Turn off the light. Call when user says 'turn off the light'.",
            PropertyList(),
            turn_off,
        ),
        McpTool(
            "self.light.set_brightness",
            "Set light brightness. Parameter: brightness (0-100).",
            PropertyList(
                [
                    Property(
                        "brightness",
                        PropertyType.INTEGER,
                        min_value=0,
                        max_value=100,
                    )
                ]
            ),
            set_brightness,
        ),
        McpTool(
            "self.light.get_status",
            "View current light state (on/off, brightness).",
            PropertyList(),
            get_status,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("Registered %d light MCP tools", len(tools))
```

### Step 4: `__init__.py`

```python
"""Light control tools."""

from ._tools import register_light_tools

__all__ = ["register_light_tools"]
```

### Step 5: Wire into the host

In `src/mcp/mcp_server.py` → `add_common_tools`:

```python
from src.mcp.tools.light import register_light_tools

register_light_tools(self.add_tool)
```

If the tool needs a container-owned object, create it in `McpPlugin.setup` and pass it into `register_light_tools(server.add_tool, manager)`.

**Done.** Restart the app to load the tools.

## API Reference

### `McpTool` / `Property`

```python
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

McpTool(
    name="self.module.action",  # globally unique
    description="Used by the model to decide when to call",
    properties=PropertyList(
        [
            Property("city", PropertyType.STRING),
            Property(
                "days",
                PropertyType.INTEGER,
                default_value=3,
                min_value=1,
                max_value=7,
            ),
            Property("verbose", PropertyType.BOOLEAN, default_value=False),
        ]
    ),
    callback=async_handler,  # async def handler(args: dict) -> str | int | bool
)
```

### Parameter types

| Type | Usage | Notes |
|------|------|------|
| `PropertyType.STRING` | `Property("name", PropertyType.STRING)` | String |
| `PropertyType.INTEGER` | `Property("n", PropertyType.INTEGER, min_value=0, max_value=100)` | Integer, optional range |
| `PropertyType.BOOLEAN` | `Property("flag", PropertyType.BOOLEAN, default_value=False)` | Boolean |

### Return values

Prefer **`str`** (or bool/int). Use `json.dumps(..., ensure_ascii=False)` for structured payloads.

## Registration conventions

| Rule | Description |
|------|------|
| Entry | Export `register_*_tools(add_tool, ...)` from the package |
| Wiring | Call once from `add_common_tools` or `McpPlugin.setup` |
| Dependencies | Inject into the closure; no module-level singletons |
| Naming | Prefer `self.module.action`, globally unique |
| Async | `async def`; wrap blocking I/O with `asyncio.to_thread` |
| Timeout | Always set `timeout` for external APIs |
| Logging | `get_logger()`, prefix `[ToolName]` |
| Errors | try/except, user-readable message + `exc_info=True` |

## Built-in tool modules

| Module | Path | Registration | Docs |
|------|------|----------|------|
| Volume | `volume/` | `register_volume_tools` | [system.md](system.md) |
| Apps | `app/` | `register_app_tools` | [system.md](system.md) |
| Camera | `camera/` | `register_camera_tools` (McpPlugin) | [camera.md](camera.md) |
| Screenshot | `screenshot/` | `register_screenshot_tools` (McpPlugin) | — |
| Music | `music/` | `register_music_tools` (injected MusicPlayer) | [music.md](music.md) |
| Weather | `weather/` | `register_weather_tools` (mock for now) | — |

User-directory **external** Python plugins (`mcp_plugins`) are described in the repo’s MCP extension design note; they coexist with built-in `register_*` and do not bring back decorator discovery.
