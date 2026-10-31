"""Entry-point behavior without audio hardware or user configuration."""

import importlib.util
import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

from src import cli

REPOSITORY = Path(__file__).resolve().parents[1]


def test_parse_args_rejects_removed_cli_mode():
    assert cli.parse_args([]).mode == "gui"
    with pytest.raises(SystemExit) as rejected:
        cli.parse_args(["--mode", "cli"])
    assert rejected.value.code == 2


def test_tui_loop_checks_optional_dependency_before_runtime(monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, "textual", SimpleNamespace())

    async def start(*args, **kwargs):
        seen.append(args)
        return 4

    monkeypatch.setattr(cli, "start_app", start)
    assert cli._run(cli.parse_args(["--mode", "tui", "--skip-activation"])) == 4
    assert seen == [("tui", "websocket", True)]


def test_importing_launchers_has_no_startup_side_effects(tmp_path):
    data = tmp_path / "user-data"
    logs = tmp_path / "logs"
    env = dict(os.environ, XIAOZHI_DATA_DIR=str(data), XIAOZHI_LOG_DIR=str(logs))
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            textwrap.dedent("""
            import os
            import signal
            import sys
            sys.argv = ['embedding-host', '--unrelated-host-option']
            before = dict(os.environ)
            handler = signal.getsignal(signal.SIGINT)
            import main
            import src.cli
            import src.__main__
            assert callable(main.main)
            assert main.main is src.cli.main
            assert dict(os.environ) == before
            assert signal.getsignal(signal.SIGINT) == handler
            assert 'src.utils.config_manager' not in sys.modules
            assert 'src.bootstrap.container' not in sys.modules
            assert 'PySide6' not in sys.modules
            assert 'sounddevice' not in sys.modules
        """),
        ],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == result.stderr == ""
    assert not data.exists()
    assert not logs.exists()


