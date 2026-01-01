# -*- coding: utf-8 -*-
"""CLI 终端显示界面.

提供终端 TUI 界面，包含:
- 状态仪表盘（顶部框架）
- 日志显示区域
- 命令输入区域
"""

import asyncio
import logging
import os
import shutil
import sys
from collections import deque
from typing import Callable, Optional

from src.constants.system import SystemConstants
from src.logging import get_logger

logger = get_logger()


class CLIDisplay:
    """CLI 终端显示界面."""

    def __init__(self):
        self.running = True
        self._use_ansi = sys.stdout.isatty()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_drawn_rows = 0
        self._render_lock = None
        self._initialized = False  # 是否已初始化
        self._log_handler_installed = False  # 日志处理器是否已安装

        # 仪表盘数据
        self._dash_status = "待命"
        self._dash_connected = False
        self._dash_text = ""
        self._dash_emotion = "neutral"
        self._dash_auto_mode = False

        # 布局设置
        self._input_area_lines = 3  # 输入区行数
        self._dashboard_lines = 8  # 显示区最少行数

        # ANSI 样式
        self._ansi = {
            "reset": "\x1b[0m",
            "bold": "\x1b[1m",
            "dim": "\x1b[2m",
            "blue": "\x1b[34m",
            "cyan": "\x1b[36m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "magenta": "\x1b[35m",
            "red": "\x1b[31m",
        }

        # 回调函数
        self._on_command: Optional[Callable[[str], None]] = None

        # 日志缓冲
        self._log_lines: deque[str] = deque(maxlen=6)

        # 命令队列
        self._command_queue: asyncio.Queue = asyncio.Queue()

    def set_command_callback(self, callback: Callable[[str], None]):
        """设置命令回调."""
        self._on_command = callback

    def intercept_logging(self):
        """尽早拦截日志输出（在 start 之前调用）.

        模仿旧实现：在 __init__ 阶段就移除 StreamHandler 并安装自定义处理器。
        """
        # 先移除所有 StreamHandler
        self._remove_stream_handlers()
        # 再安装我们的日志处理器
        self._install_log_handler()

    async def start(self):
        """启动 CLI 显示."""
        # 先获取事件循环
        self._loop = asyncio.get_running_loop()
        self._render_lock = asyncio.Lock()

        # 确保日志已被拦截（如果还没有调用 intercept_logging）
        if not hasattr(self, "_original_add_handler"):
            self.intercept_logging()

        # 清屏并初始化界面
        if self._use_ansi:
            # 彻底清屏：清除屏幕 + 清除滚动缓冲区 + 光标移到左上角
            sys.stdout.write("\x1b[3J\x1b[2J\x1b[H")
            sys.stdout.flush()

        # 标记已初始化
        self._initialized = True

        # 初始化屏幕显示
        await self._init_screen()

        # 启动输入循环
        try:
            await self._keyboard_input_loop()
        except asyncio.CancelledError:
            pass

    async def close(self):
        """关闭 CLI 显示."""
        self.running = False

        # 恢复标准日志
        self._restore_logging()

        # 清屏
        if self._use_ansi:
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()

        print("正在关闭应用...\n")

    # ========== 状态更新 ==========

    def update_status(self, status: str, connected: bool = True):
        """更新状态."""
        self._dash_status = status
        self._dash_connected = connected
        self._schedule_render()

    def update_text(self, text: str):
        """更新文本显示."""
        if text and text.strip():
            self._dash_text = text.strip()
            self._schedule_render()

    def update_emotion(self, emotion: str):
        """更新表情."""
        self._dash_emotion = emotion
        self._schedule_render()

    def update_auto_mode(self, auto_mode: bool):
        """更新自动模式状态."""
        self._dash_auto_mode = auto_mode
        self._schedule_render()

    def add_log(self, message: str):
        """添加日志."""
        self._log_lines.append(message)
        self._schedule_render()

    def _schedule_render(self):
        """调度渲染."""
        if not self._initialized:
            return
        if self._loop and self._use_ansi and self.running:
            try:
                if self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._do_render)
            except Exception:
                pass

    def _do_render(self):
        """执行渲染（在事件循环中调用）."""
        if not self._initialized:
            return
        try:
            asyncio.create_task(self._safe_render())
        except Exception:
            pass

    async def _safe_render(self):
        """安全渲染（带锁）."""
        if self._render_lock is None:
            return
        async with self._render_lock:
            await self._render_dashboard()

    # ========== 屏幕渲染 ==========

    async def _init_screen(self):
        """初始化屏幕."""
        # 注意：清屏已在 start() 中完成
        await self._render_dashboard(full=True)
        await self._render_input_area()

    async def _render_dashboard(self, full: bool = False):
        """渲染仪表盘."""

        def trunc(s: str, limit: int = 60) -> str:
            return s if len(s) <= limit else s[: limit - 1] + "…"

        # 构建状态行
        mode_text = "自动" if self._dash_auto_mode else "手动"
        conn_text = "已连接" if self._dash_connected else "未连接"

        lines = [
            f"状态: {trunc(self._dash_status)}",
            f"连接: {conn_text} | 模式: {mode_text}",
            f"表情: {self._dash_emotion}",
            f"文本: {trunc(self._dash_text)}",
        ]

        # 不显示日志行（日志仍被拦截，只是不在界面显示）

        if not self._use_ansi:
            print(f"\r{lines[0]}        ", end="", flush=True)
            return

        cols, rows = self._term_size()
        usable_rows = max(5, rows - self._input_area_lines)

        # 样式函数
        def style(s: str, *names: str) -> str:
            if not self._use_ansi:
                return s
            prefix = "".join(self._ansi.get(n, "") for n in names)
            return f"{prefix}{s}{self._ansi['reset']}"

        title = style(f" {SystemConstants.APP_DISPLAY_NAME} ", "bold", "cyan")

        # 框架
        top_bar = "┌" + ("─" * (max(2, cols - 2))) + "┐"
        title_line = "│" + title.center(max(2, cols - 2) + 14) + "│"  # +14 补偿 ANSI
        sep_line = "├" + ("─" * (max(2, cols - 2))) + "┤"
        bottom_bar = "└" + ("─" * (max(2, cols - 2))) + "┘"

        # 内容区
        body_rows = max(1, usable_rows - 4)
        body = []
        for i in range(body_rows):
            if i < len(lines):
                text = lines[i]
                if i == 0:
                    text = style(text, "green")
                elif i == 1:
                    text = style(text, "cyan")
                elif "INFO" in text or "DEBUG" in text:
                    text = style(text, "dim")
                elif "ERROR" in text or "WARNING" in text:
                    text = style(text, "yellow")
            else:
                text = ""
            body.append("│" + text.ljust(max(2, cols - 2))[: max(2, cols - 2)] + "│")

        # 保存光标
        sys.stdout.write("\x1b7")

        # 清空旧区域
        total_rows = 4 + body_rows
        rows_to_clear = max(self._last_drawn_rows, total_rows)
        for i in range(rows_to_clear):
            self._goto(1 + i, 1)
            sys.stdout.write("\x1b[2K")

        # 绘制
        self._goto(1, 1)
        sys.stdout.write("\x1b[2K" + top_bar[:cols])
        self._goto(2, 1)
        sys.stdout.write("\x1b[2K" + title_line[:cols])
        self._goto(3, 1)
        sys.stdout.write("\x1b[2K" + sep_line[:cols])

        for idx in range(body_rows):
            self._goto(4 + idx, 1)
            sys.stdout.write("\x1b[2K")
            sys.stdout.write(body[idx][:cols])

        self._goto(4 + body_rows, 1)
        sys.stdout.write("\x1b[2K" + bottom_bar[:cols])

        # 恢复光标
        sys.stdout.write("\x1b8")
        sys.stdout.flush()

        self._last_drawn_rows = total_rows

    async def _render_input_area(self):
        """渲染输入区."""
        if not self._use_ansi:
            return

        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        first_input_row = min(rows, separator_row + 1)
        second_input_row = min(rows, separator_row + 2)

        sys.stdout.write("\x1b7")

        # 分隔线
        self._goto(separator_row, 1)
        sys.stdout.write("\x1b[2K")
        sys.stdout.write("═" * max(1, cols))

        # 输入提示
        self._goto(first_input_row, 1)
        sys.stdout.write("\x1b[2K")
        prompt = "\x1b[1m\x1b[36m输入:\x1b[0m " if self._use_ansi else "输入: "
        sys.stdout.write(prompt)

        # 预留行
        self._goto(second_input_row, 1)
        sys.stdout.write("\x1b[2K")
        sys.stdout.flush()

        sys.stdout.write("\x1b8")
        self._goto(first_input_row, 1)
        sys.stdout.write(prompt)
        sys.stdout.flush()

    def _clear_input_area(self):
        """清空输入区."""
        if not self._use_ansi:
            return
        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        for r in range(separator_row, min(rows + 1, separator_row + 3)):
            self._goto(r, 1)
            sys.stdout.write("\x1b[2K")
        sys.stdout.flush()

    # ========== 输入处理 ==========

    async def _keyboard_input_loop(self):
        """键盘输入循环."""
        try:
            while self.running:
                if self._use_ansi:
                    await self._render_input_area()
                    cmd = await asyncio.to_thread(self._read_line_raw)
                    self._clear_input_area()
                    await self._render_dashboard()
                else:
                    cmd = await asyncio.to_thread(input, "输入: ")

                await self._handle_command(cmd.strip())
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            await self.close()

    def _read_line_raw(self) -> str:
        """原始模式读取输入（支持中文）."""
        try:
            import termios
            import tty
        except ImportError:
            # Windows 不支持 termios
            return input()

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            buffer: list[str] = []
            while True:
                ch = os.read(fd, 4)
                if not ch:
                    break
                try:
                    s = ch.decode("utf-8")
                except UnicodeDecodeError:
                    while True:
                        ch += os.read(fd, 1)
                        try:
                            s = ch.decode("utf-8")
                            break
                        except UnicodeDecodeError:
                            continue

                if s in ("\r", "\n"):
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    break
                elif s in ("\x7f", "\b"):
                    if buffer:
                        buffer.pop()
                    self._redraw_input_line("".join(buffer))
                elif s == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                else:
                    buffer.append(s)
                    self._redraw_input_line("".join(buffer))

            return "".join(buffer)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _redraw_input_line(self, content: str):
        """重绘输入行."""
        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        first_input_row = min(rows, separator_row + 1)
        prompt = "\x1b[1m\x1b[36m输入:\x1b[0m " if self._use_ansi else "输入: "
        self._goto(first_input_row, 1)
        sys.stdout.write("\x1b[2K")
        visible = content
        max_len = max(1, cols - len("输入: ") - 1)
        if len(visible) > max_len:
            visible = visible[-max_len:]
        sys.stdout.write(f"{prompt}{visible}")
        sys.stdout.flush()

    async def _handle_command(self, cmd: str):
        """处理命令 - 全部转发给 ViewManager."""
        if not cmd:
            return

        if self._on_command:
            # 所有命令都转发，不拦截
            self._on_command(cmd)

    def show_help(self):
        """显示帮助."""
        self._dash_text = "命令: r=开始/停止 | x=打断 | q=退出 | h=帮助 | 其他=发送文本"
        self._schedule_render()

    # ========== 日志处理 ==========

    def _install_log_handler(self):
        """安装日志处理器."""
        # 防止重复安装
        if self._log_handler_installed:
            return
        self._log_handler_installed = True

        class DisplayLogHandler(logging.Handler):
            def __init__(self, display: "CLIDisplay"):
                super().__init__()
                self.display = display

            def emit(self, record: logging.LogRecord):
                try:
                    msg = self.format(record)
                    self.display._log_lines.append(msg)
                    self.display._schedule_render()
                except Exception:
                    pass

        handler = DisplayLogHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        # 使用原始方法添加处理器，绕过过滤
        if hasattr(self, "_original_add_handler"):
            self._original_add_handler(logging.getLogger(), handler)
        else:
            logging.getLogger().addHandler(handler)

    def _remove_stream_handlers(self):
        """移除所有标准输出的日志处理器."""
        # 保存原始的 addHandler 方法
        self._original_add_handler = logging.Logger.addHandler

        # 创建一个包装函数，阻止添加 StreamHandler
        def filtered_add_handler(logger_self, handler):
            if isinstance(handler, logging.StreamHandler):
                stream = getattr(handler, "stream", None)
                if stream in (sys.stdout, sys.stderr, None):
                    # 忽略 stdout/stderr 的 StreamHandler
                    return
            self._original_add_handler(logger_self, handler)

        # 替换 addHandler 方法
        logging.Logger.addHandler = filtered_add_handler

        # 移除根 logger 的所有 StreamHandler
        root = logging.getLogger()
        for h in list(root.handlers):
            if isinstance(h, logging.StreamHandler):
                root.removeHandler(h)

        # 遍历所有已注册的 logger
        for name in list(logging.Logger.manager.loggerDict.keys()):
            log = logging.getLogger(name)
            for h in list(log.handlers):
                if isinstance(h, logging.StreamHandler):
                    log.removeHandler(h)

        # 设置根 logger 级别
        root.setLevel(logging.DEBUG)

    def _restore_logging(self):
        """恢复标准日志."""
        # 恢复原始的 addHandler 方法
        if hasattr(self, "_original_add_handler"):
            logging.Logger.addHandler = self._original_add_handler

        root = logging.getLogger()

        # 移除 DisplayLogHandler
        for h in list(root.handlers):
            if h.__class__.__name__ == "DisplayLogHandler":
                root.removeHandler(h)

        # 添加简单的 StreamHandler
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        root.addHandler(handler)

    # ========== 工具函数 ==========

    def _goto(self, row: int, col: int = 1):
        """移动光标."""
        sys.stdout.write(f"\x1b[{max(1, row)};{max(1, col)}H")

    def _term_size(self) -> tuple[int, int]:
        """获取终端尺寸."""
        try:
            size = shutil.get_terminal_size(fallback=(80, 24))
            return size.columns, size.lines
        except Exception:
            return 80, 24
