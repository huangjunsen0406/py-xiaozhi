"""MCP 插件.

管理 MCP 工具和消息处理。
"""

from typing import TYPE_CHECKING, Optional

from src.logging import get_logger
from src.mcp.mcp_server import McpServer
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


class McpPlugin(Plugin):
    name = "mcp"
    priority = 20  # 工具注册，需要较早初始化

    def __init__(self) -> None:
        super().__init__()
        self._server: Optional[McpServer] = None

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self._server = McpServer.get_instance()

        # MCP 响应需要使用 send_mcp_message 包装消息格式
        async def _send(msg: str):
            try:
                await cmd.send_mcp_message(msg)
            except Exception:
                pass

        try:
            self._server.set_send_callback(_send)
            self._server.add_common_tools()
        except Exception:
            pass

        # 为 MusicPlayer 注入 EventBus
        try:
            from src.mcp.tools.music.music_player import get_music_player_instance

            music_player = get_music_player_instance()
            music_player.set_event_bus(ctx.event_bus)
            logger.info("MusicPlayer EventBus 已注入")
        except Exception as e:
            logger.warning(f"设置 MusicPlayer EventBus 失败: {e}")

    async def on_incoming_json(self, message) -> None:
        if not isinstance(message, dict):
            return
        try:
            if message.get("type") == "mcp":
                payload = message.get("payload")
                if not payload:
                    return
                if self._server is None:
                    self._server = McpServer.get_instance()
                await self._server.parse_message(payload)
        except Exception:
            pass

    async def shutdown(self) -> None:
        # 停止音乐播放器
        try:
            from src.mcp.tools.music.music_player import get_music_player_instance

            music_player = get_music_player_instance()
            if music_player.is_playing:
                await music_player.stop()
                logger.debug("MCP shutdown: 已停止音乐播放器")
        except Exception as e:
            logger.debug(f"停止音乐播放器失败: {e}")

        try:
            if self._server:
                self._server.set_send_callback(None)
        except Exception:
            pass
