import asyncio
import json
from typing import Any, Dict, Optional, Tuple

from src.iot.thing import Thing
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class ThingManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ThingManager()
        return cls._instance

    def __init__(self):
        self.things = []
        self.last_states = {}  # 添加状态缓存字典，存储上一次的状态

    async def initialize_iot_devices(self, config):
        """初始化物联网设备.

        注意：倒计时器功能已迁移到MCP工具中，提供更好的AI集成和状态反馈。
        """
        from src.iot.things.lamp import Lamp

        # 添加设备
        self.add_thing(Lamp())

    def add_thing(self, thing: Thing) -> None:
        self.things.append(thing)

    async def get_descriptors_json(self) -> str:
        """
        获取所有设备的描述符JSON.
        """
        # 由于get_descriptor_json()是同步方法（返回静态数据），
        # 这里保持简单的同步调用即可
        descriptors = [thing.get_descriptor_json() for thing in self.things]
        return json.dumps(descriptors)

    async def get_states_json(self, delta=False) -> Tuple[bool, str]:
        """获取所有设备的状态JSON.

        Args:
            delta: 是否只返回变化的部分，True表示只返回变化的部分

        Returns:
            Tuple[bool, str]: 返回是否有状态变化的布尔值和JSON字符串
        """
        if not delta:
            self.last_states.clear()

        changed = False

        tasks = [thing.get_state_json() for thing in self.things]
        states_results = await asyncio.gather(*tasks)

        states = []
        for i, thing in enumerate(self.things):
            state_json = states_results[i]

            if delta:
                # 检查状态是否变化
                is_same = (
                    thing.name in self.last_states
                    and self.last_states[thing.name] == state_json
                )
                if is_same:
                    continue
                changed = True
                self.last_states[thing.name] = state_json

            # 检查state_json是否已经是字典对象
            if isinstance(state_json, dict):
                states.append(state_json)
            else:
                states.append(json.loads(state_json))  # 转换JSON字符串为字典

        return changed, json.dumps(states)

    async def get_states_json_str(self) -> str:
        """
        为了兼容旧代码，保留原来的方法名和返回值类型.
        """
        _, json_str = await self.get_states_json(delta=False)
        return json_str

    async def invoke(self, command: Dict) -> Optional[Any]:
        """调用设备方法.

        Args:
            command: 包含name和method等信息的命令字典

        Returns:
            Optional[Any]: 如果找到设备并调用成功，返回调用结果；否则抛出异常
        """
        thing_name = command.get("name")
        for thing in self.things:
            if thing.name == thing_name:
                return await thing.invoke(command)

        # 记录错误日志
        logger.error(f"设备不存在: {thing_name}")
        raise ValueError(f"设备不存在: {thing_name}")
