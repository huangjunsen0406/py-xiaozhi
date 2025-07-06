from dataclasses import dataclass
from typing import Union, Optional, Callable, List, Dict
import json


ReturnValue = Union[bool, int, str]


class PropertyType:
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    STRING = 'string'


@dataclass
class Property:
    name: str
    type: str
    value: Optional[ReturnValue] = None
    min: Optional[int] = None
    max: Optional[int] = None
    has_default: bool = False

    def __post_init__(self):
        if self.type == PropertyType.INTEGER:
            if self.min is not None and self.max is not None:
                if isinstance(self.value, int) and not (self.min <= self.value <= self.max):
                    raise ValueError("Default value must be within the specified range")

    def set_value(self, val: ReturnValue):
        if self.type == PropertyType.INTEGER and isinstance(val, int):
            if self.min is not None and val < self.min:
                raise ValueError(f"Value below minimum allowed: {self.min}")
            if self.max is not None and val > self.max:
                raise ValueError(f"Value exceeds maximum allowed: {self.max}")
        self.value = val

    def to_json(self) -> Dict:
        data = {"type": self.type}
        if self.has_default and self.value is not None:
            data["default"] = self.value
        if self.type == PropertyType.INTEGER:
            if self.min is not None:
                data["minimum"] = self.min
            if self.max is not None:
                data["maximum"] = self.max
        return data


class PropertyList:
    def __init__(self, properties: Optional[List[Property]] = None):
        self.properties: List[Property] = properties or []

    def add_property(self, prop: Property):
        self.properties.append(prop)

    def __getitem__(self, name: str) -> Property:
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise KeyError(f"Property not found: {name}")

    def get_required(self) -> List[str]:
        return [prop.name for prop in self.properties if not prop.has_default]

    def to_json(self) -> Dict:
        return {prop.name: prop.to_json() for prop in self.properties}


@dataclass
class McpTool:
    name: str
    description: str
    properties: PropertyList
    callback: Callable[[PropertyList], ReturnValue]

    def to_json(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties.to_json(),
                "required": self.properties.get_required()
            }
        }

    def call(self, prop_list: PropertyList) -> str:
        result = self.callback(prop_list)
        response = {
            "content": [
                {
                    "type": "text",
                    "text": str(result)
                }
            ],
            "isError": False
        }
        return json.dumps(response, separators=(',', ':'))


class BaseMcpServer:
    _instance = None

    def __init__(self):
        self.tools: Dict[str, McpTool] = {}

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def add_tool(self, tool: McpTool):
        self.tools[tool.name] = tool

    def add_tool_with_callback(self, name: str, description: str, props: PropertyList, cb: Callable[[PropertyList], ReturnValue]):
        self.tools[name] = McpTool(name, description, props, cb)
