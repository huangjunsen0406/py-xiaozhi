#!/usr/bin/env python3
"""校验外挂 MCP 插件包结构（不启动完整应用）."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def check_plugin(path: Path, *, strict: bool = False) -> list[str]:
    """返回错误列表；空 = 通过."""
    errors: list[str] = []
    if not path.is_dir():
        return [f"不是目录: {path}"]

    manifest_path = path / "manifest.json"
    plugin_py = path / "plugin.py"
    if not manifest_path.is_file() and not plugin_py.is_file():
        errors.append("缺少 manifest.json 且无 plugin.py")
        return errors

    manifest: dict = {}
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"manifest.json 无法解析: {e}")
            return errors
    else:
        if strict:
            errors.append("严格模式要求 manifest.json")
        manifest = {"id": path.name, "entry": "plugin:register"}

    pid = manifest.get("id") or path.name
    if not pid:
        errors.append("manifest.id 为空")

    entry = str(manifest.get("entry") or "plugin:register")
    if ":" not in entry:
        errors.append(f"entry 须为 module:attr，得到: {entry}")
    else:
        mod, _attr = entry.split(":", 1)
        py = path / f"{mod.replace('.', '/')}.py"
        if not py.is_file() and not (path / mod).is_dir():
            errors.append(f"找不到入口模块文件: {py}")

    runtime = manifest.get("runtime", "python-inprocess")
    if runtime != "python-inprocess":
        errors.append(f"当前仅支持 runtime=python-inprocess，得到: {runtime}")

    if strict:
        if "api_version" not in manifest:
            errors.append("严格模式要求 api_version")
        if "python_abi" not in manifest:
            errors.append("严格模式要求 python_abi")
        if "platforms" not in manifest:
            errors.append("严格模式要求 platforms")
        if "tool_name_prefix" not in manifest:
            errors.append("严格模式要求 tool_name_prefix")

    # lib 可选；若存在应是目录
    lib = path / "lib"
    if lib.exists() and not lib.is_dir():
        errors.append("lib 存在但不是目录")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="检查 MCP 外挂插件包（manifest + 入口 + 可选 lib）"
    )
    parser.add_argument(
        "path",
        type=Path,
        help="插件目录路径，如 mcp_plugins/com.example.hello",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="要求 api_version / python_abi / platforms / tool_name_prefix",
    )
    args = parser.parse_args(argv)
    path = args.path.expanduser().resolve()
    errs = check_plugin(path, strict=args.strict)
    if errs:
        print(f"FAIL {path}")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"OK {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
