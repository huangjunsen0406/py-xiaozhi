"""服务容器.

整合所有核心服务，提供统一的应用入口。
"""

import asyncio
import os
from typing import Any, Awaitable, Callable, Optional

from src.bootstrap.protocols import PluginCommands, PluginContext, WindowContext
from src.constants.constants import DeviceState, ListeningMode
from src.core.event_bus import EventBus, Events
from src.core.protocol_manager import ProtocolManager
from src.core.resource_pool import ResourcePool
from src.core.state_manager import StateManager
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.plugins.manager import PluginManager
from src.utils.config_manager import ConfigManager

logger = get_logger()

# 启动失败时直接退出，避免 zombie wait_shutdown
_CRITICAL_PLUGINS = ("ui",)
# audio 为关键能力，除非显式禁用
_AUDIO_CRITICAL = True


class PluginContextAdapter:
    """
    PluginContext 适配器.
    """

    def __init__(self, container: "ServiceContainer"):
        self._container = container

    def get_device_state(self) -> DeviceState:
        return self._container.state.device_state

    def get_listening_mode(self) -> ListeningMode:
        return self._container.state.listening_mode

    def is_listening(self) -> bool:
        return self._container.state.is_listening()

    def is_speaking(self) -> bool:
        return self._container.state.is_speaking()

    def is_idle(self) -> bool:
        return self._container.state.is_idle()

    def is_audio_channel_opened(self) -> bool:
        return self._container.protocol.is_audio_channel_opened()

    def should_capture_audio(self) -> bool:
        return self._container.state.should_capture_audio()

    def is_keep_listening(self) -> bool:
        return self._container.state.keep_listening

    def get_config(self) -> ConfigManager:
        return self._container.config

    @property
    def event_bus(self):
        """获取事件总线"""
        return self._container.event_bus


class PluginCommandsAdapter:
    """
    PluginCommands 适配器.
    """

    def __init__(self, container: "ServiceContainer"):
        self._container = container

    async def start_listening(self, mode: ListeningMode) -> None:
        await self._container.start_listening(mode)

    async def stop_listening(self) -> None:
        await self._container.stop_listening()

    async def abort_speaking(self, reason: str) -> None:
        await self._container.abort_speaking(reason)

    async def send_audio(self, data: bytes) -> None:
        await self._container.protocol.send_audio(data)

    async def send_text(self, text: str) -> None:
        await self._container.protocol.send_text(text)

    async def send_wake_word_detected(self, text: str) -> None:
        await self._container.protocol.send_wake_word_detected(text)

    async def send_mcp_message(self, payload: str) -> None:
        await self._container.protocol.send_mcp_message(payload)

    async def connect_protocol(self) -> bool:
        return await self._container.connect_protocol()

    def spawn(self, coro: Awaitable[Any], name: str) -> Any:
        return self._container.tasks.spawn(coro, name)

    def schedule_command_nowait(self, fn: Callable, *args, **kwargs) -> None:
        self._container.tasks.schedule_nowait(fn, *args, **kwargs)

    def request_shutdown(self) -> None:
        self._container.tasks.request_shutdown()


class WindowContextAdapter:
    """
    WindowContext 适配器.
    """

    def __init__(self, container: "ServiceContainer"):
        self._container = container

    def get_device_state(self) -> DeviceState:
        return self._container.state.device_state

    def get_listening_mode(self) -> ListeningMode:
        return self._container.state.listening_mode

    def is_listening(self) -> bool:
        return self._container.state.is_listening()

    def is_speaking(self) -> bool:
        return self._container.state.is_speaking()

    def is_idle(self) -> bool:
        return self._container.state.is_idle()

    def is_audio_channel_opened(self) -> bool:
        return self._container.protocol.is_audio_channel_opened()

    def request_shutdown(self) -> None:
        self._container.tasks.request_shutdown()

    def on_start_listening(self) -> None:
        self._container.tasks.schedule_nowait(self._container.start_auto_conversation)

    def on_stop_listening(self) -> None:
        self._container.tasks.schedule_nowait(self._container.stop_listening)

    def on_manual_listen_press(self) -> None:
        self._container.tasks.schedule_nowait(self._container.start_listening_manual)

    def on_manual_listen_release(self) -> None:
        self._container.tasks.schedule_nowait(self._container.stop_listening_manual)

    def on_auto_conversation_start(self) -> None:
        self._container.tasks.schedule_nowait(self._container.start_auto_conversation)


