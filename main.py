import argparse
import asyncio
import os
import signal
import sys

# 强制 qasync 使用 PySide6
os.environ["QT_API"] = "pyside6"
# 使用 Basic 样式以支持自定义控件
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"


def parse_args():
    """解析命令行参数."""
    from src.constants.system import SystemConstants

    parser = argparse.ArgumentParser(description=SystemConstants.APP_DISPLAY_NAME)
    # 运行模式选择
    # - gui: 图形界面模式，使用 PySide6 + QML
    # - cli: 命令行模式，使用终端交互
    # - gpio: GPIO 按键模式，仅支持 Linux（树莓派），通过物理按键控制
    parser.add_argument(
        "--mode",
        choices=["gui", "cli", "gpio"],
        default="gui",
        help="运行模式：gui(图形界面)、cli(命令行) 或 gpio(GPIO按键，仅Linux)",
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


# 先解析参数，再初始化日志
_args = parse_args()

from src.logging import setup_logging  # noqa: E402

# CLI 模式禁用控制台日志输出（由 CLIDisplay 接管）
setup_logging(enable_console=(_args.mode != "cli"))

from src.bootstrap.container import ServiceContainer  # noqa: E402
from src.constants.system import SystemConstants  # noqa: E402
from src.logging import get_logger  # noqa: E402

logger = get_logger()


async def handle_activation(mode: str) -> bool:
    """处理设备激活流程.

    Args:
        mode: 运行模式，"gui"、"cli" 或 "gpio"

    Returns:
        bool: 激活是否成功
    """
    try:
        from src.activation import ActivationService

        logger.info("开始设备激活流程检查...")
        activation_service = await ActivationService.get_instance()
        init_result = await activation_service.initialize()

        if not init_result.get("success", False):
            logger.error(f"初始化失败: {init_result.get('error', '未知错误')}")
            return False

        if not init_result.get("need_activation_ui", False):
            logger.info("设备已激活，无需激活流程")
            return True

        return await _create_activation(mode, activation_service, init_result).run()

    except Exception as e:
        logger.error(f"激活流程异常: {e}", exc_info=True)
        return False


def _create_activation(mode: str, activation_service, init_result: dict):
    """创建激活处理器工厂.

    GUI 使用 PySide6 窗口，CLI/GPIO 共用终端交互。
    init_result 传入避免重复调用 initialize()。
    """
    if mode == "gui":
        from src.ui.gui import GUIActivation

        return GUIActivation(activation_service, init_result)
    else:
        # cli / gpio 同走 CLIActivation
        from src.ui.cli import CLIActivation

        return CLIActivation(activation_service, init_result)


async def start_app(mode: str, protocol: str, skip_activation: bool) -> int:
    """启动应用的统一入口."""
    global _container  # 用于 SIGINT 处理
    logger.info(f"启动{SystemConstants.APP_DISPLAY_NAME}")

    # 处理激活流程
    if not skip_activation:
        activation_success = await handle_activation(mode)
        if not activation_success:
            logger.error("设备激活失败，程序退出")
            return 1
    else:
        logger.warning("跳过激活流程（调试模式）")

    # 创建并启动应用程序
    _container = ServiceContainer()
    return await _container.run(mode=mode, protocol=protocol)


# 全局容器引用，用于 SIGINT 处理
_container = None


if __name__ == "__main__":
    exit_code = 1
    try:
        # 使用已解析的参数
        args = _args

        # 检测Wayland环境并设置Qt平台插件配置
        import os

        is_wayland = (
            os.environ.get("WAYLAND_DISPLAY")
            or os.environ.get("XDG_SESSION_TYPE") == "wayland"
        )

        if args.mode == "gui" and is_wayland:
            if "QT_QPA_PLATFORM" not in os.environ:
                os.environ["QT_QPA_PLATFORM"] = "wayland;xcb"
                logger.info("Wayland环境：设置QT_QPA_PLATFORM=wayland;xcb")
            os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")
            logger.info("Wayland环境检测完成，已应用兼容性配置")

        # 信号处理
        try:
            if hasattr(signal, "SIGTRAP"):
                signal.signal(signal.SIGTRAP, signal.SIG_IGN)
        except Exception:
            pass

        if args.mode == "gui":
            # GUI 模式：使用 PySide6 + qasync
            try:
                import qasync
                from PySide6.QtWidgets import QApplication
            except ImportError as e:
                logger.error(
                    "GUI 模式需要 PySide6 + qasync,但未安装。请运行:\n"
                    "  uv sync --extra gui          # 推荐 (uv 用户)\n"
                    "  pip install '.[gui]'         # pip 用户\n"
                    "若改用 CLI 或 GPIO 模式: python main.py --mode cli  "
                    f"(原始错误: {e})"
                )
                sys.exit(1)

            qt_app = QApplication.instance() or QApplication(sys.argv)
            qt_app.setQuitOnLastWindowClosed(False)

            loop = qasync.QEventLoop(qt_app)
            asyncio.set_event_loop(loop)
            logger.info("已创建 PySide6 + qasync 事件循环")

            # 设置 SIGINT 信号处理 - 通过 TaskManager 请求关闭
            shutdown_state = {"requested": False}

            def handle_sigint(*_):
                if shutdown_state["requested"]:
                    return
                shutdown_state["requested"] = True
                logger.info("收到 SIGINT 信号，正在退出...")

                # 通过 TaskManager 请求优雅关闭
                try:
                    if _container and _container.tasks:
                        _container.tasks.request_shutdown()
                    else:
                        # 容器未就绪，直接退出 Qt
                        if loop.is_running():
                            loop.call_soon_threadsafe(qt_app.quit)
                except Exception:
                    qt_app.quit()

            signal.signal(signal.SIGINT, handle_sigint)

            try:
                with loop:
                    exit_code = loop.run_until_complete(
                        start_app(args.mode, args.protocol, args.skip_activation)
                    )
            except RuntimeError as e:
                # 捕获 qasync 的 "Event loop stopped before Future completed" 错误
                if "Event loop stopped before Future completed" in str(e):
                    logger.debug("事件循环已正常终止")
                    exit_code = 0
                else:
                    raise
        else:
            # CLI / GPIO 模式：标准 asyncio
            exit_code = asyncio.run(
                start_app(args.mode, args.protocol, args.skip_activation)
            )

    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        exit_code = 0
    except Exception as e:
        logger.error(f"程序异常退出: {e}", exc_info=True)
        exit_code = 1
    finally:
        sys.exit(exit_code)
