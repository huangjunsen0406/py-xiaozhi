"""
MCP Server Implementation for Python
Supports legacy 2024-11-05 and modern 2026-07-28 protocols.
Reference: https://modelcontextprotocol.io/specification/2026-07-28/basic/index
"""

import json
from collections.abc import Callable
from contextlib import nullcontext
from typing import Any

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.mcp.plugins.registry import PluginRuntime
from src.mcp.tool_catalog import normalize_disabled
from src.mcp.tooling import McpTool, PropertyList
from src.mcp.tools.camera.base_camera import vision_config_override
from src.utils.config_manager import ConfigManager

logger = get_logger()

MCP_VERSION_MODERN = "2026-07-28"
MCP_VERSION_LEGACY = "2024-11-05"
SUPPORTED_MCP_VERSIONS = [MCP_VERSION_MODERN, MCP_VERSION_LEGACY]

_META_PROTOCOL_VERSION = "io.modelcontextprotocol/protocolVersion"
_META_CLIENT_CAPABILITIES = "io.modelcontextprotocol/clientCapabilities"
_META_CLIENT_INFO = "io.modelcontextprotocol/clientInfo"
_META_SERVER_INFO = "io.modelcontextprotocol/serverInfo"
_VISION_EXTENSION = "me.xiaozhi/vision"
_MAX_SAFE_INT = (1 << 53) - 1
_DISCOVERY_TTL_MS = 60000
_MAX_TOOLS_LIST_BYTES = 8000

_JSONRPC_PARSE_ERROR = -32700
_JSONRPC_INVALID_REQUEST = -32600
_JSONRPC_METHOD_NOT_FOUND = -32601
_JSONRPC_INVALID_PARAMS = -32602
_JSONRPC_INTERNAL_ERROR = -32603
_MCP_MISSING_CAPABILITY = -32021
_MCP_UNSUPPORTED_VERSION = -32022


def _is_valid_request_id(request_id: Any) -> bool:
    if isinstance(request_id, str):
        return True
    if isinstance(request_id, int) and not isinstance(request_id, bool):
        return abs(request_id) <= _MAX_SAFE_INT
    return False


def _is_modern_request(method: str, params: Any) -> bool:
    if method == "server/discover":
        return True
    if not isinstance(params, dict):
        return False
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return False
    return any(
        isinstance(key, str) and key.startswith("io.modelcontextprotocol/")
        for key in meta
    )


def _is_valid_vision_url(url: Any) -> bool:
    if not isinstance(url, str):
        return False
    if url.startswith("https://"):
        scheme_len = 8
    elif url.startswith("http://"):
        scheme_len = 7
    else:
        return False
    if len(url) <= scheme_len or url[scheme_len] in ("/", "?", "#"):
        return False
    return not any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url)


