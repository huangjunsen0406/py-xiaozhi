"""外挂 MCP 宿主 API（稳定契约）.

插件仅通过 McpHost 注册工具与按白名单取能力，禁止依赖全局单例。
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from src.logging import get_logger
from src.mcp.plugins.media_facade import PluginLifecycle
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()

# 默认允许的 host.get 名称（media_player 等需配置显式加入）
DEFAULT_ALLOW_GET = frozenset({"config_readonly", "logger", "data_dir"})


def config_readonly_snapshot(config: Any) -> dict[str, Any]:
    """只复制公开字段；不把 ConfigManager 或未知配置送入插件。"""
    if isinstance(config, ReadOnlyConfig):
        return deepcopy(config._snapshot)
    paths = (
        "CONFIG_VERSION",
        "SYSTEM_OPTIONS.WINDOW_SIZE_MODE",
        "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL",
        "SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL",
        "SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION",
    )
    snapshot: dict[str, Any] = {}
    for path in paths:
        if isinstance(config, Mapping):
            value: Any = config
            for part in path.split("."):
                value = value.get(part) if isinstance(value, Mapping) else None
        else:
            value = config.get_config(path) if hasattr(config, "get_config") else None
        if value is None or not isinstance(value, (str, int, float, bool)):
            continue
        if path.endswith("_URL"):
            try:
                url = urlsplit(str(value))
                # 查询串/片段/用户信息也可能含密钥。
                value = urlunsplit((url.scheme, url.netloc.rsplit("@", 1)[-1], url.path, "", ""))
            except ValueError:
                continue
        target = snapshot
        *parents, key = path.split(".")
        for part in parents:
            target = target.setdefault(part, {})
        target[key] = value
    return snapshot


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


class ReadOnlyConfig(Mapping):
    """独立的脱敏快照，兼容 get_config(path, default)，没有写入方法。"""

    def __init__(self, config: Any) -> None:
        self._snapshot = config_readonly_snapshot(config)
        self._data = _freeze(self._snapshot)

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def get_config(self, path: str, default: Any = None) -> Any:
        value: Any = self._data
        for part in path.split("."):
            if not isinstance(value, Mapping) or part not in value:
                return default
            value = value[part]
        return value


class McpHost:
    """绑定到一次装配过程的宿主门面."""

    def __init__(
        self,
        add_tool: Callable[[McpTool], None],
        *,
        capabilities: dict[str, Any] | None = None,
        capability_factories: dict[str, Callable[[str, PluginLifecycle], Any]] | None = None,
        allow_get: Sequence[str] | None = None,
        plugin_id: str | None = None,
        lifecycle: PluginLifecycle | None = None,
    ) -> None:
        self._add_tool = add_tool
        self._capabilities = dict(capabilities or {})
        self._capability_factories = dict(capability_factories or {})
        self._resolved_caps: dict[str, Any] = {}
        if "config_readonly" in self._capabilities:
            self._capabilities["config_readonly"] = ReadOnlyConfig(
                self._capabilities["config_readonly"]
            )
        self._allow_get = (
            frozenset(allow_get) if allow_get is not None else DEFAULT_ALLOW_GET
        )
        self._plugin_id = plugin_id or "unknown"
        self._lifecycle = lifecycle or PluginLifecycle(self._plugin_id)
        self._registered_names: list[str] = []
        self._registration_open = True

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def lifecycle(self) -> PluginLifecycle:
        return self._lifecycle

    @property
    def registered_tool_names(self) -> list[str]:
        return list(self._registered_names)

    def add_tool(self, tool: McpTool) -> None:
        """注册工具；记录名称供卸载/诊断."""
        if not self._registration_open:
            raise RuntimeError("插件注册阶段已结束")
        if tool.name in self._registered_names:
            raise ValueError(f"Tool name conflict: {tool.name}")
        self._add_tool(tool)
        self._registered_names.append(tool.name)
        logger.info("[MCP插件:%s] 注册工具: %s", self._plugin_id, tool.name)

    def close_registration(self) -> None:
        self._registration_open = False

    def get(self, name: str) -> Any:
        """按白名单返回宿主能力；未授权或未提供则 None."""
        self._lifecycle.assert_active()
        if name not in self._allow_get:
            logger.warning(
                "[MCP插件:%s] host.get(%r) 不在白名单 %s",
                self._plugin_id,
                name,
                sorted(self._allow_get),
            )
            return None
        if name == "logger":
            return get_logger()
        if name == "data_dir":
            if "data_dir" not in self._resolved_caps:
                from src.utils.resource_finder import get_mcp_plugin_data_dir

                self._resolved_caps["data_dir"] = get_mcp_plugin_data_dir(
                    self._plugin_id
                )
            return self._resolved_caps["data_dir"]
        if name in self._capability_factories:
            if name not in self._resolved_caps:
                self._resolved_caps[name] = self._capability_factories[name](
                    self._plugin_id, self._lifecycle
                )
            return self._resolved_caps[name]
        return self._capabilities.get(name)

    def tool(
        self,
        name: str,
        description: str,
        props: Sequence[Property | dict[str, Any]] | None = None,
    ):
        """装饰器：将函数注册为 McpTool（不写全局 registry）."""

        def decorator(func: Callable):
            prop_list = _to_property_list(props)
            self.add_tool(McpTool(name, description, prop_list, func))
            return func

        return decorator


def _to_property_list(
    props: Sequence[Property | dict[str, Any]] | None,
) -> PropertyList:
    if not props:
        return PropertyList()
    converted: list[Property] = []
    for p in props:
        if isinstance(p, Property):
            converted.append(p)
            continue
        if not isinstance(p, dict):
            raise TypeError(f"props 项须为 Property 或 dict，得到 {type(p)}")
        converted.append(_dict_to_property(p))
    return PropertyList(converted)


_PROPERTY_TYPE_MAP = {
    "str": PropertyType.STRING,
    "string": PropertyType.STRING,
    "int": PropertyType.INTEGER,
    "integer": PropertyType.INTEGER,
    "bool": PropertyType.BOOLEAN,
    "boolean": PropertyType.BOOLEAN,
}


def property_from_dict(data: dict[str, Any], *, strict: bool = True) -> Property:
    """将简化 dict 反序列化为 Property：{name, type: str|int|bool|..., ...}."""
    name = str(data["name"])
    raw_type = data.get("type", "string")
    if isinstance(raw_type, PropertyType):
        ptype = raw_type
    else:
        ptype = _PROPERTY_TYPE_MAP.get(str(raw_type).lower())
        if ptype is None:
            if strict:
                raise ValueError(f"未知属性类型: {raw_type}")
            ptype = PropertyType.STRING
    return Property(
        name,
        ptype,
        default_value=data.get("default", data.get("default_value")),
        min_value=data.get("min", data.get("min_value")),
        max_value=data.get("max", data.get("max_value")),
    )


def _dict_to_property(data: dict[str, Any]) -> Property:
    return property_from_dict(data, strict=True)
