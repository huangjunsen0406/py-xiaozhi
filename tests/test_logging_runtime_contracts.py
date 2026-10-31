"""Logging setup and shutdown contracts, with an isolated logging hierarchy."""

import copy
import io
import logging
import threading
from types import SimpleNamespace

import pytest

import src.logging as logs
from src.logging import log_config
from src.logging.filters import DuplicateFilter, SensitiveDataFilter
from src.logging.log_handlers import AsyncHandler, TimeSizeRotatingFileHandler


@pytest.fixture(autouse=True)
def isolated_logging(monkeypatch):
    root = logging.RootLogger(logging.INFO)
    monkeypatch.setattr(logging, "root", root)
    monkeypatch.setattr(logging.Logger, "root", root)
    monkeypatch.setattr(logging.Logger, "manager", logging.Manager(root))
    monkeypatch.setattr(logs, "_initialized", False)
    monkeypatch.setattr(logs, "_bootstrap_handlers", {})
    monkeypatch.setattr(logs, "_owned_handlers", [])
    yield root
    logs.shutdown_logging()


@pytest.mark.parametrize(
    "environment, configured, explicit, expected",
    [
        ("development", "WARNING", None, "WARNING"),
        ("production", "DEBUG", None, "DEBUG"),
        ("testing", "ERROR", None, "ERROR"),
        ("development", "ERROR", "info", "INFO"),
        ("development", None, None, "DEBUG"),
        ("production", None, None, "INFO"),
        ("testing", None, None, "INFO"),
    ],
)
def test_loaded_level_precedence(
    monkeypatch, tmp_path, environment, configured, explicit, expected
):
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    if explicit is not None:
        monkeypatch.setenv("LOG_LEVEL", explicit)
    source = SimpleNamespace(
        get_config=lambda *_: {"LEVEL": configured} if configured else {}
    )
    monkeypatch.setattr(log_config, "_get_default_log_dir", lambda: tmp_path)
    assert logs.load_logging_config(source).level == expected


def test_qasync_noise_default_can_be_overridden(monkeypatch, tmp_path):
    monkeypatch.setattr(log_config, "_get_default_log_dir", lambda: tmp_path)
    assert logs.LoggingConfig().third_party_levels["qasync"] == "WARNING"
    source = SimpleNamespace(
        get_config=lambda *_: {"THIRD_PARTY_LEVELS": {"qasync": "DEBUG"}}
    )
    config = logs.load_logging_config(source)
    logs.setup_logging(
        config=config, enable_console=False, enable_file=False, enable_json=False
    )
    assert logging.getLogger("qasync").level == logging.DEBUG


def test_setup_replaces_bootstrap_console_and_restores_inherited_level(
    tmp_path, capsys
):
    logging.getLogger().handlers.clear()
    logger = logs.get_logger("contracts.bootstrap")
    bootstrap = logger.handlers[0]
    logs.setup_logging(
        config=logs.LoggingConfig(log_dir=tmp_path, enable_error_file=False),
        enable_file=False,
    )
    logger.info("BOOTSTRAP_TRANSITION token=private-value")
    output = capsys.readouterr()
    assert output.out.count("BOOTSTRAP_TRANSITION") == 1
    assert "private-value" not in output.out
    assert "BOOTSTRAP_TRANSITION" not in output.err
    assert logger.handlers == []
    assert logger.level == logging.NOTSET
    assert logger.propagate
    assert bootstrap._closed


def test_disabled_console_removes_only_owned_bootstrap_handlers(tmp_path, capsys):
    root = logging.getLogger()
    root.handlers.clear()
    logger = logs.get_logger("contracts.disabled")
    module_stream, root_stream = io.StringIO(), io.StringIO()
    caller_module = logging.StreamHandler(module_stream)
    caller_root = logging.StreamHandler(root_stream)
    logger.addHandler(caller_module)
    root.addHandler(caller_root)
    try:
        logs.setup_logging(
            config=logs.LoggingConfig(
                log_dir=tmp_path,
                enable_console=False,
                enable_file=False,
                enable_error_file=False,
            )
        )
        logger.info("only-caller-handlers")
        assert logger.handlers == [caller_module]
        assert root.handlers == [caller_root]
        assert "only-caller-handlers" in module_stream.getvalue()
        assert "only-caller-handlers" in root_stream.getvalue()
        assert "only-caller-handlers" not in capsys.readouterr().err
        logs.shutdown_logging()
        assert not caller_module._closed
        assert not caller_root._closed
    finally:
        caller_module.close()
        caller_root.close()


