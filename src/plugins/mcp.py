"""MCP 插件.

管理 MCP 工具和消息处理。McpServer 由容器注入；MediaPlayer 为可选能力，
不在此管理其 EventBus 生命周期。
"""

from typing import TYPE_CHECKING, Any, Optional

from src.core.event_bus import Events
from src.logging import get_logger
from src.mcp.mcp_server import McpServer
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.media.media_player import MediaPlayer

logger = get_logger()


class McpPlugin(Plugin):
    name = "mcp"

    def __init__(
        self,
        server: McpServer | None = None,
        media_player: Optional["MediaPlayer"] = None,
    ) -> None:
        super().__init__()
        if server is None:
            raise ValueError("McpPlugin 需要容器注入的 McpServer")
        self._server: McpServer = server
        self._media_player = media_player
        self._plugins_config_snapshot: dict | None = None

    def _plugins_config(self) -> dict:
        if self._ctx is None:
            return {}
        cfg = self._ctx.get_config()
        raw = cfg.get_config("MCP_PLUGINS", {}) if cfg is not None else {}
        return dict(raw) if isinstance(raw, dict) else {}

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        server = self._server

        async def _send(msg: str):
            try:
                delivered = await cmd.send_mcp_message(msg)
                if delivered is False:
                    raise RuntimeError("MCP 响应未发布到当前协议")
            except Exception as e:
                logger.error(f"MCP 发送响应失败: {e}", exc_info=True)

        try:
            server.set_send_callback(_send)
            # 摄像头：懒创建一次，挂到 server，供 vision 配置与 take_photo 共用
            from src.mcp.tools.camera import create_camera, register_camera_tools
            from src.mcp.tools.screenshot import register_screenshot_tools

            camera = create_camera(config=ctx.get_config())
            server.set_camera(camera)
            register_camera_tools(server.add_tool, camera)
            register_screenshot_tools(server.add_tool, camera)

            server.register_builtin_tools()
            server.reload_external_plugins(media_player=self._media_player)
            self._plugins_config_snapshot = self._plugins_config()
            ctx.event_bus.on(Events.CONFIG_CHANGED, self._on_config_changed)
        except Exception as e:
            logger.error(f"MCP 工具注册失败: {e}", exc_info=True)
            self.mark_failed()
            server.detach()
            raise

    async def stop(self) -> None:
        if self._ctx is not None and self._ctx.event_bus is not None:
            self._ctx.event_bus.off(Events.CONFIG_CHANGED, self._on_config_changed)
        await super().stop()

    async def _on_config_changed(self, data=None) -> None:
        """外挂配置变更或强制刷新时热重载外挂及条件播控工具."""
        current = self._plugins_config()
        force = isinstance(data, dict) and bool(data.get("reload_mcp_plugins"))
        if not force and current == self._plugins_config_snapshot:
            return
        self._plugins_config_snapshot = current
        try:
            self._server.reload_external_plugins(media_player=self._media_player)
        except Exception as e:
            logger.error("热重载外挂 MCP 插件失败: %s", e, exc_info=True)

    async def on_incoming_json(self, message: Any) -> None:
        if not isinstance(message, dict):
            return
        try:
            if message.get("type") == "mcp":
                payload = message.get("payload")
                if not payload:
                    return
                await self._server.parse_message(payload)
        except Exception as e:
            logger.error(f"MCP 消息处理失败: {e}", exc_info=True)
