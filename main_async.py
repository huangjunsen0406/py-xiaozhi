import argparse
import asyncio
import sys
import signal
import io
from src.async_application import AsyncApplication
from src.utils.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


def parse_args():
    """解析命令行参数"""
    # 确保sys.stdout和sys.stderr不为None
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

    parser = argparse.ArgumentParser(description='小智Ai客户端 (异步版本)')

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


def signal_handler():
    """处理Ctrl+C信号"""
    logger.info("接收到中断信号，正在关闭...")
    app = AsyncApplication.get_instance()
    app.running = False


async def main():
    """程序入口点"""
    try:
        # 日志
        setup_logging()

        # 注册信号处理器（仅在Unix系统上）
        if sys.platform != 'win32':
            loop = asyncio.get_event_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(sig, signal_handler)
        else:
            # Windows上使用不同的信号处理方式
            def windows_signal_handler(sig, frame):
                # sig和frame参数由signal模块传入但在这里不使用
                signal_handler()
            signal.signal(signal.SIGINT, windows_signal_handler)

        # 解析命令行参数
        args = parse_args()

        # 创建并运行应用程序
        app = AsyncApplication.get_instance()

        logger.info("应用程序已启动，按Ctrl+C退出")

        # 启动应用，传入参数
        await app.run(
            mode=args.mode,
            protocol=args.protocol
        )

        # 如果是GUI模式，启动Qt事件循环
        if args.mode == 'gui':
            try:
                from PyQt5.QtWidgets import QApplication
                qt_app = QApplication.instance()
                if qt_app:
                    logger.info("开始Qt事件循环")

                    # 简单的事件循环集成
                    while app.running:
                        # 处理Qt事件
                        qt_app.processEvents()
                        # 处理asyncio任务
                        await asyncio.sleep(0.01)  # 减少延迟

                    logger.info("Qt事件循环结束")
                else:
                    logger.error("无法获取QApplication实例")
            except ImportError:
                logger.warning("PyQt5未安装，无法启动Qt事件循环")
            except Exception as e:
                logger.error(f"Qt事件循环出错: {e}", exc_info=True)
        else:
            # CLI模式，保持运行直到收到信号
            try:
                while app.running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("CLI模式被取消")

        # 关闭应用程序
        await app.shutdown()

    except Exception as e:
        logger.error(f"程序发生错误: {e}", exc_info=True)
        return 1

    return 0


def run_async_main():
    """运行异步主函数的包装器"""
    if sys.platform == 'win32':
        # Windows上设置事件循环策略
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        return asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0


if __name__ == "__main__":
    sys.exit(run_async_main())
