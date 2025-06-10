"""
MCP Server Implementation
Reference: https://modelcontextprotocol.io/specification/2024-11-05
"""
import asyncio
import json
import logging
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Union

from src.constants.constants import AecMode
from src.protocols.aec_manager import get_aec_manager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MCP")

# 返回值类型
ReturnValue = Union[bool, int, str]


class PropertyType(Enum):
    """属性类型枚举"""
    BOOLEAN = auto()
    INTEGER = auto()
    STRING = auto()


class Property:
    """表示工具的参数属性"""

    def __init__(self,
                 name: str,
                 prop_type: PropertyType,
                 default_value: Any = None,
                 min_value: Optional[int] = None,
                 max_value: Optional[int] = None):
        self.name = name
        self.type = prop_type
        self.value = default_value
        self.has_default_value = default_value is not None
        self.min_value = min_value
        self.max_value = max_value

        # 验证范围限制仅适用于整数类型
        if ((min_value is not None or max_value is not None)
                and prop_type != PropertyType.INTEGER):
            raise ValueError("Range limits only apply to integer properties")

        # 验证默认值在指定范围内
        if prop_type == PropertyType.INTEGER and default_value is not None:
            if min_value is not None and default_value < min_value:
                raise ValueError(f"Default value must be >= {min_value}")
            if max_value is not None and default_value > max_value:
                raise ValueError(f"Default value must be <= {max_value}")

    def set_value(self, value: Any) -> None:
        """设置属性值，包含范围验证"""
        if self.type == PropertyType.INTEGER:
            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"Value is below minimum allowed: {self.min_value}")
            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"Value exceeds maximum allowed: {self.max_value}")
        self.value = value

    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        result = {}

        if self.type == PropertyType.BOOLEAN:
            result["type"] = "boolean"
            if self.has_default_value:
                result["default"] = self.value
        elif self.type == PropertyType.INTEGER:
            result["type"] = "integer"
            if self.has_default_value:
                result["default"] = self.value
            if self.min_value is not None:
                result["minimum"] = self.min_value
            if self.max_value is not None:
                result["maximum"] = self.max_value
        elif self.type == PropertyType.STRING:
            result["type"] = "string"
            if self.has_default_value:
                result["default"] = self.value

        return result


class PropertyList:
    """属性列表，包含多个属性"""

    def __init__(self, properties: Optional[List[Property]] = None):
        self.properties = properties or []

    def add_property(self, property: Property) -> None:
        """添加属性"""
        self.properties.append(property)

    def __getitem__(self, name: str) -> Property:
        """通过名称获取属性"""
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise KeyError(f"Property not found: {name}")

    def __iter__(self):
        return iter(self.properties)

    def get_required(self) -> List[str]:
        """获取必需属性列表"""
        return [prop.name for prop in self.properties if not prop.has_default_value]

    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        return {prop.name: prop.to_json() for prop in self.properties}


class McpTool:
    """MCP工具定义"""

    def __init__(self,
                 name: str,
                 description: str,
                 properties: PropertyList,
                 callback: Callable[[PropertyList], ReturnValue]):
        self.name = name
        self.description = description
        self.properties = properties
        self.callback = callback

    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        required = self.properties.get_required()

        input_schema = {
            "type": "object",
            "properties": self.properties.to_json()
        }

        if required:
            input_schema["required"] = required

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema
        }

    def call(self, properties: PropertyList) -> str:
        """调用工具并返回结果"""
        try:
            return_value = self.callback(properties)

            # 构建响应
            content = [{
                "type": "text",
                "text": str(return_value)
            }]

            result = {
                "content": content,
                "isError": False
            }

            return json.dumps(result)
        except Exception as e:
            logger.error(f"Error calling tool {self.name}: {str(e)}")
            raise RuntimeError(str(e))