class ServiceContainer:
    """服务容器.

    整合所有核心服务，作为应用的中央协调者。
    """

    def __init__(self):
        logger.debug("初始化 ServiceContainer")

        # 配置
        self.config = ConfigManager.get_instance()

        # 获取 AEC 配置
        try:
            aec_enabled = bool(self.config.get_config("AEC_OPTIONS.ENABLED", True))
        except Exception:
            aec_enabled = True

        # 核心服务
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

        # 适配器
        self._plugin_context: Optional[PluginContextAdapter] = None
        self._plugin_commands: Optional[PluginCommandsAdapter] = None
        self._window_context: Optional[WindowContextAdapter] = None

        # 中止标志
        self._aborted = False

        # 运行模式
        self._mode: str = "cli"

        # 关闭状态（防重入）
        self._shutting_down = False

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

    def create_window_context(self) -> WindowContext:
        if not self._window_context:
            self._window_context = WindowContextAdapter(self)
        return self._window_context

    # -------------------------
    # 生命周期
    # -------------------------
    async def run(self, *, protocol: str = "websocket", mode: str = "gui") -> int:
        logger.info(f"启动 ServiceContainer, protocol={protocol}, mode={mode}")

        # 保存运行模式
        self._mode = mode

        try:
            # 初始化任务管理器
            self.tasks.initialize()
            self.protocol.set_task_manager(self.tasks)

            # 设置协议
            self.protocol.set_protocol(protocol)

            # 注册事件处理器
            self._setup_event_handlers()

            # 创建适配器
            ctx = self.create_plugin_context()
            cmd = self.create_plugin_commands()

            # 设置并启动插件
            await self._setup_plugins(mode, ctx, cmd)
            await self.plugins.start_all()

            # 关键插件健康门闩：失败则退出，禁止 silent zombie
            health_error = self._check_critical_plugins()
            if health_error:
                logger.error(health_error)
                return 1

            # 广播初始状态
            await self.plugins.notify_device_state_changed(
                self.state.device_state
            )

            # 等待关闭信号
            await self.tasks.wait_shutdown()
            return 0

        except Exception as e:
            logger.error(f"应用运行失败: {e}", exc_info=True)
            return 1
        finally:
            await self.shutdown()

    def _bind_shared_services(self) -> None:
        """创建并绑定跨插件共享服务（McpServer / MusicPlayer）."""
        from src.mcp.mcp_server import McpServer
        from src.mcp.tools.music.music_player import MusicPlayer, bind_music_player

        if self.mcp_server is None:
            self.mcp_server = McpServer()
            McpServer.bind_instance(self.mcp_server)

        if self.music_player is None:
            self.music_player = MusicPlayer()
            bind_music_player(self.music_player)

        logger.info("共享服务已绑定: McpServer, MusicPlayer")

    def _unbind_shared_services(self) -> None:
        """解除共享服务绑定（资源池最后阶段调用）."""
        from src.mcp.mcp_server import McpServer
        from src.mcp.tools.music.music_player import unbind_music_player

        try:
            unbind_music_player()
        except Exception as e:
            logger.debug(f"unbind MusicPlayer 失败: {e}", exc_info=True)
        try:
            McpServer.unbind_instance()
        except Exception as e:
            logger.debug(f"unbind McpServer 失败: {e}", exc_info=True)
        self.music_player = None
        self.mcp_server = None

    async def _setup_plugins(
        self, mode: str, ctx: PluginContext, cmd: PluginCommands
    ) -> None:
        """
        设置插件.
        """
        from src.plugins.audio import AudioPlugin
        from src.plugins.mcp import McpPlugin
        from src.plugins.shortcuts import ShortcutsPlugin
        from src.plugins.ui import UIPlugin
        from src.plugins.wake_word import WakeWordPlugin

        # 先绑定容器级共享服务，再初始化插件
        self._bind_shared_services()

        # 创建插件实例（注入容器持有的共享服务）
        audio_plugin = AudioPlugin(music_player=self.music_player)
        wake_word_plugin = WakeWordPlugin()
        ui_plugin = UIPlugin(mode=mode, task_manager=self.tasks)
        shortcuts_plugin = ShortcutsPlugin()
        mcp_plugin = McpPlugin(
            server=self.mcp_server,
            music_player=self.music_player,
        )

        # 注册插件
        self.plugins.register(
            mcp_plugin,
            audio_plugin,
            wake_word_plugin,
            ui_plugin,
            shortcuts_plugin,
        )

        # 初始化所有插件（PluginManager 会自动拓扑排序并注入依赖）
        await self.plugins.setup_all(ctx, cmd)

        # 注册所有资源的清理函数到资源池（逆序释放）
        self._register_cleanup_resources()

        # 设置音频直连通道（TTS 音频不经过 EventBus，减少延迟）
        if not audio_plugin.failed:
            self.protocol.set_audio_handler(audio_plugin.on_incoming_audio)

    def _check_critical_plugins(self) -> Optional[str]:
        """检查关键插件是否可用.

        Returns:
            错误描述；全部健康时返回 None
        """
        failed: list[str] = []
        for name in _CRITICAL_PLUGINS:
            if self.plugins.is_failed(name):
                failed.append(name)

        audio_disabled = os.getenv("XIAOZHI_DISABLE_AUDIO") == "1"
        if _AUDIO_CRITICAL and not audio_disabled and self.plugins.is_failed("audio"):
            failed.append("audio")

        if not failed:
            return None
        return (
            f"关键插件启动失败: {', '.join(failed)}。"
            "应用将退出以避免空转（zombie）。"
            "若需无音频调试，可设置 XIAOZHI_DISABLE_AUDIO=1。"
        )

    def _setup_event_handlers(self) -> None:
        """
        设置事件处理器.
        """
        self.event_bus.on(Events.AUDIO_CHANNEL_OPENED, self._on_audio_channel_opened)
        self.event_bus.on(Events.AUDIO_CHANNEL_CLOSED, self._on_audio_channel_closed)
        self.event_bus.on(Events.INCOMING_JSON, self._on_incoming_json)
        # 注意：INCOMING_AUDIO 走直连通道，不再通过 EventBus
        self.event_bus.on(Events.NETWORK_ERROR, self._on_network_error)
        self.event_bus.on(Events.DEVICE_STATE_CHANGED, self._on_device_state_changed)

    def _register_cleanup_resources(self) -> None:
        """将所有模块的清理函数注册到资源池（先注册的后释放）."""
        pool = self.resource_pool

        # 最先注册 = 最后释放：共享服务 unbind 在插件清理之后
        pool.register("shared_services", self._unbind_shared_services)

        # 事件总线最后释放（次先注册）
        pool.register("event_bus", self.event_bus.clear)

        # 各插件注册自身资源
        for plugin in self.plugins._plugins:
            plugin.register_resources(pool)

        # 网络连接
        pool.register("protocol", self.protocol.disconnect)

        # 异步任务
        pool.register("tasks", self.tasks.cancel_all)

    async def shutdown(self) -> None:
        """关闭应用，统一通过资源池逆序释放所有资源."""
        if self._shutting_down:
            logger.debug("ServiceContainer 已在关闭中，跳过")
            return
        self._shutting_down = True
        logger.info("正在关闭 ServiceContainer...")

        try:
            # 资源池统一释放（逆序执行注册的清理函数）
            await self.resource_pool.shutdown()
            logger.info("ServiceContainer 关闭完成")
        except Exception as e:
            logger.error(f"关闭时出错: {e}", exc_info=True)
        finally:
            # GUI 模式下需要退出 Qt 应用以结束 qasync 事件循环
            if self._mode == "gui":
                try:
                    from PySide6.QtWidgets import QApplication

                    if QApplication.instance():
                        logger.debug("退出 Qt 应用")
                        QApplication.quit()
                except Exception as e:
                    logger.debug(f"退出 Qt 应用时出错: {e}")

    # -------------------------
    # 事件处理器
    # -------------------------
    async def _on_audio_channel_opened(self, _=None) -> None:
        await self.state.set_device_state(DeviceState.LISTENING)

    async def _on_audio_channel_closed(self, _=None) -> None:
        await self.state.set_device_state(DeviceState.IDLE)

    async def _on_network_error(self, error_message: str = None) -> None:
        """网络错误：停止持续监听并复位设备状态到 IDLE."""
        self.state.set_keep_listening(False)
        try:
            if not self.state.is_idle():
                await self.state.set_device_state(DeviceState.IDLE)
        except Exception as e:
            logger.error(f"网络错误后复位设备状态失败: {e}", exc_info=True)

    async def _on_device_state_changed(self, data: dict) -> None:
        new_state = data.get("new_state")
        if new_state:
            await self.plugins.notify_device_state_changed(new_state)
            if new_state == DeviceState.LISTENING:
                await asyncio.sleep(0.5)
                self._aborted = False

    async def _on_incoming_json(self, json_data: dict) -> None:
        try:
            msg_type = json_data.get("type") if isinstance(json_data, dict) else None
            logger.info(f"收到JSON消息: type={msg_type}")

            if msg_type == "tts":
                state = json_data.get("state")
                if state == "start":
                    await self._handle_tts_start()
                elif state == "stop":
                    await self._handle_tts_stop()

            await self.plugins.notify_incoming_json(json_data)

        except Exception as e:
            logger.error(f"处理 JSON 消息失败: {e}", exc_info=True)

    async def _handle_tts_start(self) -> None:
        if (
            self.state.keep_listening
            and self.state.listening_mode == ListeningMode.REALTIME
        ):
            await self.state.set_device_state(DeviceState.LISTENING)
        else:
            await self.state.set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self) -> None:
        if self.state.keep_listening:
            try:
                audio_plugin = self.plugins.get_plugin("audio")
                if audio_plugin and audio_plugin.codec:
                    await audio_plugin.codec.clear_audio_queue()
            except Exception as e:
                logger.warning(f"清空音频队列失败: {e}", exc_info=True)
            await self.state.set_device_state(DeviceState.LISTENING)
            if not (
                self.state.listening_mode == ListeningMode.REALTIME
                and self.state.is_listening()
            ):
                await self.protocol.send_start_listening(self.state.listening_mode)
        else:
            await self.state.set_device_state(DeviceState.IDLE)

    # -------------------------
    # 操作方法
    # -------------------------
    async def connect_protocol(self) -> bool:
        if self.protocol.is_audio_channel_opened():
            return True

        opened = await self.protocol.connect()
        if opened:
            await self.plugins.notify_protocol_connected(self.protocol.protocol)
        return opened

    async def start_listening(self, mode: ListeningMode) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        self.state.set_listening_mode(mode)
        self.state.set_keep_listening(mode != ListeningMode.MANUAL)
        await self.protocol.send_start_listening(mode)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def stop_listening(self) -> None:
        self.state.set_keep_listening(False)
        await self.protocol.send_stop_listening()
        await self.state.set_device_state(DeviceState.IDLE)

    async def start_listening_manual(self) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        self.state.set_keep_listening(False)

        if self.state.is_speaking():
            logger.info("说话中发送打断")
            await self.protocol.send_abort_speaking(None)
            await self.state.set_device_state(DeviceState.IDLE)

        await self.protocol.send_start_listening(ListeningMode.MANUAL)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def stop_listening_manual(self) -> None:
        await self.protocol.send_stop_listening()
        await self.state.set_device_state(DeviceState.IDLE)

    async def start_auto_conversation(self) -> None:
        ok = await self.connect_protocol()
        if not ok:
            return

        mode = (
            ListeningMode.REALTIME
            if self.state.aec_enabled
            else ListeningMode.AUTO_STOP
        )
        self.state.set_listening_mode(mode)
        self.state.set_keep_listening(True)

        await self.protocol.send_start_listening(mode)
        await self.state.set_device_state(DeviceState.LISTENING)

    async def abort_speaking(self, reason: str) -> None:
        if self._aborted:
            logger.debug(f"已经中止，忽略重复请求: {reason}")
            return

        logger.info(f"中止语音输出: {reason}")
        self._aborted = True
        self.state.set_aborted(True)
        await self.protocol.send_abort_speaking(reason)
        await self.state.set_device_state(DeviceState.IDLE)
