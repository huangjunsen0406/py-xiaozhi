"""TUI logging must never wait for the UI while holding a logging lock."""

import asyncio
import io
import logging
import threading

import pytest

pytest.importorskip("textual")


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["main", "mqtt-worker"])
async def test_tui_logs_are_delivered_without_waiting_for_ui(source, monkeypatch):
    from src.ui.tui.app import XiaozhiTuiApp

    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", list(root.handlers))
    app = XiaozhiTuiApp()
    written = []
    monkeypatch.setattr(app, "write_log", written.append)
    logger = logging.Logger("test.tui", level=logging.INFO)
    worker = None
    try:
        async with app.run_test() as pilot:
            logger.addHandler(app._tui_log_handler)
            if source == "mqtt-worker":
                returned = threading.Event()

                def emit():
                    logger.info("MQTT connected")
                    returned.set()

                worker = threading.Thread(target=emit, daemon=True)
                worker.start()
                # Deliberately keep the UI loop busy: a network callback must
                # return and release the logging lock even before UI rendering.
                completed_without_ui = returned.wait(timeout=1)
                # Let the original implementation unwind before asserting, so
                # a failing regression cannot leave a blocked logging thread.
                await asyncio.to_thread(worker.join, 2)
                assert not worker.is_alive()
                assert completed_without_ui, "TUI logging blocked the MQTT callback"
            else:
                logger.info("MQTT connected")

            await pilot.pause()
            assert any("MQTT connected" in message for message in written)
            # Main-loop logging after a worker log must also remain visible.
            logger.info("control channel ready")
            await pilot.pause()
            assert any("control channel ready" in message for message in written)
        assert not app._log_handler_installed
        assert app._tui_log_handler is None
    finally:
        app.uninstall_log_handler()
        logger.handlers.clear()
        if worker is not None and worker.is_alive():
            await asyncio.to_thread(worker.join, 2)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_tui_mutes_only_owned_console_and_restores_it(
    monkeypatch, tmp_path, capsys, asynchronous
):
    import src.logging as logs
    from src.ui.tui.app import XiaozhiTuiApp

    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [])
    monkeypatch.setattr(root, "level", logging.INFO)
    monkeypatch.setattr(logs, "_owned_handlers", [])
    monkeypatch.setattr(logs, "_bootstrap_handlers", {})
    monkeypatch.setattr(logs, "_initialized", False)
    host_output = io.StringIO()
    host = logging.StreamHandler(host_output)
    root.addHandler(host)
    app = XiaozhiTuiApp()
    try:
        logs.setup_logging(
            config=logs.LoggingConfig(
                log_dir=tmp_path,
                enable_async=asynchronous,
                enable_error_file=False,
            )
        )
        owned = logs._owned_handlers[0]

        def drain():
            if asynchronous:
                owned._log_queue.join()

        drain()
        capsys.readouterr()
        original_handlers = list(root.handlers)
        app._install_log_handler()
        tui_handler = app._tui_log_handler
        app._install_log_handler()
        assert root.handlers == [*original_handlers, tui_handler]
        root.info("during-tui")
        drain()
        assert "during-tui" in host_output.getvalue()
        assert "during-tui" not in capsys.readouterr().out
        assert "during-tui" in (tmp_path / "app.log").read_text(encoding="utf-8")
        app.uninstall_log_handler()
        app.uninstall_log_handler()
        assert root.handlers == original_handlers
        assert tui_handler._closed
        assert not host._closed
        root.info("after-tui")
        drain()
        assert "after-tui" in host_output.getvalue()
        assert "after-tui" in capsys.readouterr().out
        # Re-entering the TUI must suppress and restore the same sinks again.
        app._install_log_handler()
        app.uninstall_log_handler()
        assert root.handlers == original_handlers
        assert app._muted_console_handlers == []
    finally:
        app.uninstall_log_handler()
        logs.shutdown_logging()
        host.close()
