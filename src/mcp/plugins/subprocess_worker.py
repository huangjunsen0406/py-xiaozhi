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
import sys
import traceback
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any


def _log(msg: str) -> None:
    sys.stderr.write(f"[mcp-plugin-worker] {msg}\n")
    sys.stderr.flush()


class _WorkerHost:
    """子进程内给 register(host) 用的最小 Host（与 McpHost 表面兼容）."""

    def __init__(
        self,
        *,
        plugin_id: str,
        capabilities: dict[str, Any],
        allow_get: Sequence[str],
    ) -> None:
        self._plugin_id = plugin_id
        self._capabilities = dict(capabilities or {})
        self._allow_get = frozenset(allow_get or [])
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
        return self._capabilities.get(name)

    def add_tool(self, tool: Any) -> None:
        """接受 McpTool 或具备 name/description/properties/callback 的对象."""
        name = tool.name
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
        self._tools.append(
            {"name": name, "description": desc, "properties": prop_defs}
        )
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

            self.add_tool(
                McpTool(name, description, _to_property_list(props), func)
            )
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
        native = alt if alt.is_dir() else (
            plugin_root / "native" / platform_tag.replace("amd64", "x86_64")
        )
    if native.is_dir():
        paths.append(str(native.resolve()))
    for p in reversed(paths):
        if p not in sys.path:
            sys.path.insert(0, p)


def _read_msg() -> dict[str, Any] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return _read_msg()
    return json.loads(line)


def _write_msg(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main() -> int:
    host: _WorkerHost | None = None
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

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
                allow_get = params.get("allow_get") or ["config_readonly", "logger"]
                capabilities = params.get("capabilities") or {}
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
                )
                register_fn(host)
                _write_msg(
                    {"id": req_id, "result": {"tools": host.export_tools()}}
                )

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
