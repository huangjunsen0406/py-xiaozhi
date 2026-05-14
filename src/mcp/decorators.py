"""
MCP 工具装饰器与注册表.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

logger = get_logger()


class PropType(Enum):
    """装饰器使用的属性类型."""

    BOOL = "boolean"
    INT = "integer"
    STR = "string"

    def to_property_type(self) -> PropertyType:
        mapping = {
            PropType.BOOL: PropertyType.BOOLEAN,
            PropType.INT: PropertyType.INTEGER,
            PropType.STR: PropertyType.STRING,
        }
        return mapping[self]


_NOT_SET = object()


@dataclass
class Prop:
    """属性定义."""

    name: str
    type: PropType
    default: Any = _NOT_SET
    min_val: int | None = None
    max_val: int | None = None

    def to_property(self) -> Property:
        kwargs: dict[str, Any] = {}
        if self.default is not _NOT_SET:
            kwargs["default_value"] = self.default
        if self.type == PropType.INT:
            kwargs["min_value"] = self.min_val
            kwargs["max_value"] = self.max_val
        return Property(
            self.name,
            self.type.to_property_type(),
            **kwargs,
        )


@dataclass
class ToolDef:
    """工具定义."""

    name: str
    description: str
    props: list[Prop] = field(default_factory=list)
    callback: Callable = field(default=None)

    def to_mcp_tool(self) -> McpTool:
        prop_list = PropertyList([prop.to_property() for prop in self.props])
        return McpTool(self.name, self.description, prop_list, self.callback)


_TOOL_REGISTRY: dict[str, ToolDef] = {}
_DISCOVERY_DONE = False


def mcp_tool(
    *,
    name: str,
    description: str,
    props: list[Prop] | None = None,
) -> Callable:
    """MCP 工具装饰器."""

    def decorator(func: Callable):
        if name in _TOOL_REGISTRY:
            logger.warning("Tool %s already registered, overriding.", name)
        _TOOL_REGISTRY[name] = ToolDef(
            name=name,
            description=description,
            props=props or [],
            callback=func,
        )
        return func

    return decorator


def discover_tool_modules():
    """自动发现并导入所有工具模块."""
    global _DISCOVERY_DONE
    if _DISCOVERY_DONE:
        return

    from importlib import import_module

    package = "src.mcp.tools"
    base_path = Path(__file__).parent / "tools"

    def _safe_import(mod_name: str):
        try:
            import_module(mod_name)
        except Exception as e:
            logger.warning("跳过工具模块 %s (import 失败): %s", mod_name, e)

    # 先导入根目录下的 module (例如 tools/foo.py)
    for file_path in base_path.glob("*.py"):
        if file_path.name.startswith("_"):
            continue
        module_name = f"{package}.{file_path.stem}"
        if module_name.endswith(".__init__"):
            continue
        logger.debug("Discovering MCP tool module: %s", module_name)
        _safe_import(module_name)

    # 再导入子目录（package 和 _tools.py）
    for subdir in base_path.iterdir():
        if not subdir.is_dir() or subdir.name.startswith("_"):
            continue
        module_base = f"{package}.{subdir.name}"
        logger.debug("Discovering MCP tool package: %s", module_base)
        _safe_import(module_base)

        tools_file = subdir / "_tools.py"
        if tools_file.exists():
            module_name = f"{module_base}._tools"
            logger.debug("Discovering MCP sub-tools module: %s", module_name)
            _safe_import(module_name)

    _DISCOVERY_DONE = True


def iter_registered_mcp_tools(auto_discover: bool = True) -> Iterable[McpTool]:
    """将注册表内容转换为 McpTool 对象."""
    if auto_discover:
        discover_tool_modules()
    for tool_def in _TOOL_REGISTRY.values():
        yield tool_def.to_mcp_tool()
