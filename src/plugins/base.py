"""内置插件基类，通过 PluginContext 和 PluginCommands 与核心服务交互。"""

import asyncio
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.core.resource_pool import ResourcePool


class Plugin:
    """内置插件的生命周期和事件钩子。

    name 用于装配校验和日志；requires 声明必须先注册且健康的组件名称。
    组件之间的引用由装配代码通过构造参数传入。
    """

    name: str = "plugin"
    requires: list[str] = []

    def __init__(self) -> None:
        self._started = False
        self._failed = False
        self._ctx: PluginContext = None
        self._cmd: PluginCommands = None

    @property
    def ctx(self) -> "PluginContext":
        """获取插件上下文。"""
        return self._ctx

    @property
    def cmd(self) -> "PluginCommands":
        """获取插件命令接口。"""
        return self._cmd

    @property
    def failed(self) -> bool:
        """插件是否已标记为失败（setup/start 失败或依赖失败）。"""
        return self._failed

    def mark_failed(self) -> None:
        """标记插件失败，跳过后续启动和 wiring 事件交付。"""
        self._failed = True
        self._started = False

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        """保存插件上下文和命令接口。"""
        self._ctx = ctx
        self._cmd = cmd
        await asyncio.sleep(0)

    async def start(self) -> None:
        """启动插件。"""
        self._started = True
        await asyncio.sleep(0)

    async def on_incoming_json(self, message: Any) -> None:
        """wiring 订阅的会话 JSON 消息钩子。"""
        await asyncio.sleep(0)

    async def on_incoming_audio(self, data: bytes) -> None:
        """音频处理钩子，由装配代码直接绑定到协议音频处理器。"""
        await asyncio.sleep(0)

    async def on_device_state_changed(self, state: Any) -> None:
        """wiring 订阅的设备状态变更钩子。"""
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """停止插件。"""
        self._started = False
        await asyncio.sleep(0)

    def register_resources(self, pool: "ResourcePool") -> None:
        """向资源池注册清理函数，资源按注册的逆序释放。"""
        pass
