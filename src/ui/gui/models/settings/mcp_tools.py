"""MCP 工具启用：黑名单 MCP_TOOLS.DISABLED，分组列表供设置 UI."""

from __future__ import annotations

import json
from typing import Any

from src.mcp.tool_catalog import full_catalog_rows, normalize_disabled


class SettingsMcpToolsMixin:
    """依赖宿主提供 _get_value / _set_value / settingsChanged."""

    def _get_mcpToolsDisabledJson(self) -> str:
        raw = self._get_value("MCP_TOOLS.DISABLED", []) or []
        return json.dumps(normalize_disabled(raw), ensure_ascii=False)

    def _set_mcpToolsDisabledJson(self, value: str) -> None:
        try:
            data = json.loads(value) if value else []
        except Exception:
            data = []
        self._set_value("MCP_TOOLS.DISABLED", normalize_disabled(data))

    def _mcp_disabled_list(self) -> list[str]:
        return normalize_disabled(self._get_value("MCP_TOOLS.DISABLED", []) or [])

    def _try_list_runtime_tools(self) -> list[str]:
        """尽力获取进程内已注册 MCP 工具名（可能为空）."""
        import gc

        try:
            from src.mcp.mcp_server import McpServer
        except Exception:
            return []
        for obj in gc.get_objects():
            try:
                if isinstance(obj, McpServer) and getattr(obj, "tools", None):
                    return [t.name for t in obj.tools]
            except Exception:
                continue
        return []

    def _all_catalog_base_rows(self) -> list[dict[str, str]]:
        return full_catalog_rows(
            runtime_names=self._try_list_runtime_tools(),
            extra_disabled=self._mcp_disabled_list(),
        )

    def _get_mcpToolsCatalogJson(self) -> str:
        disabled = set(self._mcp_disabled_list())
        rows: list[dict[str, Any]] = []
        for r in self._all_catalog_base_rows():
            item = dict(r)
            item["enabled"] = item["name"] not in disabled
            rows.append(item)
        return json.dumps(rows, ensure_ascii=False)

    def _set_mcpToolEnabled(self, name: str, enabled: bool) -> None:
        name = (name or "").strip()
        if not name:
            return
        disabled = self._mcp_disabled_list()
        if enabled:
            disabled = [n for n in disabled if n != name]
        else:
            if name not in disabled:
                disabled.append(name)
        self._set_value("MCP_TOOLS.DISABLED", disabled)

    def _set_mcpToolGroupEnabled(self, group: str, enabled: bool) -> None:
        group = (group or "").strip()
        if not group:
            return
        disabled = set(self._mcp_disabled_list())
        names = {
            r["name"] for r in self._all_catalog_base_rows() if r.get("group") == group
        }
        if not names:
            return
        if enabled:
            disabled -= names
        else:
            disabled |= names
        self._set_value("MCP_TOOLS.DISABLED", sorted(disabled))
