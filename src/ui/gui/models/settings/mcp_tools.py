"""MCP 工具启用 + 外挂插件管理（导入 ZIP/文件夹、卸载、应用内播放授权、刷新）."""

from __future__ import annotations

import json
from typing import Any

from src.i18n import t
from src.logging import get_logger
from src.mcp.plugins.host import DEFAULT_ALLOW_GET
from src.mcp.plugins.installer import (
    install_plugin_from_dir,
    install_plugin_from_zip,
    list_installed_plugins,
    open_directory_in_file_manager,
    uninstall_plugin,
)
from src.mcp.tool_catalog import full_catalog_rows, normalize_disabled
from src.utils.resource_finder import get_mcp_plugins_dir

logger = get_logger()


class SettingsMcpToolsMixin:
    """依赖宿主提供 _get_value / _set_value / settingsChanged / statusMessage / set_error."""

    def _get_mcpToolsDisabledJson(self) -> str:
        raw = self._get_value("MCP_TOOLS.DISABLED", []) or []
        return json.dumps(normalize_disabled(raw), ensure_ascii=False)

    def _set_mcpToolsDisabledJson(self, value: str) -> None:
        try:
            data = json.loads(value) if value else []
        except json.JSONDecodeError:
            data = []
        self._set_value("MCP_TOOLS.DISABLED", normalize_disabled(data))

    def _mcp_disabled_list(self) -> list[str]:
        return normalize_disabled(self._get_value("MCP_TOOLS.DISABLED", []) or [])

    def _all_catalog_base_rows(self) -> list[dict[str, str]]:
        return full_catalog_rows(
            runtime_names=list(self._runtime_tool_names()),
            extra_disabled=self._mcp_disabled_list(),
            config=self._config_manager,
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

    # ========== 外挂插件能力授权与安装管理 ==========

    def _mcp_allow_host_get(self) -> list[str]:
        raw = self._get_value("MCP_PLUGINS.ALLOW_HOST_GET", list(DEFAULT_ALLOW_GET))
        if not isinstance(raw, list):
            return sorted(DEFAULT_ALLOW_GET)
        return [str(x).strip() for x in raw if str(x).strip()]

    def _get_mcpAllowMediaPlayer(self) -> bool:
        return "media_player" in self._mcp_allow_host_get()

    def _set_mcpAllowMediaPlayer(self, allowed: bool) -> None:
        items = self._mcp_allow_host_get()
        if allowed:
            if "media_player" not in items:
                items.append("media_player")
        else:
            items = [x for x in items if x != "media_player"]
        self._set_value("MCP_PLUGINS.ALLOW_HOST_GET", items)

    def _get_mcpPluginsDir(self) -> str:
        try:
            return str(get_mcp_plugins_dir(self._config_manager))
        except Exception as exc:
            logger.debug("解析 MCP 插件目录失败: %s", exc)
            return ""

    def _get_mcpInstalledPluginsJson(self) -> str:
        try:
            plugins_dir = get_mcp_plugins_dir(self._config_manager)
            rows = list_installed_plugins(plugins_dir)
            return json.dumps(rows, ensure_ascii=False)
        except Exception as exc:
            logger.warning("扫描已安装 MCP 插件失败: %s", exc)
            return "[]"

    def _trigger_runtime_plugin_reload(self) -> None:
        """通知运行中的 McpPlugin 热重载外挂，并刷新设置页视图."""
        bus = getattr(self, "_event_bus", None)
        tm = getattr(self, "_task_manager", None)
        if bus is not None and tm is not None:
            try:
                from src.core.event_bus import Events

                tm.spawn_threadsafe(
                    bus.emit(Events.CONFIG_CHANGED, {"reload_mcp_plugins": True}),
                    name="mcp:plugins:reload",
                )
            except Exception as exc:
                logger.debug("触发 MCP 插件热重载失败: %s", exc)
        self.settingsChanged.emit()

    def _import_mcp_plugin_zip(self) -> bool:
        from PySide6.QtWidgets import QApplication, QFileDialog

        parent = QApplication.activeWindow()
        zip_path, _ = QFileDialog.getOpenFileName(
            parent,
            t("settings.mcp.import_zip_dialog"),
            "",
            t("settings.mcp.import_zip_filter"),
        )
        if not zip_path:
            return False
        try:
            plugins_dir = get_mcp_plugins_dir(self._config_manager)
            info = install_plugin_from_zip(zip_path, plugins_dir)
            key = (
                "settings.mcp.plugin_updated"
                if info.get("replaced")
                else "settings.mcp.plugin_imported"
            )
            self.set_error("")
            self.statusMessage.emit(t(key, name=info["name"]))
            self._trigger_runtime_plugin_reload()
            return True
        except Exception as exc:
            logger.warning("导入 MCP 插件 ZIP 失败: %s", exc)
            self.set_error(t("settings.mcp.import_failed", error=exc))
            return False

    def _import_mcp_plugin_dir(self) -> bool:
        from PySide6.QtWidgets import QApplication, QFileDialog

        parent = QApplication.activeWindow()
        src_dir = QFileDialog.getExistingDirectory(
            parent,
            t("settings.mcp.import_dir_dialog"),
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )
        if not src_dir:
            return False
        try:
            plugins_dir = get_mcp_plugins_dir(self._config_manager)
            info = install_plugin_from_dir(src_dir, plugins_dir)
            key = (
                "settings.mcp.plugin_updated"
                if info.get("replaced")
                else "settings.mcp.plugin_imported"
            )
            self.set_error("")
            self.statusMessage.emit(t(key, name=info["name"]))
            self._trigger_runtime_plugin_reload()
            return True
        except Exception as exc:
            logger.warning("导入 MCP 插件文件夹失败: %s", exc)
            self.set_error(t("settings.mcp.import_failed", error=exc))
            return False

    def _uninstall_mcp_plugin(self, plugin_id: str) -> bool:
        try:
            plugins_dir = get_mcp_plugins_dir(self._config_manager)
            res = uninstall_plugin(plugin_id, plugins_dir)
            if not res.get("ok"):
                self.set_error(
                    res.get("error") or t("settings.mcp.uninstall_failed")
                )
                return False
            self.set_error("")
            self.statusMessage.emit(
                t("settings.mcp.plugin_uninstalled", plugin_id=plugin_id)
            )
            self._trigger_runtime_plugin_reload()
            return True
        except Exception as exc:
            logger.warning("卸载 MCP 插件失败 %s: %s", plugin_id, exc)
            self.set_error(t("settings.mcp.uninstall_failed_detail", error=exc))
            return False

    def _open_mcp_plugins_dir(self) -> bool:
        try:
            plugins_dir = get_mcp_plugins_dir(self._config_manager)
            return open_directory_in_file_manager(plugins_dir)
        except Exception as exc:
            logger.warning("打开 MCP 插件目录失败: %s", exc)
            return False
