"""外挂插件子进程 worker：与宿主通过 stdin/stdout 行分隔 JSON 通信.

协议（每行一个 JSON 对象）::

    → {"id":1,"method":"bootstrap","params":{...}}
    ← {"id":1,"result":{"tools":[{"name","description","properties":[...]}]}}

    → {"id":2,"method":"call","params":{"name":"...","arguments":{...}}}
    ← {"id":2,"result":{"value": ...}}  # value 为工具原始返回（bool/int/str 等）
    ← {"id":2,"error":{"message":"..."}}

    → {"id":3,"method":"shutdown","params":{}}
    ← {"id":3,"result":{"ok":true}}

capabilities：仅支持只读快照（config_readonly 字典）；logger 在子进程本地创建。
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import json
import os
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

_PROTOCOL_STDOUT = sys.stdout


def _log(msg: str) -> None:
    sys.stderr.write(f"[mcp-plugin-worker] {msg}\n")
    sys.stderr.flush()


class _RemoteMediaPlayerProxy:
    """子进程内代理宿主 media_player 能力（与 MediaPlayerFacade API 100% 一致）."""

    def __init__(self, rpc_call: Callable[[str, str, dict[str, Any]], Any]) -> None:
        self._rpc_call = rpc_call

    async def play_url(
        self,
        url: str,
        *,
        title: str = "",
        start_position: float = 0.0,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._rpc_call(
            "media_player",
            "play_url",
            {
                "url": url,
                "title": title,
                "start_position": start_position,
                "headers": headers,
            },
        )

    async def pause(self) -> dict[str, Any]:
        return self._rpc_call("media_player", "pause", {})

    async def resume(self) -> dict[str, Any]:
        return self._rpc_call("media_player", "resume", {})

    async def stop(self) -> dict[str, Any]:
        return self._rpc_call("media_player", "stop", {})

    async def seek(
        self,
        *,
        position: float | None = None,
        percent: float | None = None,
    ) -> dict[str, Any]:
        return self._rpc_call(
            "media_player",
            "seek",
            {"position": position, "percent": percent},
        )

    async def get_status(self) -> dict[str, Any]:
        return self._rpc_call("media_player", "get_status", {})

    async def set_subtitle(self, text: str) -> dict[str, Any]:
        return self._rpc_call("media_player", "set_subtitle", {"text": text})


class _WorkerHost:
    """子进程内给 register(host) 用的最小 Host（与 McpHost 表面兼容）."""

    def __init__(
        self,
        *,
        plugin_id: str,
        capabilities: dict[str, Any],
        allow_get: Sequence[str],
        remote_caps: Sequence[str] = (),
        rpc_call: Callable[[str, str, dict[str, Any]], Any] | None = None,
    ) -> None:
        self._plugin_id = plugin_id
        self._capabilities = dict(capabilities or {})
        self._allow_get = frozenset(allow_get or [])
        self._remote_caps = frozenset(remote_caps or [])
        self._rpc_call = rpc_call
        self._tools: list[dict[str, Any]] = []
        self._callbacks: dict[str, Callable] = {}

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def registered_tool_names(self) -> list[str]:
        return list(self._callbacks.keys())

    def get(self, name: str) -> Any:
        if name not in self._allow_get:
            return None
        if name == "logger":
            import logging

            return logging.getLogger(f"mcp_plugin.{self._plugin_id}")
        if name == "media_player":
            if "media_player" in self._remote_caps and self._rpc_call is not None:
                return _RemoteMediaPlayerProxy(self._rpc_call)
            return None
        if name == "data_dir":
            if "data_dir" in self._capabilities and self._capabilities["data_dir"]:
                return Path(str(self._capabilities["data_dir"]))
            if "data_dir" in self._remote_caps and self._rpc_call is not None:
                resolved = self._rpc_call("data_dir", "get", {})
                if resolved:
                    self._capabilities["data_dir"] = str(resolved)
                    return Path(str(resolved))
            return None
        value = self._capabilities.get(name)
        if name == "config_readonly" and value is not None:
            from src.mcp.plugins.host import ReadOnlyConfig

            return ReadOnlyConfig(value)
        return value

    def add_tool(self, tool: Any) -> None:
        """接受 McpTool 或具备 name/description/properties/callback 的对象."""
        name = tool.name
        if name in self._callbacks:
            raise ValueError(f"Tool name conflict: {name}")
        desc = getattr(tool, "description", "") or ""
        props_obj = getattr(tool, "properties", None)
        callback = getattr(tool, "callback", None)
        prop_defs: list[dict[str, Any]] = []
        if props_obj is not None and getattr(props_obj, "properties", None):
            for p in props_obj.properties:
                item: dict[str, Any] = {
                    "name": p.name,
                    "type": p.type.value if hasattr(p.type, "value") else str(p.type),
                }
                if getattr(p, "default_value", None) is not None:
                    item["default"] = p.default_value
                if getattr(p, "min_value", None) is not None:
                    item["min"] = p.min_value
                if getattr(p, "max_value", None) is not None:
                    item["max"] = p.max_value
                prop_defs.append(item)
        self._tools.append({"name": name, "description": desc, "properties": prop_defs})
        if callback is not None:
            self._callbacks[name] = callback

    def tool(
        self,
        name: str,
        description: str,
        props: Sequence[Any] | None = None,
    ):
        def decorator(func: Callable):
            # 延迟导入 tooling，路径已在 bootstrap 里设好
            from src.mcp.plugins.host import _to_property_list
            from src.mcp.tooling import McpTool

            self.add_tool(McpTool(name, description, _to_property_list(props), func))
            return func

        return decorator

    def export_tools(self) -> list[dict[str, Any]]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None) -> Any:
        if name not in self._callbacks:
            raise KeyError(f"Unknown tool in worker: {name}")
        cb = self._callbacks[name]
        args = arguments or {}
        if asyncio.iscoroutinefunction(cb):
            return await cb(args)
        return cb(args)


def _import_entry(plugin_root: Path, module_part: str, attr_part: str):
    unique = f"mcp_sub_{plugin_root.name}_{module_part}".replace(".", "_")
    py_file = plugin_root / f"{module_part.replace('.', '/')}.py"
    if py_file.is_file():
        spec = importlib.util.spec_from_file_location(unique, py_file)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载 {py_file}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique] = mod
        spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(module_part)
    fn = getattr(mod, attr_part, None)
    if not callable(fn):
        raise RuntimeError(f"入口 {module_part}:{attr_part} 不可调用")
    return fn


def _setup_sys_path(plugin_root: Path, platform_tag: str) -> None:
    paths = [str(plugin_root.resolve())]
    lib = plugin_root / "lib"
    if lib.is_dir():
        paths.append(str(lib.resolve()))
    native = plugin_root / "native" / platform_tag
    if not native.is_dir():
        alt = plugin_root / "native" / platform_tag.replace("x86_64", "amd64")
        native = (
            alt
            if alt.is_dir()
            else (plugin_root / "native" / platform_tag.replace("amd64", "x86_64"))
        )
    if native.is_dir():
        paths.append(str(native.resolve()))
    for p in reversed(paths):
        if p not in sys.path:
            sys.path.insert(0, p)


def _read_msg() -> dict[str, Any] | None:
    while True:
        line = sys.stdin.readline()
        if not line:
            return None
        line = line.strip()
        if line:
            return json.loads(line)


def _write_msg(obj: dict[str, Any]) -> None:
    _PROTOCOL_STDOUT.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _PROTOCOL_STDOUT.flush()


def _restore_standard_streams() -> None:
    for name, fd, mode in (("stdin", 0, "r"), ("stdout", 1, "w"), ("stderr", 2, "w")):
        if getattr(sys, name) is not None:
            continue
        if sys.platform == "win32":
            import ctypes
            import msvcrt

            get_handle = ctypes.windll.kernel32.GetStdHandle
            get_handle.argtypes = [ctypes.c_ulong]
            get_handle.restype = ctypes.c_void_p
            handle = get_handle(-10 - fd)
            if handle in (None, ctypes.c_void_p(-1).value):
                raise RuntimeError(f"worker 缺少继承的 {name} 管道")
            flags = os.O_RDONLY if fd == 0 else os.O_WRONLY
            inherited_fd = msvcrt.open_osfhandle(handle, flags)
            if inherited_fd != fd:
                os.dup2(inherited_fd, fd)
                os.close(inherited_fd)
        stream = os.fdopen(
            fd, mode, encoding="utf-8", errors="replace", buffering=1, closefd=False
        )
        setattr(sys, name, stream)
        if getattr(sys, f"__{name}__") is None:
            setattr(sys, f"__{name}__", stream)


def main() -> int:
    global _PROTOCOL_STDOUT
    _restore_standard_streams()
    # 独立协议 fd；Python print、os.write(1, ...) 和原生库输出均送往 stderr。
    _PROTOCOL_STDOUT = os.fdopen(
        os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1
    )
    sys.stdout.flush()
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    host: _WorkerHost | None = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    host_call_seq = 0

    def _host_rpc(cap: str, action: str, kwargs: dict[str, Any]) -> Any:
        nonlocal host_call_seq
        host_call_seq += 1
        call_id = host_call_seq
        _write_msg(
            {
                "id": call_id,
                "method": "host_call",
                "params": {"cap": cap, "action": action, "kwargs": kwargs},
            }
        )
        reply = _read_msg()
        if reply is None:
            raise RuntimeError("宿主连接已断开")
        if reply.get("type") != "host_response" or reply.get("id") != call_id:
            raise RuntimeError(f"宿主响应异常: {reply!r}")
        if reply.get("error"):
            err = reply["error"]
            raise RuntimeError(
                err.get("message") if isinstance(err, dict) else str(err)
            )
        return reply.get("result")

    while True:
        try:
            msg = _read_msg()
        except Exception as e:
            _log(f"读消息失败: {e}")
            return 1
        if msg is None:
            break

        req_id = msg.get("id")
        method = msg.get("method")
        params = msg.get("params") or {}

        try:
            if method == "bootstrap":
                plugin_root = Path(params["plugin_root"])
                plugin_id = str(params.get("plugin_id") or plugin_root.name)
                entry = str(params.get("entry") or "plugin:register")
                platform_tag = str(params.get("platform_tag") or "")
                allow_get = params.get(
                    "allow_get", ["config_readonly", "logger", "data_dir"]
                )
                capabilities = params.get("capabilities") or {}
                remote_caps = params.get("remote_caps") or []
                # 宿主工程根（含 src/）供 import src.mcp.*
                app_root = params.get("app_root")
                if app_root and app_root not in sys.path:
                    sys.path.insert(0, app_root)

                _setup_sys_path(plugin_root, platform_tag)
                if ":" not in entry:
                    raise RuntimeError(f"entry 无效: {entry}")
                module_part, attr_part = entry.split(":", 1)
                register_fn = _import_entry(plugin_root, module_part, attr_part)

                host = _WorkerHost(
                    plugin_id=plugin_id,
                    capabilities=capabilities,
                    allow_get=allow_get,
                    remote_caps=remote_caps,
                    rpc_call=_host_rpc,
                )
                register_fn(host)
                _write_msg({"id": req_id, "result": {"tools": host.export_tools()}})

            elif method == "call":
                if host is None:
                    raise RuntimeError("worker 未 bootstrap")
                name = params.get("name")
                arguments = params.get("arguments") or {}
                value = loop.run_until_complete(host.call_tool(name, arguments))
                # 保证 JSON 可序列化
                if isinstance(value, (bool, int, float, str)) or value is None:
                    out_val = value
                else:
                    out_val = str(value)
                _write_msg({"id": req_id, "result": {"value": out_val}})

            elif method == "shutdown":
                _write_msg({"id": req_id, "result": {"ok": True}})
                break

            else:
                raise RuntimeError(f"未知 method: {method}")

        except Exception as e:
            _log(traceback.format_exc())
            _write_msg(
                {
                    "id": req_id,
                    "error": {"message": str(e)},
                }
            )

    loop.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
