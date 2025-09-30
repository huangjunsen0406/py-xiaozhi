from typing import Any, Optional

from src.mcp.mcp_server import McpServer
from src.plugins.base import Plugin


class McpPlugin(Plugin):
    name = "mcp"

    def __init__(self) -> None:
        super().__init__()
        self.app: Any = None
        self._server: Optional[McpServer] = None

    async def setup(self, app: Any) -> None:
        self.app = app
        self._server = McpServer.get_instance()

        # 通过应用协议发送MCP响应
        async def _send(msg: str):
            try:
                if not self.app or not getattr(self.app, "protocol", None):
                    return
                await self.app.protocol.send_mcp_message(msg)
            except Exception:
                pass

        try:
            self._server.set_send_callback(_send)
            # 注册通用工具（包含 calendar 工具）。提醒服务的运行改由 CalendarPlugin 管理
            self._server.add_common_tools()
            # 若音乐播放器存在，将其app引用指向当前应用（example模式下用于UI更新）
            try:
                from src.mcp.tools.music import get_music_player_instance

                player = get_music_player_instance()
                try:
                    player.app = self.app
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    async def on_incoming_json(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        try:
            if message.get("type") != "mcp":
                return
            payload = message.get("payload")
            if not payload:
                return
            if self._server is None:
                self._server = McpServer.get_instance()
            await self._server.parse_message(payload)
        except Exception:
            pass

    async def shutdown(self) -> None:
        # 可选：解除回调引用，帮助GC
        try:
            if self._server:
                self._server.set_send_callback(None)  # type: ignore[arg-type]
        except Exception:
            pass
