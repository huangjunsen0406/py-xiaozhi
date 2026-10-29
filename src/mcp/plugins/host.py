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
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()

# 默认允许的 host.get 名称（music_player 等需配置显式加入）
DEFAULT_ALLOW_GET = frozenset({"config_readonly", "logger"})


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
        target[key] = deepcopy(value)
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
        self._data = _freeze(deepcopy(self._snapshot))

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
        allow_get: Sequence[str] | None = None,
        plugin_id: str | None = None,
    ) -> None:
        self._add_tool = add_tool
        self._capabilities = dict(capabilities or {})
        if "config_readonly" in self._capabilities:
            self._capabilities["config_readonly"] = ReadOnlyConfig(
                self._capabilities["config_readonly"]
            )
        self._allow_get = frozenset(allow_get) if allow_get is not None else DEFAULT_ALLOW_GET
        self._plugin_id = plugin_id or "unknown"
        self._registered_names: list[str] = []
        self._registration_open = True

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def registered_tool_names(self) -> list[str]:
        return list(self._registered_names)

    def bind_plugin(self, plugin_id: str) -> "McpHost":
        """返回绑定到指定 plugin_id 的视图（共享 add_tool / capabilities）."""
        child = McpHost(
            self._add_tool,
            capabilities=self._capabilities,
            allow_get=self._allow_get,
            plugin_id=plugin_id,
        )
        return child

    def add_tool(self, tool: McpTool) -> None:
        """注册工具；记录名称供卸载/诊断."""
        if not self._registration_open:
            raise RuntimeError("插件注册阶段已结束")
        if tool.name in self._registered_names:
            raise ValueError(f"Tool name conflict: {tool.name}")
        self._add_tool(tool)
        self._registered_names.append(tool.name)
        logger.info(
            "[MCP插件:%s] 注册工具: %s", self._plugin_id, tool.name
        )

    def close_registration(self) -> None:
        self._registration_open = False

    def get(self, name: str) -> Any:
        """按白名单返回宿主能力；未授权或未提供则 None."""
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


def _dict_to_property(data: dict[str, Any]) -> Property:
    """支持简化 dict：{name, type: str|int|bool|string|integer|boolean, ...}."""
    name = data["name"]
    raw_type = data.get("type", "string")
    type_map = {
        "str": PropertyType.STRING,
        "string": PropertyType.STRING,
        "int": PropertyType.INTEGER,
        "integer": PropertyType.INTEGER,
        "bool": PropertyType.BOOLEAN,
        "boolean": PropertyType.BOOLEAN,
        PropertyType.STRING: PropertyType.STRING,
        PropertyType.INTEGER: PropertyType.INTEGER,
        PropertyType.BOOLEAN: PropertyType.BOOLEAN,
    }
    if isinstance(raw_type, PropertyType):
        ptype = raw_type
    else:
        ptype = type_map.get(str(raw_type).lower())
        if ptype is None:
            raise ValueError(f"未知属性类型: {raw_type}")
    return Property(
        name,
        ptype,
        default_value=data.get("default", data.get("default_value")),
        min_value=data.get("min", data.get("min_value")),
        max_value=data.get("max", data.get("max_value")),
    )
