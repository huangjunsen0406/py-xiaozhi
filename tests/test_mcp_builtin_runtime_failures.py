"""MCP-01..05 regressions; every device/process/launch boundary is fake."""

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, mock_open

import pytest

from src.mcp.tools.app import (
    launcher,
    launcher_linux,
    launcher_mac,
    process_manager,
    scanner_linux,
    utils,
)
from src.mcp.tools.app.register import register_app_tools
from src.mcp.tools.camera import capture_backend
from src.mcp.tools.camera.normal_camera import NormalCamera
from src.mcp.tools.camera.register import register_camera_tools
from src.mcp.tools.volume import linux, macos, windows
from src.mcp.tools.volume.register import register_volume_tools
from src.mcp.tools.volume.volume_controller import VolumeController
from src.utils.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def fake_os_only(monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError("OS boundary must be explicitly faked")

    monkeypatch.setattr(launcher_mac.subprocess, "Popen", unexpected)
    monkeypatch.setattr(launcher_mac.subprocess, "run", unexpected)
    monkeypatch.setattr(process_manager.psutil, "process_iter", unexpected)
    monkeypatch.setattr(process_manager.psutil, "Process", unexpected)
    monkeypatch.setattr(
        utils, "get_cached_applications", AsyncMock(side_effect=unexpected)
    )
    monkeypatch.setattr(capture_backend, "_capture_opencv", unexpected)
    monkeypatch.setattr(capture_backend, "_capture_picamera2", unexpected)


def text(reply):
    return json.loads(reply)["content"][0]["text"]


def app_tools():
    tools = []
    register_app_tools(tools.append)
    return {tool.name.rsplit(".", 1)[-1]: tool for tool in tools}


def volume_tools(backend):
    controller = VolumeController.__new__(VolumeController)
    controller._backend = backend
    tools = []
    register_volume_tools(tools.append, controller)
    return tools


@pytest.mark.asyncio
async def test_camera_deadline_bounds_registered_call_and_retry_workers(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    workers = []

    def blocked_driver(_):
        workers.append(threading.current_thread())
        entered.set()
        assert release.wait(2)
        return b"late-jpeg"

    monkeypatch.setattr(capture_backend, "_CAPTURE_TIMEOUT_S", 0.02)
    monkeypatch.setattr(capture_backend, "_capture_opencv", blocked_driver)
    camera = NormalCamera(ConfigManager.from_dict({"CAMERA": {"backend": "opencv"}}))
    camera.analyze = Mock(side_effect=AssertionError("failed capture analyzed"))
    tools = []
    register_camera_tools(tools.append, camera)
    started = time.monotonic()
    try:
        reply = json.loads(text(await tools[0].call({"question": "what"})))
        elapsed = time.monotonic() - started
        assert entered.is_set()
        assert elapsed < 0.3
        assert reply["success"] is False
        assert workers[0].daemon
        for _ in range(10):
            assert not camera.capture()
        assert len(workers) == 1
        assert camera.get_jpeg_data()["buf"] == b""
        camera.analyze.assert_not_called()
    finally:
        release.set()
        for worker in workers:
            worker.join(2)
    monkeypatch.setattr(capture_backend, "_capture_opencv", lambda _: b"fresh-jpeg")
    assert camera.capture()
    assert camera.get_jpeg_data()["buf"] == b"fresh-jpeg"


@pytest.mark.parametrize("tool", ["pactl", "wpctl", "amixer"])
@pytest.mark.asyncio
async def test_volume_command_failures_reach_registered_results(monkeypatch, tool):
    backend = linux.LinuxVolumeBackend.__new__(linux.LinuxVolumeBackend)
    backend.linux_tool = tool
    monkeypatch.setattr(
        linux,
        "_run_command",
        lambda *a, **kw: SimpleNamespace(
            returncode=1, stdout="", stderr="Connection refused"
        ),
    )
    tools = volume_tools(backend)
    assert text(await tools[0].call({"volume": 23})) == "false"
    assert json.loads(await tools[1].call({}))["isError"] is True
    status = json.loads(text(await tools[2].call({})))
    assert status["available"] is False
    assert status["volume"] is None and status["muted"] is None


@pytest.mark.parametrize("tool", ["pactl", "wpctl", "amixer"])
@pytest.mark.parametrize("output", ["", "garbled"])
def test_volume_invalid_measurement_is_an_error(monkeypatch, tool, output):
    backend = linux.LinuxVolumeBackend.__new__(linux.LinuxVolumeBackend)
    backend.linux_tool = tool
    monkeypatch.setattr(
        linux,
        "_run_command",
        lambda *a, **kw: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )
    with pytest.raises(RuntimeError):
        backend.get_volume()


@pytest.mark.asyncio
async def test_native_volume_backend_errors_are_not_swallowed(monkeypatch):
    for backend_type in [macos.MacosVolumeBackend, windows.WindowsVolumeBackend]:
        backend = backend_type.__new__(backend_type)
        failure = Mock(side_effect=OSError("device disconnected"))
        if backend_type is macos.MacosVolumeBackend:
            backend._lazy_import = lambda _, operation=failure: SimpleNamespace(
                run=operation
            )
        else:
            backend.volume_control = SimpleNamespace(
                GetMasterVolumeLevelScalar=failure, SetMasterVolumeLevelScalar=failure
            )
        tools = volume_tools(backend)
        assert text(await tools[0].call({"volume": 23})) == "false"
        assert json.loads(await tools[1].call({}))["isError"] is True
        assert json.loads(text(await tools[2].call({})))["available"] is False


def test_macos_volume_rejected_result_is_an_error():
    backend = macos.MacosVolumeBackend.__new__(macos.MacosVolumeBackend)
    backend._lazy_import = lambda _: SimpleNamespace(
        run=lambda _: SimpleNamespace(code=1, out="70", err="rejected")
    )
    with pytest.raises(RuntimeError):
        backend.get_volume()
    with pytest.raises(RuntimeError):
        backend.set_volume(23)


@pytest.mark.asyncio
async def test_successful_volume_roundtrip_still_reports_measured_value(monkeypatch):
    backend = linux.LinuxVolumeBackend.__new__(linux.LinuxVolumeBackend)
    backend.linux_tool = "pactl"
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(
            returncode=0, stdout="Volume: front-left: 42%", stderr=""
        )

    monkeypatch.setattr(linux, "_run_command", run)
    tools = volume_tools(backend)
    assert text(await tools[0].call({"volume": 23})) == "true"
    assert text(await tools[1].call({})) == "42"
    assert json.loads(text(await tools[2].call({}))) == {
        "volume": 42,
        "muted": False,
        "available": True,
    }
    assert calls[0] == ["pactl", "set-sink-volume", "@DEFAULT_SINK@", "23%"]


def fake_processes(monkeypatch, entries):
    killed = []
    infos = [
        SimpleNamespace(info={"pid": pid, "name": name, "exe": exe, "cmdline": [name]})
        for pid, name, exe in entries
    ]

    class FakeProc:
        def __init__(self, pid):
            self.pid = pid

        def children(self, recursive=True):
            return [FakeProc(201)] if self.pid == 101 else []

        def terminate(self):
            killed.append(self.pid)

        def kill(self):
            killed.append(self.pid)

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(process_manager.sys, "platform", "win32")
    monkeypatch.setattr(process_manager.psutil, "process_iter", lambda *a: infos)
    monkeypatch.setattr(process_manager.psutil, "Process", FakeProc)
    return killed


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.asyncio
async def test_kill_qq_selects_exact_identity_and_its_tree(monkeypatch, force):
    killed = fake_processes(
        monkeypatch,
        [
            (101, "QQ.exe", "C:/Apps/QQ/QQ.exe"),
            (102, "QQMusic.exe", "C:/Apps/QQMusic/QQMusic.exe"),
            (103, "OtherQQ.exe", "C:/Apps/OtherQQ/OtherQQ.exe"),
        ],
    )
    assert (
        text(await app_tools()["kill"].call({"app_name": "QQ", "force": force}))
        == "true"
    )
    assert sorted(killed) == [101, 201]


@pytest.mark.asyncio
async def test_kill_qq_never_falls_back_to_qqmusic(monkeypatch):
    killed = fake_processes(monkeypatch, [(102, "QQMusic.exe", "C:/Apps/QQMusic.exe")])
    assert text(await app_tools()["kill"].call({"app_name": "QQ"})) == "false"
    assert killed == []


@pytest.mark.asyncio
async def test_kill_refuses_multiple_distinct_exact_identities(monkeypatch):
    killed = fake_processes(
        monkeypatch,
        [
            (101, "Editor.exe", "C:/Apps/first/Editor.exe"),
            (102, "Editor.exe", "C:/Apps/second/Editor.exe"),
        ],
    )
    assert text(await app_tools()["kill"].call({"app_name": "Editor"})) == "false"
    assert killed == []


@pytest.mark.asyncio
async def test_kill_preserves_unambiguous_exact_alias(monkeypatch):
    killed = fake_processes(monkeypatch, [(101, "QQNT.exe", "C:/Apps/QQNT.exe")])
    assert text(await app_tools()["kill"].call({"app_name": "QQ"})) == "true"
    assert sorted(killed) == [101, 201]


@pytest.mark.asyncio
async def test_macos_open_rejection_does_not_report_launch_success(monkeypatch):
    monkeypatch.setattr(
        launcher, "_find_matching_application", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(launcher_mac.os.path, "exists", lambda _: False)
    run = Mock(return_value=SimpleNamespace(returncode=1, stderr="not found"))
    monkeypatch.setattr(launcher_mac.subprocess, "run", run)
    monkeypatch.setattr(
        launcher_mac.subprocess, "Popen", Mock(side_effect=OSError("not found"))
    )
    assert (
        text(await app_tools()["launch"].call({"app_name": "AuditMissingApp"}))
        == "false"
    )
    assert run.call_count >= 1
    assert all(call.kwargs["timeout"] <= 5 for call in run.call_args_list)


@pytest.mark.asyncio
async def test_macos_open_acceptance_does_not_wait_for_gui(monkeypatch):
    monkeypatch.setattr(
        launcher, "_find_matching_application", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Darwin")
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher_mac.subprocess, "run", run)
    monkeypatch.setattr(
        launcher_mac.subprocess,
        "Popen",
        Mock(side_effect=AssertionError("GUI fallback")),
    )
    assert text(await app_tools()["launch"].call({"app_name": "AuditApp"})) == "true"
    assert run.call_args.args[0] == ["open", "-a", "AuditApp"]


@pytest.mark.parametrize(
    "exec_line",
    [
        "env AUDIT_MODE=1 /opt/audit/player --desktop %U",
        '"/opt/Audit Player/player" --title "A B" %u %% %i %c %k',
    ],
)
@pytest.mark.asyncio
async def test_desktop_registered_launch_preserves_entry_identity(
    monkeypatch, exec_line
):
    desktop = Path("/virtual/Audit Player.desktop")
    monkeypatch.setattr(
        "builtins.open",
        mock_open(
            read_data=(
                f"[Desktop Entry]\nName=AuditPlayer\nExec={exec_line}\n"
                "[Desktop Action Other]\nName=Wrong\nExec=wrong-command\n"
            )
        ),
    )
    app = scanner_linux._parse_desktop_file(desktop)
    assert app["name"] == "AuditPlayer"
    assert app["path"] == str(desktop)
    monkeypatch.setattr(utils, "get_cached_applications", AsyncMock(return_value=[app]))
    monkeypatch.setattr(launcher.platform, "system", lambda: "Linux")
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(launcher_linux.subprocess, "run", run)
    monkeypatch.setattr(
        launcher_linux.subprocess,
        "Popen",
        Mock(side_effect=AssertionError("raw Exec launch")),
    )
    assert text(await app_tools()["launch"].call({"app_name": "AuditPlayer"})) == "true"
    assert run.call_args.args[0] == ["gio", "launch", str(desktop)]
    assert not run.call_args.kwargs.get("shell", False)


@pytest.mark.asyncio
async def test_desktop_helper_rejection_is_failure_without_raw_exec_fallback(
    monkeypatch,
):
    monkeypatch.setattr(
        utils,
        "get_cached_applications",
        AsyncMock(
            return_value=[
                {
                    "name": "AuditPlayer",
                    "path": "/virtual/audit.desktop",
                    "type": "desktop",
                }
            ]
        ),
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Linux")
    monkeypatch.setattr(
        launcher_linux.subprocess,
        "run",
        Mock(return_value=SimpleNamespace(returncode=1)),
    )
    monkeypatch.setattr(
        launcher_linux.subprocess,
        "Popen",
        Mock(side_effect=AssertionError("raw launch")),
    )
    assert (
        text(await app_tools()["launch"].call({"app_name": "AuditPlayer"})) == "false"
    )


def test_launch_alias_matching_still_accepts_wanted_names():
    assert utils.AppMatcher.match_application("QQ音乐", {"name": "QQMusic"}) >= 90
    assert utils.AppMatcher.match_application("Chrome", {"name": "Google Chrome"}) >= 90


@pytest.mark.asyncio
async def test_camera_driver_error_reaches_registered_tool_and_recovers(monkeypatch):
    monkeypatch.setattr(
        capture_backend, "_capture_opencv", Mock(side_effect=OSError("driver failed"))
    )
    camera = NormalCamera(ConfigManager.from_dict({"CAMERA": {"backend": "opencv"}}))
    tools = []
    register_camera_tools(tools.append, camera)
    reply = json.loads(await tools[0].call({"question": "what"}))
    assert reply["isError"] is True
    assert "driver failed" in reply["content"][0]["text"]
    worker = capture_backend._capture_worker
    worker.join(2)
    monkeypatch.setattr(capture_backend, "_capture_opencv", lambda _: b"fresh")
    assert camera.capture()


@pytest.mark.asyncio
async def test_volume_missing_dependencies_never_invents_measurement(monkeypatch):
    from src.mcp.tools.volume import register

    monkeypatch.setattr(register, "create_volume_controller", lambda: None)
    tools = []
    register_volume_tools(tools.append)
    assert text(await tools[0].call({"volume": 23})) == "false"
    assert json.loads(await tools[1].call({}))["isError"] is True
    status = json.loads(text(await tools[2].call({})))
    assert status["available"] is False
    assert status["volume"] is None and status["muted"] is None


@pytest.mark.asyncio
async def test_kill_qq_music_resolves_its_own_exact_alias_identity(monkeypatch):
    killed = fake_processes(
        monkeypatch,
        [
            (101, "QQ.exe", "C:/Apps/QQ.exe"),
            (102, "QQMusic.exe", "C:/Apps/QQMusic.exe"),
        ],
    )
    assert text(await app_tools()["kill"].call({"app_name": "QQ音乐"})) == "true"
    assert killed == [102]


@pytest.mark.asyncio
async def test_kill_refuses_aliases_resolving_to_distinct_apps(monkeypatch):
    killed = fake_processes(
        monkeypatch,
        [
            (101, "QQNT.exe", "C:/Apps/QQNT.exe"),
            (102, "TencentQQ.exe", "C:/Apps/TencentQQ.exe"),
        ],
    )
    assert text(await app_tools()["kill"].call({"app_name": "QQ"})) == "false"
    assert killed == []


@pytest.mark.asyncio
async def test_macos_checked_open_can_reach_successful_bundle_fallback(monkeypatch):
    monkeypatch.setattr(
        launcher, "_find_matching_application", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(launcher_mac.os.path, "exists", lambda _: True)
    run = Mock(
        side_effect=[SimpleNamespace(returncode=1), SimpleNamespace(returncode=0)]
    )
    monkeypatch.setattr(launcher_mac.subprocess, "run", run)
    monkeypatch.setattr(
        launcher_mac.subprocess, "Popen", Mock(side_effect=OSError("no executable"))
    )
    assert text(await app_tools()["launch"].call({"app_name": "AuditApp"})) == "true"
    assert run.call_args.args[0] == ["open", "/Applications/AuditApp.app"]


@pytest.mark.asyncio
async def test_macos_open_timeout_reaches_failure_without_hanging(monkeypatch):
    monkeypatch.setattr(
        launcher, "_find_matching_application", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(launcher_mac.os.path, "exists", lambda _: False)
    monkeypatch.setattr(
        launcher_mac.subprocess,
        "run",
        Mock(side_effect=launcher_mac.subprocess.TimeoutExpired("open", 5)),
    )
    monkeypatch.setattr(
        launcher_mac.subprocess, "Popen", Mock(side_effect=OSError("no executable"))
    )
    assert text(await app_tools()["launch"].call({"app_name": "AuditApp"})) == "false"


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("gio missing"),
        launcher_linux.subprocess.TimeoutExpired("gio", 5),
    ],
)
@pytest.mark.asyncio
async def test_desktop_unavailable_or_timed_out_helper_fails(monkeypatch, error):
    monkeypatch.setattr(
        utils,
        "get_cached_applications",
        AsyncMock(
            return_value=[
                {
                    "name": "AuditPlayer",
                    "path": "/virtual/audit.desktop",
                    "type": "desktop",
                }
            ]
        ),
    )
    monkeypatch.setattr(launcher.platform, "system", lambda: "Linux")
    monkeypatch.setattr(launcher_linux.subprocess, "run", Mock(side_effect=error))
    assert (
        text(await app_tools()["launch"].call({"app_name": "AuditPlayer"})) == "false"
    )