class McpServer:
    """MCP服务器实现"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = McpServer()
        return cls._instance

    def __init__(self):
        """初始化服务器"""
        self.tools = []
        self.add_common_tools()

    def add_common_tools(self):
        """添加通用工具"""
        # 添加AEC控制工具
        self.add_tool(
            "system.aec.get_status",
            "Get the current AEC (Acoustic Echo Cancellation) status and configuration",
            PropertyList(),
            lambda properties: self._get_aec_status()
        )

        self.add_tool(
            "system.aec.set_mode",
            "Set AEC mode. Available modes: aec_off, aec_on_server_side, aec_on_device_side",
            PropertyList([
                Property("mode", PropertyType.STRING, AecMode.AEC_OFF)
            ]),
            lambda properties: self._set_aec_mode(properties)
        )

        self.add_tool(
            "system.aec.get_queue_status",
            "Get AEC timestamp queue status (for server-side AEC)",
            PropertyList(),
            lambda properties: self._get_aec_queue_status()
        )

        self.add_tool(
            "system.aec.clear_queue",
            "Clear AEC timestamp queue",
            PropertyList(),
            lambda properties: self._clear_aec_queue()
        )

        # 原有的音频和屏幕控制工具
        self.add_tool(
            "self.audio_speaker.set_volume",
            "Set the volume of the audio speaker. If the current volume is unknown, you must call `self.get_device_status` tool first and then call this tool.",
            PropertyList([
                Property("volume", PropertyType.INTEGER, min_value=0, max_value=100)
            ]),
            lambda properties: self._set_audio_volume(properties)
        )

        self.add_tool(
            "self.screen.set_theme",
            "Set the screen theme.",
            PropertyList([
                Property("theme", PropertyType.STRING)
            ]),
            lambda properties: self._set_screen_theme(properties)
        )

    def _get_aec_status(self) -> str:
        """获取AEC状态."""
        aec_manager = get_aec_manager()
        status = {
            "aec_mode": aec_manager.get_aec_mode(),
            "enabled": aec_manager.is_enabled(),
            "server_side_aec": aec_manager.is_server_side_aec(),
            "device_side_aec": aec_manager.is_device_side_aec(),
            "queue_size": aec_manager.get_queue_size()
        }
        return json.dumps(status, indent=2)

    def _set_aec_mode(self, properties: PropertyList) -> bool:
        """设置AEC模式."""
        try:
            mode = properties["mode"].value
            aec_manager = get_aec_manager()
            aec_manager.set_aec_mode(mode)
            logger.info(f"AEC模式已设置为: {mode}")
            return True
        except Exception as e:
            logger.error(f"设置AEC模式失败: {e}")
            return False

    def _get_aec_queue_status(self) -> str:
        """获取AEC队列状态."""
        aec_manager = get_aec_manager()
        status = aec_manager.get_queue_status()
        return json.dumps(status, indent=2)

    def _clear_aec_queue(self) -> bool:
        """清空AEC队列."""
        try:
            aec_manager = get_aec_manager()
            aec_manager.clear_timestamp_queue()
            logger.info("AEC时间戳队列已清空")
            return True
        except Exception as e:
            logger.error(f"清空AEC队列失败: {e}")
            return False

    def _set_audio_volume(self, properties: PropertyList) -> bool:
        """设置音频音量."""
        try:
            volume = properties["volume"].value
            # TODO: 实现实际的音量设置逻辑
            logger.info(f"音量已设置为: {volume}")
            return True
        except Exception as e:
            logger.error(f"设置音量失败: {e}")
            return False

    def _set_screen_theme(self, properties: PropertyList) -> bool:
        """设置屏幕主题."""
        try:
            theme = properties["theme"].value
            # TODO: 实现实际的主题设置逻辑
            logger.info(f"主题已设置为: {theme}")
            return True
        except Exception as e:
            logger.error(f"设置主题失败: {e}")
            return False

    def add_tool(self, name: str, description: str, properties: PropertyList,
                 callback: Callable[[PropertyList], ReturnValue]):
        """添加工具"""
        tool = McpTool(name, description, properties, callback)
        self.tools.append(tool)

    def parse_message(self, message: Union[str, Dict]):
        """解析并处理MCP消息"""
        try:
            # 如果是字符串，解析为JSON
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            # 获取消息类型
            method = data.get("method")
            id_value = data.get("id")

            if method == "tools/list":
                # 处理工具列表请求
                cursor = data.get("params", {}).get("cursor")
                return self.get_tools_list(id_value, cursor)

            elif method == "tools/call":
                # 处理工具调用请求
                params = data.get("params", {})
                tool_name = params.get("name")
                tool_arguments = params.get("arguments", {})
                return self.do_tool_call(id_value, tool_name, tool_arguments)

            else:
                # 未知方法
                return self.reply_error(id_value, f"Unknown method: {method}")

        except json.JSONDecodeError as e:
            return self.reply_error(None, f"Invalid JSON: {str(e)}")
        except Exception as e:
            return self.reply_error(None, f"Error processing message: {str(e)}")

    def reply_result(self, id_value, result):
        """发送成功响应"""
        response = {
            "jsonrpc": "2.0",
            "id": id_value,
            "result": result
        }
        return json.dumps(response)

    def reply_error(self, id_value, message):
        """发送错误响应"""
        response = {
            "jsonrpc": "2.0",
            "id": id_value,
            "error": {
                "code": -1,
                "message": message
            }
        }
        return json.dumps(response)

    def get_tools_list(self, id_value, cursor: str):
        """获取工具列表"""
        try:
            # 简单实现，返回所有工具
            tools_data = []
            for tool in self.tools:
                tools_data.append(tool.to_json())

            result = {
                "tools": tools_data
            }

            # 如果有cursor参数，可以实现分页逻辑
            # 这里简单返回所有工具
            if cursor:
                # TODO: 实现基于cursor的分页
                pass

            return self.reply_result(id_value, result)

        except Exception as e:
            return self.reply_error(id_value, f"Error getting tools list: {str(e)}")

    def do_tool_call(self, id_value, tool_name, tool_arguments):
        """执行工具调用"""
        try:
            # 查找工具
            target_tool = None
            for tool in self.tools:
                if tool.name == tool_name:
                    target_tool = tool
                    break

            if not target_tool:
                return self.reply_error(id_value, f"Tool not found: {tool_name}")

            # 准备参数
            properties = PropertyList()
            for prop in target_tool.properties:
                prop_name = prop.name
                if prop_name in tool_arguments:
                    # 创建新的属性并设置值
                    new_prop = Property(prop_name, prop.type,
                                        prop.value, prop.min_value, prop.max_value)
                    new_prop.set_value(tool_arguments[prop_name])
                    properties.add_property(new_prop)
                elif not prop.has_default_value:
                    return self.reply_error(id_value,
                                            f"Required parameter missing: {prop_name}")
                else:
                    # 使用默认值
                    properties.add_property(prop)

            # 在新线程中执行工具（避免阻塞）
            def execute_tool():
                try:
                    result_json = target_tool.call(properties)
                    result = json.loads(result_json)
                    return self.reply_result(id_value, result)
                except Exception as e:
                    return self.reply_error(id_value, f"Tool execution failed: {str(e)}")

            # 如果是异步环境，可以使用asyncio
            try:
                loop = asyncio.get_event_loop()
                future = loop.run_in_executor(None, execute_tool)
                return future
            except RuntimeError:
                # 没有事件循环，直接执行
                return execute_tool()

        except Exception as e:
            return self.reply_error(id_value, f"Error executing tool: {str(e)}")