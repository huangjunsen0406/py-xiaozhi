"""Application entry point shared by source, wheel and frozen launches.

Importing this module does not parse arguments, initialize configuration or load Qt.
"""

import argparse
import asyncio
import locale
import logging
import os
import signal
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bootstrap.container import ServiceContainer

logger = logging.getLogger(__name__)
_container: "ServiceContainer | None" = None


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse only the supplied arguments, or sys.argv for a command-line launch."""
    from src.constants.system import SystemConstants

    parser = argparse.ArgumentParser(description=SystemConstants.APP_DISPLAY_NAME)
    parser.add_argument(
        "--mode",
        choices=["gui", "cli", "tui", "gpio"],
        default="gui",
        help="运行模式（默认 gui）：gui / cli / tui(全屏终端) / gpio(仅Linux)",
    )
    parser.add_argument(
        "--protocol",
        choices=["mqtt", "websocket"],
        default="websocket",
        metavar="PROTOCOL",
        help="通信协议：mqtt 或 websocket（默认 websocket）",
    )
    parser.add_argument(
        "--skip-activation",
        action="store_true",
        help="跳过激活流程，直接启动应用（仅用于调试）",
    )
    return parser.parse_args(argv)


def _configure_environment(mode: str) -> None:
    """Apply startup settings before importing the runtime or Qt."""
    if sys.platform == "win32":
        os.environ["PYTHONIOENCODING"] = "utf-8"
        try:
            locale.setlocale(locale.LC_ALL, ".UTF-8")
        except locale.Error:
            pass
    os.environ["QSG_RHI_BACKEND"] = "opengl"
    os.environ["QT_API"] = "pyside6"
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    is_wayland = (
        os.environ.get("WAYLAND_DISPLAY")
        or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )
    if mode == "gui" and is_wayland:
        os.environ.setdefault("QT_QPA_PLATFORM", "wayland;xcb")
        os.environ.setdefault("QT_WAYLAND_DISABLE_WINDOWDECORATION", "1")


async def handle_activation(mode: str, config=None) -> bool:
    """Run the existing activation flow for the selected UI."""
    try:
        from src.activation import ActivationService, create_activation_ui

        logger.info("开始设备激活流程检查...")
        service = await ActivationService.create(config=config)
        result = await service.initialize()
        if not result.get("success", False):
            logger.error("初始化失败: %s", result.get("error", "未知错误"))
            return False
        if not result.get("need_activation_ui", False):
            logger.info("设备已激活，无需激活流程")
            return True
        return await create_activation_ui(mode, service, result).run()
    except Exception as exc:
        logger.error("激活流程异常: %s", exc, exc_info=True)
        return False


async def start_app(
    mode: str, protocol: str, skip_activation: bool, config=None
) -> int:
    """Create the runtime only after configuration and logging are ready."""
    from src.bootstrap.container import ServiceContainer
    from src.constants.system import SystemConstants

    global _container
    logger.info("启动%s", SystemConstants.APP_DISPLAY_NAME)
    try:
        if not skip_activation:
            activated = await handle_activation(mode, config=config)
            if not activated:
                logger.error("设备激活失败，程序退出")
                return 1
        else:
            logger.warning("跳过激活流程（调试模式）")
        _container = ServiceContainer(config=config)
        return await _container.run(mode=mode, protocol=protocol)
    finally:
        if mode == "gui":
            try:
                from PySide6.QtWidgets import QApplication

                app = QApplication.instance()
                if app is not None:
                    app.quit()
            except ImportError:
                pass


def _run(args: argparse.Namespace, config=None) -> int:
    """Choose an event loop and restore signal handlers after it exits."""
    previous_signals = {}
    requested = False
    startup_task = None

    async def run_startup():
        nonlocal startup_task
        startup_task = asyncio.current_task()
        if requested:
            return 0
        try:
            result = await start_app(
                args.mode, args.protocol, args.skip_activation, config=config
            )
        except asyncio.CancelledError:
            if requested:
                return 0
            raise
        # Some activation services translate cancellation to False internally.
        return 0 if requested else result

    def request_shutdown():
        if _container and _container.tasks:
            _container.tasks.request_shutdown()
        elif startup_task is not None:
            startup_task.cancel()

    def install_signal(sig, handler):
        previous_signals[sig] = signal.getsignal(sig)
        signal.signal(sig, handler)

    try:
        if hasattr(signal, "SIGTRAP"):
            try:
                install_signal(signal.SIGTRAP, signal.SIG_IGN)
            except (OSError, ValueError):
                pass
        if args.mode == "gui":
            try:
                import qasync
                from PySide6.QtWidgets import QApplication
            except ImportError as exc:
                logger.error(
                    "GUI 模式需要 PySide6 + qasync。请安装: pip install 'py-xiaozhi[gui]' "
                    "或在源码目录执行 uv sync --extra gui。"
                    "无 GUI 时可用 --mode cli。原始错误: %s",
                    exc,
                )
                return 1
            qt_app = QApplication.instance() or QApplication([sys.argv[0]])
            qt_app.setQuitOnLastWindowClosed(False)
            loop = qasync.QEventLoop(qt_app)
            asyncio.set_event_loop(loop)
            requested = False

            def handle_sigint(*_):
                nonlocal requested
                if requested:
                    return
                requested = True
                logger.info("收到 SIGINT 信号，正在退出...")
                request_shutdown()

            install_signal(signal.SIGINT, handle_sigint)
            try:
                with loop:
                    return loop.run_until_complete(run_startup())
            except RuntimeError as exc:
                if "Event loop stopped before Future completed" in str(exc):
                    logger.debug("事件循环已正常终止")
                    return 0
                raise
        if args.mode == "tui":
            try:
                import textual  # noqa: F401
            except ImportError as exc:
                logger.error(
                    "TUI 模式需要 textual。请安装: pip install 'py-xiaozhi[tui]' "
                    "或在源码目录执行 uv sync --extra tui。原始错误: %s",
                    exc,
                )
                return 1
        requested = False

        def handle_sigint_cli(*_):
            nonlocal requested
            if requested:
                logger.warning("再次收到 SIGINT，强制退出")
                os._exit(130)
            requested = True
            logger.info("收到 SIGINT 信号，正在退出...")
            request_shutdown()

        install_signal(signal.SIGINT, handle_sigint_cli)
        return asyncio.run(run_startup())
    finally:
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the application and return its exit status.

    ArgumentParser handles --help and invalid arguments before any initialization.
    """
    args = parse_args(argv)
    global _container
    _container = None
    try:
        _configure_environment(args.mode)
        from src.utils.config_manager import initialize_config

        config = initialize_config()
        from src.logging import load_logging_config, setup_logging

        logging_config = load_logging_config(config)
        setup_logging(
            enable_console=args.mode not in ("cli", "tui"),
            config=logging_config,
        )
        return _run(args, config=config)
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
        return 0
    except Exception as exc:
        logger.error("程序异常退出: %s", exc, exc_info=True)
        return 1
    finally:
        _container = None
