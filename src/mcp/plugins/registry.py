"""外挂 MCP 插件运行时注册表：归属索引与卸载."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.logging import get_logger

if TYPE_CHECKING:
    from src.mcp.mcp_server import McpServer

logger = get_logger()


@dataclass
class PluginRegistry:
    """记录外挂 tool_name -> plugin_id，支持按 id 从 McpServer 卸工具."""

    tool_owner: dict[str, str] = field(default_factory=dict)

    def register_ownership(self, plugin_id: str, tool_names: list[str]) -> None:
        for name in tool_names:
            self.tool_owner[name] = plugin_id

    def tools_for_plugin(self, plugin_id: str) -> list[str]:
        return [n for n, p in self.tool_owner.items() if p == plugin_id]

    def unload_plugin(self, server: "McpServer", plugin_id: str) -> int:
        """从 server.tools 移除该插件注册的工具；返回移除数量."""
        names = set(self.tools_for_plugin(plugin_id))
        if not names:
            logger.info("[MCP插件] 卸载 %s：无已注册工具", plugin_id)
            return 0
        before = len(server.tools)
        server.tools = [t for t in server.tools if t.name not in names]
        removed = before - len(server.tools)
        for n in names:
            self.tool_owner.pop(n, None)
        logger.info(
            "[MCP插件] 已卸载 %s：移除 %d 个工具 %s",
            plugin_id,
            removed,
            sorted(names),
        )
        return removed

    def clear(self) -> None:
        self.tool_owner.clear()


# 进程内可选共享（由 McpServer 持有更清晰；此处供简单场景）
_default_registry: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = PluginRegistry()
    return _default_registry