@pytest.mark.parametrize("launcher", [["main.py"], ["-m", "src"]])
@pytest.mark.parametrize(
    "args, code", [(["--help"], 0), (["--bad-option"], 2), (["--mode", "cli"], 2)]
)
def test_help_and_invalid_arguments_do_not_initialize(tmp_path, launcher, args, code):
    data = tmp_path / "data"
    env = dict(
        os.environ, XIAOZHI_DATA_DIR=str(data), XIAOZHI_LOG_DIR=str(tmp_path / "logs")
    )
    result = subprocess.run(
        [sys.executable, "-B", *launcher, *args],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == code, result.stderr
    assert "--mode" in result.stdout + result.stderr
    assert not data.exists()
    assert not (tmp_path / "logs").exists()


def test_main_orders_initialization_and_returns_runtime_status(monkeypatch):
    events = []
    config = object()
    monkeypatch.setattr(
        cli, "_configure_environment", lambda mode: events.append(("env", mode))
    )
    monkeypatch.setitem(
        sys.modules,
        "src.utils.config_manager",
        SimpleNamespace(
            initialize_config=lambda: (events.append(("config", None)) or config),
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "src.logging",
        SimpleNamespace(
            load_logging_config=lambda source: "logging-config"
            if source is config
            else pytest.fail("wrong config"),
            setup_logging=lambda **kwargs: events.append(("logging", kwargs)),
        ),
    )

    def run(args, config=None):
        assert config is not None
        events.append(("run", args))
        return 7

    monkeypatch.setattr(cli, "_run", run)
    assert cli.main(["--mode", "tui", "--protocol", "mqtt", "--skip-activation"]) == 7
    assert [event[0] for event in events] == ["env", "config", "logging", "run"]
    assert events[2][1] == {"enable_console": False, "config": "logging-config"}
    args = events[3][1]
    assert (args.mode, args.protocol, args.skip_activation) == ("tui", "mqtt", True)
    assert cli._container is None


@pytest.mark.asyncio
async def test_failed_activation_does_not_create_container(monkeypatch):
    from src.bootstrap import container

    async def activation(mode, config=None):
        return False

    monkeypatch.setattr(cli, "handle_activation", activation)
    monkeypatch.setattr(
        container, "ServiceContainer", lambda **kwargs: pytest.fail("container created")
    )
    assert await cli.start_app("tui", "websocket", False) == 1


@pytest.mark.asyncio
async def test_start_app_passes_explicit_config_to_activation_and_container(
    monkeypatch,
):
    from src.bootstrap import container
    from src.utils.config_manager import ConfigManager

    config = ConfigManager.from_dict(
        {"SYSTEM_OPTIONS": {"NETWORK": {"ACTIVATION_VERSION": "v1"}}}
    )
    seen = {}

    async def activation(mode, config=None):
        seen["activation"] = config
        return True

    class FakeContainer:
        def __init__(self, config=None):
            seen["container"] = config

        async def run(self, *, mode, protocol):
            return 4

    monkeypatch.setattr(cli, "handle_activation", activation)
    monkeypatch.setattr(container, "ServiceContainer", FakeContainer)
    assert await cli.start_app("tui", "mqtt", False, config=config) == 4
    assert seen == {"activation": config, "container": config}


def test_terminal_loop_propagates_status_and_restores_signals(monkeypatch):
    seen = []
    original = signal.getsignal(signal.SIGINT)

    async def start(mode, protocol, skip_activation, config=None):
        seen.append((mode, protocol, skip_activation))
        assert signal.getsignal(signal.SIGINT) is not original
        return 3

    monkeypatch.setattr(cli, "start_app", start)
    assert cli._run(cli.parse_args(["--mode", "gpio", "--skip-activation"])) == 3
    assert seen == [("gpio", "websocket", True)]
    assert signal.getsignal(signal.SIGINT) is original


def test_gui_environment_is_configured_before_import(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))
    monkeypatch.setattr(cli.locale, "setlocale", lambda *args: None)
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    for name in (
        "QT_API",
        "QSG_RHI_BACKEND",
        "QT_QUICK_CONTROLS_STYLE",
        "QT_WAYLAND_DISABLE_WINDOWDECORATION",
    ):
        monkeypatch.delenv(name, raising=False)
    cli._configure_environment("gui")
    assert os.environ["QT_API"] == "pyside6"
    assert os.environ["QT_QPA_PLATFORM"] == "wayland;xcb"
    assert os.environ["QSG_RHI_BACKEND"] == "opengl"
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    cli._configure_environment("gui")
    assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


@pytest.mark.parametrize("mode", ["gpio", "gui"])
def test_main_with_real_event_loop_and_fake_runtime(tmp_path, mode):
    if mode == "gui" and any(
        importlib.util.find_spec(name) is None for name in ("PySide6", "qasync")
    ):
        pytest.skip("GUI extra is not installed")
    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        XIAOZHI_DATA_DIR=str(tmp_path / "data"),
        XIAOZHI_LOG_DIR=str(tmp_path / "logs"),
        PYTHONIOENCODING="utf-8",
    )
    script = textwrap.dedent("""
        import asyncio
        import signal
        import sys
        import types
        from src.cli import main

        mode = sys.argv[1]
        runtime = types.ModuleType('src.bootstrap.container')
        class FakeContainer:
            def __init__(self, config):
                assert config.config_file is not None
            async def run(self, *, mode, protocol):
                assert protocol == 'mqtt'
                is_qasync = 'qasync' in type(asyncio.get_running_loop()).__module__
                assert is_qasync == (mode == 'gui')
                await asyncio.sleep(0)
                return 7
        runtime.ServiceContainer = FakeContainer
        sys.modules['src.bootstrap.container'] = runtime
        previous = signal.getsignal(signal.SIGINT)
        assert main(['--mode', mode, '--protocol', 'mqtt', '--skip-activation']) == 7
        assert signal.getsignal(signal.SIGINT) is previous
    """)
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, mode],
        cwd=REPOSITORY,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "data" / "config" / "config.json").is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["gui", "tui"])
@pytest.mark.parametrize("fails", [False, True])
async def test_start_app_quits_existing_qt_only_in_gui_finally(
    monkeypatch, mode, fails
):
    from unittest.mock import Mock

    from src.bootstrap import container

    app = SimpleNamespace(quit=Mock())
    qapplication = SimpleNamespace(instance=Mock(return_value=app))
    monkeypatch.setitem(
        sys.modules, "PySide6.QtWidgets", SimpleNamespace(QApplication=qapplication)
    )

    class FakeContainer:
        def __init__(self, config=None):
            pass

        async def run(self, **kwargs):
            if fails:
                raise ValueError("runtime failure")
            return 8

    monkeypatch.setattr(container, "ServiceContainer", FakeContainer)
    if fails:
        with pytest.raises(ValueError, match="runtime failure"):
            await cli.start_app(mode, "mqtt", True)
    else:
        assert await cli.start_app(mode, "mqtt", True) == 8
    assert app.quit.call_count == (1 if mode == "gui" else 0)
    assert qapplication.instance.call_count == (1 if mode == "gui" else 0)


@pytest.mark.asyncio
async def test_activation_service_create_keeps_supplied_config(monkeypatch):
    from unittest.mock import AsyncMock

    from src.activation.service import ActivationService
    from src.utils.config_manager import ConfigManager

    config = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"DEVICE_ID": "injected"}})
    monkeypatch.setattr(ActivationService, "_async_init", AsyncMock())
    service = await ActivationService.create(config=config)
    assert service.get_config_manager() is config
    assert service._http._config is config
    assert service._ota._config is config
