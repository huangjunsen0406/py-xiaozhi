import json
from typing import Any, Dict

from src.iot.thing import Thing


class ThingManager:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = ThingManager()
        return cls._instance

    def __init__(self):
        self.things = []

    def add_thing(self, thing: Thing) -> None:
        self.things.append(thing)

    def get_descriptors_json(self) -> str:
        descriptors = [thing.get_descriptor_json() for thing in self.things]
        return json.dumps(descriptors)

    def get_states_json(self) -> str:
        states = [thing.get_state_json() for thing in self.things]
        return json.dumps(states)

    def invoke(self, command: Dict) -> Any:
        thing_name = command.get("name")
        for thing in self.things:
            if thing.name == thing_name:
                return thing.invoke(command)

        raise ValueError(f"设备不存在: {thing_name}")