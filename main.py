import argparse
import logging
import sys
import signal
from src.application import Application
from src.utils.logging_config import setup_logging, get_logger

logger = get_logger(__name__)
# 配置日志

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='小智ai客户端')
    
    # 添加界面模式参数
    parser.add_argument(
        '--mode', 
        choices=['gui', 'cli'],
        default='gui',
        help='运行模式：gui(图形界面) 或 cli(命令行)'
    )
    
    # 添加协议选择参数
    parser.add_argument(
        '--protocol', 
        choices=['mqtt', 'websocket'], 
        default='websocket',
        help='通信协议：mqtt 或 websocket'
    )
    
    return parser.parse_args()

def signal_handler(sig, frame):
    """处理Ctrl+C信号"""
    logger.info("接收到中断信号，正在关闭...")
    app = Application.get_instance()
    app.shutdown()
    sys.exit(0)


def main():
    """程序入口点"""
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    # 解析命令行参数
    args = parse_args()
    try:
        # 日志
        setup_logging()
        # 创建并运行应用程序
        app = Application.get_instance()

        logger.info("应用程序已启动，按Ctrl+C退出")

        # 启动应用，传入参数
        app.run(
            mode=args.mode,
            protocol=args.protocol
        )

    except Exception as e:
        logger.error(f"程序发生错误: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())