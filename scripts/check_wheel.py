#!/usr/bin/env python3
"""Install a wheel outside the checkout and smoke-test its entry point/resources.

Only platformdirs and packaging are installed alongside the wheel: audio/Qt
dependencies are not needed for this packaging check. The normal test job
validates runtime imports.
"""

import argparse
import os
import subprocess
import tempfile
import textwrap
import venv
import zipfile
from pathlib import Path

REQUIRED_FILES = {
    "src/cli.py",
    "src/__main__.py",
    "src/ui/gui/qml/main.qml",
    "src/_resources/assets/icon.png",
    "src/_resources/assets/sounds/zh-CN/activation.wav",
    "src/_resources/models/zh/encoder.onnx",
    "src/_resources/models/en/tokens.txt",
    "src/_resources/libs/webrtc_apm/__init__.py",
    "src/_resources/libs/libopus/linux/x64/libopus.so",
}

IMPORT_CHECK = textwrap.dedent("""
    import importlib.metadata
    import os
    import sys
    from pathlib import Path

    sys.argv = ['embedding-host', '--unrelated-host-option']
    before = dict(os.environ)
    from src.cli import main
    assert callable(main)
    assert dict(os.environ) == before
    assert 'src.utils.config_manager' not in sys.modules
    assert 'src.bootstrap.container' not in sys.modules
    assert 'PySide6' not in sys.modules
    assert 'sounddevice' not in sys.modules
    from packaging.version import Version
    from src.constants.system import SystemConstants
    assert Version(importlib.metadata.version('py-xiaozhi')) == Version(
        SystemConstants.APP_VERSION
    )
    entry, = [e for e in importlib.metadata.distribution('py-xiaozhi').entry_points
              if e.group == 'console_scripts' and e.name == 'xiaozhi']
    assert entry.load() is main
    import src.cli
    assert Path(src.cli.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())

    from src.utils.resource_finder import (
        get_app_root, get_assets_dir, get_models_dir, get_lib_path, get_resource_root,
    )
    root = get_resource_root()
    assert root.is_relative_to(Path(sys.prefix).resolve())
    assert root != get_app_root()
    assert (get_assets_dir() / 'icon.png').is_file()
    assert (get_assets_dir() / 'sounds' / 'zh-CN' / 'activation.wav').is_file()
    assert (get_models_dir() / 'zh' / 'encoder.onnx').is_file()
    assert (get_models_dir() / 'en' / 'tokens.txt').is_file()
    assert get_lib_path('libopus').is_file()
    from src._resources.libs import webrtc_apm
    assert Path(webrtc_apm._get_library_path()).is_file()
    assert dict(os.environ) == before
""")


def check_wheel(wheel: Path) -> None:
    wheel = wheel.resolve(strict=True)
    with zipfile.ZipFile(wheel) as archive:
        files = set(archive.namelist())
        missing = REQUIRED_FILES - files
        if missing:
            raise RuntimeError(f"Wheel is missing files: {sorted(missing)}")
        forbidden = [
            name for name in files if "__pycache__" in name or name.endswith(".pyc")
        ]
        if forbidden:
            raise RuntimeError(f"Wheel includes bytecode: {forbidden}")

    with tempfile.TemporaryDirectory(prefix="xiaozhi-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        venv.EnvBuilder(with_pip=True, symlinks=os.name != "nt").create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        command = scripts / ("xiaozhi.exe" if os.name == "nt" else "xiaozhi")
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["XIAOZHI_DATA_DIR"] = str(root / "data")
        env["XIAOZHI_LOG_DIR"] = str(root / "logs")
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "--disable-pip-version-check",
                "install",
                "--no-deps",
                str(wheel),
                "platformdirs>=4.0.0",
                "packaging",
            ],
            cwd=root,
            env=env,
            check=True,
            timeout=180,
        )
        subprocess.run(
            [str(python), "-I", "-B", "-c", IMPORT_CHECK],
            cwd=root,
            env=env,
            check=True,
            timeout=30,
        )
        for args in (
            [str(command), "--help"],
            [str(python), "-I", "-X", "utf8", "-B", "-m", "src", "--help"],
        ):
            result = subprocess.run(
                args,
                cwd=root,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )
            if result.returncode:
                raise RuntimeError(
                    f"Help command failed ({result.returncode}): {args}\n"
                    f"{result.stdout}\n{result.stderr}"
                )
            if "--mode" not in result.stdout:
                raise RuntimeError(f"Help output is incomplete: {result.stdout}")
        if (root / "data").exists() or (root / "logs").exists():
            raise RuntimeError("Import/help created user configuration or logs")
    print(f"Wheel entry point and resources verified: {wheel.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    check_wheel(parser.parse_args().wheel)


if __name__ == "__main__":
    main()