def test_setup_preserves_loaded_flags_and_does_not_mutate_config(tmp_path, monkeypatch):
    logging.getLogger().handlers.clear()
    source = SimpleNamespace(
        get_config=lambda *_: {
            "ENABLE_FILE": False,
            "ENABLE_JSON_FILE": True,
            "ENABLE_ASYNC": True,
            "ENABLE_SENSITIVE_FILTER": False,
            "ENABLE_ERROR_FILE": False,
        }
    )
    monkeypatch.setattr(log_config, "_get_default_log_dir", lambda: tmp_path)
    config = logs.load_logging_config(source)
    before = copy.deepcopy(config)
    assert logs.setup_logging(config=config, enable_console=False) is None
    assert config == before
    wrapper = logging.getLogger().handlers[0]
    assert isinstance(wrapper, AsyncHandler)
    assert len(wrapper._listener.handlers) == 1
    sink = wrapper._listener.handlers[0]
    assert sink.baseFilename.endswith("app.json.log")
    assert not any(isinstance(f, SensitiveDataFilter) for f in sink.filters)
    logs.shutdown_logging()
    assert not (tmp_path / "app.log").exists()
    assert (tmp_path / "app.json.log").exists()


def test_explicit_false_overrides_loaded_true_without_mutation(tmp_path):
    logging.getLogger().handlers.clear()
    config = logs.LoggingConfig(
        level="WARNING",
        log_dir=tmp_path / "original",
        enable_console=True,
        enable_file=True,
        enable_json_file=True,
        enable_async=True,
        enable_error_file=False,
    )
    before = copy.deepcopy(config)
    logs.setup_logging(
        config=config,
        level="debug",
        log_dir=tmp_path / "override",
        enable_console=False,
        enable_file=False,
        enable_json=False,
        enable_async=False,
        enable_sensitive_filter=False,
    )
    assert config == before
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger().handlers == []
    assert not config.log_dir.exists()


@pytest.mark.parametrize("compress", [False, True])
@pytest.mark.parametrize("when", ["midnight", "H"])
def test_retention_keeps_other_sink_files_and_archives(tmp_path, compress, when):
    app = TimeSizeRotatingFileHandler(
        tmp_path / "app.log", backup_count=1, compress=compress, when=when
    )
    json_sink = TimeSizeRotatingFileHandler(
        tmp_path / "app.json.log", backup_count=1, compress=compress, when=when
    )
    unrelated = tmp_path / "app.notes"
    unrelated.write_text("user-file", encoding="utf-8")
    wrong_extension = tmp_path / "app.2000-01-01.txt"
    wrong_extension.write_text("user-file", encoding="utf-8")
    archive_directory = tmp_path / "app.2000-01-01.log"
    archive_directory.mkdir()
    try:
        json_sink.emit(logging.makeLogRecord({"msg": "before"}))
        json_sink.doRollover()
        json_archive = next(
            p for p in tmp_path.iterdir() if p.name.startswith("app.json.2")
        )
        for _ in range(3):
            app.emit(logging.makeLogRecord({"msg": "text"}))
            app.doRollover()
        assert json_archive.exists()
        assert (tmp_path / "app.json.log").exists()
        json_sink.emit(logging.makeLogRecord({"msg": "after"}))
        json_sink.flush()
        assert "after" in (tmp_path / "app.json.log").read_text(encoding="utf-8")
        text_archives = [
            p
            for p in tmp_path.iterdir()
            if p.is_file() and p.name.startswith("app.2") and p != wrong_extension
        ]
        assert len(text_archives) == 1
        json_sink.doRollover()
        assert text_archives[0].exists()
        assert unrelated.read_text(encoding="utf-8") == "user-file"
        assert wrong_extension.read_text(encoding="utf-8") == "user-file"
        assert archive_directory.is_dir()
    finally:
        app.close()
        json_sink.close()


