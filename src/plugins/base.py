"""插件基类.

使用 PluginContext 和 PluginCommands 接口与核心服务交互。
"""

import asyncio
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.core.resource_pool import ResourcePool


class Plugin:
    """插件基类.

    插件通过 PluginContext 获取状态，通过 PluginCommands 执行操作。

    属性:
        name: 插件名称，用于依赖声明和日志
        priority: 优先级，数值越小越优先（范围: 1-100）
        requires: 依赖的插件名称列表，PluginManager 会自动注入

    用法:
        class MyPlugin(Plugin):
            name = "my_plugin"
            priority = 50
            requires = ["audio"]  # 声明依赖 AudioPlugin

            async def setup(self, ctx, cmd):
                await super().setup(ctx, cmd)
                # self.deps["audio"] 可获取 AudioPlugin 实例
    """

    name: str = "plugin"
    priority: int = 50  # 优先级，数值越小越优先（范围: 1-100）
    requires: List[str] = []  # 依赖的插件名称列表

    def __init__(self) -> None:
        self._started = False
        self._ctx: "PluginContext" = None
        self._cmd: "PluginCommands" = None
        self._deps: dict[str, "Plugin"] = {}  # 依赖注入的插件实例

    @property
    def ctx(self) -> "PluginContext":
        """
        获取插件上下文.
        """
        return self._ctx

    @property
    def cmd(self) -> "PluginCommands":
        """
        获取插件命令接口.
        """
        return self._cmd

    @property
    def deps(self) -> dict[str, "Plugin"]:
        """获取依赖的插件实例."""
        return self._deps

    def get_dep(self, name: str) -> Optional["Plugin"]:
        """获取指定名称的依赖插件."""
        return self._deps.get(name)

    def _inject_dependency(self, name: str, plugin: "Plugin") -> None:
        """注入依赖插件（由 PluginManager 调用）."""
        self._deps[name] = plugin

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        """插件准备阶段.

        Args:
            ctx: 插件上下文（只读状态访问）
            cmd: 插件命令接口（执行操作）
        """
        self._ctx = ctx
        self._cmd = cmd
        await asyncio.sleep(0)

    async def start(self) -> None:
        """
        插件启动（通常在协议连接建立后调用）.
        """
        self._started = True
        await asyncio.sleep(0)

    async def on_protocol_connected(self, protocol: Any) -> None:
        """
        协议通道建立后的通知.
        """
        await asyncio.sleep(0)

    async def on_incoming_json(self, message: Any) -> None:
        """
        收到JSON消息时的通知.
        """
        await asyncio.sleep(0)

    async def on_incoming_audio(self, data: bytes) -> None:
        """
        收到音频数据时的通知.
        """
        await asyncio.sleep(0)

    async def on_device_state_changed(self, state: Any) -> None:
        """
        设备状态变更通知.
        """
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """
        插件停止.
        """
        self._started = False
        await asyncio.sleep(0)

    def register_resources(self, pool: "ResourcePool") -> None:
        """
        向资源池注册清理函数。子类重写此方法以注册需要释放的资源。
        资源按注册的逆序释放，先注册的后释放。

        Args:
            pool: 资源池实例
        """
        pass
