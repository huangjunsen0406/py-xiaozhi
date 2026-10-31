"""Validate MCP arguments and defaults without executing external tools."""

import json
from unittest.mock import Mock

import pytest

from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType


@pytest.mark.parametrize(
    "value",
    [True, False, 1.2, -1.2, float("nan"), float("inf"), -float("inf"), "3", [], {}],
)
@pytest.mark.parametrize("source", ["argument", "default"])
def test_integer_rejects_invalid_arguments_and_defaults(value, source):
    prop = Property("count", PropertyType.INTEGER)
    if source == "default":
        prop.default_value = value
        arguments = {}
    else:
        arguments = {"count": value}
    with pytest.raises(ValueError):
        PropertyList([prop]).parse_arguments(arguments)


@pytest.mark.parametrize("value", [0, -4, 7, 3.0])
@pytest.mark.parametrize("source", ["argument", "default"])
def test_integer_preserves_integral_values(value, source):
    prop = Property("count", PropertyType.INTEGER)
    if source == "default":
        prop.default_value = value
        arguments = {}
    else:
        arguments = {"count": value}
    result = PropertyList([prop]).parse_arguments(arguments)
    assert result == {"count": int(value)}
    assert type(result["count"]) is int


@pytest.mark.parametrize(
    "bounds,invalid,valid", [({"min_value": 2}, 1, 2), ({"max_value": 2}, 3, 2)]
)
@pytest.mark.parametrize("source", ["argument", "default"])
def test_single_sided_bounds_apply_to_defaults_too(bounds, invalid, valid, source):
    prop = Property("count", PropertyType.INTEGER, **bounds)
    assert prop.has_range
    assert prop.value(valid) == valid
    if source == "default":
        prop.default_value = invalid
        arguments = {}
    else:
        arguments = {"count": invalid}
    with pytest.raises(ValueError):
        PropertyList([prop]).parse_arguments(arguments)


@pytest.mark.parametrize(
    "kind,default",
    [
        (PropertyType.STRING, 3),
        (PropertyType.BOOLEAN, 1),
        (PropertyType.BOOLEAN, "false"),
    ],
)
@pytest.mark.asyncio
async def test_invalid_default_never_reaches_callback(kind, default):
    callback = Mock(return_value=True)
    tool = McpTool(
        "test",
        "test",
        PropertyList([Property("value", kind, default_value=default)]),
        callback,
    )
    result = json.loads(await tool.call({}))
    assert result["isError"] is True
    callback.assert_not_called()


@pytest.mark.parametrize("arguments", [[], "", False, 3])
def test_arguments_must_be_an_object_even_when_empty(arguments):
    with pytest.raises(ValueError, match="object"):
        PropertyList().parse_arguments(arguments)