def test_async_full_queue_drops_without_recursion_then_close_drains(
    tmp_path, monkeypatch
):
    entered, allow, sentinel_requested = (threading.Event() for _ in range(3))
    messages = []

    class Gate(logging.Handler):
        closes = 0

        def emit(self, record):
            if record.msg == "first":
                entered.set()
                allow.wait(timeout=5)
            messages.append(record.getMessage())

        def close(self):
            self.closes += 1
            super().close()

    gate = Gate()
    file_sink = logging.FileHandler(tmp_path / "async.log")
    stream = file_sink.stream
    wrapper = AsyncHandler([gate, file_sink], queue_size=1)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(wrapper)
    worker = wrapper._listener._thread
    original_enqueue_sentinel = wrapper._listener.enqueue_sentinel

    def enqueue_sentinel():
        sentinel_requested.set()
        original_enqueue_sentinel()

    monkeypatch.setattr(wrapper._listener, "enqueue_sentinel", enqueue_sentinel)
    closers = []
    try:
        root.info("first")
        assert entered.wait(timeout=1)
        root.info("second")
        root.error("third")
        assert wrapper.dropped_records == 1
        for _ in range(2):
            closer = threading.Thread(target=wrapper.close, daemon=True)
            closer.start()
            closers.append(closer)
        assert sentinel_requested.wait(timeout=1)
        root.debug("after-close-started")
        assert wrapper._log_queue.qsize() == 1
        assert not stream.closed
        allow.set()
        for closer in closers:
            closer.join(timeout=2)
            assert not closer.is_alive()
        assert not worker.is_alive()
        assert wrapper._listener._thread is None
        assert wrapper._log_queue.empty()
        assert messages == ["first", "second"]
        assert (tmp_path / "async.log").read_text(encoding="utf-8").splitlines() == [
            "first",
            "second",
        ]
        assert stream.closed
        assert gate.closes == 1
        wrapper.close()
        root.info("after-close-completed")
        assert gate.closes == 1
        assert wrapper._log_queue.empty()
    finally:
        allow.set()
        for closer in closers:
            closer.join(timeout=2)
        root.removeHandler(wrapper)
        wrapper.close()


def test_async_prepare_snapshots_mutable_arguments_before_sink_runs():
    entered, allow = threading.Event(), threading.Event()
    received = []

    class Gate(logging.Handler):
        def emit(self, record):
            if record.getMessage() == "snapshot block":
                entered.set()
                allow.wait(timeout=5)
            received.append(record)

    wrapper = AsyncHandler([Gate()])
    wrapper.setFormatter(logging.Formatter("snapshot %(message)s"))
    logger = logging.Logger("contracts.snapshot", level=logging.INFO)
    logger.addHandler(wrapper)
    values = ["before"]
    original = logging.LogRecord(
        logger.name, logging.INFO, "", 0, "items=%s", (values,), None
    )
    try:
        logger.info("block")
        assert entered.wait(timeout=1)
        logger.handle(original)
        assert original.msg == "items=%s"
        assert original.args == (values,)
        values.append("after")
        original.msg = "changed=%s"
        allow.set()
        wrapper.close()
        assert [record.getMessage() for record in received] == [
            "snapshot block",
            "snapshot items=['before']",
        ]
        prepared = received[1]
        assert prepared is not original
        assert prepared.args is None
        assert prepared.exc_info is None
        assert original.args[0] is values
    finally:
        allow.set()
        wrapper.close()


