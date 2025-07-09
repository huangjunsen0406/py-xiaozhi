import asyncio
import os
import platform
from typing import Callable, Optional

from src.display.base_display import BaseDisplay

# 根据不同操作系统处理 pynput 导入
try:
    if platform.system() == "Windows":
        from pynput import keyboard as pynput_keyboard
    elif os.environ.get("DISPLAY"):
        from pynput import keyboard as pynput_keyboard
    else:
        pynput_keyboard = None
except ImportError:
    pynput_keyboard = None


class CliDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()
        self.running = True

        # 回调函数
        self.auto_callback = None
        self.abort_callback = None
        self.send_text_callback = None
        self.mode_callback = None

        # 异步队列用于处理命令
        self.command_queue = asyncio.Queue()

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
        print(f"按钮状态: {text}")

    async def update_status(self, status: str):
        """
        更新状态文本.
        """
        print(f"\r状态: {status}        ", end="", flush=True)

    async def update_text(self, text: str):
        """
        更新TTS文本.
        """
        if text and text.strip():
            print(f"\n文本: {text}")

    async def update_emotion(self, emotion_name: str):
        """
        更新表情显示.
        """
        print(f"表情: {emotion_name}")

    async def start(self):
        """
        启动异步CLI显示.
        """
        print("\n=== 小智Ai命令行控制 ===")
        print("可用命令：")
        print("  r     - 开始/停止对话")
        print("  x     - 打断当前对话")
        print("  q     - 退出程序")
        print("  h     - 显示此帮助信息")
        print("  其他  - 发送文本消息")
        print("============================\n")

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
                cmd = await asyncio.to_thread(input)
                await self._handle_command(cmd.lower().strip())
        except asyncio.CancelledError:
            pass

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
        print("\n正在关闭应用...")

    def _print_help(self):
        """
        打印帮助信息.
        """
        print("\n=== 小智Ai命令行控制 ===")
        print("可用命令：")
        print("  r     - 开始/停止对话")
        print("  x     - 打断当前对话")
        print("  q     - 退出程序")
        print("  h     - 显示此帮助信息")
        print("  其他  - 发送文本消息")
        print("============================\n")

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
