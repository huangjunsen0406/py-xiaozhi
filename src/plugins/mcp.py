"""MCP 插件.

管理 MCP 工具和消息处理。共享 McpServer / MusicPlayer 由容器注入。
"""

from typing import TYPE_CHECKING, Any, Optional

from src.logging import get_logger
from src.mcp.mcp_server import McpServer
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.mcp.tools.music.music_player import MusicPlayer

logger = get_logger()


class McpPlugin(Plugin):
    name = "mcp"
    priority = 20  # 工具注册，需要较早初始化

    def __init__(
        self,
        server: Optional[McpServer] = None,
        music_player: Optional["MusicPlayer"] = None,
    ) -> None:
        super().__init__()
        self._server: Optional[McpServer] = server
        self._music_player = music_player

    def _get_server(self) -> McpServer:
        if self._server is None:
            self._server = McpServer.get_instance()
        return self._server

    def _get_music_player(self):
        if self._music_player is not None:
            return self._music_player
        from src.mcp.tools.music.music_player import get_music_player_instance

        return get_music_player_instance()

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        server = self._get_server()

        # MCP 响应需要使用 send_mcp_message 包装消息格式
        async def _send(msg: str):
            try:
                await cmd.send_mcp_message(msg)
            except Exception as e:
                logger.error(f"MCP 发送响应失败: {e}", exc_info=True)

        try:
            server.set_send_callback(_send)
            server.add_common_tools()
        except Exception as e:
            logger.error(f"MCP 工具注册失败: {e}", exc_info=True)

        # 为 MusicPlayer 注入 EventBus
        try:
            music_player = self._get_music_player()
            music_player.set_event_bus(ctx.event_bus, ctx)
            logger.info("MusicPlayer EventBus 已注入")
        except Exception as e:
            logger.warning(f"设置 MusicPlayer EventBus 失败: {e}", exc_info=True)

    async def on_incoming_json(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        try:
            if message.get("type") == "mcp":
                payload = message.get("payload")
                if not payload:
                    return
                await self._get_server().parse_message(payload)
        except Exception as e:
            logger.error(f"MCP 消息处理失败: {e}", exc_info=True)

    def register_resources(self, pool) -> None:
        async def _mcp_cleanup():
            try:
                music_player = self._get_music_player()
                if music_player.is_playing:
                    await music_player.stop()
                # 解绑 EventBus / codec；容器 unbind 会再次 detach（幂等）
                music_player.detach()
            except Exception as e:
                logger.debug(f"停止/detach 音乐播放器失败: {e}", exc_info=True)

            try:
                if self._server:
                    self._server.detach()
            except Exception as e:
                logger.debug(f"MCP shutdown 清理失败: {e}", exc_info=True)

        pool.register("mcp.server", _mcp_cleanup)
