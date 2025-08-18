import asyncio
import logging
import os
import shutil
import sys
import termios
import tty
from collections import deque
from typing import Callable, Optional

from src.display.base_display import BaseDisplay


class CliDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()
        self.running = True
        self._use_ansi = sys.stdout.isatty()
        self._loop = None
        self._last_drawn_rows = 0

        # 仪表盘数据（顶部内容显示区）
        self._dash_status = ""
        self._dash_connected = False
        self._dash_text = ""
        self._dash_emotion = ""
        # 布局：仅两块区域（显示区 + 输入区）
        # 预留两行输入空间（分隔线 + 输入行），并额外多留一行用于中文输入溢出的清理
        self._input_area_lines = 3
        self._dashboard_lines = 8  # 默认显示区最少行数（会按终端高度动态调整）

        # 颜色/样式（仅在 TTY 下生效）
        self._ansi = {
            "reset": "\x1b[0m",
            "bold": "\x1b[1m",
            "dim": "\x1b[2m",
            "blue": "\x1b[34m",
            "cyan": "\x1b[36m",
            "green": "\x1b[32m",
            "yellow": "\x1b[33m",
            "magenta": "\x1b[35m",
        }

        # 回调函数
        self.auto_callback = None
        self.abort_callback = None
        self.send_text_callback = None
        self.mode_callback = None

        # 异步队列用于处理命令
        self.command_queue = asyncio.Queue()

        # 日志缓冲（只在 CLI 顶部显示，不直接打印到控制台）
        self._log_lines: deque[str] = deque(maxlen=6)
        self._install_log_handler()

    async def set_callbacks(
        self,
        press_callback: Optional[Callable] = None,
        release_callback: Optional[Callable] = None,
        mode_callback: Optional[Callable] = None,
        auto_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        send_text_callback: Optional[Callable] = None,
    ):
        """
        设置回调函数.
        """
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback
        self.send_text_callback = send_text_callback
        self.mode_callback = mode_callback

    async def update_button_status(self, text: str):
        """
        更新按钮状态.
        """
        # 简化：按钮状态仅在仪表盘文本中展示
        self._dash_text = text
        await self._render_dashboard()

    async def update_status(self, status: str, connected: bool):
        """
        更新状态（仅更新仪表盘，不追加新行）。
        """
        self._dash_status = status
        self._dash_connected = bool(connected)
        await self._render_dashboard()

    async def update_text(self, text: str):
        """
        更新文本（仅更新仪表盘，不追加新行）。
        """
        if text and text.strip():
            self._dash_text = text.strip()
            await self._render_dashboard()

    async def update_emotion(self, emotion_name: str):
        """
        更新表情（仅更新仪表盘，不追加新行）。
        """
        self._dash_emotion = emotion_name
        await self._render_dashboard()

    async def start(self):
        """
        启动异步CLI显示.
        """
        self._loop = asyncio.get_running_loop()
        await self._init_screen()

        # 启动命令处理任务
        command_task = asyncio.create_task(self._command_processor())
        input_task = asyncio.create_task(self._keyboard_input_loop())

        try:
            await asyncio.gather(command_task, input_task)
        except KeyboardInterrupt:
            await self.close()

    async def _command_processor(self):
        """
        命令处理器.
        """
        while self.running:
            try:
                command = await asyncio.wait_for(self.command_queue.get(), timeout=1.0)
                if asyncio.iscoroutinefunction(command):
                    await command()
                else:
                    command()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"命令处理错误: {e}")

    async def _keyboard_input_loop(self):
        """
        键盘输入循环.
        """
        try:
            while self.running:
                # 在TTY下，固定底部输入区读取输入
                if self._use_ansi:
                    await self._render_input_area()
                    # 自己接管输入（禁用终端回显），逐字重绘输入行，彻底解决中文首字符残留
                    cmd = await asyncio.to_thread(self._read_line_raw)
                    # 清理输入区（含可能的中文换行残留）并刷新顶部内容
                    self._clear_input_area()
                    await self._render_dashboard()
                else:
                    cmd = await asyncio.to_thread(input)
                await self._handle_command(cmd.lower().strip())
        except asyncio.CancelledError:
            pass

    # ===== 日志拦截并转发到显示区 =====
    def _install_log_handler(self) -> None:
        class _DisplayLogHandler(logging.Handler):
            def __init__(self, display: "CliDisplay"):
                super().__init__()
                self.display = display

            def emit(self, record: logging.LogRecord) -> None:
                try:
                    msg = self.format(record)
                    self.display._log_lines.append(msg)
                    loop = self.display._loop
                    if loop and self.display._use_ansi:
                        loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(
                                self.display._render_dashboard()
                            )
                        )
                except Exception:
                    pass

        root = logging.getLogger()
        # 移除直接写 stdout/stderr 的处理器，避免覆盖渲染
        for h in list(root.handlers):
            if isinstance(h, logging.StreamHandler) and getattr(h, "stream", None) in (
                sys.stdout,
                sys.stderr,
            ):
                root.removeHandler(h)

        handler = _DisplayLogHandler(self)
        handler.setLevel(logging.WARNING)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(name)s] - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)

    async def _handle_command(self, cmd: str):
        """
        处理命令.
        """
        if cmd == "q":
            await self.close()
        elif cmd == "h":
            self._print_help()
        elif cmd == "r":
            if self.auto_callback:
                await self.command_queue.put(self.auto_callback)
        elif cmd == "x":
            if self.abort_callback:
                await self.command_queue.put(self.abort_callback)
        else:
            if self.send_text_callback:
                await self.send_text_callback(cmd)

    async def close(self):
        """
        关闭CLI显示.
        """
        self.running = False
        print("\n正在关闭应用...\n")

    def _print_help(self):
        """
        将帮助信息写入顶部内容显示区，而非直接打印。
        """
        help_text = "r: 开始/停止 | x: 打断 | q: 退出 | h: 帮助 | 其他: 发送文本"
        self._dash_text = help_text

    async def _init_screen(self):
        """
        初始化屏幕并渲染两块区域（显示区 + 输入区）。
        """
        if self._use_ansi:
            # 清屏并回到左上
            sys.stdout.write("\x1b[2J\x1b[H")
            sys.stdout.flush()

        # 初始一次全量绘制
        await self._render_dashboard(full=True)
        await self._render_input_area()

    def _goto(self, row: int, col: int = 1):
        sys.stdout.write(f"\x1b[{max(1,row)};{max(1,col)}H")

    def _term_size(self):
        try:
            size = shutil.get_terminal_size(fallback=(80, 24))
            return size.columns, size.lines
        except Exception:
            return 80, 24

    # ====== 原始输入（Raw mode）支持，避免中文残留 ======
    def _read_line_raw(self) -> str:
        """
        使用原始模式读取一行：关闭回显、逐字符读取并自行回显， 通过整行重绘避免宽字符（中文）删除残留。
        """
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            buffer: list[str] = []
            while True:
                ch = os.read(fd, 4)  # 读取最多4字节，足够覆盖常见UTF-8中文
                if not ch:
                    break
                try:
                    s = ch.decode("utf-8")
                except UnicodeDecodeError:
                    # 若未能组成完整UTF-8，继续多读直到能解码
                    while True:
                        ch += os.read(fd, 1)
                        try:
                            s = ch.decode("utf-8")
                            break
                        except UnicodeDecodeError:
                            continue

                if s in ("\r", "\n"):
                    # 回车：换行，结束输入
                    sys.stdout.write("\r\n")
                    sys.stdout.flush()
                    break
                elif s in ("\x7f", "\b"):
                    # 退格：删除一个 Unicode 字符
                    if buffer:
                        buffer.pop()
                    # 整行重绘，避免中文宽字符残留
                    self._redraw_input_line("".join(buffer))
                elif s == "\x03":  # Ctrl+C
                    raise KeyboardInterrupt
                else:
                    buffer.append(s)
                    self._redraw_input_line("".join(buffer))

            return "".join(buffer)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def _redraw_input_line(self, content: str) -> None:
        """
        清空输入行并重写当前内容，确保中文删除无残留。
        """
        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        first_input_row = min(rows, separator_row + 1)
        prompt = "输入: " if not self._use_ansi else "\x1b[1m\x1b[36m输入:\x1b[0m "
        self._goto(first_input_row, 1)
        sys.stdout.write("\x1b[2K")
        visible = content
        # 避免超过一行导致折行
        max_len = max(1, cols - len("输入: ") - 1)
        if len(visible) > max_len:
            visible = visible[-max_len:]
        sys.stdout.write(f"{prompt}{visible}")
        sys.stdout.flush()

    async def _render_dashboard(self, full: bool = False):
        """
        在顶部固定区域更新内容显示，不触碰底部输入行。
        """

        # 截断长文本，避免换行撕裂界面
        def trunc(s: str, limit: int = 80) -> str:
            return s if len(s) <= limit else s[: limit - 1] + "…"

        lines = [
            f"状态: {trunc(self._dash_status)}",
            f"连接: {'已连接' if self._dash_connected else '未连接'}",
            f"表情: {trunc(self._dash_emotion)}",
            f"文本: {trunc(self._dash_text)}",
        ]

        if not self._use_ansi:
            # 退化：仅打印最后一行状态
            print(f"\r{lines[0]}        ", end="", flush=True)
            return

        cols, rows = self._term_size()

        # 可用显示行数 = 终端总行数 - 输入区行数
        usable_rows = max(5, rows - self._input_area_lines)

        # 一点点样式函数
        def style(s: str, *names: str) -> str:
            if not self._use_ansi:
                return s
            prefix = "".join(self._ansi.get(n, "") for n in names)
            return f"{prefix}{s}{self._ansi['reset']}"

        title = style(" 小智 AI 终端 ", "bold", "cyan")
        # 头部框和底部框
        top_bar = "┌" + ("─" * (max(2, cols - 2))) + "┐"
        title_line = "│" + title.center(max(2, cols - 2)) + "│"
        sep_line = "├" + ("─" * (max(2, cols - 2))) + "┤"
        bottom_bar = "└" + ("─" * (max(2, cols - 2))) + "┘"

        # 内容区可用行数（减去上下框的4行）
        body_rows = max(1, usable_rows - 4)
        body = []
        for i in range(body_rows):
            text = lines[i] if i < len(lines) else ""
            text = style(text, "green") if i == 0 else text
            body.append("│" + text.ljust(max(2, cols - 2))[: max(2, cols - 2)] + "│")

        # 保存光标位置
        sys.stdout.write("\x1b7")

        # 在绘制前彻底清空上一帧可能残留的区域，避免视觉上出现“两层”
        total_rows = 4 + body_rows  # 顶部框三行 + 底部框一行 + 正文行数
        rows_to_clear = max(self._last_drawn_rows, total_rows)
        for i in range(rows_to_clear):
            self._goto(1 + i, 1)
            sys.stdout.write("\x1b[2K")

        # 绘制头部
        self._goto(1, 1)
        sys.stdout.write("\x1b[2K" + top_bar[:cols])
        self._goto(2, 1)
        sys.stdout.write("\x1b[2K" + title_line[:cols])
        self._goto(3, 1)
        sys.stdout.write("\x1b[2K" + sep_line[:cols])

        # 绘制主体
        for idx in range(body_rows):
            self._goto(4 + idx, 1)
            sys.stdout.write("\x1b[2K")
            sys.stdout.write(body[idx][:cols])

        # 底部框
        self._goto(4 + body_rows, 1)
        sys.stdout.write("\x1b[2K" + bottom_bar[:cols])

        # 恢复光标位置
        sys.stdout.write("\x1b8")
        sys.stdout.flush()

        # 记录本次绘制高度
        self._last_drawn_rows = total_rows

    def _clear_input_area(self):
        if not self._use_ansi:
            return
        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        first_input_row = min(rows, separator_row + 1)
        second_input_row = min(rows, separator_row + 2)
        # 依次清空分隔线和两个输入行，避免中文宽字符回显残留
        for r in [separator_row, first_input_row, second_input_row]:
            self._goto(r, 1)
            sys.stdout.write("\x1b[2K")
        sys.stdout.flush()

    async def _render_input_area(self):
        if not self._use_ansi:
            return
        cols, rows = self._term_size()
        separator_row = max(1, rows - self._input_area_lines + 1)
        first_input_row = min(rows, separator_row + 1)
        second_input_row = min(rows, separator_row + 2)

        # 保存光标
        sys.stdout.write("\x1b7")
        # 分隔线
        self._goto(separator_row, 1)
        sys.stdout.write("\x1b[2K")
        sys.stdout.write("═" * max(1, cols))

        # 输入提示行（清空并写提示）
        self._goto(first_input_row, 1)
        sys.stdout.write("\x1b[2K")
        prompt = "输入: " if not self._use_ansi else "\x1b[1m\x1b[36m输入:\x1b[0m "
        sys.stdout.write(prompt)

        # 预留一行做溢出清理
        self._goto(second_input_row, 1)
        sys.stdout.write("\x1b[2K")
        sys.stdout.flush()

        # 恢复光标到原处，再把光标移动到输入位置供 input 使用
        sys.stdout.write("\x1b8")
        self._goto(first_input_row, 1)
        sys.stdout.write(prompt)
        sys.stdout.flush()

    async def toggle_mode(self):
        """
        CLI模式下的模式切换（无操作）
        """
        self.logger.debug("CLI模式下不支持模式切换")

    async def toggle_window_visibility(self):
        """
        CLI模式下的窗口切换（无操作）
        """
        self.logger.debug("CLI模式下不支持窗口切换")
