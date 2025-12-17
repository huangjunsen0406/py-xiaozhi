"""
IoT 插件.

管理物联网设备和命令处理。
"""

from typing import Any, TYPE_CHECKING

from src.plugins.base import Plugin

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginContext, PluginCommands


class IoTPlugin(Plugin):
    name = "iot"
    priority = 50  # 独立服务，默认优先级

    def __init__(self) -> None:
        super().__init__()
        self._protocol = None  # 协议引用

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        try:
            from src.iot.thing_manager import ThingManager

            manager = ThingManager.get_instance()
            config = ctx.get_config()
            await manager.initialize_iot_devices(config)
        except Exception:
            pass

    async def on_protocol_connected(self, protocol: Any) -> None:
        """协议连接后发送 IoT 描述符和状态."""
        self._protocol = protocol
        try:
            from src.iot.thing_manager import ThingManager

            manager = ThingManager.get_instance()
            descriptors_json = await manager.get_descriptors_json()
            await protocol.send_iot_descriptors(descriptors_json)

            changed, states_json = await manager.get_states_json(delta=False)
            await protocol.send_iot_states(states_json)
        except Exception:
            pass

    async def on_incoming_json(self, message) -> None:
        """处理 IoT 命令消息."""
        try:
            if not isinstance(message, dict):
                return
            if message.get("type") != "iot":
                return

            commands = message.get("commands", [])
            if not commands:
                return

            from src.iot.thing_manager import ThingManager

            manager = ThingManager.get_instance()
            for command in commands:
                try:
                    result = await manager.invoke(command)
                    print(f"[IOT] 执行命令结果: {result}")
                except Exception:
                    pass

            try:
                changed, states_json = await manager.get_states_json(delta=True)
                if changed and self._protocol:
                    await self._protocol.send_iot_states(states_json)
            except Exception:
                pass
        except Exception:
            pass
