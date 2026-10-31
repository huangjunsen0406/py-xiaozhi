"""每个 McpServer 长期持有的外挂安装记录与生命周期。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.logging import get_logger
from src.mcp.tooling import McpTool

logger = get_logger()

if TYPE_CHECKING:
    from src.mcp.plugins.subprocess_runtime import PluginSubprocessSession


@dataclass(frozen=True)
class PluginInstallation:
    tool_names: tuple[str, ...]
    session: PluginSubprocessSession | None = None


class PluginRuntime:
    """以一次安装为单位拥有工具和可选 worker，包括零工具插件。"""

    def __init__(
        self,
        add_tools_atomic: Callable[[list[McpTool]], None],
        remove_tools_by_names: Callable[[set[str]], int],
    ) -> None:
        self._add_tools_atomic = add_tools_atomic
        self._remove_tools_by_names = remove_tools_by_names
        self._installations: dict[str, PluginInstallation] = {}

    @property
    def tool_owner(self) -> dict[str, str]:
        """从安装记录生成诊断快照，调用方不能更改归属。"""
        return {
            name: plugin_id
            for plugin_id, installation in self._installations.items()
            for name in installation.tool_names
        }

    def has_plugin(self, plugin_id: str) -> bool:
        return plugin_id in self._installations

    def install(
        self,
        plugin_id: str,
        tools: list[McpTool],
        *,
        session: PluginSubprocessSession | None = None,
    ) -> None:
        """整批工具提交成功后才接管安装；失败的 session 仍由 loader 回收。"""
        if self.has_plugin(plugin_id):
            raise ValueError(f"插件 id 冲突: {plugin_id}")
        names = tuple(tool.name for tool in tools)
        if len(names) != len(set(names)):
            raise ValueError(f"插件工具名称冲突: {plugin_id}")
        if set(names) & self.tool_owner.keys():
            raise ValueError(f"插件工具归属冲突: {plugin_id}")
        installation = PluginInstallation(names, session)
        self._add_tools_atomic(tools)
        self._installations[plugin_id] = installation

    def unload(self, plugin_id: str) -> int:
        installation = self._installations.pop(plugin_id, None)
        if installation is None:
            return 0
        try:
            return self._remove_tools_by_names(set(installation.tool_names))
        finally:
            if installation.session is not None:
                installation.session.terminate()

    def unload_all(self) -> None:
        for plugin_id in tuple(self._installations):
            try:
                self.unload(plugin_id)
            except Exception:
                logger.error("[MCP插件:%s] 卸载失败", plugin_id, exc_info=True)