def test_async_prepare_format_errors_use_handle_error(monkeypatch):
    output = io.StringIO()
    wrapper = AsyncHandler([logging.StreamHandler(output)])
    errors = []
    monkeypatch.setattr(wrapper, "handleError", errors.append)
    invalid = logging.LogRecord(
        "contracts.invalid", logging.INFO, "", 0, "number=%d", ("invalid",), None
    )
    try:
        wrapper.handle(invalid)
        assert errors == [invalid]
        assert wrapper.dropped_records == 0
        wrapper.handle(
            logging.makeLogRecord({"msg": "valid-after-error", "levelno": logging.INFO})
        )
        wrapper.close()
        assert output.getvalue().strip() == "valid-after-error"
    finally:
        wrapper.close()


def test_async_reconfigure_closes_owned_files_and_unregisters_exit(
    tmp_path, monkeypatch
):
    logging.getLogger().handlers.clear()
    callbacks = []
    monkeypatch.setattr("src.logging.log_handlers.atexit.register", callbacks.append)
    monkeypatch.setattr("src.logging.log_handlers.atexit.unregister", callbacks.remove)
    config = logs.LoggingConfig(
        log_dir=tmp_path, enable_console=False, enable_async=True
    )
    logs.setup_logging(config=config)
    root = logging.getLogger()
    old = root.handlers[0]
    worker = old._listener._thread
    streams = [h.stream for h in old._listener.handlers]
    root.error("pending-before-reconfiguration")
    logs.setup_logging(config=config)
    assert not worker.is_alive()
    assert all(stream.closed for stream in streams)
    assert all(h._closed for h in old._listener.handlers)
    assert old.close not in callbacks
    assert len(callbacks) == 1
    assert "pending-before-reconfiguration" in (tmp_path / "error.log").read_text(
        encoding="utf-8"
    )
    old.close()
    logs.shutdown_logging()
    logs.shutdown_logging()
    assert callbacks == []


def test_async_close_releases_all_sinks_if_one_flush_fails(tmp_path):
    class BrokenFlush(logging.Handler):
        def flush(self):
            raise OSError("flush failed")

    broken = BrokenFlush()
    file_sink = logging.FileHandler(tmp_path / "owned.log")
    stream = file_sink.stream
    wrapper = AsyncHandler([broken, file_sink])
    worker = wrapper._listener._thread
    with pytest.raises(OSError, match="flush failed"):
        wrapper.close()
    assert not worker.is_alive()
    assert broken._closed
    assert file_sink._closed
    assert stream.closed
    assert wrapper._closed
    wrapper.close()


def test_duplicate_filter_uses_rendered_arguments():
    duplicate_filter = DuplicateFilter(suppress_seconds=3)
    first = logging.LogRecord(
        "plugins",
        logging.ERROR,
        "",
        0,
        "加载失败 %s: %s",
        ("first", "invalid-first"),
        None,
    )
    second = logging.LogRecord(
        "plugins",
        logging.ERROR,
        "",
        0,
        "加载失败 %s: %s",
        ("second", "invalid-second"),
        None,
    )
    assert duplicate_filter.filter(first)
    assert duplicate_filter.filter(second)
    assert not duplicate_filter.filter(first)


@pytest.mark.parametrize("asynchronous", [False, True])
def test_distinct_errors_reach_every_sink_with_sensitive_filter_intact(
    tmp_path, capsys, asynchronous
):
    logs.setup_logging(
        config=logs.LoggingConfig(log_dir=tmp_path, enable_json_file=True),
        enable_async=asynchronous,
    )
    logger = logging.getLogger("contracts.errors")
    for plugin in ("first", "second", "second"):
        logger.error("加载失败 %s: %s", plugin, "token=private-value")
    logs.shutdown_logging()
    outputs = [capsys.readouterr().out]
    outputs.extend(
        (tmp_path / name).read_text(encoding="utf-8")
        for name in ("app.log", "error.log", "app.json.log")
    )
    for output in outputs:
        assert output.count("加载失败 first") == 1
        assert output.count("加载失败 second") == 1
        assert "private-value" not in output
