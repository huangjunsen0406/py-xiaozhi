"""外挂 MCP 插件目录加载（python-inprocess / python-subprocess + vendored lib）."""

from __future__ import annotations

import importlib
import importlib.util
import json
import platform
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.constants.system import SystemConstants
from src.logging import get_logger
from src.mcp.plugins.host import DEFAULT_ALLOW_GET, McpHost
from src.utils.resource_finder import get_user_data_dir

logger = get_logger()

HOST_PLUGIN_API_VERSION = 1
SUPPORTED_RUNTIMES = frozenset({"python-inprocess", "python-subprocess"})


def default_plugins_dir() -> Path:
    path = get_user_data_dir() / "mcp_plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_platform_tag() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        os_name = "macos"
    elif system == "windows":
        os_name = "windows"
    elif system == "linux":
        os_name = "linux"
    else:
        os_name = system
    if machine in ("x86_64", "amd64"):
        arch = "amd64" if os_name == "windows" else "x86_64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("i386", "i686", "x86"):
        arch = "x86"
    else:
        arch = machine
    return f"{os_name}-{arch}"


def current_python_abi() -> str:
    v = sys.version_info
    return f"cp{v.major}{v.minor}"


def parse_version(ver: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", ver or "0")
    return tuple(int(p) for p in parts) if parts else (0,)


def version_gte(current: str, minimum: str) -> bool:
    a, b = parse_version(current), parse_version(minimum)
    n = max(len(a), len(b))
    a = a + (0,) * (n - len(a))
    b = b + (0,) * (n - len(b))
    return a >= b


@dataclass
class LoadedPlugin:
    plugin_id: str
    path: Path
    tool_names: list[str] = field(default_factory=list)
    error: str | None = None
    runtime: str = "python-inprocess"


class PluginLoader:
    def __init__(
        self,
        host: McpHost,
        *,
        plugins_dir: Path | None = None,
        enabled_ids: list[str] | None = None,
        disabled_ids: list[str] | None = None,
        enforce_prefix: bool = False,
        require_python_abi: bool = False,
        require_platforms: bool = False,
        tool_owner: dict[str, str] | None = None,
        raw_add_tool=None,
    ) -> None:
        self._base_host = host
        self.plugins_dir = Path(plugins_dir) if plugins_dir else default_plugins_dir()
        self.enabled_ids = list(enabled_ids or [])
        self.disabled_ids = set(disabled_ids or [])
        self.enforce_prefix = enforce_prefix
        self.require_python_abi = require_python_abi
        self.require_platforms = require_platforms
        self.tool_owner = tool_owner
        self._raw_add_tool = raw_add_tool or host._add_tool
        self.loaded: list[LoadedPlugin] = []
        self._platform = current_platform_tag()
        self._abi = current_python_abi()
        self._host_version = getattr(SystemConstants, "APP_VERSION", "0.0.0")

    def load_all(self) -> list[LoadedPlugin]:
        self.loaded.clear()
        root = self.plugins_dir
        if not root.is_dir():
            logger.info("[MCP插件] 目录不存在，跳过: %s", root)
            return self.loaded
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if child.name.startswith(".") or child.name.startswith("_"):
                continue
            if child.is_dir():
                self._load_package_dir(child)
            elif child.suffix == ".py" and child.is_file():
                self._load_simple_py(child)
        ok = sum(1 for x in self.loaded if not x.error)
        fail = sum(1 for x in self.loaded if x.error)
        logger.info(
            "[MCP插件] 加载完成: 成功 %d, 跳过/失败 %d, 目录 %s",
            ok, fail, root,
        )
        return self.loaded

    def _is_enabled(self, plugin_id: str, enabled_by_default: bool) -> bool:
        if plugin_id in self.disabled_ids:
            return False
        if self.enabled_ids:
            return plugin_id in self.enabled_ids
        return enabled_by_default

    def _load_package_dir(self, path: Path) -> None:
        manifest_path = path / "manifest.json"
        if not manifest_path.is_file():
            if (path / "plugin.py").is_file():
                self._load_package_dir_without_manifest(path)
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            self._record(path.name, path, error=f"manifest 无效: {e}")
            return
        plugin_id = str(manifest.get("id") or path.name)
        try:
            self._validate_and_import_package(path, manifest, plugin_id)
        except Exception as e:
            logger.error("[MCP插件] 加载失败 %s: %s", plugin_id, e, exc_info=True)
            self._record(plugin_id, path, error=str(e))

    def _load_package_dir_without_manifest(self, path: Path) -> None:
        plugin_id = path.name
        manifest = {
            "id": plugin_id,
            "entry": "plugin:register",
            "runtime": "python-inprocess",
            "enabled_by_default": True,
        }
        try:
            self._validate_and_import_package(path, manifest, plugin_id)
        except Exception as e:
            logger.error("[MCP插件] 加载失败 %s: %s", plugin_id, e, exc_info=True)
            self._record(plugin_id, path, error=str(e))

    def _check_manifest_compat(self, manifest: dict[str, Any]) -> None:
        api = manifest.get("api_version", 1)
        try:
            api_i = int(api)
        except (TypeError, ValueError) as e:
            raise RuntimeError(f"api_version 无效: {api}") from e
        if api_i > HOST_PLUGIN_API_VERSION:
            raise RuntimeError(
                f"插件 api_version={api_i} 高于宿主 {HOST_PLUGIN_API_VERSION}"
            )
        if api_i < 1:
            raise RuntimeError(f"api_version 过低: {api_i}")
        min_host = manifest.get("min_host_version")
        if min_host and not version_gte(str(self._host_version), str(min_host)):
            raise RuntimeError(
                f"宿主版本 {self._host_version} < 插件要求 min_host_version={min_host}"
            )
        platforms = manifest.get("platforms")
        if platforms is None and self.require_platforms:
            raise RuntimeError("manifest 缺少 platforms（已开启强制校验）")
        if platforms is not None:
            plat_set = set(platforms)
            aliases = {self._platform}
            if "x86_64" in self._platform:
                aliases.add(self._platform.replace("x86_64", "amd64"))
            if "amd64" in self._platform:
                aliases.add(self._platform.replace("amd64", "x86_64"))
            if not aliases & plat_set:
                raise RuntimeError(
                    f"平台不匹配: host={self._platform}, plugin={platforms}"
                )
        abi = manifest.get("python_abi")
        if abi is None and self.require_python_abi:
            raise RuntimeError("manifest 缺少 python_abi（已开启强制校验）")
        if abi and abi != self._abi:
            raise RuntimeError(
                f"Python ABI 不匹配: host={self._abi}, plugin={abi}"
            )

    def _validate_and_import_package(
        self, path: Path, manifest: dict[str, Any], plugin_id: str
    ) -> None:
        if not self._is_enabled(
            plugin_id, bool(manifest.get("enabled_by_default", True))
        ):
            self._record(plugin_id, path, error="disabled")
            logger.info("[MCP插件] 已禁用，跳过: %s", plugin_id)
            return

        runtime = str(manifest.get("runtime") or "python-inprocess")
        if runtime not in SUPPORTED_RUNTIMES:
            raise RuntimeError(
                f"不支持的 runtime: {runtime}（支持: {sorted(SUPPORTED_RUNTIMES)}）"
            )
        self._check_manifest_compat(manifest)
        entry = str(manifest.get("entry") or "plugin:register")
        if ":" not in entry:
            raise RuntimeError(f"entry 须为 module:attr，得到: {entry}")
        prefix = manifest.get("tool_name_prefix")

        if runtime == "python-subprocess":
            self._load_subprocess_package(
                path, plugin_id, entry=entry, prefix=prefix, manifest=manifest
            )
            return
        self._load_inprocess_package(
            path, plugin_id, entry=entry, prefix=prefix, manifest=manifest
        )

    def _load_inprocess_package(
        self, path: Path, plugin_id: str, *, entry: str, prefix: Any, manifest: dict[str, Any]
    ) -> None:
        module_part, attr_part = entry.split(":", 1)
        host = self._base_host.bind_plugin(plugin_id)
        extra_paths: list[Path] = [path]
        lib = path / "lib"
        if lib.is_dir():
            extra_paths.append(lib)
        native = path / "native" / self._platform
        if not native.is_dir():
            alt = path / "native" / self._platform.replace("x86_64", "amd64")
            if alt.is_dir():
                native = alt
            else:
                alt2 = path / "native" / self._platform.replace("amd64", "x86_64")
                if alt2.is_dir():
                    native = alt2
        if native.is_dir():
            extra_paths.append(native)
        try:
            for p in reversed(extra_paths):
                sp = str(p.resolve())
                if sp not in sys.path:
                    sys.path.insert(0, sp)
            unique_name = f"mcp_plugin_{_safe_mod_name(plugin_id)}_{module_part}"
            mod = _import_plugin_module(path, module_part, unique_name)
            register_fn = getattr(mod, attr_part, None)
            if not callable(register_fn):
                raise RuntimeError(
                    f"入口 {entry} 不可调用（模块 {module_part} 无属性 {attr_part}）"
                )
            register_fn(host)
            names = host.registered_tool_names
            if prefix:
                bad = [n for n in names if not n.startswith(str(prefix))]
                if bad:
                    msg = f"工具名未使用前缀 {prefix}: {bad}"
                    if self.enforce_prefix:
                        raise RuntimeError(msg)
                    logger.warning("[MCP插件:%s] %s", plugin_id, msg)
            if self.tool_owner is not None:
                for n in names:
                    self.tool_owner[n] = plugin_id
            self._record(
                plugin_id, path, tool_names=names, runtime="python-inprocess"
            )
            logger.info(
                "[MCP插件] 已加载 %s (%d 工具, inprocess) from %s",
                plugin_id, len(names), path,
            )
        except Exception:
            raise

    def _load_subprocess_package(
        self, path: Path, plugin_id: str, *, entry: str, prefix: Any, manifest: dict[str, Any]
    ) -> None:
        from src.mcp.plugins.subprocess_runtime import (
            PluginSubprocessSession,
            register_subprocess_plugin_tools,
            track_session,
        )

        allow = list(self._base_host._allow_get)
        caps = dict(self._base_host._capabilities)
        timeout = float(manifest.get("call_timeout") or 60)
        session = PluginSubprocessSession(
            plugin_id=plugin_id,
            plugin_root=path,
            entry=entry,
            platform_tag=self._platform,
            allow_get=allow,
            capabilities=caps,
            call_timeout=timeout,
        )
        try:
            session.start_and_bootstrap()
            names = register_subprocess_plugin_tools(
                self._raw_add_tool,
                session=session,
                tool_owner=self.tool_owner,
                enforce_prefix=self.enforce_prefix,
                prefix=str(prefix) if prefix else None,
            )
            track_session(plugin_id, session)
            self._record(
                plugin_id, path, tool_names=names, runtime="python-subprocess"
            )
            logger.info(
                "[MCP插件] 已加载 %s (%d 工具, subprocess) from %s",
                plugin_id, len(names), path,
            )
        except Exception:
            session.terminate()
            raise

    def _load_simple_py(self, path: Path) -> None:
        plugin_id = path.stem
        if not self._is_enabled(plugin_id, True):
            self._record(plugin_id, path, error="disabled")
            return
        host = self._base_host.bind_plugin(plugin_id)
        try:
            unique_name = f"mcp_plugin_{_safe_mod_name(plugin_id)}"
            spec = importlib.util.spec_from_file_location(unique_name, path)
            if spec is None or spec.loader is None:
                raise RuntimeError("无法创建模块 spec")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = mod
            spec.loader.exec_module(mod)
            register_fn = getattr(mod, "register", None)
            if not callable(register_fn):
                raise RuntimeError("单文件插件须定义 register(host)")
            register_fn(host)
            names = host.registered_tool_names
            if self.tool_owner is not None:
                for n in names:
                    self.tool_owner[n] = plugin_id
            self._record(
                plugin_id, path, tool_names=names, runtime="python-inprocess"
            )
            logger.info(
                "[MCP插件] 已加载单文件 %s (%d 工具)", plugin_id, len(names)
            )
        except Exception as e:
            logger.error(
                "[MCP插件] 单文件加载失败 %s: %s", plugin_id, e, exc_info=True
            )
            self._record(plugin_id, path, error=str(e))

    def _record(
        self,
        plugin_id: str,
        path: Path,
        *,
        tool_names: list[str] | None = None,
        error: str | None = None,
        runtime: str = "python-inprocess",
    ) -> None:
        self.loaded.append(
            LoadedPlugin(
                plugin_id=plugin_id,
                path=path,
                tool_names=list(tool_names or []),
                error=error,
                runtime=runtime,
            )
        )


def _safe_mod_name(plugin_id: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in plugin_id)


def _import_plugin_module(plugin_root: Path, module_part: str, unique_name: str):
    py_file = plugin_root / f"{module_part.replace('.', '/')}.py"
    pkg_init = plugin_root / module_part.split(".")[0] / "__init__.py"
    if py_file.is_file():
        spec = importlib.util.spec_from_file_location(unique_name, py_file)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"无法加载 {py_file}")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[unique_name] = mod
        sys.modules[module_part] = mod
        spec.loader.exec_module(mod)
        return mod
    if (plugin_root / module_part).is_dir() and pkg_init.is_file():
        return importlib.import_module(module_part)
    return importlib.import_module(module_part)


