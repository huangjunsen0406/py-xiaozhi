"""CLI 终端显示界面.

提供终端 TUI 界面，包含:
- 状态仪表盘（顶部框架）
- 日志显示区域
- 命令输入区域
"""

import asyncio
import codecs
import io
import logging
import os
import shutil
import stat
import sys
from collections import deque
from collections.abc import Callable

from src.constants.system import SystemConstants
from src.logging import get_logger

logger = get_logger()


class CLIDisplay:
    """CLI 终端显示界面."""

    def __init__(self):
        self.running = True
        self._use_ansi = sys.stdout.isatty()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._last_drawn_rows = 0
        self._render_lock = None
        self._initialized = False  # 是否已初始化
        self._log_handler_installed = False  # 日志处理器是否已安装
        self._display_log_handler = None
        self._intercepted_handlers = []
        self._start_task = None
        self._input_waiter = None
        self._input_text = ""
        self._input_decoder = None
        self._closed = False

        # 仪表盘数据
        self._dash_status = "待命"
        self._dash_connected = False
        self._dash_text = ""
        self._dash_music = ""
        self._dash_emotion = "neutral"
        self._dash_auto_mode = False

        # 布局设置
        self._input_area_lines = 3  # 输入区行数
        self._dashboard_lines = 9  # 显示区最少行数

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
        self._on_command: Callable[[str], None] | None = None

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
        if self._log_handler_installed:
            return
        # 只暂时接管控制台输出，保留文件处理器。
        self._remove_stream_handlers()
        # 再安装我们的日志处理器
        self._install_log_handler()

    async def start(self):
        """Own the interruptible input lifetime and restore it before returning."""
        self._loop = asyncio.get_running_loop()
        self._start_task = asyncio.current_task()
        self._render_lock = asyncio.Lock()
        self.running = True
        self._closed = False
        self._input_text = ""
        encoding = getattr(sys.stdin, "encoding", None) or "utf-8"
        self._input_decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        try:
            if not self._log_handler_installed:
                self.intercept_logging()
            if self._use_ansi:
                sys.stdout.write("\x1b[3J\x1b[2J\x1b[H")
                sys.stdout.flush()
            self._initialized = True
            await self._init_screen()
            await self._keyboard_input_loop()
        finally:
            self.running = False
            self._initialized = False
            self._start_task = None
            await self.close()

    async def close(self):
        """Stop and join the input owner; no executor thread waits for a key."""
        if self._closed:
            return
        self._closed = True
        self.running = False
        task = self._start_task
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self._restore_logging()
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
        if text and text.strip():
            self._dash_text = text.strip()
            self._schedule_render()

    def update_music_line(self, text: str):
        self._dash_music = (text or "").strip()
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
            except Exception as e:
                logging.getLogger(__name__).error(f"调度渲染失败: {e}")

    def _do_render(self):
        """执行渲染（在事件循环中调用）."""
        if not self._initialized:
            return
        try:
            task = asyncio.create_task(self._safe_render(), name="cli:render")

            def _on_done(t: asyncio.Task):
                if t.cancelled():
                    return
                exc = t.exception()
                if exc:
                    logging.getLogger(__name__).error(
                        f"CLI 渲染任务异常: {exc}", exc_info=exc
                    )

            task.add_done_callback(_on_done)
        except Exception as e:
            logging.getLogger(__name__).error(f"创建渲染任务失败: {e}", exc_info=True)

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
            f"对话: {trunc(self._dash_text)}",
            f"音乐: {trunc(self._dash_music) if self._dash_music else '—'}",
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
        try:
            while self.running:
                if self._use_ansi:
                    await self._render_input_area()
                    cmd = await self._read_line_raw()
                    self._clear_input_area()
                    await self._render_dashboard()
                else:
                    print("输入: ", end="", flush=True)
                    cmd = await self._read_line()
                if cmd is None:
                    await self._handle_command("q")
                    break
                cmd = cmd.strip()
                await self._handle_command(cmd)
                if cmd.lower() == "q":
                    break
        except KeyboardInterrupt:
            await self._handle_command("q")
        finally:
            self.running = False

    async def _read_input_chunk(self):
        """Wait for descriptor readiness; cancellation unregisters the reader."""
        if sys.platform == "win32" and sys.stdin.isatty():
            import msvcrt

            while self.running:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        msvcrt.getwch()
                        continue
                    return ch
                await asyncio.sleep(0.03)
            return ""
        if isinstance(sys.stdin, io.StringIO):
            return sys.stdin.read(1)
        fd = sys.stdin.fileno()
        if stat.S_ISREG(os.fstat(fd).st_mode):
            return os.read(fd, 4096)
        if sys.platform == "win32":
            return await self._read_windows_pipe(fd)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._input_waiter = future

        def ready():
            if future.done():
                return
            try:
                data = os.read(fd, 4096)
            except (BlockingIOError, InterruptedError):
                return
            except Exception as error:
                future.set_exception(error)
            else:
                future.set_result(data)

        try:
            loop.add_reader(fd, ready)
            return await future
        finally:
            loop.remove_reader(fd)
            if self._input_waiter is future:
                self._input_waiter = None

    async def _read_windows_pipe(self, fd):
        import ctypes
        import msvcrt
        from ctypes import wintypes

        peek = ctypes.WinDLL("kernel32", use_last_error=True).PeekNamedPipe
        peek.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.LPDWORD,
            wintypes.LPDWORD,
            wintypes.LPDWORD,
        ]
        peek.restype = wintypes.BOOL
        handle = wintypes.HANDLE(msvcrt.get_osfhandle(fd))
        while self.running:
            available = wintypes.DWORD()
            if not peek(handle, None, 0, None, ctypes.byref(available), None):
                error = ctypes.get_last_error()
                if error in (109, 233):  # ERROR_BROKEN_PIPE / PIPE_NOT_CONNECTED
                    return b""
                raise ctypes.WinError(error)
            if available.value:
                return os.read(fd, min(4096, available.value))
            await asyncio.sleep(0.03)
        return b""

    async def _read_character(self):
        while not self._input_text:
            chunk = await self._read_input_chunk()
            if not chunk:
                return None
            if isinstance(chunk, bytes):
                chunk = self._input_decoder.decode(chunk)
            self._input_text += chunk
        character = self._input_text[0]
        self._input_text = self._input_text[1:]
        return character

    async def _read_line(self, *, raw=False):
        buffer = []
        while self.running:
            character = await self._read_character()
            if character is None or character in ("\x04", "\x1a"):
                return "".join(buffer) if buffer else None
            if character == "\x03":
                raise KeyboardInterrupt
            if character in ("\r", "\n"):
                if raw:
                    print("\r")
                return "".join(buffer)
            if raw and character in ("\x7f", "\b"):
                if buffer:
                    buffer.pop()
            else:
                buffer.append(character)
            if raw:
                self._redraw_input_line("".join(buffer))
        return None

    async def _read_line_raw(self):
        """Restore raw terminal state even if close cancels a pending read."""
        settings = None
        fd = None
        if sys.platform != "win32":
            import termios
            import tty

            fd = sys.stdin.fileno()
            if os.isatty(fd):
                settings = termios.tcgetattr(fd)
                tty.setraw(fd)
        try:
            return await self._read_line(raw=True)
        finally:
            if settings is not None:
                termios.tcsetattr(fd, termios.TCSADRAIN, settings)

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
        """处理命令 - 全部转发给 CliViewManager."""
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
                except Exception as e:
                    logging.getLogger(__name__).error(f"日志记录失败: {e}")

        handler = DisplayLogHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logging.getLogger().addHandler(handler)
        self._display_log_handler = handler

    def _remove_stream_handlers(self):
        """Temporarily detach console handlers, keeping disk logging active."""
        loggers = [logging.getLogger()] + [
            item
            for item in logging.Logger.manager.loggerDict.values()
            if isinstance(item, logging.Logger)
        ]
        streams = (sys.stdout, sys.stderr, sys.__stdout__, sys.__stderr__)
        for log in loggers:
            for index, handler in enumerate(list(log.handlers)):
                if (
                    isinstance(handler, logging.StreamHandler)
                    and not isinstance(handler, logging.FileHandler)
                    and any(handler.stream is stream for stream in streams)
                ):
                    self._intercepted_handlers.append((log, handler, index))
                    log.removeHandler(handler)

    def _restore_logging(self):
        """Restore the exact handlers borrowed by this display, once."""
        handler = self._display_log_handler
        self._display_log_handler = None
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            handler.close()
        for log, original, index in self._intercepted_handlers:
            if original not in log.handlers and not original._closed:
                log.handlers.insert(min(index, len(log.handlers)), original)
        self._intercepted_handlers.clear()
        self._log_handler_installed = False

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
