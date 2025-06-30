# mcp_server.py

import threading
import json
import logging
from src.mcp.mcp_server_util import BaseMcpServer, McpTool, Property, PropertyType, PropertyList
from typing import Callable, Any, Dict, List
from src.application import Application  # 假设你有类似的模块发送 MCP 响应
from src.mcp.camera import Camera

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MCP")


class McpServer(BaseMcpServer):
    def __init__(self):
        super().__init__()
        self.camera = Camera.get_instance()
        self.add_common_tools()

    def add_common_tools(self):

        if self.camera:
            self.add_tool(McpTool(
                name="take_photo",
                description="Take photo and answer a question about it.",
                properties=PropertyList([
                    Property("question", PropertyType.STRING),
                ]),
                callback=lambda args: (
                    self.camera.explain(args["question"])
                    if self.camera.capture()
                    else {"success": False, "message": "Failed to capture photo"}
                )
            ))

    def parse_message(self, message: str):
        """解析MCP消息"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse MCP message: {message}")
            return

        self._handle_message(data)

    def _handle_message(self, data: Dict[str, Any]):
        """处理解析后的消息"""
        if data.get("jsonrpc") != "2.0":
            logger.error(f"Invalid JSONRPC version: {data.get('jsonrpc')}")
            return

        method = data.get("method")
        if not method:
            logger.error("Missing method")
            return

        params = data.get("params", {})
        msg_id = data.get("id")

        if method == "initialize":
            self._handle_initialize(params, msg_id)
        elif method == "tools/list":
            self._handle_tools_list(params, msg_id)
        elif method == "tools/call":
            self._handle_tools_call(params, msg_id)
        else:
            logger.error(f"Method not implemented: {method}")
            self._reply_error(msg_id, f"Method not implemented: {method}")

    def _handle_initialize(self, params: Dict[str, Any], msg_id: int):
        """处理initialize方法"""
        capabilities = params.get("capabilities", {})
        self._parse_capabilities(capabilities)

        app_info = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "Python MCP Server", "version": "1.0"}
        }
        self._reply_result(msg_id, app_info)

    def _parse_capabilities(self, capabilities: Dict[str, Any]):
        """解析capabilities"""
        vision = capabilities.get("vision", {})
        url = vision.get("url")
        token = vision.get("token")
        if url:
            # 设置相机解释URL
            logger.info(f"Set vision URL: {url}")
            # 这里可以根据需要设置相机解释URL和token
            self.camera.set_explain_url(url)
            self.camera.set_explain_token(token)

    def _handle_tools_list(self, params: Dict[str, Any], msg_id: int):
        """处理tools/list方法"""
        cursor = params.get("cursor", "")
        tools_list = self._get_tools_list(cursor)
        self._reply_result(msg_id, tools_list)

    def _get_tools_list(self, cursor: str) -> Dict[str, Any]:
        """获取工具列表"""
        max_payload_size = 8000
        tools = []
        found_cursor = not cursor
        next_cursor = ""

        for tool_name, tool_item in self.tools.items():
            if not found_cursor:
                if tool_name == cursor:
                    found_cursor = True
                continue
            tool_info = tool_item.to_json()
            tool_json = {
                "name": tool_name,
                "description": tool_info["description"],
                "inputSchema": tool_info["inputSchema"]
            }
            print(tool_json)
            tools.append(tool_json)

            if len(json.dumps(tools)) > max_payload_size:
                next_cursor = tool_name
                break
        print(tools)
        result = {"tools": tools}
        if next_cursor:
            result["nextCursor"] = next_cursor
        return result

    def _handle_tools_call(self, params: Dict[str, Any], msg_id: int):
        """处理tools/call方法"""
        tool_name = params.get("name")
        tool_arguments = params.get("arguments", {})
        stack_size = params.get("stackSize", 6144)

        if tool_name not in self.tools:
            logger.error(f"Unknown tool: {tool_name}")
            self._reply_error(msg_id, f"Unknown tool: {tool_name}")
            return

        tool_info = self.tools[tool_name]
        try:
            result = tool_info.callback(tool_arguments)
            self._reply_result(msg_id, result)
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            self._reply_error(msg_id, str(e))

    def _reply_result(self, msg_id: int, result: Any):
        """回复结果"""
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result
        }
        Application.get_instance().send_mcp_message(payload)

    def _reply_error(self, msg_id: int, message: str):
        """回复错误"""
        payload = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"message": message}
        }
        Application.get_instance().send_mcp_message(payload)
