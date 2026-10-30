"""Own per-client services and their application lifecycle."""

import asyncio

from src.bootstrap.adapters import PluginCommandsAdapter, PluginContextAdapter
from src.bootstrap.health import (
    DEGRADED_AUDIO_NOTICE,
    audio_is_fatal,
    check_critical_plugins,
)
from src.bootstrap.plugin_wiring import setup_plugins
from src.bootstrap.protocols import PluginCommands, PluginContext
from src.bootstrap.session import ConversationSession
from src.constants.constants import AudioConfig
from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolManager
from src.core.resource_pool import ResourcePool
from src.core.state_manager import StateManager
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.plugins.manager import PluginManager
from src.utils.config_manager import ConfigManager

logger = get_logger()


class ServiceContainer:
    """An independent runtime; the application owns Qt and process configuration."""

    def __init__(self, config: ConfigManager | None = None):
        self.config = config if config is not None else ConfigManager.from_dict()
        self.audio_config = AudioConfig.from_config(self.config)
        self.event_bus = EventBus()
        self.state = StateManager(self.event_bus)
        self.tasks = TaskManager()
        self.protocol = ProtocolManager(
            self.event_bus,
            task_manager=self.tasks,
            config=self.config,
            audio_config=self.audio_config,
        )
        self.plugins = PluginManager()
        self.resource_pool = ResourcePool()
        self.mcp_server = None
        self.music_player = None
        self.notification_player = None
        self.session = ConversationSession(
            state=self.state,
            protocol=self.protocol,
            event_bus=self.event_bus,
            config=self.config,
        )
        self._plugin_context = PluginContextAdapter(self)
        self._plugin_commands = PluginCommandsAdapter(self)
        self._shutting_down = False
        self._degraded_audio = False

    def create_plugin_context(self) -> PluginContext:
        return self._plugin_context

    def create_plugin_commands(self) -> PluginCommands:
        return self._plugin_commands

    async def run(self, *, protocol: str = "websocket", mode: str = "gui") -> int:
        logger.info("启动 ServiceContainer, protocol=%s, mode=%s", protocol, mode)
        try:
            self.tasks.initialize()
            self.protocol.set_protocol(protocol)
            self.protocol.set_idle_checker(self.state.is_idle)
            self.session.bind_events(self.event_bus)
            await setup_plugins(self, mode, self._plugin_context, self._plugin_commands)
            await self.plugins.start_all()
            health_error = check_critical_plugins(self.plugins)
            if health_error:
                logger.error(health_error)
                return 1
            if self.plugins.is_failed("audio") and not audio_is_fatal():
                self._degraded_audio = True
                await self.event_bus.emit(Events.SYSTEM_NOTICE, DEGRADED_AUDIO_NOTICE)
            await self.event_bus.emit(
                Events.DEVICE_STATE_CHANGED,
                {
                    "old_state": self.state.device_state,
                    "new_state": self.state.device_state,
                },
            )
            await self._wait_for_runtime()
            health_error = check_critical_plugins(self.plugins)
            if health_error:
                logger.error(health_error)
                return 1
            return 0
        except Exception:
            logger.exception("应用运行失败")
            return 1
        finally:
            await self.shutdown()

    async def _wait_for_runtime(self) -> None:
        if self.tasks.shutdown_event.is_set():
            return
        startup = asyncio.create_task(
            self.protocol.start(), name="runtime:protocol_start"
        )
        shutdown = asyncio.create_task(
            self.tasks.wait_shutdown(), name="runtime:wait_shutdown"
        )
        try:
            await asyncio.wait((startup, shutdown), return_when=asyncio.FIRST_COMPLETED)
            if startup.done():
                await startup
            await shutdown
        finally:
            for task in (startup, shutdown):
                if not task.done():
                    task.cancel()
            await asyncio.gather(startup, shutdown, return_exceptions=True)

    async def shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        try:
            try:
                await self.plugins.stop_all()
            except Exception:
                logger.exception("停止内置组件失败")
            finally:
                await self.resource_pool.shutdown()
        finally:
            self.session.unbind_events()
