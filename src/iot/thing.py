import json
from typing import Dict, List, Callable, Any, Optional, Union


class ValueType:
    BOOLEAN = "boolean"
    NUMBER = "number"
    STRING = "string"


class Property:
    def __init__(self, name: str, description: str, getter: Callable):
        self.name = name
        self.description = description
        self.getter = getter

        # 根据 getter 返回值类型确定属性类型
        test_value = getter()
        if isinstance(test_value, bool):
            self.type = ValueType.BOOLEAN
        elif isinstance(test_value, (int, float)):
            self.type = ValueType.NUMBER
        elif isinstance(test_value, str):
            self.type = ValueType.STRING
        else:
            raise TypeError(f"不支持的属性类型: {type(test_value)}")

    def get_descriptor_json(self) -> Dict:
        return {
            "description": self.description,
            "type": self.type
        }

    def get_state_value(self):
        return self.getter()


class Parameter:
    def __init__(self, name: str, description: str, type_: str, required: bool = True):
        self.name = name
        self.description = description
        self.type = type_
        self.required = required
        self.value = None

    def get_descriptor_json(self) -> Dict:
        return {
            "description": self.description,
            "type": self.type
        }

    def set_value(self, value: Any):
        self.value = value

    def get_value(self) -> Any:
        return self.value


class Method:
    def __init__(self, name: str, description: str, parameters: List[Parameter], callback: Callable):
        self.name = name
        self.description = description
        self.parameters = {param.name: param for param in parameters}
        self.callback = callback

    def get_descriptor_json(self) -> Dict:
        return {
            "description": self.description,
            "parameters": {name: param.get_descriptor_json()
                           for name, param in self.parameters.items()}
        }

    def invoke(self, params: Dict[str, Any]) -> Any:
        # 设置参数值
        for name, value in params.items():
            if name in self.parameters:
                self.parameters[name].set_value(value)

        # 检查必需参数
        for name, param in self.parameters.items():
            if param.required and param.get_value() is None:
                raise ValueError(f"缺少必需参数: {name}")

        # 调用回调函数
        return self.callback(self.parameters)


class Thing:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.properties = {}
        self.methods = {}

    def add_property(self, name: str, description: str, getter: Callable) -> None:
        self.properties[name] = Property(name, description, getter)

    def add_method(self, name: str, description: str, parameters: List[Parameter], callback: Callable) -> None:
        self.methods[name] = Method(name, description, parameters, callback)

    def get_descriptor_json(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "properties": {name: prop.get_descriptor_json()
                           for name, prop in self.properties.items()},
            "methods": {name: method.get_descriptor_json()
                        for name, method in self.methods.items()}
        }

    def get_state_json(self) -> Dict:
        return {
            "name": self.name,
            "state": {name: prop.get_state_value()
                      for name, prop in self.properties.items()}
        }

    def invoke(self, command: Dict) -> Any:
        method_name = command.get("method")
        if method_name not in self.methods:
            raise ValueError(f"方法不存在: {method_name}")

        parameters = command.get("parameters", {})
        return self.methods[method_name].invoke(parameters)