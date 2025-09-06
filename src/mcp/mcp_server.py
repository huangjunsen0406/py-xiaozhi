"""
MCP Server Implementation for Python
Reference: https://modelcontextprotocol.io/specification/2024-11-05
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.constants.system import SystemConstants
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 返回值类型
ReturnValue = Union[bool, int, str]


class PropertyType(Enum):
    """
    属性类型枚举.
    """

    BOOLEAN = "boolean"
    INTEGER = "integer"
    STRING = "string"


@dataclass
class Property:
    """
    MCP工具属性定义.
    """

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
        """
        验证并返回值.
        """
        if self.type == PropertyType.INTEGER and self.has_range:
            if value < self.min_value:
                raise ValueError(
                    f"Value {value} is below minimum allowed: " f"{self.min_value}"
                )
            if value > self.max_value:
                raise ValueError(
                    f"Value {value} exceeds maximum allowed: " f"{self.max_value}"
                )
        return value

    def to_json(self) -> Dict[str, Any]:
        """
        转换为JSON格式.
        """
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
    """
    属性列表.
    """

    properties: List[Property] = field(default_factory=list)

    def __init__(self, properties: Optional[List[Property]] = None):
        """
        初始化属性列表.
        """
        self.properties = properties or []

    def add_property(self, prop: Property):
        self.properties.append(prop)

    def __getitem__(self, name: str) -> Property:
        for prop in self.properties:
            if prop.name == name:
                return prop
        raise KeyError(f"Property not found: {name}")

    def get_required(self) -> List[str]:
        """
        获取必需的属性名称列表.
        """
        return [p.name for p in self.properties if not p.has_default_value]

    def to_json(self) -> Dict[str, Any]:
        """
        转换为JSON格式.
        """
        return {prop.name: prop.to_json() for prop in self.properties}

    def parse_arguments(self, arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        解析并验证参数.
        """
        result = {}

        for prop in self.properties:
            if arguments and prop.name in arguments:
                value = arguments[prop.name]
                # 类型检查
                if prop.type == PropertyType.BOOLEAN and isinstance(value, bool):
                    result[prop.name] = value
                elif prop.type == PropertyType.INTEGER and isinstance(
                    value, (int, float)
                ):
                    result[prop.name] = prop.value(int(value))
                elif prop.type == PropertyType.STRING and isinstance(value, str):
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
    """
    MCP工具定义.
    """

    name: str
    description: str
    properties: PropertyList
    callback: Callable[[Dict[str, Any]], ReturnValue]

    def to_json(self) -> Dict[str, Any]:
        """
        转换为JSON格式.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": self.properties.to_json(),
                "required": self.properties.get_required(),
            },
        }

    async def call(self, arguments: Dict[str, Any]) -> str:
        """
        调用工具.
        """
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

            return json.dumps(
                {"content": [{"type": "text", "text": text}], "isError": False}
            )

        except Exception as e:
            logger.error(f"Error calling tool {self.name}: {e}", exc_info=True)
            return json.dumps(
                {"content": [{"type": "text", "text": str(e)}], "isError": True}
            )


class McpServer:
    """
    MCP服务器实现.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """
        获取单例实例.
        """
        if cls._instance is None:
            cls._instance = McpServer()
        return cls._instance

    def __init__(self):
        self.tools: List[McpTool] = []
        self._send_callback: Optional[Callable] = None
        self._camera = None

    def set_send_callback(self, callback: Callable):
        """
        设置发送消息的回调函数.
        """
        self._send_callback = callback

    def add_tool(self, tool: Union[McpTool, Tuple[str, str, PropertyList, Callable]]):
        """
        添加工具.
        """
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
        """
        添加通用工具.
        """
        # 备份原有工具列表
        original_tools = self.tools.copy()
        self.tools.clear()

        # 添加系统工具
        from src.mcp.tools.system import get_system_tools_manager

        system_manager = get_system_tools_manager()
        system_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)

        # 添加日程管理工具
        from src.mcp.tools.calendar import get_calendar_manager

        calendar_manager = get_calendar_manager()
        calendar_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)

        # 添加倒计时器工具
        from src.mcp.tools.timer import get_timer_manager

        timer_manager = get_timer_manager()
        timer_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)

        # 添加音乐播放器工具
        from src.mcp.tools.music import get_music_tools_manager

        music_manager = get_music_tools_manager()
        music_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)

        # 添加摄像头工具
        from src.mcp.tools.camera import take_photo

        # 注册take_photo工具
        properties = PropertyList([Property("question", PropertyType.STRING)])
        VISION_DESC = (
            "【图像/识图/OCR/问答】当用户提到：拍照、识图、读取/提取文字、OCR、翻译图片文字、"
            "看一下这张图/截图、这是什么、数一数、识别二维码/条码、对比两张图、分析场景/报错截图、"
            "表格/票据信息抽取、图片问答 时调用本工具。"
            "功能：①拍照或接收已有图片/截图/URL；②物体/场景/标签识别；③OCR(多语)与翻译；④计数/位置；"
            "⑤二维码/条码读取；⑥关键信息抽取(表格/票据)；⑦两图对比；⑧就图回答问题。"
            "输入建议：{ mode:'capture'|'upload'|'url', image?, url?, question?, target_lang? }；"
            "若用户未提供图片且允许，可触发拍照(mode='capture')。"
            "避免：纯文本知识问答、与图片无关的请求。"
            "English: Vision/OCR/QA tool. Use when the user provides or asks about a photo/screenshot/image: "
            "describe, classify, OCR, translate, count objects, read QR/barcodes, extract tables/receipts, "
            "compare two images, image QA. Inputs as above. Do NOT use for pure text queries."
            "Examples: '这张图是什么', 'OCR这张发票并翻译成英文', '数一下图里有几只猫', '读一下这个二维码', "
            "'对比这两张UI截图的差异', '把截图里的表格提取成CSV'。"
        )

        self.add_tool(
            McpTool(
                "take_photo",            # 保留原名兼容
                VISION_DESC,
                properties,
                take_photo,
            )
        )

        # 添加桌面截图工具
        from src.mcp.tools.screenshot import take_screenshot

        # 注册take_screenshot工具
        screenshot_properties = PropertyList([
            Property("question", PropertyType.STRING),
            Property("display", PropertyType.STRING, default_value=None)
        ])
        SCREENSHOT_DESC = (
            "【桌面截图/屏幕分析】当用户提到：截屏、截图、看看桌面、分析屏幕、桌面上有什么、"
            "屏幕截图、查看当前界面、分析当前页面、读取屏幕内容、屏幕OCR 时调用本工具。"
            "功能：①截取整个桌面画面；②屏幕内容识别与分析；③屏幕OCR文字提取；④界面元素分析；"
            "⑤应用程序识别；⑥错误信息截图分析；⑦桌面状态检查；⑧多屏幕截图。"
            "参数说明：{ question: '你想了解的关于桌面/屏幕的问题', display: '显示器选择(可选)' }；"
            "display可选值：'main'/'主屏'/'笔记本'(主显示器), 'secondary'/'副屏'/'外屏'(副显示器), 或留空(所有显示器)；"
            "适用场景：桌面截图、屏幕分析、界面问题诊断、应用状态查看、错误截图分析等。"
            "注意：该工具会截取桌面，请确保用户同意截图操作。"
            "English: Desktop screenshot/screen analysis tool. Use when user mentions: screenshot, screen capture, "
            "desktop analysis, screen content, current interface, screen OCR, etc. "
            "Functions: ①Full desktop capture; ②Screen content recognition; ③Screen OCR; ④Interface analysis; "
            "⑤Application identification; ⑥Error screenshot analysis; ⑦Desktop status check. "
            "Parameters: { question: 'Question about desktop/screen', display: 'Display selection (optional)' }; "
            "Display options: 'main'(primary), 'secondary'(external), or empty(all displays). "
            "Examples: '截个图看看主屏', '查看副屏有什么', '分析当前屏幕内容', '读取屏幕上的文字'。"
        )

        self.add_tool(
            McpTool(
                "take_screenshot",
                SCREENSHOT_DESC,
                screenshot_properties,
                take_screenshot,
            )
        )

        # 添加八字命理工具
        from src.mcp.tools.bazi import get_bazi_manager

        bazi_manager = get_bazi_manager()
        bazi_manager.init_tools(self.add_tool, PropertyList, Property, PropertyType)

        # 恢复原有工具
        self.tools.extend(original_tools)

    async def parse_message(self, message: Union[str, Dict[str, Any]]):
        """
        解析MCP消息.
        """
        try:
            if isinstance(message, str):
                data = json.loads(message)
            else:
                data = message

            logger.info(
                f"[MCP] 解析消息: {json.dumps(data, ensure_ascii=False, indent=2)}"
            )

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
                await self._reply_error(id, f"Method not implemented: {method}")

        except Exception as e:
            logger.error(f"Error parsing MCP message: {e}", exc_info=True)
            if "id" in locals():
                await self._reply_error(id, str(e))

    async def _handle_initialize(self, id: int, params: Dict[str, Any]):
        """
        处理初始化请求.
        """
        # 解析capabilities
        capabilities = params.get("capabilities", {})
        await self._parse_capabilities(capabilities)

        # 返回服务器信息
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": SystemConstants.APP_NAME,
                "version": SystemConstants.APP_VERSION,
            },
        }

        await self._reply_result(id, result)

    async def _handle_tools_list(self, id: int, params: Dict[str, Any]):
        """
        处理工具列表请求.
        """
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
        """
        处理工具调用请求.
        """
        logger.info(f"[MCP] 收到工具调用请求! ID={id}, 参数={params}")

        tool_name = params.get("name")
        if not tool_name:
            await self._reply_error(id, "Missing tool name")
            return

        logger.info(f"[MCP] 尝试调用工具: {tool_name}")

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

        logger.info(f"[MCP] 开始执行工具 {tool_name}, 参数: {arguments}")

        # 异步调用工具
        try:
            result = await tool.call(arguments)
            logger.info(f"[MCP] 工具 {tool_name} 执行成功，结果: {result}")
            await self._reply_result(id, json.loads(result))
        except Exception as e:
            logger.error(f"[MCP] 工具 {tool_name} 执行失败: {e}", exc_info=True)
            await self._reply_error(id, str(e))

    async def _parse_capabilities(self, capabilities):
        """
        解析capabilities.
        """
        vision = capabilities.get("vision", {})
        if vision and isinstance(vision, dict):
            url = vision.get("url")
            token = vision.get("token")
            if url:
                from src.mcp.tools.camera import get_camera_instance

                camera = get_camera_instance()
                if hasattr(camera, "set_explain_url"):
                    camera.set_explain_url(url)
                if token and hasattr(camera, "set_explain_token"):
                    camera.set_explain_token(token)
                logger.info(f"Vision service configured with URL: {url}")

    async def _reply_result(self, id: int, result: Any):
        """
        发送成功响应.
        """
        payload = {"jsonrpc": "2.0", "id": id, "result": result}

        result_len = len(json.dumps(result))
        logger.info(f"[MCP] 发送成功响应: ID={id}, 结果长度={result_len}")

        if self._send_callback:
            await self._send_callback(json.dumps(payload))
        else:
            logger.error("[MCP] 发送回调未设置!")

    async def _reply_error(self, id: int, message: str):
        """
        发送错误响应.
        """
        payload = {"jsonrpc": "2.0", "id": id, "error": {"message": message}}

        logger.error(f"[MCP] 发送错误响应: ID={id}, 错误={message}")

        if self._send_callback:
            await self._send_callback(json.dumps(payload))
