import argparse
import asyncio
import io
import sys

# 添加qasync支持
try:
    import qasync
    from PyQt5.QtWidgets import QApplication
    QASYNC_AVAILABLE = True
except ImportError:
    QASYNC_AVAILABLE = False

from src.application import Application
from src.utils.logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def parse_args():
    """解析命令行参数"""
    # 确保sys.stdout和sys.stderr不为None
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()

    parser = argparse.ArgumentParser(description="小智Ai客户端 (异步版本)")

    # 添加界面模式参数
    parser.add_argument(
        "--mode",
        choices=["gui", "cli"],
        default="gui",
        help="运行模式：gui(图形界面) 或 cli(命令行)",
    )

    # 添加协议选择参数
    parser.add_argument(
        "--protocol",
        choices=["mqtt", "websocket"],
        default="websocket",
        help="通信协议：mqtt 或 websocket",
    )

    return parser.parse_args()


async def main_async():
    """异步主函数"""
    # 解析命令行参数
    args = parse_args()
    
    try:
        # 配置日志
        setup_logging()
        
        # 创建并运行应用程序
        app = Application.get_instance()
        
        logger.info("异步应用程序已启动，按Ctrl+C退出")
        
        # 启动应用，传入参数
        await app.run(mode=args.mode, protocol=args.protocol)
        
        # 等待应用程序运行（GUI和CLI都需要）
        while app.running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("接收到中断信号")
    except Exception as e:
        logger.error(f"程序发生错误: {e}", exc_info=True)
        return 1
    finally:
        # 确保应用程序正确关闭
        try:
            app = Application.get_instance()
            await app.shutdown()
        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}")

    return 0


def main():
    """同步主函数入口"""
    try:
        args = parse_args()
        
        if args.mode == "gui":
            # GUI模式：使用qasync集成Qt和asyncio
            if not QASYNC_AVAILABLE:
                logger.error("GUI模式需要qasync库，请安装: pip install qasync")
                return 1
                
            # 创建QApplication
            app = QApplication(sys.argv)
            
            # 创建qasync事件循环
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)
            
            try:
                # 运行异步主函数
                with loop:
                    task = loop.create_task(main_async())
                    
                    # 启动Qt事件循环，这会运行直到应用关闭
                    loop.run_until_complete(task)
                    
            except KeyboardInterrupt:
                logger.info("程序被用户中断")
                return 0
            except Exception as e:
                logger.error(f"GUI程序异常退出: {e}", exc_info=True)
                return 1
            finally:
                # 确保事件循环正确关闭
                try:
                    loop.close()
                except Exception:
                    pass
        else:
            # CLI模式：使用标准asyncio
            return asyncio.run(main_async())
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())