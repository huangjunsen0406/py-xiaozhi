"""外挂 MCP 宿主 API（稳定契约）.

插件仅通过 McpHost 注册工具与按白名单取能力，禁止依赖全局单例。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()

# 默认允许的 host.get 名称（music_player 等需配置显式加入）
DEFAULT_ALLOW_GET = frozenset({"config_readonly", "logger"})


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
        self._allow_get = frozenset(allow_get) if allow_get is not None else DEFAULT_ALLOW_GET
        self._plugin_id = plugin_id or "unknown"
        self._registered_names: list[str] = []

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
        self._add_tool(tool)
        self._registered_names.append(tool.name)
        logger.info(
            "[MCP插件:%s] 注册工具: %s", self._plugin_id, tool.name
        )

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