def load_mcp_plugins_from_config(
    add_tool,
    *,
    config=None,
    capabilities: dict | None = None,
    tool_owner: dict[str, str] | None = None,
) -> list[LoadedPlugin]:
    if config is None:
        try:
            from src.utils.config_manager import get_config
            config = get_config()
        except Exception:
            logger.debug("[MCP插件] 无配置，使用默认目录加载")
            config = None

    def _get(path: str, default=None):
        if config is None:
            return default
        return config.get_config(path, default)

    if not _get("MCP_PLUGINS.ENABLED", True):
        logger.info("[MCP插件] MCP_PLUGINS.ENABLED=false，跳过外挂")
        return []

    dir_cfg = _get("MCP_PLUGINS.DIR", None)
    plugins_dir = Path(dir_cfg) if dir_cfg else default_plugins_dir()
    allow = _get("MCP_PLUGINS.ALLOW_HOST_GET", list(DEFAULT_ALLOW_GET))
    if not isinstance(allow, list):
        allow = list(DEFAULT_ALLOW_GET)
    enabled_ids = _get("MCP_PLUGINS.ENABLED_IDS", []) or []
    disabled_ids = _get("MCP_PLUGINS.DISABLED_IDS", []) or []
    enforce_prefix = bool(_get("MCP_PLUGINS.ENFORCE_PREFIX", False))
    require_abi = bool(_get("MCP_PLUGINS.REQUIRE_PYTHON_ABI", False))
    require_plat = bool(_get("MCP_PLUGINS.REQUIRE_PLATFORMS", False))

    host = McpHost(
        add_tool,
        capabilities=capabilities or {},
        allow_get=allow,
    )
    loader = PluginLoader(
        host,
        plugins_dir=plugins_dir,
        enabled_ids=list(enabled_ids),
        disabled_ids=list(disabled_ids),
        enforce_prefix=enforce_prefix,
        require_python_abi=require_abi,
        require_platforms=require_plat,
        tool_owner=tool_owner,
        raw_add_tool=add_tool,
    )
    results = loader.load_all()
    if tool_owner is not None:
        for item in results:
            if item.error:
                continue
            for name in item.tool_names:
                tool_owner[name] = item.plugin_id
    return results
