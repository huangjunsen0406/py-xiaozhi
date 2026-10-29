"""TUI logging must never wait for the UI while holding a logging lock."""

import asyncio
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
    finally:
        app.uninstall_log_handler()
        logger.handlers.clear()
        if worker is not None and worker.is_alive():
            await asyncio.to_thread(worker.join, 2)
