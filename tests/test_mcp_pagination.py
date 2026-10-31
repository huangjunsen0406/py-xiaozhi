"""Test actual serialized MCP list replies using memory callbacks."""

import json

import pytest

from src.mcp.mcp_server import McpServer
from src.mcp.tooling import McpTool, PropertyList


def tool(name, description="test"):
    return McpTool(name, description, PropertyList(), lambda _: True)


async def list_page(server, cursor="", request_id=1):
    messages = []

    async def send(payload):
        messages.append(payload)

    server.set_send_callback(send)
    await server._handle_tools_list(request_id, {"cursor": cursor})
    assert len(messages) == 1
    return json.loads(messages[0]), messages[0]


@pytest.mark.asyncio
async def test_pages_advance_fit_full_wire_budget_and_return_every_tool():
    server = McpServer()
    server.tools = [tool(f"tool-{index}", "屏幕" * 160) for index in range(13)]
    cursor, seen, names = "", set(), []
    for _ in range(len(server.tools) + 1):
        reply, payload = await list_page(
            server, cursor, request_id="request-" + "x" * 700
        )
        assert len(payload.encode("utf-8")) <= 8000
        page = reply["result"]
        assert page["tools"]
        names.extend(entry["name"] for entry in page["tools"])
        cursor = page.get("nextCursor", "")
        if not cursor:
            break
        assert cursor not in seen
        seen.add(cursor)
    else:
        pytest.fail("pagination did not terminate")
    assert names == [entry.name for entry in server.tools]


@pytest.mark.asyncio
async def test_oversized_first_tool_returns_error_instead_of_same_empty_page():
    server = McpServer()
    server.tools = [tool("huge", "x" * 9000)]
    reply, _ = await list_page(server)
    assert "error" in reply
    assert "payload limit" in reply["error"]["message"]


@pytest.mark.asyncio
async def test_later_oversized_tool_is_reachable_then_fails_explicitly():
    server = McpServer()
    server.tools = [tool("small"), tool("huge", "x" * 9000)]
    first, _ = await list_page(server)
    assert [entry["name"] for entry in first["result"]["tools"]] == ["small"]
    assert first["result"]["nextCursor"] == "huge"
    second, _ = await list_page(server, "huge")
    assert "error" in second


@pytest.mark.asyncio
async def test_request_envelope_counts_toward_the_limit():
    server = McpServer()
    server.tools = [tool("fits-alone", "x" * 6000)]
    reply, payload = await list_page(server, request_id="x" * 2200)
    assert "error" in reply
    assert len(payload.encode("utf-8")) <= 8000


@pytest.mark.parametrize("cursor", ["missing", [], 1])
@pytest.mark.asyncio
async def test_unknown_or_malformed_cursor_is_explicit_error(cursor):
    server = McpServer()
    server.tools = [tool("test")]
    reply, _ = await list_page(server, cursor)
    assert "error" in reply


@pytest.mark.asyncio
async def test_empty_registry_is_a_terminal_page():
    reply, _ = await list_page(McpServer())
    assert reply["result"] == {"tools": []}
