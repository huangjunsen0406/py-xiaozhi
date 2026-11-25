"""宿主通用媒体播控 MCP 工具（按条件注册）.

仅在授权外挂使用 media_player 且存在已加载外挂时由 McpServer 激活，
避免多音频外挂重复注册暂停/停止导致大模型调用歧义。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

if TYPE_CHECKING:
    from src.media.media_player import MediaPlayer

logger = get_logger()

MEDIA_TRANSPORT_TOOL_NAMES: tuple[str, ...] = (
    "media.pause",
    "media.resume",
    "media.stop",
    "media.seek",
    "media.get_status",
)


def _dump(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)


def register_media_tools(
    add_tool: Callable[[McpTool], None],
    player: MediaPlayer,
) -> list[str]:
    """向宿主注册 5 个极简通用媒体播控工具."""

    async def _pause(_args: dict[str, Any]) -> str:
        return _dump(await player.pause(source="manual"))

    async def _resume(_args: dict[str, Any]) -> str:
        return _dump(await player.resume())

    async def _stop(_args: dict[str, Any]) -> str:
        return _dump(await player.stop())

    async def _seek(args: dict[str, Any]) -> str:
        pos = args.get("position")
        pct = args.get("percent")
        position = float(pos) if pos is not None and int(pos) >= 0 else None
        percent = float(pct) if pct is not None and int(pct) >= 0 else None
        return _dump(await player.seek(position=position, percent=percent))

    async def _get_status(_args: dict[str, Any]) -> str:
        return _dump(await player.get_status())

    tools = [
        McpTool(
            "media.pause",
            "暂停当前正在播放的背景媒体。",
            PropertyList(),
            _pause,
        ),
        McpTool(
            "media.resume",
            "恢复已暂停的背景媒体播放。",
            PropertyList(),
            _resume,
        ),
        McpTool(
            "media.stop",
            "停止当前正在播放的背景媒体。",
            PropertyList(),
            _stop,
        ),
        McpTool(
            "media.seek",
            "跳转当前背景媒体播放位置。position 为目标秒数，percent 为百分比(0-100)，二选一。",
            PropertyList(
                [
                    Property("position", PropertyType.INTEGER, default_value=-1, min_value=-1),
                    Property(
                        "percent",
                        PropertyType.INTEGER,
                        default_value=-1,
                        min_value=-1,
                        max_value=100,
                    ),
                ]
            ),
            _seek,
        ),
        McpTool(
            "media.get_status",
            "查询当前背景媒体的播放状态、标题和进度。",
            PropertyList(),
            _get_status,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("已注册 %d 个通用媒体播控 MCP 工具", len(tools))
    return [tool.name for tool in tools]
