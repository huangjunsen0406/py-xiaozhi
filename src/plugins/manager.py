"""
插件管理器.

管理插件生命周期，使用 PluginContext 和 PluginCommands 进行依赖注入。
"""

from typing import Any, List, TYPE_CHECKING

from .base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginContext, PluginCommands


class PluginManager:
    """
    轻量插件管理器.

    职责:
    - 按优先级排序注册插件
    - 统一 setup/start/stop/shutdown 广播
    - 错误隔离，单个插件失败不影响其他插件
    """

    def __init__(self) -> None:
        self._plugins: List[Plugin] = []
        self._by_name: dict[str, Plugin] = {}

    def register(self, *plugins: Plugin) -> None:
        """
        注册插件.

        按 priority 排序（数值越小越优先）。
        """
        sorted_plugins = sorted(plugins, key=lambda p: getattr(p, "priority", 50))
        for p in sorted_plugins:
            if p not in self._plugins:
                self._plugins.append(p)
                try:
                    name = getattr(p, "name", None)
                    if isinstance(name, str) and name:
                        self._by_name[name] = p
                except Exception:
                    pass

    def get_plugin(self, name: str) -> Plugin | None:
        """根据插件名获取插件实例."""
        try:
            return self._by_name.get(name)
        except Exception:
            return None

    async def setup_all(
        self, ctx: "PluginContext", cmd: "PluginCommands"
    ) -> None:
        """
        初始化所有插件.

        Args:
            ctx: 插件上下文
            cmd: 插件命令接口
        """
        for p in list(self._plugins):
            try:
                await p.setup(ctx, cmd)
            except Exception:
                pass

    async def start_all(self) -> None:
        """启动所有插件."""
        for p in list(self._plugins):
            try:
                await p.start()
            except Exception:
                pass

    async def notify_protocol_connected(self, protocol: Any) -> None:
        """通知协议已连接."""
        for p in list(self._plugins):
            try:
                if p.on_protocol_connected:
                    await p.on_protocol_connected(protocol)
            except Exception:
                pass

    async def notify_incoming_json(self, message: Any) -> None:
        """通知收到 JSON 消息."""
        for p in list(self._plugins):
            try:
                await p.on_incoming_json(message)
            except Exception:
                pass

    async def notify_incoming_audio(self, data: bytes) -> None:
        """通知收到音频数据."""
        for p in list(self._plugins):
            try:
                await p.on_incoming_audio(data)
            except Exception:
                pass

    async def notify_device_state_changed(self, state: Any) -> None:
        """通知设备状态变更."""
        for p in list(self._plugins):
            try:
                await p.on_device_state_changed(state)
            except Exception:
                pass

    async def stop_all(self) -> None:
        """停止所有插件（逆序）."""
        for p in reversed(self._plugins):
            try:
                await p.stop()
            except Exception:
                pass

    async def shutdown_all(self) -> None:
        """关闭所有插件（逆序）."""
        for p in reversed(self._plugins):
            try:
                await p.shutdown()
            except Exception:
                pass
