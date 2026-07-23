"""插件与共享服务装配.

集中：创建 McpServer/MusicPlayer、注册插件清单、资源池清理、音频直连。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.logging import get_logger

if TYPE_CHECKING:
    from src.bootstrap.container import ServiceContainer
    from src.bootstrap.protocols import PluginCommands, PluginContext

logger = get_logger()


def bind_shared_services(container: "ServiceContainer") -> None:
    """创建跨插件共享服务（McpServer / MusicPlayer），仅容器持有.

    不再写入模块级单例；插件与 MCP 工具经构造注入 / 闭包拿到同一实例。
    """
    from src.mcp.mcp_server import McpServer
    from src.mcp.tools.music.music_player import MusicPlayer

    if container.mcp_server is None:
        container.mcp_server = McpServer()

    if container.music_player is None:
        container.music_player = MusicPlayer()

    logger.debug("共享服务已创建: McpServer, MusicPlayer")


def unbind_shared_services(container: "ServiceContainer") -> None:
    """释放共享服务引用（资源池最后阶段调用）."""
    if container.music_player is not None:
        try:
            container.music_player.detach()
        except Exception as e:
            logger.debug(f"detach MusicPlayer 失败: {e}", exc_info=True)
    if container.mcp_server is not None:
        try:
            container.mcp_server.detach()
        except Exception as e:
            logger.debug(f"detach McpServer 失败: {e}", exc_info=True)
    container.music_player = None
    container.mcp_server = None


async def setup_plugins(
    container: "ServiceContainer",
    mode: str,
    ctx: "PluginContext",
    cmd: "PluginCommands",
) -> None:
    """绑定共享服务、注册并初始化插件、挂资源清理与音频直连."""
    from src.plugins.audio import AudioPlugin
    from src.plugins.mcp import McpPlugin
    from src.plugins.shortcuts import ShortcutsPlugin
    from src.plugins.ui import UIPlugin
    from src.plugins.wake_word import WakeWordPlugin

    bind_shared_services(container)

    # 创建插件实例（Audio 经事件发布 codec，不注入 MusicPlayer）
    audio_plugin = AudioPlugin()
    wake_word_plugin = WakeWordPlugin()
    ui_plugin = UIPlugin(mode=mode, task_manager=container.tasks)
    shortcuts_plugin = ShortcutsPlugin()
    mcp_plugin = McpPlugin(
        server=container.mcp_server,
        music_player=container.music_player,
    )

    container.plugins.register(
        mcp_plugin,
        audio_plugin,
        wake_word_plugin,
        ui_plugin,
        shortcuts_plugin,
    )

    await container.plugins.setup_all(ctx, cmd)

    register_cleanup_resources(container)

    # 设置音频直连通道（TTS 音频不经过 EventBus，减少延迟）
    if not audio_plugin.failed:
        container.protocol.set_audio_handler(audio_plugin.on_incoming_audio)


def register_cleanup_resources(container: "ServiceContainer") -> None:
    """将所有模块的清理函数注册到资源池（先注册的后释放）."""
    pool = container.resource_pool

    # 最先注册 = 最后释放：共享服务 unbind 在插件清理之后
    pool.register(
        "shared_services", lambda: unbind_shared_services(container)
    )

    # 事件总线最后释放（次先注册）
    pool.register("event_bus", container.event_bus.clear)

    # 各插件注册自身资源
    for plugin in container.plugins._plugins:
        plugin.register_resources(pool)

    # 网络连接
    pool.register("protocol", container.protocol.disconnect)

    # 异步任务
    pool.register("tasks", container.tasks.cancel_all)
