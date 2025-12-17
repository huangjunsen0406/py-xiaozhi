"""
插件基类.

使用 PluginContext 和 PluginCommands 接口与核心服务交互。
"""

import asyncio
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginContext, PluginCommands


class Plugin:
    """
    插件基类.

    插件通过 PluginContext 获取状态，通过 PluginCommands 执行操作。

    用法:
        class MyPlugin(Plugin):
            name = "my_plugin"
            priority = 50

            async def setup(self, ctx, cmd):
                await super().setup(ctx, cmd)
                # 初始化逻辑

            async def start(self):
                # 启动逻辑
                pass
    """

    name: str = "plugin"
    priority: int = 50  # 优先级，数值越小越优先（范围: 1-100）

    def __init__(self) -> None:
        self._started = False
        self._ctx: "PluginContext" = None
        self._cmd: "PluginCommands" = None

    @property
    def ctx(self) -> "PluginContext":
        """获取插件上下文."""
        return self._ctx

    @property
    def cmd(self) -> "PluginCommands":
        """获取插件命令接口."""
        return self._cmd

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        """
        插件准备阶段.

        Args:
            ctx: 插件上下文（只读状态访问）
            cmd: 插件命令接口（执行操作）
        """
        self._ctx = ctx
        self._cmd = cmd
        await asyncio.sleep(0)

    async def start(self) -> None:
        """插件启动（通常在协议连接建立后调用）."""
        self._started = True
        await asyncio.sleep(0)

    async def on_protocol_connected(self, protocol: Any) -> None:
        """协议通道建立后的通知."""
        await asyncio.sleep(0)

    async def on_incoming_json(self, message: Any) -> None:
        """收到JSON消息时的通知."""
        await asyncio.sleep(0)

    async def on_incoming_audio(self, data: bytes) -> None:
        """收到音频数据时的通知."""
        await asyncio.sleep(0)

    async def on_device_state_changed(self, state: Any) -> None:
        """设备状态变更通知."""
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """插件停止."""
        self._started = False
        await asyncio.sleep(0)

    async def shutdown(self) -> None:
        """插件最终清理."""
        await asyncio.sleep(0)
