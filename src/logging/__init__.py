import inspect
import logging
import sys
from pathlib import Path
from typing import Any, Optional, Union

from .log_config import LoggingConfig, LoggingConfigManager
from .context import (
    LogContext,
    clear_all_context,
    copy_context_to_thread,
    get_all_context,
    get_request_id,
    get_session_id,
    get_trace_id,
    get_user_id,
    set_context,
    set_request_id,
    set_session_id,
    set_trace_id,
    set_user_id,
    with_context,
    with_trace,
)
from .filters import (
    ContextFilter,
    DuplicateFilter,
    ModuleFilter,
    RateLimitFilter,
    SensitiveDataFilter,
)
from .formatters import ColoredFormatter, JsonFormatter, SimpleFormatter
from .log_handlers import (
    AsyncHandler,
    BufferedHandler,
    CallbackHandler,
    LevelSeparatedHandler,
    TimeSizeRotatingFileHandler,
)

# 模块版本
__version__ = "1.0.0"

# 日志系统是否已初始化
_initialized = False

# 导出的公共接口
__all__ = [
    # 主要函数
    "setup_logging",
    "get_logger",
    "shutdown_logging",
    # 配置
    "LoggingConfig",
    "LoggingConfigManager",
    # 上下文
    "LogContext",
    "set_trace_id",
    "get_trace_id",
    "set_request_id",
    "get_request_id",
    "set_user_id",
    "get_user_id",
    "set_session_id",
    "get_session_id",
    "set_context",
    "get_all_context",
    "clear_all_context",
    "with_trace",
    "with_context",
    "copy_context_to_thread",
    # 过滤器
    "SensitiveDataFilter",
    "ContextFilter",
    "ModuleFilter",
    "RateLimitFilter",
    "DuplicateFilter",
    # 格式化器
    "ColoredFormatter",
    "JsonFormatter",
    "SimpleFormatter",
    # 处理器
    "TimeSizeRotatingFileHandler",
    "AsyncHandler",
    "BufferedHandler",
    "LevelSeparatedHandler",
    "CallbackHandler",
]


