import argparse
import asyncio
import sys

from src.application import Application
from src.views.components.shortcut_manager import start_global_shortcuts_async
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="小智Ai客户端")
    parser.add_argument(
        "--mode",
        choices=["gui", "cli"],
        default="gui",
        help="运行模式：gui(图形界面) 或 cli(命令行)",
    )
    parser.add_argument(
        "--protocol",
        choices=["mqtt", "websocket"],
        default="websocket",
        help="通信协议：mqtt 或 websocket",
    )
    parser.add_argument(
        "--skip-activation",
        action="store_true",
        help="跳过激活流程，直接启动应用（仅用于调试）",
    )
    return parser.parse_args()


async def main():
    """主函数"""
    setup_logging()
    args = parse_args()

    logger.info("启动应用程序")
    app = Application.get_instance()

    # 启动全局快捷键服务
    await start_global_shortcuts_async(logger)

    return await app.run(
        mode=args.mode, protocol=args.protocol, skip_activation=args.skip_activation
    )


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