class McpServer:
    """
    MCP服务器实现.

    由 ServiceContainer 创建，经 McpPlugin 注入。
    """

    def __init__(self, config=None):
        self.config = (
            config if config is not None
            else ConfigManager.from_dict({"MCP_PLUGINS": {"ENABLED": False}})
        )
        self.tools: list[McpTool] = []
        self._send_callback: Callable | None = None
        self._camera = None
        self._plugin_runtime = PluginRuntime(
            self.add_tools_atomic, self.remove_tools_by_names
        )
        self._common_tool_names: set[str] = set()

    def set_send_callback(self, callback: Callable | None):
        """
        设置发送消息的回调函数；传 None 表示解绑。
        """
        self._send_callback = callback

    def set_camera(self, camera) -> None:
        """注入摄像头（vision 配置 / take_photo 共用）."""
        self._camera = camera

    def get_camera(self):
        return self._camera

    def detach(self) -> None:
        """容器关闭时回收外挂和运行时依赖；内置工具保留。"""
        try:
            self._unload_external_plugins()
        finally:
            self._send_callback = None
            self._camera = None

    def add_tool(
        self, tool: McpTool | tuple[str, str, PropertyList, Callable]
    ):
        """
        添加工具.
        """
        if isinstance(tool, tuple):
            # 从参数创建McpTool
            name, description, properties, callback = tool
            tool = McpTool(name, description, properties, callback)

        self.add_tools_atomic([tool])

    def add_tools_atomic(self, tools: list[McpTool]) -> None:
        """整批校验成功后提交；冲突不改变现有工具列表。"""
        names = {tool.name for tool in self.tools}
        for tool in tools:
            if tool.name in names:
                raise ValueError(f"Tool name conflict: {tool.name}")
            names.add(tool.name)
        self.tools.extend(tools)
        for tool in tools:
            logger.info(f"Add tool: {tool.name}")

    def remove_tools_by_names(self, names: set[str] | list[str]) -> int:
        """按名称移除工具，返回移除数量."""
        name_set = set(names)
        if not name_set:
            return 0
        before = len(self.tools)
        self.tools = [t for t in self.tools if t.name not in name_set]
        return before - len(self.tools)

    @property
    def _plugin_tool_owner(self) -> dict[str, str]:
        """兼容诊断读取；归属仅由运行时安装记录生成。"""
        return self._plugin_runtime.tool_owner

    def unload_plugin(self, plugin_id: str) -> int:
        """卸载插件工具和 worker，零工具插件也使用同一路径。"""
        return self._plugin_runtime.unload(plugin_id)

    def _unload_external_plugins(self) -> None:
        self._plugin_runtime.unload_all()

    def reload_external_plugins(
        self, music_player=None, volume_controller=None
    ) -> list:
        """仅重载外挂：先卸掉已知外挂工具，再按配置扫描加载.

        注意：不会重新 register 内置工具；内置应已在 tools 中。
        """
        self._unload_external_plugins()

        from src.mcp.plugins.loader import load_mcp_plugins_from_config

        capabilities = {"config_readonly": self.config}
        if music_player is not None:
            capabilities["music_player"] = music_player

        return load_mcp_plugins_from_config(
            self.add_tool,
            config=self.config,
            capabilities=capabilities,
            runtime=self._plugin_runtime,
        )

    def register_builtin_tools(self, music_player=None, volume_controller=None):
        """
        添加通用工具（全部经 register_* 显式挂载）.

        music_player: 容器注入的 MusicPlayer；提供时注册音乐工具。
        volume_controller: 可选注入的 VolumeController；未提供时由 register 内创建。
        camera / screenshot 由 McpPlugin 在 setup 中单独 register。
        """
        # 先暂存新工具，注册失败时保留现有工具和外挂会话。
        common_tools: list[McpTool] = []
        if music_player is not None:
            from src.mcp.tools.music import register_music_tools

            register_music_tools(common_tools.append, music_player)

        from src.mcp.tools.app import register_app_tools
        from src.mcp.tools.volume import register_volume_tools
        from src.mcp.tools.weather import register_weather_tools

        register_volume_tools(common_tools.append, volume_controller)
        register_app_tools(common_tools.append)
        register_weather_tools(common_tools.append)

        preserved = [
            tool for tool in self.tools
            if tool.name not in self._common_tool_names
        ]
        names = {tool.name for tool in preserved}
        for tool in common_tools:
            if tool.name in names:
                raise ValueError(f"Tool name conflict: {tool.name}")
            names.add(tool.name)
        self.tools = common_tools + preserved
        self._common_tool_names = {tool.name for tool in common_tools}

    def add_common_tools(self, music_player=None, volume_controller=None):
        """兼容旧调用；新装配分别注册内置工具和加载外挂。"""
        self.register_builtin_tools(music_player, volume_controller)
        try:
            return self.reload_external_plugins(music_player, volume_controller)
        except Exception as e:
            logger.error(f"加载外挂 MCP 插件失败: {e}", exc_info=True)
            return []

    @staticmethod
    def _server_info() -> dict[str, str]:
        return {
            "name": SystemConstants.APP_NAME,
            "version": SystemConstants.APP_VERSION,
        }

    def _modern_meta(self) -> dict[str, Any]:
        return {_META_SERVER_INFO: self._server_info()}

    def _has_vision_tools(self) -> bool:
        return any(tool.requires_vision for tool in self._iter_enabled_tools())

    async def _validate_modern_meta(
        self, request_id: int | str, params: Any
    ) -> dict[str, Any] | None:
        """校验新版 2026-07-28 params._meta，失败直接发送错误响应并返回 None."""
        if not isinstance(params, dict):
            await self._reply_error(
                request_id, "Invalid params", code=_JSONRPC_INVALID_PARAMS
            )
            return None
        meta = params.get("_meta")
        if not isinstance(meta, dict):
            await self._reply_error(
                request_id, "Missing _meta", code=_JSONRPC_INVALID_PARAMS
            )
            return None

        version = meta.get(_META_PROTOCOL_VERSION)
        if not isinstance(version, str) or not version:
            await self._reply_error(
                request_id,
                f"Invalid or missing {_META_PROTOCOL_VERSION}",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None
        if version != MCP_VERSION_MODERN:
            await self._reply_error(
                request_id,
                "Unsupported protocol version",
                code=_MCP_UNSUPPORTED_VERSION,
                data={"supported": list(SUPPORTED_MCP_VERSIONS), "requested": version},
            )
            return None

        client_caps = meta.get(_META_CLIENT_CAPABILITIES)
        if not isinstance(client_caps, dict):
            await self._reply_error(
                request_id,
                f"Invalid or missing {_META_CLIENT_CAPABILITIES}",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None
        if "extensions" in client_caps and not isinstance(
            client_caps["extensions"], dict
        ):
            await self._reply_error(
                request_id,
                "Invalid MCP client capabilities extensions",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None

        if _META_CLIENT_INFO in meta:
            info = meta[_META_CLIENT_INFO]
            if (
                not isinstance(info, dict)
                or not isinstance(info.get("name"), str)
                or not isinstance(info.get("version"), str)
            ):
                await self._reply_error(
                    request_id,
                    f"Invalid {_META_CLIENT_INFO}",
                    code=_JSONRPC_INVALID_PARAMS,
                )
                return None

        return client_caps

    async def _extract_modern_vision(
        self, request_id: int | str, client_caps: dict[str, Any]
    ) -> tuple[str, str] | None:
        extensions = client_caps.get("extensions")
        if not isinstance(extensions, dict) or _VISION_EXTENSION not in extensions:
            await self._reply_error(
                request_id,
                "Missing required client capability",
                code=_MCP_MISSING_CAPABILITY,
                data={"requiredCapabilities": {"extensions": {_VISION_EXTENSION: {}}}},
            )
            return None

        vision = extensions[_VISION_EXTENSION]
        if not isinstance(vision, dict):
            await self._reply_error(
                request_id,
                "Invalid vision configuration",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None

        url = vision.get("url")
        if not _is_valid_vision_url(url):
            await self._reply_error(
                request_id,
                "Invalid vision url in client capability",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None

        token = vision.get("token", "")
        if token is None:
            token = ""
        elif not isinstance(token, str) or "\r" in token or "\n" in token:
            await self._reply_error(
                request_id,
                "Invalid vision token in client capability",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None

        return url, token

    async def _decode_request(
        self, message: str | dict[str, Any]
    ) -> tuple[int | str, str, dict[str, Any]] | None:
        """解码并校验 JSON-RPC 2.0 请求信封；通知或校验失败返回 None."""
        if isinstance(message, str):
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in MCP message: %s", e)
                await self._reply_error(None, "Parse error", code=_JSONRPC_PARSE_ERROR)
                return None
        else:
            data = message

        if not isinstance(data, dict):
            await self._reply_error(
                None, "Invalid Request", code=_JSONRPC_INVALID_REQUEST
            )
            return None

        logger.debug(
            "[MCP] 解析消息: method=%s, id=%r", data.get("method"), data.get("id")
        )

        has_id = "id" in data
        request_id: int | str | None = None
        if has_id:
            raw_id = data.get("id")
            if not _is_valid_request_id(raw_id):
                logger.error("Invalid request id: %r", raw_id)
                await self._reply_error(
                    None, "Invalid request id", code=_JSONRPC_INVALID_REQUEST
                )
                return None
            request_id = raw_id

        if data.get("jsonrpc") != "2.0":
            logger.error(f"Invalid JSONRPC version: {data.get('jsonrpc')}")
            if request_id is not None:
                await self._reply_error(
                    request_id,
                    "Invalid JSON-RPC version",
                    code=_JSONRPC_INVALID_REQUEST,
                )
            return None

        method = data.get("method")
        if not isinstance(method, str) or not method:
            logger.error("Missing method")
            if request_id is not None:
                await self._reply_error(
                    request_id, "Missing method", code=_JSONRPC_INVALID_REQUEST
                )
            return None

        if not has_id or method.startswith("notifications"):
            logger.info(f"[MCP] 忽略通知消息: {method}")
            return None

        params = data.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            await self._reply_error(
                request_id, "Invalid params", code=_JSONRPC_INVALID_PARAMS
            )
            return None
        if "_meta" in params and not isinstance(params["_meta"], dict):
            await self._reply_error(
                request_id,
                "Missing or invalid MCP request metadata",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return None

        assert request_id is not None
        return request_id, method, params

    async def _dispatch_method(
        self,
        request_id: int | str,
        method: str,
        params: dict[str, Any],
        *,
        modern: bool,
        client_caps: dict[str, Any] | None,
    ) -> None:
        if method == "server/discover":
            await self._handle_discover(request_id)
        elif method == "initialize" and not modern:
            await self._handle_initialize(request_id, params)
        elif method == "tools/list":
            await self._handle_tools_list(request_id, params, modern=modern)
        elif method == "tools/call":
            await self._handle_tool_call(
                request_id, params, modern=modern, client_caps=client_caps
            )
        else:
            logger.warning(f"Method not found: {method}")
            await self._reply_error(
                request_id,
                f"Method not found: {method}",
                code=_JSONRPC_METHOD_NOT_FOUND,
            )

    async def parse_message(self, message: str | dict[str, Any]):
        """解析 MCP 消息（独立按请求选择 2026-07-28 或 2024-11-05 处理器）."""
        request_id: int | str | None = None
        try:
            decoded = await self._decode_request(message)
            if decoded is None:
                return
            request_id, method, params = decoded

            modern = _is_modern_request(method, params)
            client_caps: dict[str, Any] | None = None
            if modern:
                client_caps = await self._validate_modern_meta(request_id, params)
                if client_caps is None:
                    return

            await self._dispatch_method(
                request_id, method, params, modern=modern, client_caps=client_caps
            )
        except Exception as e:
            logger.error(f"Error parsing MCP message: {e}", exc_info=True)
            if request_id is not None:
                await self._reply_error(request_id, str(e))

    async def _handle_discover(self, request_id: int | str) -> None:
        """处理新版 MCP 2026-07-28 server/discover 发现请求."""
        capabilities: dict[str, Any] = {"tools": {}}
        if self._has_vision_tools():
            capabilities["extensions"] = {_VISION_EXTENSION: {}}
        result = {
            "resultType": "complete",
            "supportedVersions": list(SUPPORTED_MCP_VERSIONS),
            "capabilities": capabilities,
            "ttlMs": _DISCOVERY_TTL_MS,
            "cacheScope": "private",
            "_meta": self._modern_meta(),
        }
        await self._reply_result(request_id, result)

    async def _handle_initialize(
        self, request_id: int | str, params: dict[str, Any]
    ):
        """处理旧版 2024-11-05 初始化请求."""
        capabilities = params.get("capabilities", {})
        if isinstance(capabilities, dict):
            await self._parse_capabilities(capabilities)

        result = {
            "protocolVersion": MCP_VERSION_LEGACY,
            "capabilities": {"tools": {}},
            "serverInfo": self._server_info(),
        }

        await self._reply_result(request_id, result)

    def _disabled_tool_names(self) -> set[str]:
        """从配置读取 MCP_TOOLS.DISABLED（黑名单）."""
        try:
            raw = self.config.get_config("MCP_TOOLS.DISABLED", []) or []
            return set(normalize_disabled(raw))
        except Exception as exc:
            logger.warning("读取 MCP_TOOLS.DISABLED 失败，回退空黑名单: %s", exc)
            return set()

    def _iter_enabled_tools(self):
        disabled = self._disabled_tool_names()
        for tool in self.tools:
            if tool.name not in disabled:
                yield tool

    def _build_tools_list_result(
        self,
        tools_json: list[dict[str, Any]],
        *,
        next_cursor: str | None = None,
        modern: bool = False,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"tools": tools_json}
        if next_cursor is not None:
            result["nextCursor"] = next_cursor
        if modern:
            result["resultType"] = "complete"
            result["ttlMs"] = _DISCOVERY_TTL_MS
            result["cacheScope"] = "private"
            result["_meta"] = self._modern_meta()
        return result

    async def _handle_tools_list(
        self,
        request_id: int | str,
        params: dict[str, Any],
        *,
        modern: bool = False,
    ):
        """处理工具列表请求（已按 MCP_TOOLS.DISABLED 过滤，支持双版本格式）."""
        cursor = params.get("cursor", "")
        if "withUserTools" in params and not isinstance(params["withUserTools"], bool):
            await self._reply_error(
                request_id,
                "Invalid withUserTools parameter",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return
        tools = list(self._iter_enabled_tools())
        if not isinstance(cursor, str):
            await self._reply_error(
                request_id,
                "Invalid tools/list cursor",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return
        start = 0
        if cursor:
            start = next((i for i, t in enumerate(tools) if t.name == cursor), -1)
            if start < 0:
                await self._reply_error(
                    request_id,
                    "Unknown tools/list cursor",
                    code=_JSONRPC_INVALID_PARAMS,
                )
                return

        result = self._build_tools_list_result([], modern=modern)
        for index in range(start, len(tools)):
            next_cursor = tools[index + 1].name if index + 1 < len(tools) else None
            candidate = self._build_tools_list_result(
                result["tools"] + [tools[index].to_json()],
                next_cursor=next_cursor,
                modern=modern,
            )
            payload = {"jsonrpc": "2.0", "id": request_id, "result": candidate}
            if len(json.dumps(payload).encode("utf-8")) > _MAX_TOOLS_LIST_BYTES:
                if not result["tools"]:
                    await self._reply_error(
                        request_id,
                        "Tool definition exceeds tools/list payload limit",
                    )
                    return
                break
            result = candidate
        await self._reply_result(request_id, result)

    async def _handle_tool_call(
        self,
        request_id: int | str,
        params: dict[str, Any],
        *,
        modern: bool = False,
        client_caps: dict[str, Any] | None = None,
    ):
        """处理工具调用请求（支持旧版 2024-11-05 与新版 2026-07-28）."""
        tool_name = params.get("name")
        if not isinstance(tool_name, str) or not tool_name:
            await self._reply_error(
                request_id, "Missing tool name", code=_JSONRPC_INVALID_PARAMS
            )
            return

        logger.info(f"[MCP] 尝试调用工具: {tool_name} (modern={modern})")

        if tool_name in self._disabled_tool_names():
            if modern:
                await self._reply_error(
                    request_id,
                    f"Tool disabled: {tool_name}",
                    code=_JSONRPC_INVALID_PARAMS,
                )
            else:
                await self._reply_error(request_id, f"Tool disabled: {tool_name}")
            return

        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            await self._reply_error(
                request_id,
                f"Unknown tool: {tool_name}",
                code=_JSONRPC_INVALID_PARAMS,
            )
            return

        arguments = params.get("arguments", {})
        if arguments is None:
            arguments = {}

        if not modern:
            try:
                result = await tool.call(arguments)
                logger.info(f"[MCP] 工具 {tool_name} 执行成功")
                await self._reply_result(request_id, json.loads(result))
            except Exception as e:
                logger.error(
                    f"[MCP] 工具 {tool_name} 执行失败: {e}", exc_info=True
                )
                await self._reply_error(request_id, str(e))
            return

        # 新版 2026-07-28：先校验视觉扩展与工具参数，再执行
        vision_ctx = nullcontext()
        if tool.requires_vision:
            vision = await self._extract_modern_vision(request_id, client_caps or {})
            if vision is None:
                return
            vision_ctx = vision_config_override(*vision)

        try:
            parsed_args = tool.properties.parse_arguments(arguments)
        except Exception as e:
            await self._reply_error(
                request_id, str(e), code=_JSONRPC_INVALID_PARAMS
            )
            return

        with vision_ctx:
            text, is_error = await tool.invoke_parsed(parsed_args)

        await self._reply_result(
            request_id,
            {
                "resultType": "complete",
                "content": [{"type": "text", "text": text}],
                "isError": is_error,
                "_meta": self._modern_meta(),
            },
        )

    async def _parse_capabilities(self, capabilities):
        """
        解析capabilities.
        """
        vision = capabilities.get("vision", {})
        if vision and isinstance(vision, dict):
            url = vision.get("url")
            token = vision.get("token")
            if url:
                camera = self._camera
                if camera is None:
                    from src.mcp.tools.camera import create_camera

                    camera = create_camera(config=self.config)
                    self._camera = camera
                camera.set_explain_url(url)
                if token:
                    camera.set_explain_token(token)
                logger.info(f"Vision service configured with URL: {url}")

    async def _reply_result(self, request_id: int | str, result: Any):
        """发送成功响应."""
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

        result_len = len(json.dumps(result))
        logger.info(
            f"[MCP] 发送成功响应: ID={request_id}, 结果长度={result_len}"
        )

        if self._send_callback:
            await self._send_callback(json.dumps(payload))
        else:
            logger.error("[MCP] 发送回调未设置!")

    async def _reply_error(
        self,
        request_id: int | str | None,
        message: str,
        *,
        code: int = _JSONRPC_INTERNAL_ERROR,
        data: Any = None,
    ):
        """发送错误响应."""
        error_obj: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            error_obj["data"] = data
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error_obj,
        }

        logger.error(
            "[MCP] 发送错误响应: ID=%r, code=%d, 错误=%s", request_id, code, message
        )

        if self._send_callback:
            await self._send_callback(json.dumps(payload))