def setup_logging(
    level: Optional[str] = None,
    log_dir: Union[str, Path, None] = None,
    enable_console: bool = True,
    enable_file: bool = True,
    enable_json: bool = False,
    enable_async: bool = False,
    enable_sensitive_filter: bool = True,
    config: Optional[LoggingConfig] = None,
) -> Optional[Path]:
    """初始化日志系统.

    Args:
        level: 日志级别，默认根据环境自动设置
        log_dir: 日志目录，默认为项目根目录下的 logs
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        enable_json: 是否启用 JSON 格式的文件输出
        enable_async: 是否启用异步日志
        enable_sensitive_filter: 是否启用敏感信息过滤
        config: 自定义配置对象

    Returns:
        日志文件路径（如果启用了文件输出）
    """
    global _initialized

    # 获取或创建配置
    if config is None:
        config_manager = LoggingConfigManager.get_instance()
        config = config_manager.config

    # 应用参数覆盖
    if level:
        config.level = level.upper()
    if log_dir:
        config.log_dir = Path(log_dir)
    config.enable_console = enable_console
    config.enable_file = enable_file
    config.enable_json_file = enable_json
    config.enable_async = enable_async
    config.enable_sensitive_filter = enable_sensitive_filter

    # 确保日志目录存在
    if config.log_dir:
        config.log_dir.mkdir(parents=True, exist_ok=True)

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.level, logging.INFO))

    # 清除已有的处理器
    if root_logger.handlers:
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

    # 创建过滤器
    filters = [ContextFilter(), DuplicateFilter(suppress_seconds=3.0)]
    if config.enable_sensitive_filter:
        filters.append(SensitiveDataFilter(patterns=config.sensitive_patterns))

    # 创建处理器列表
    handlers: list[logging.Handler] = []

    # 控制台处理器
    if config.enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.level, logging.INFO))
        console_handler.setFormatter(
            ColoredFormatter(
                use_colors=True,
                show_trace_id=True,
                show_thread=True,
            )
        )
        for f in filters:
            console_handler.addFilter(f)
        handlers.append(console_handler)

    # 文件处理器
    log_file = None
    if config.enable_file and config.log_dir:
        log_file = config.log_dir / config.log_file

        file_handler = TimeSizeRotatingFileHandler(
            log_file,
            when=config.rotation_when,
            interval=config.rotation_interval,
            max_bytes=config.max_bytes,
            backup_count=config.backup_count,
            compress=True,
        )
        file_handler.setLevel(getattr(logging, config.level, logging.INFO))
        file_handler.setFormatter(
            SimpleFormatter(
                fmt="%(asctime)s | %(levelname)-8s | [%(trace_id)s] | %(name)s | %(message)s | %(threadName)s",
                include_trace_id=True,
            )
        )
        for f in filters:
            file_handler.addFilter(f)
        handlers.append(file_handler)

    # 错误日志文件处理器
    if config.enable_error_file and config.log_dir:
        error_file = config.log_dir / config.error_log_file

        error_handler = TimeSizeRotatingFileHandler(
            error_file,
            when=config.rotation_when,
            interval=config.rotation_interval,
            max_bytes=config.max_bytes,
            backup_count=config.backup_count,
            compress=True,
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(
            SimpleFormatter(
                fmt="%(asctime)s | %(levelname)-8s | [%(trace_id)s] | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                include_trace_id=True,
            )
        )
        for f in filters:
            error_handler.addFilter(f)
        handlers.append(error_handler)

    # JSON 文件处理器
    if config.enable_json_file and config.log_dir:
        json_file = config.log_dir / "app.json.log"

        json_handler = TimeSizeRotatingFileHandler(
            json_file,
            when=config.rotation_when,
            interval=config.rotation_interval,
            max_bytes=config.max_bytes,
            backup_count=config.backup_count,
            compress=True,
        )
        json_handler.setLevel(getattr(logging, config.level, logging.INFO))
        json_handler.setFormatter(JsonFormatter())
        for f in filters:
            json_handler.addFilter(f)
        handlers.append(json_handler)

    # 使用异步处理器包装
    if config.enable_async and handlers:
        async_handler = AsyncHandler(handlers)
        root_logger.addHandler(async_handler)
    else:
        for handler in handlers:
            root_logger.addHandler(handler)

    # 设置第三方库日志级别
    for module_name, level_str in config.third_party_levels.items():
        logging.getLogger(module_name).setLevel(
            getattr(logging, level_str, logging.WARNING)
        )

    _initialized = True

    # 记录日志系统初始化完成
    logger = logging.getLogger(__name__)
    logger.info("日志系统已初始化")
    if log_file:
        logger.debug(f"日志文件: {log_file}")

    return log_file


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取配置好的日志记录器.

    Args:
        name: 日志记录器名称。如果不传，自动使用调用者的模块名。

    Returns:
        配置好的日志记录器

    示例:
        logger = get_logger()  # 自动注入模块名
        logger = get_logger("custom.name")  # 自定义名称
    """
    if name is None:
        # 自动获取调用者的模块名
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "__main__")
        else:
            name = "__main__"

    logger = logging.getLogger(name)

    # 如果日志系统未初始化，添加一个基本的控制台处理器
    if not _initialized and not logger.handlers and not logging.root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

    return logger


def shutdown_logging() -> None:
    """关闭日志系统，清理资源.

    在应用退出时调用，确保所有日志都被写入。
    """
    global _initialized

    logging.shutdown()
    _initialized = False


# 便捷函数：创建带上下文的 logger
class ContextLogger:
    """
    带上下文支持的 Logger 包装器.
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log_with_context(
        self, level: int, msg: str, *args: Any, **kwargs: Any
    ) -> None:
        """
        带上下文信息记录日志.
        """
        extra = kwargs.pop("extra", {})
        extra.update(get_all_context())
        kwargs["extra"] = extra
        self._logger.log(level, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log_with_context(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log_with_context(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log_with_context(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self._log_with_context(logging.CRITICAL, msg, *args, **kwargs)

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        kwargs["exc_info"] = True
        self._log_with_context(logging.ERROR, msg, *args, **kwargs)


def get_context_logger(name: Optional[str] = None) -> ContextLogger:
    """获取带上下文支持的日志记录器.

    Args:
        name: 日志记录器名称。如果不传，自动使用调用者的模块名。

    Returns:
        带上下文支持的日志记录器
    """
    if name is None:
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "__main__")
        else:
            name = "__main__"
    return ContextLogger(get_logger(name))
