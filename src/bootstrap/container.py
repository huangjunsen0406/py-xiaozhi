"""服务容器.

整合核心服务，作为应用的中央协调者；会话/门闩/装配/适配器已拆到子模块。
"""

from src.bootstrap.adapters import PluginCommandsAdapter, PluginContextAdapter
from src.bootstrap.health import (
    DEGRADED_AUDIO_NOTICE,
    audio_is_fatal,
    check_critical_plugins,
)
from src.bootstrap.plugin_wiring import setup_plugins
from src.bootstrap.protocols import PluginCommands, PluginContext
from src.bootstrap.session import ConversationSession
from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolManager
from src.core.resource_pool import ResourcePool
from src.core.state_manager import StateManager
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.plugins.manager import PluginManager
from src.utils.config_manager import get_config

logger = get_logger()


class ServiceContainer:
    """服务容器.

    持有核心服务与 ConversationSession，编排 run / shutdown 生命周期。
    会话操作走 ``self.session``；门闩走 ``health`` 模块。
    """

    def __init__(self):
        logger.debug("初始化 ServiceContainer")

        self.config = get_config()

        try:
            aec_enabled = bool(self.config.get_config("AEC_OPTIONS.ENABLED", True))
        except Exception:
            aec_enabled = True

        self.event_bus = EventBus()
        self.state = StateManager(self.event_bus, aec_enabled=aec_enabled)
        self.tasks = TaskManager()
        # Protocol 入站任务走 TaskManager，避免 fire-and-forget
        self.protocol = ProtocolManager(self.event_bus, task_manager=self.tasks)
        self.plugins = PluginManager()
        self.resource_pool = ResourcePool()

        # 容器持有的跨插件共享服务（启动时 bind，关闭时 unbind）
        self.mcp_server = None
        self.music_player = None

        # 会话控制（听/说/打断/TTS 回环）
        self.session = ConversationSession(
            state=self.state,
            protocol=self.protocol,
            plugins=self.plugins,
            event_bus=self.event_bus,
        )

        self._plugin_context: PluginContextAdapter | None = None
        self._plugin_commands: PluginCommandsAdapter | None = None

        self._mode: str = "cli"
        self._shutting_down = False
        # audio 降级运行（XIAOZHI_DEGRADED_AUDIO=1 且 audio failed）
        self._degraded_audio = False

    # -------------------------
    # 适配器创建
    # -------------------------
    def create_plugin_context(self) -> PluginContext:
        if not self._plugin_context:
            self._plugin_context = PluginContextAdapter(self)
        return self._plugin_context

    def create_plugin_commands(self) -> PluginCommands:
        if not self._plugin_commands:
            self._plugin_commands = PluginCommandsAdapter(self)
        return self._plugin_commands

    # -------------------------
    # 生命周期
    # -------------------------
    async def run(self, *, protocol: str = "websocket", mode: str = "gui") -> int:
        logger.info(f"启动 ServiceContainer, protocol={protocol}, mode={mode}")
        self._mode = mode

        try:
            self.tasks.initialize()
            self.protocol.set_task_manager(self.tasks)
            self.protocol.set_protocol(protocol)

            self.session.bind_events(self.event_bus)

            ctx = self.create_plugin_context()
            cmd = self.create_plugin_commands()

            await setup_plugins(self, mode, ctx, cmd)
            await self.plugins.start_all()

            # 关键插件健康门闩：失败则退出，禁止 silent zombie
            health_error = check_critical_plugins(self.plugins)
            if health_error:
                logger.error(health_error)
                return 1

            # audio 失败但允许降级：打横幅/日志，继续跑 UI
            if self.plugins.is_failed("audio") and not audio_is_fatal():
                logger.warning(DEGRADED_AUDIO_NOTICE)
                self._degraded_audio = True
                try:
                    await self.event_bus.emit(
                        Events.SYSTEM_NOTICE, DEGRADED_AUDIO_NOTICE
                    )
                except Exception as e:
                    logger.debug(f"降级提示事件失败: {e}", exc_info=True)

            await self.plugins.notify_device_state_changed(self.state.device_state)

            await self.tasks.wait_shutdown()
            return 0

        except Exception as e:
            logger.error(f"应用运行失败: {e}", exc_info=True)
            return 1
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """关闭应用，统一通过资源池逆序释放所有资源."""
        if self._shutting_down:
            logger.debug("ServiceContainer 已在关闭中，跳过")
            return
        self._shutting_down = True
        logger.info("正在关闭 ServiceContainer...")

        try:
            await self.resource_pool.shutdown()
            logger.info("ServiceContainer 关闭完成")
        except Exception as e:
            logger.error(f"关闭时出错: {e}", exc_info=True)
        finally:
            if self._mode == "gui":
                try:
                    from PySide6.QtWidgets import QApplication

                    if QApplication.instance():
                        logger.debug("退出 Qt 应用")
                        QApplication.quit()
                except Exception as e:
                    logger.debug(f"退出 Qt 应用时出错: {e}")
