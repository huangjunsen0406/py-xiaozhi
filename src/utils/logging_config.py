import logging
from logging.handlers import TimedRotatingFileHandler

from colorlog import ColoredFormatter


def setup_logging():
    """
    配置日志系统.
    """
    from .resource_finder import get_project_root

    # 使用resource_finder获取项目根目录并创建logs目录
    project_root = get_project_root()
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    # 日志文件路径
    log_file = log_dir / "app.log"

    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # 设置根日志级别

    # 清除已有的处理器（避免重复添加）
    if root_logger.handlers:
        root_logger.handlers.clear()

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 创建按天切割的文件处理器
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",  # 每天午夜切割
        interval=1,  # 每1天
        backupCount=30,  # 保留30天的日志
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.suffix = "%Y-%m-%d.log"  # 日志文件后缀格式

    # 创建格式化器
    formatter = logging.Formatter(
        "%(asctime)s[%(name)s] - %(levelname)s - %(message)s - %(threadName)s"
    )

    # 控制台颜色格式化器
    color_formatter = ColoredFormatter(
        "%(green)s%(asctime)s%(reset)s[%(blue)s%(name)s%(reset)s] - "
        "%(log_color)s%(levelname)s%(reset)s - %(green)s%(message)s%(reset)s - "
        "%(cyan)s%(threadName)s%(reset)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "white",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
        secondary_log_colors={"asctime": {"green": "green"}, "name": {"blue": "blue"}},
    )
    console_handler.setFormatter(color_formatter)
    file_handler.setFormatter(formatter)

    # 添加处理器到根日志记录器
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 输出日志配置信息
    logging.info("日志系统已初始化，日志文件: %s", log_file)

    return log_file


def get_logger(name):
    """获取统一配置的日志记录器.

    Args:
        name: 日志记录器名称，通常是模块名

    Returns:
        logging.Logger: 配置好的日志记录器

    示例:
        logger = get_logger(__name__)
        logger.info("这是一条信息")
        logger.error("出错了: %s", error_msg)
    """
    logger = logging.getLogger(name)

    # 添加一些辅助方法
    def log_error_with_exc(msg, *args, **kwargs):
        """
        记录错误并自动包含异常堆栈.
        """
        kwargs["exc_info"] = True
        logger.error(msg, *args, **kwargs)

    # 添加到日志记录器
    logger.error_exc = log_error_with_exc

    return logger
