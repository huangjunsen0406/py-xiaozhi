#!/usr/bin/env python3
"""Compile the lightweight native system_loopback library for the current host.

Zero third-party dependencies:
  - macOS:   Apple clang + CoreAudio / Foundation / AudioToolbox (-mmacosx-version-min=11.0)
  - Windows: MSVC cl.exe (or clang-cl) + Windows SDK ole32 / avrt / uuid
  - Linux:   gcc / clang + libdl / pthread (loads libpulse.so.0 via dlopen at runtime)

Usage:
    python scripts/build_system_loopback.py
    python scripts/build_system_loopback.py --arch arm64
    python scripts/build_system_loopback.py --arch all   # macOS: builds both arm64 & x64
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIB_ROOT = ROOT / "libs" / "system_loopback"
NATIVE_DIR = LIB_ROOT / "native"


def _host_arch() -> str:
    m = platform.machine().lower()
    if m in ("arm64", "aarch64"):
        return "arm64"
    if m in ("x86_64", "amd64"):
        return "x64"
    return m


def _run(cmd: list[str], cwd: Path | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def build_macos(arch: str) -> Path:
    clang = shutil.which("clang")
    if not clang:
        raise RuntimeError("clang not found (install Xcode Command Line Tools)")
    clang_arch = "arm64" if arch == "arm64" else "x86_64"
    out_dir = LIB_ROOT / "macos" / arch
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "libsystem_loopback.dylib"

    _run(
        [
            clang,
            "-shared",
            "-O2",
            "-Wall",
            "-Wextra",
            "-fobjc-arc",
            "-fvisibility=hidden",
            "-arch",
            clang_arch,
            "-mmacosx-version-min=11.0",
            f"-I{NATIVE_DIR}",
            str(NATIVE_DIR / "macos_tap.m"),
            "-framework",
            "CoreAudio",
            "-framework",
            "Foundation",
            "-framework",
            "AudioToolbox",
            "-install_name",
            "@rpath/libsystem_loopback.dylib",
            "-o",
            str(out_path),
        ]
    )
    return out_path


def build_linux(arch: str) -> Path:
    cc = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    if not cc:
        raise RuntimeError("gcc/clang not found")
    out_dir = LIB_ROOT / "linux" / arch
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "libsystem_loopback.so"

    _run(
        [
            cc,
            "-shared",
            "-fPIC",
            "-O2",
            "-Wall",
            "-Wextra",
            "-fvisibility=hidden",
            f"-I{NATIVE_DIR}",
            str(NATIVE_DIR / "linux_pulse.c"),
            "-ldl",
            "-lpthread",
            "-o",
            str(out_path),
        ]
    )
    return out_path


def build_windows(arch: str) -> Path:
    out_dir = LIB_ROOT / "windows" / arch
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "system_loopback.dll"
    src = NATIVE_DIR / "windows_wasapi.cpp"

    cl = shutil.which("cl") or shutil.which("cl.exe")
    if cl:
        obj_path = out_dir / "windows_wasapi.obj"
        _run(
            [
                cl,
                "/nologo",
                "/LD",
                "/O2",
                "/EHsc",
                "/W3",
                "/std:c++17",
                f"/I{NATIVE_DIR}",
                str(src),
                f"/Fo{obj_path}",
                f"/Fe{out_path}",
                "ole32.lib",
                "avrt.lib",
                "uuid.lib",
            ],
            cwd=out_dir,
        )
        for ext in (".obj", ".exp", ".lib"):
            junk = out_dir / f"system_loopback{ext}"
            if junk.exists():
                junk.unlink()
        if obj_path.exists():
            obj_path.unlink()
        return out_path

    gxx = shutil.which("g++") or shutil.which("clang++")
    if gxx:
        _run(
            [
                gxx,
                "-shared",
                "-O2",
                "-std=c++17",
                f"-I{NATIVE_DIR}",
                str(src),
                "-lole32",
                "-lavrt",
                "-luuid",
                "-o",
                str(out_path),
            ]
        )
        return out_path

    raise RuntimeError(
        "No Windows C++ compiler found in PATH (run from Developer Command Prompt / MSVC)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arch",
        default=_host_arch(),
        help="Target arch: arm64, x64, or 'all' (macOS builds both arm64 and x64)",
    )
    args = parser.parse_args()

    system = platform.system().lower()
    if system == "darwin":
        arches = ["arm64", "x64"] if args.arch == "all" else [args.arch]
        built = [build_macos(a) for a in arches]
    elif system == "linux":
        built = [build_linux(args.arch)]
    elif system == "windows":
        built = [build_windows(args.arch)]
    else:
        raise RuntimeError(f"Unsupported platform: {system}")

    for path in built:
        print(f"Built: {path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
