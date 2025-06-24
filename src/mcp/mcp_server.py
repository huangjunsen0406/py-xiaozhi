"""
MCP Server Implementation for Python
Reference: https://modelcontextprotocol.io/specification/2024-11-05
"""

import json
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# 返回值类型
ReturnValue = Union[bool, int, str]


class PropertyType(Enum):
    """属性类型枚举"""
    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"


@dataclass
class Property:
    """MCP工具属性定义"""
    name: str
    type: PropertyType
    default_value: Optional[Any] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    
    @property
    def has_default_value(self) -> bool:
        return self.default_value is not None
    
    @property
    def has_range(self) -> bool:
        return self.min_value is not None and self.max_value is not None
    
    def value(self, value: Any) -> Any:
        """验证并返回值"""
        if self.type == PropertyType.INTEGER and self.has_range:
            if value < self.min_value:
                raise ValueError(
                    f"Value {value} is below minimum allowed: "
                    f"{self.min_value}"
                )
            if value > self.max_value:
                raise ValueError(
                    f"Value {value} exceeds maximum allowed: "
                    f"{self.max_value}"
                )
        return value
    
    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        result = {"type": self.type.value}
        
        if self.has_default_value:
            result["default"] = self.default_value
            
        if self.type == PropertyType.INTEGER:
            if self.min_value is not None:
                result["minimum"] = self.min_value
            if self.max_value is not None:
                result["maximum"] = self.max_value
                
        return result


