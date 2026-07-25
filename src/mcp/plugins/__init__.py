"""MCP 外挂插件：宿主 API 与加载器."""

from .host import McpHost
from .loader import PluginLoader, default_plugins_dir
from .registry import PluginRegistry, get_plugin_registry

__all__ = [
    "McpHost",
    "PluginLoader",
    "PluginRegistry",
    "default_plugins_dir",
    "get_plugin_registry",
]
