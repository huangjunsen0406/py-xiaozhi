"""Explicit assembly, event routing and ownership of built-in components."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.core.event_bus import Events
from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.container import ServiceContainer
    from src.bootstrap.protocols import PluginCommands, PluginContext


def bind_shared_services(container: ServiceContainer) -> None:
    from src.mcp.mcp_server import McpServer
    from src.mcp.tools.music.music_player import MusicPlayer
    from src.notifications.notification_player import NotificationPlayer

    container.mcp_server = McpServer(config=container.config)
    container.music_player = MusicPlayer(config=container.config)
    container.notification_player = NotificationPlayer(
        audio_config=container.audio_config
    )
    container.notification_player.set_event_bus(container.event_bus)
    container.session.set_notification_player(container.notification_player)


def unbind_shared_services(container: ServiceContainer) -> None:
    """Drop references only; each owner registers its cleanup exactly once."""
    container.session.audio = None
    for event, handler in getattr(container, "_builtin_subscriptions", ()):
        container.event_bus.off(event, handler)
    container._builtin_subscriptions = []
    container.session.set_notification_player(None)
    container.music_player = None
    container.mcp_server = None
    container.notification_player = None


def subscribe_builtin_events(container: ServiceContainer) -> None:
    """One delivery route; no runtime broadcast through PluginManager."""
    bus = container.event_bus
    for event, handler in getattr(container, "_builtin_subscriptions", ()):
        bus.off(event, handler)
    container._builtin_subscriptions = []
    for plugin in container.plugins.plugins:
        for event, method, state_payload in (
            (Events.SESSION_MESSAGE, "on_incoming_json", False),
            (Events.DEVICE_STATE_CHANGED, "on_device_state_changed", True),
        ):
            if getattr(type(plugin), method) is getattr(Plugin, method):
                continue

            async def deliver(
                data, plugin=plugin, method=method, state_payload=state_payload
            ):
                if not plugin.failed:
                    payload = data.get("new_state") if state_payload else data
                    await getattr(plugin, method)(payload)

            bus.on(event, deliver)
            container._builtin_subscriptions.append((event, deliver))


async def setup_plugins(
    container: ServiceContainer,
    mode: str,
    ctx: PluginContext,
    cmd: PluginCommands,
) -> None:
    try:
        from src.plugins.audio import AudioPlugin
        from src.plugins.mcp import McpPlugin
        from src.plugins.shortcuts import ShortcutsPlugin
        from src.plugins.ui import UIPlugin
        from src.plugins.wake_word import WakeWordPlugin

        bind_shared_services(container)
        audio = AudioPlugin()
        container.plugins.register(
            audio,
            McpPlugin(server=container.mcp_server, music_player=container.music_player),
            WakeWordPlugin(audio=audio),
            UIPlugin(mode=mode, task_manager=container.tasks),
            ShortcutsPlugin(),
        )
        await container.plugins.setup_all(ctx, cmd)
        container.session.set_audio(audio.codec if not audio.failed else None)
        subscribe_builtin_events(container)
        if not audio.failed:
            container.protocol.set_audio_handler(audio.on_incoming_audio)
    finally:
        # Also runs after partial construction/setup failure.
        register_cleanup_resources(container)


def register_cleanup_resources(container: ServiceContainer) -> None:
    pool = container.resource_pool
    pool.register("shared_services", lambda: unbind_shared_services(container))
    pool.register("event_bus", container.event_bus.clear)
    for plugin in container.plugins.plugins:
        plugin.register_resources(pool)

    if container.mcp_server is not None:
        pool.register("mcp.server", container.mcp_server.detach)
    if container.music_player is not None:
        player = container.music_player

        async def close_music(player=player):
            try:
                await player.stop()
            finally:
                await player.detach()

        pool.register("music_player", close_music)
    if container.notification_player is not None:
        player = container.notification_player

        async def close_notifications(player=player):
            try:
                await player.stop()
            finally:
                player.detach()

        pool.register("notification_player", close_notifications)
    pool.register("protocol", container.protocol.shutdown)
    pool.register("tasks", container.tasks.cancel_all)