@dataclass
class PropertyList:
    """属性列表"""
    properties: List[Property] = field(default_factory=list)
    
    def __init__(self, properties: Optional[List[Property]] = None):
        """初始化属性列表"""
        self.properties = properties or []
    
    def add_property(self, prop: Property):
        self.properties.append(prop)
    
    def __getitem__(self, name: str) -> Property:
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise KeyError(f"Property not found: {name}")
    
    def get_required(self) -> List[str]:
        """获取必需的属性名称列表"""
        return [p.name for p in self.properties if not p.has_default_value]
    
    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        return {prop.name: prop.to_json() for prop in self.properties}
    
    def parse_arguments(
            self,
            arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """解析并验证参数"""
        result = {}
        
        for prop in self.properties:
            if arguments and prop.name in arguments:
                value = arguments[prop.name]
                # 类型检查
                if (prop.type == PropertyType.BOOLEAN and 
                        isinstance(value, bool)):
                    result[prop.name] = value
                elif (prop.type == PropertyType.INTEGER and 
                      isinstance(value, (int, float))):
                    result[prop.name] = prop.value(int(value))
                elif (prop.type == PropertyType.STRING and 
                      isinstance(value, str)):
                    result[prop.name] = value
                else:
                    raise ValueError(f"Invalid type for property {prop.name}")
            elif prop.has_default_value:
                result[prop.name] = prop.default_value
            else:
                raise ValueError(f"Missing required argument: {prop.name}")
                
        return result


@dataclass
class McpTool:
    """MCP工具定义"""
    name: str
    description: str
    properties: PropertyList
    callback: Callable[[Dict[str, Any]], ReturnValue]
    
    def to_json(self) -> Dict[str, Any]:
        """转换为JSON格式"""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties.to_json(),
                "required": self.properties.get_required()
            }
        }
    
    async def call(self, arguments: Dict[str, Any]) -> str:
        """调用工具"""
        try:
            # 解析参数
            parsed_args = self.properties.parse_arguments(arguments)
            
            # 调用回调函数
            if asyncio.iscoroutinefunction(self.callback):
                result = await self.callback(parsed_args)
            else:
                result = self.callback(parsed_args)
            
            # 格式化返回值
            if isinstance(result, bool):
                text = "true" if result else "false"
            elif isinstance(result, int):
                text = str(result)
            else:
                text = str(result)
            
            return json.dumps({
                "content": [{
                    "type": "text",
                    "text": text
                }],
                "isError": False
            })
            
        except Exception as e:
            logger.error(f"Error calling tool {self.name}: {e}", exc_info=True)
            return json.dumps({
                "content": [{
                    "type": "text",
                    "text": str(e)
                }],
                "isError": True
            })


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
        self.tools: List[McpTool] = []
        self._send_callback: Optional[Callable] = None
        self._board = None
        self._display = None
        self._camera = None
        
    def set_send_callback(self, callback: Callable):
        """设置发送消息的回调函数"""
        self._send_callback = callback
        
    def add_tool(
            self,
            tool: Union[McpTool, Tuple[str, str, PropertyList, Callable]]):
        """添加工具"""
        if isinstance(tool, tuple):
            # 从参数创建McpTool
            name, description, properties, callback = tool
            tool = McpTool(name, description, properties, callback)
            
        # 检查是否已存在
        if any(t.name == tool.name for t in self.tools):
            logger.warning(f"Tool {tool.name} already added")
            return
            
        logger.info(f"Add tool: {tool.name}")
        self.tools.append(tool)
        
    def add_common_tools(self):
        """添加通用工具（与C++版本保持一致）"""
        # 导入系统工具
        from src.mcp.tools import system
        
        # 备份原有工具列表
        original_tools = self.tools.copy()
        self.tools.clear()
        
        # 添加获取设备状态工具
        self.add_tool((
            "self.get_device_status",
            "Provides the real-time information of the device, including "
            "the current status of the audio speaker, screen, battery, "
            "network, etc.\n"
            "Use this tool for: \n"
            "1. Answering questions about current condition (e.g. what is "
            "the current volume of the audio speaker?)\n"
            "2. As the first step to control the device (e.g. turn up / "
            "down the volume of the audio speaker, etc.)",
            PropertyList(),
            system.get_device_status
        ))
        
        # 添加设置音量工具
        volume_props = PropertyList([
            Property("volume", PropertyType.INTEGER, 
                     min_value=0, max_value=100)
        ])
        self.add_tool((
            "self.audio_speaker.set_volume",
            "Set the volume of the audio speaker. If the current volume is "
            "unknown, you must call `self.get_device_status` tool first and "
            "then call this tool.",
            volume_props,
            system.set_volume
        ))
        
        # 添加设置屏幕亮度工具
        brightness_props = PropertyList([
            Property("brightness", PropertyType.INTEGER, 
                     min_value=0, max_value=100)
        ])
        self.add_tool((
            "self.screen.set_brightness",
            "Set the brightness of the screen.",
            brightness_props,
            system.set_brightness
        ))
        
        # 添加获取屏幕亮度工具
        self.add_tool((
            "self.screen.get_brightness",
            "Get the current brightness of the screen on Mac computer. "
            "Returns the brightness level as a percentage (0-100%).\n"
            "Use this tool when user asks about:\n"
            "1. Current screen brightness level\n"
            "2. What is the brightness setting\n"
            "3. How bright is the screen",
            PropertyList(),
            system.get_brightness
        ))
        
        # 添加设置主题工具
        theme_props = PropertyList([
            Property("theme", PropertyType.STRING)
        ])
        self.add_tool((
            "self.screen.set_theme",
            "Set the theme of the screen. The theme can be "
            "`light` or `dark`. Will always succeed as a simulated operation.",
            theme_props,
            system.set_theme
        ))
        
        # 添加拍照工具
        camera_props = PropertyList([
            Property("question", PropertyType.STRING)
        ])
        self.add_tool((
            "self.camera.take_photo",
            "Take a photo and explain it. Use this tool after the user asks "
            "you to see something.\n"
            "Args:\n"
            "  `question`: The question that you want to ask about the "
            "photo.\n"
            "Return:\n"
            "  A JSON object that provides the photo information.",
            camera_props,
            system.take_photo
        ))
        
        # 添加获取电池电量工具
        self.add_tool((
            "self.battery.get_info",
            "Get detailed battery information for Mac computer, including "
            "battery percentage, charging status, health condition, cycle "
            "count, and estimated time remaining.\n"
            "Use this tool when user asks about:\n"
            "1. Current battery level or percentage\n"
            "2. Battery charging status\n"
            "3. Battery health and condition\n"
            "4. Estimated battery time remaining",
            PropertyList(),
            system.get_battery_info
        ))
        
        # 恢复原有工具
        self.tools.extend(original_tools)
        
    async def parse_message(self, message: Union[str, Dict[str, Any]]):
        """解析MCP消息"""
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message
                
            logger.info(f"[MCP] 解析消息: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
            # 检查JSONRPC版本
            if data.get("jsonrpc") != "2.0":
                logger.error(f"Invalid JSONRPC version: {data.get('jsonrpc')}")
                return
                
            method = data.get("method")
            if not method:
                logger.error("Missing method")
                return
                
            # 忽略通知
            if method.startswith("notifications"):
                logger.info(f"[MCP] 忽略通知消息: {method}")
                return
                
            params = data.get("params", {})
            id = data.get("id")
            
            if id is None:
                logger.error(f"Invalid id for method: {method}")
                return
                
            logger.info(f"[MCP] 处理方法: {method}, ID: {id}, 参数: {params}")
            
            # 处理不同的方法
            if method == "initialize":
                await self._handle_initialize(id, params)
            elif method == "tools/list":
                await self._handle_tools_list(id, params)
            elif method == "tools/call":
                await self._handle_tool_call(id, params)
            else:
                logger.error(f"Method not implemented: {method}")
                await self._reply_error(
                    id, f"Method not implemented: {method}")
                
        except Exception as e:
            logger.error(f"Error parsing MCP message: {e}", exc_info=True)
            if 'id' in locals():
                await self._reply_error(id, str(e))
                
    async def _handle_initialize(self, id: int, params: Dict[str, Any]):
        """处理初始化请求"""
        # 解析capabilities
        capabilities = params.get("capabilities", {})
        await self._parse_capabilities(capabilities)
        
        # 返回服务器信息
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": "xiaozhi-esp32-python",
                "version": "1.0.0"
            }
        }
        
        await self._reply_result(id, result)
        
    async def _handle_tools_list(self, id: int, params: Dict[str, Any]):
        """处理工具列表请求"""
        cursor = params.get("cursor", "")
        max_payload_size = 8000
        
        tools_json = []
        total_size = 0
        found_cursor = not cursor
        next_cursor = ""
        
        for tool in self.tools:
            # 如果还没找到起始位置，继续搜索
            if not found_cursor:
                if tool.name == cursor:
                    found_cursor = True
                else:
                    continue
                    
            # 检查大小
            tool_json = tool.to_json()
            tool_size = len(json.dumps(tool_json))
            
            if total_size + tool_size + 100 > max_payload_size:
                next_cursor = tool.name
                break
                
            tools_json.append(tool_json)
            total_size += tool_size
            
        result = {"tools": tools_json}
        if next_cursor:
            result["nextCursor"] = next_cursor
            
        await self._reply_result(id, result)
        
    async def _handle_tool_call(self, id: int, params: Dict[str, Any]):
        """处理工具调用请求"""
        logger.info(f"🔧 [MCP] 收到工具调用请求! ID={id}, 参数={params}")
        
        tool_name = params.get("name")
        if not tool_name:
            await self._reply_error(id, "Missing tool name")
            return
            
        logger.info(f"🔧 [MCP] 尝试调用工具: {tool_name}")
        
        # 查找工具
        tool = None
        for t in self.tools:
            if t.name == tool_name:
                tool = t
                break
                
        if not tool:
            await self._reply_error(id, f"Unknown tool: {tool_name}")
            return
            
        # 获取参数
        arguments = params.get("arguments", {})
        
        logger.info(f"🔧 [MCP] 开始执行工具 {tool_name}, 参数: {arguments}")
        
        # 异步调用工具
        try:
            result = await tool.call(arguments)
            logger.info(f"🔧 [MCP] 工具 {tool_name} 执行成功，结果: {result}")
            await self._reply_result(id, json.loads(result))
        except Exception as e:
            logger.error(f"🔧 [MCP] 工具 {tool_name} 执行失败: {e}", exc_info=True)
            await self._reply_error(id, str(e))
            
    async def _parse_capabilities(self, capabilities: Dict[str, Any]):
        """解析capabilities"""
        vision = capabilities.get("vision", {})
        if vision:
            url = vision.get("url")
            token = vision.get("token")
            if url and self._camera:
                await self._camera.set_explain_url(url, token)
                
    async def _reply_result(self, id: int, result: Any):
        """发送成功响应"""
        payload = {
            "jsonrpc": "2.0",
            "id": id,
            "result": result
        }
        
        result_len = len(json.dumps(result))
        logger.info(f"[MCP] 发送成功响应: ID={id}, 结果长度={result_len}")
        
        if self._send_callback:
            await self._send_callback(json.dumps(payload))
        else:
            logger.error("[MCP] 发送回调未设置!")
            
    async def _reply_error(self, id: int, message: str):
        """发送错误响应"""
        payload = {
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "message": message
            }
        }
        
        logger.error(f"[MCP] 发送错误响应: ID={id}, 错误={message}")
        
        if self._send_callback:
            await self._send_callback(json.dumps(payload))
            
