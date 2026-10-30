"""Real CLI manager shutdown must not leave an input executor blocked."""

import asyncio
import contextlib
import logging
import os
import sys
from unittest.mock import Mock

import pytest

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.plugins.ui_presenter import UiPresenter
from src.plugins.ui_session import SessionActions
from src.ui.cli.display import CLIDisplay
from src.ui.cli.manager import CliViewManager


@pytest.fixture(autouse=True)
def restore_logging():
    loggers = [logging.getLogger()] + [
        item
        for item in logging.Logger.manager.loggerDict.values()
        if isinstance(item, logging.Logger)
    ]
    original = [(log, list(log.handlers), log.level) for log in loggers]
    yield
    for log, handlers, level in original:
        log.handlers[:] = handlers
        log.setLevel(level)


@contextlib.contextmanager
def pipe_input(monkeypatch):
    reader, writer = os.pipe()
    stream = os.fdopen(reader, "r", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", stream)
    try:
        yield writer
    finally:
        os.close(writer)
        stream.close()


def manager():
    tasks = TaskManager()
    tasks.initialize()
    bus = EventBus()
    SessionActions(
        None,
        type(
            "Commands", (), {"request_shutdown": lambda self: tasks.request_shutdown()}
        )(),
        UiPresenter(),
    ).subscribe(bus)
    view = CliViewManager(bus, tasks)
    view._display._use_ansi = False
    return view, tasks, bus


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["q", "external"])
async def test_quit_and_idle_external_close_do_not_block_executor_shutdown(
    monkeypatch, action
):
    with pipe_input(monkeypatch) as writer:
        view, tasks, _ = manager()
        start = asyncio.create_task(view.start())
        executor = None
        try:
            if action == "q":
                os.write(writer, b"q\n")
                await asyncio.wait_for(tasks.wait_shutdown(), 0.5)
            else:
                for _ in range(20):
                    if view._display._initialized:
                        break
                    await asyncio.sleep(0)
                await asyncio.sleep(0.02)
            await view.close()
            if action == "external":
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(start, 0.5)
            else:
                await asyncio.wait_for(start, 0.5)
            assert not view.is_running
            executor = asyncio.create_task(
                asyncio.get_running_loop().shutdown_default_executor()
            )
            done, _ = await asyncio.wait({executor}, timeout=0.05)
            assert executor in done, (
                "CLI input still owns a blocked default executor thread"
            )
        finally:
            # Release the old implementation's blocked reader even on failure.
            os.write(writer, b"\n")
            await view.close()
            start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            await tasks.cancel_all()
            if executor is not None:
                await executor


@pytest.mark.asyncio
async def test_raw_ctrl_c_requests_real_manager_quit(monkeypatch):
    view, tasks, _ = manager()
    view._display._use_ansi = True
    monkeypatch.setattr(
        view._display, "_read_line_raw", Mock(side_effect=KeyboardInterrupt)
    )
    try:
        await asyncio.wait_for(view.start(), 0.5)
        await asyncio.wait_for(tasks.wait_shutdown(), 0.5)
        assert not view.is_running
    finally:
        await view.close()
        await tasks.cancel_all()


@pytest.mark.asyncio
async def test_raw_utf8_backspace_and_q_use_interruptible_descriptor(monkeypatch):
    with pipe_input(monkeypatch) as writer:
        view, tasks, bus = manager()
        view._display._use_ansi = True
        texts = []
        bus.on(Events.UI_SEND_TEXT, lambda data: texts.append(data["text"]))
        os.write(writer, "你好\b吗\nq\n".encode())
        start = asyncio.create_task(view.start())
        try:
            await asyncio.wait_for(tasks.wait_shutdown(), 0.5)
            await asyncio.wait_for(start, 0.5)
            assert texts == ["你吗"]
            assert not view.is_running
        finally:
            await view.close()
            start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            await tasks.cancel_all()


@pytest.mark.asyncio
async def test_cli_capture_preserves_disk_handler_and_restores_same_console(tmp_path):
    log = logging.getLogger("test.cli.disk-preservation")
    disk = logging.FileHandler(tmp_path / "cli.log", encoding="utf-8")
    console = logging.StreamHandler(sys.stderr)
    log.addHandler(disk)
    log.addHandler(console)
    log.setLevel(logging.INFO)
    display = CLIDisplay()
    try:
        display.intercept_logging()
        assert disk in log.handlers
        assert console not in log.handlers
        log.warning("disk remains active")
        disk.flush()
        assert "disk remains active" in (tmp_path / "cli.log").read_text()
        await display.close()
        assert disk in log.handlers
        assert console in log.handlers
        assert log.handlers.count(console) == 1
        await display.close()
        assert log.handlers.count(console) == 1
    finally:
        display._restore_logging()
        log.removeHandler(disk)
        log.removeHandler(console)
        disk.close()
        console.close()


@pytest.mark.asyncio
async def test_eof_is_orderly_quit(monkeypatch):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    view, tasks, _ = manager()
    try:
        await asyncio.wait_for(view.start(), 0.5)
        await asyncio.wait_for(tasks.wait_shutdown(), 0.5)
        assert not view.is_running
    finally:
        await view.close()
        await tasks.cancel_all()


@pytest.mark.asyncio
async def test_idle_close_restores_raw_terminal_before_return(monkeypatch):
    import termios
    import tty

    with pipe_input(monkeypatch):
        view, tasks, _ = manager()
        view._display._use_ansi = True
        snapshot = ["terminal snapshot"]
        monkeypatch.setattr(os, "isatty", lambda fd: True)
        monkeypatch.setattr(termios, "tcgetattr", lambda fd: snapshot)
        monkeypatch.setattr(tty, "setraw", Mock())
        restore = Mock()
        monkeypatch.setattr(termios, "tcsetattr", restore)
        start = asyncio.create_task(view.start())
        try:
            for _ in range(30):
                if view._display._input_waiter is not None:
                    break
                await asyncio.sleep(0)
            assert view._display._input_waiter is not None
            fd = sys.stdin.fileno()
            await view.close()
            restore.assert_called_once_with(fd, termios.TCSADRAIN, snapshot)
            assert view._display._input_waiter is None
            with pytest.raises(asyncio.CancelledError):
                await start
        finally:
            await view.close()
            start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            await tasks.cancel_all()


@pytest.mark.asyncio
async def test_windows_idle_pipe_poll_can_be_cancelled_without_thread(monkeypatch):
    import ctypes
    from types import SimpleNamespace

    peek = Mock(return_value=1)
    monkeypatch.setattr(
        ctypes,
        "WinDLL",
        lambda *args, **kwargs: SimpleNamespace(PeekNamedPipe=peek),
        raising=False,
    )
    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(get_osfhandle=lambda fd: 123)
    )
    display = CLIDisplay()
    read = asyncio.create_task(display._read_windows_pipe(0))
    try:
        await asyncio.sleep(0)
        peek.assert_called_once()
        read.cancel()
        with pytest.raises(asyncio.CancelledError):
            await read
    finally:
        read.cancel()
        await asyncio.gather(read, return_exceptions=True)
        await display.close()
