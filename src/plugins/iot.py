from typing import Any

from src.plugins.base import Plugin


class IoTPlugin(Plugin):
    name = "iot"

    def __init__(self) -> None:
        super().__init__()
        self.app = None

    async def setup(self, app: Any) -> None:
        self.app = app
        # 确保设备初始化完成
        try:
            from src.iot.thing_manager import ThingManager

            manager = ThingManager.get_instance()
            await manager.initialize_iot_devices(getattr(self.app, "config", None))
        except Exception:
            pass

    async def on_protocol_connected(self, protocol: Any) -> None:
        """
        协议连接后，发送 IoT 描述符与一次状态。
        """
        try:
            from src.iot.thing_manager import ThingManager

            manager = ThingManager.get_instance()
            descriptors_json = await manager.get_descriptors_json()
            await self.app.protocol.send_iot_descriptors(descriptors_json)

            changed, states_json = await manager.get_states_json(delta=False)
            await self.app.protocol.send_iot_states(states_json)
        except Exception:
            pass

    async def on_incoming_json(self, message: Any) -> None:
        """
        处理来自服务端的 IoT 命令消息。
        """
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
                # 执行后下发一次最新状态（只发变化）
                changed, states_json = await manager.get_states_json(delta=True)
                if changed:
                    await self.app.protocol.send_iot_states(states_json)
            except Exception:
                pass
        except Exception:
            pass
