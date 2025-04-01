import logging
import os
from logging.handlers import TimedRotatingFileHandler
from colorlog import ColoredFormatter
def setup_logging():
    """配置日志系统"""
    # 创建logs目录（如果不存在）
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 日志文件路径
    log_file = os.path.join(log_dir, 'app.log')
    
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
        when='midnight',  # 每天午夜切割
        interval=1,       # 每1天
        backupCount=30,   # 保留30天的日志
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.suffix = "%Y-%m-%d.log"  # 日志文件后缀格式
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s[%(name)s] - %(levelname)s - %(message)s - %(threadName)s')
    
    # 控制台颜色格式化器
    color_formatter = ColoredFormatter(
        '%(green)s%(asctime)s%(reset)s[%(blue)s%(name)s%(reset)s] - %(log_color)s%(levelname)s%(reset)s - %(green)s%(message)s%(reset)s - %(cyan)s%(threadName)s%(reset)s',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'white',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={
            'asctime': {'green': 'green'},
            'name': {'blue': 'blue'}
        }
    )
    console_handler.setFormatter(color_formatter)
    file_handler.setFormatter(formatter)
    
    # 添加处理器到根日志记录器
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # 设置特定模块的日志级别
    logging.getLogger('Application').setLevel(logging.INFO)
    logging.getLogger('WebsocketProtocol').setLevel(logging.INFO)
    
    # 输出日志配置信息
    logging.info(f"日志系统已初始化，日志文件: {log_file}")
    
    return log_file