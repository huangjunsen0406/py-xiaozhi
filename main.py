import argparse
import asyncio
import sys
import time

from src.application import Application
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def parse_args():
    """
    解析命令行参数.
    """
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


async def handle_activation(mode: str) -> bool:
    """处理设备激活流程.

    Args:
        mode: 运行模式，"gui"或"cli"

    Returns:
        bool: 激活是否成功
    """
    try:
        from src.core.system_initializer import SystemInitializer

        logger.info("开始设备激活流程检查...")

        # 创建SystemInitializer实例
        system_initializer = SystemInitializer()

        # 运行初始化流程
        init_result = await system_initializer.run_initialization()

        # 如果不需要激活界面，直接返回结果
        if not init_result.get("need_activation_ui", False):
            logger.info("无需显示激活界面，设备已激活")
            return True

        logger.info("需要显示激活界面，准备激活流程")

        # 需要激活界面，根据模式处理
        if mode == "gui":
            # GUI模式需要先创建QApplication
            try:
                # 导入必要的库
                import qasync
                from PyQt5.QtCore import QTimer
                from PyQt5.QtWidgets import QApplication

                # 创建临时QApplication实例
                logger.info("创建临时QApplication实例用于激活流程")
                temp_app = QApplication(sys.argv)

                # 创建事件循环
                loop = qasync.QEventLoop(temp_app)
                asyncio.set_event_loop(loop)

                # 创建Future来等待激活完成（使用新的事件循环）
                activation_future = loop.create_future()

                # 创建激活窗口
                from src.views.activation.activation_window import ActivationWindow

                activation_window = ActivationWindow(system_initializer)

                # 设置激活完成回调
                def on_activation_completed(success: bool):
                    logger.info(f"激活完成，结果: {success}")
                    if not activation_future.done():
                        activation_future.set_result(success)

                # 设置窗口关闭回调
                def on_window_closed():
                    logger.info("激活窗口被关闭")
                    if not activation_future.done():
                        activation_future.set_result(False)

                # 连接信号
                activation_window.activation_completed.connect(on_activation_completed)
                activation_window.window_closed.connect(on_window_closed)

                # 显示激活窗口
                activation_window.show()
                logger.info("激活窗口已显示")

                # 确保窗口显示出来
                QTimer.singleShot(100, lambda: logger.info("激活窗口显示确认"))

                # 等待激活完成
                try:
                    logger.info("开始等待激活完成")
                    activation_success = loop.run_until_complete(activation_future)
                    logger.info(f"激活流程完成，结果: {activation_success}")
                except Exception as e:
                    logger.error(f"激活流程异常: {e}")
                    activation_success = False

                # 关闭窗口
                activation_window.close()

                # 销毁临时QApplication
                logger.info("激活流程完成，销毁临时QApplication实例")
                activation_window = None
                temp_app = None

                # 强制垃圾回收，确保QApplication被销毁
                import gc

                gc.collect()

                # 等待一小段时间确保资源释放（使用同步sleep）
                logger.info("等待资源释放...")
                time.sleep(0.5)

                return activation_success

            except ImportError as e:
                logger.error(f"GUI模式需要qasync和PyQt5库: {e}")
                return False
        else:
            # CLI模式
            from src.views.activation.cli_activation import CLIActivation

            cli_activation = CLIActivation(system_initializer)
            return await cli_activation.run_activation_process()

    except Exception as e:
        logger.error(f"激活流程异常: {e}", exc_info=True)
        return False


async def main():
    """
    主函数.
    """
    setup_logging()
    args = parse_args()

    logger.info("启动小智AI客户端")

    # 处理激活流程
    if not args.skip_activation:
        activation_success = await handle_activation(args.mode)
        if not activation_success:
            logger.error("设备激活失败，程序退出")
            return 1
    else:
        logger.warning("跳过激活流程（调试模式）")

    # 创建并启动应用程序
    app = Application.get_instance()
    return await app.run(mode=args.mode, protocol=args.protocol)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        sys.exit(1)
