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

from src.utils.logging_config import get_logger


class CliDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        self.running = True

        # 状态相关
        self.current_status = "未连接"
        self.current_text = "待命"
        self.current_emotion = "😊"

        # 异步回调函数
        self.auto_callback = None
        self.status_callback = None
        self.text_callback = None
        self.emotion_callback = None
        self.abort_callback = None
        self.send_text_callback = None

        # 按键状态
        self.pressed_keys = set()

        # 状态缓存
        self.last_status = None
        self.last_text = None
        self.last_emotion = None
        self.last_volume = None

        # 键盘监听器
        self.keyboard_listener = None

        # 异步队列用于处理命令
        self.command_queue = asyncio.Queue()

    def set_callbacks(
        self,
        press_callback: Optional[Callable] = None,
        release_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        text_callback: Optional[Callable] = None,
        emotion_callback: Optional[Callable] = None,
        mode_callback: Optional[Callable] = None,
        auto_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        send_text_callback: Optional[Callable] = None,
    ):
        """设置回调函数"""
        self.status_callback = status_callback
        self.text_callback = text_callback
        self.emotion_callback = emotion_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback
        self.send_text_callback = send_text_callback

    def update_button_status(self, text: str):
        """更新按钮状态"""
        print(f"按钮状态: {text}")

    def update_status(self, status: str):
        """更新状态文本"""
        if status != self.current_status:
            self.current_status = status
            print(f"\r状态: {status}        ", end="", flush=True)

    def update_text(self, text: str):
        """更新TTS文本"""
        if text != self.current_text:
            self.current_text = text
            # 只有在有实际文本内容时才显示
            if text and text.strip():
                print(f"\n文本: {text}")

    def update_emotion(self, emotion_path: str):
        """更新表情"""
        if emotion_path != self.current_emotion:
            if emotion_path.endswith(".gif"):
                emotion_name = os.path.basename(emotion_path)
                emotion_name = emotion_name.replace(".gif", "")
                self.current_emotion = f"[{emotion_name}]"
            else:
                self.current_emotion = emotion_path

    async def start(self):
        """启动异步CLI显示"""
        print("\n=== 小智Ai命令行控制（异步版本） ===")
        print("可用命令：")
        print("  r     - 开始/停止对话")
        print("  x     - 打断当前对话")
        print("  s     - 显示当前状态")
        print("  v 数字 - 设置音量(0-100)")
        print("  q     - 退出程序")
        print("  h     - 显示此帮助信息")
        print("============================\n")

        # 启动命令处理任务
        command_task = asyncio.create_task(self._command_processor())
        input_task = asyncio.create_task(self._keyboard_input_loop())

        try:
            await asyncio.gather(command_task, input_task)
        except KeyboardInterrupt:
            await self.on_close()

    async def _command_processor(self):
        """命令处理器"""
        while self.running:
            try:
                command = await asyncio.wait_for(
                    self.command_queue.get(), timeout=1.0
                )
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
        """键盘输入循环"""
        try:
            while self.running:
                try:
                    # 使用超时机制，避免无限阻塞
                    cmd = await asyncio.wait_for(
                        asyncio.to_thread(input), 
                        timeout=1.0
                    )
                    await self._handle_command(cmd.lower().strip())
                except asyncio.TimeoutError:
                    # 超时后继续循环，检查running状态
                    continue
                except EOFError:
                    # 处理Ctrl+D或输入流关闭
                    await self.on_close()
                    break
        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            # 处理Ctrl+C
            await self.on_close()

    async def _handle_command(self, cmd: str):
        """处理命令"""
        if cmd == "q":
            await self.on_close()
        elif cmd == "h":
            self._print_help()
        elif cmd == "r":
            if self.auto_callback:
                await self.command_queue.put(self.auto_callback)
        elif cmd == "x":
            if self.abort_callback:
                await self.command_queue.put(self.abort_callback)
        elif cmd == "s":
            self._print_current_status()
        elif cmd.startswith("v "):
            try:
                volume = int(cmd.split()[1])
                if 0 <= volume <= 100:
                    self.update_volume(volume)
                    print(f"音量已设置为: {volume}%")
                else:
                    print("音量必须在0-100之间")
            except (IndexError, ValueError):
                print("无效的音量值，格式：v <0-100>")
        else:
            if self.send_text_callback:
                await self.send_text_callback(cmd)

    async def on_close(self):
        """关闭CLI显示"""
        self.running = False
        print("\n正在关闭应用...")

    def _print_help(self):
        """打印帮助信息"""
        print("\n=== 小智Ai命令行控制（异步版本） ===")
        print("可用命令：")
        print("  r     - 开始/停止对话")
        print("  x     - 打断当前对话")
        print("  s     - 显示当前状态")
        print("  v 数字 - 设置音量(0-100)")
        print("  q     - 退出程序")
        print("  h     - 显示此帮助信息")
        print("============================\n")

    def _print_current_status(self):
        """打印当前状态"""
        print("\n=== 当前状态 ===")
        print(f"状态: {self.current_status}")
        print(f"文本: {self.current_text}")
        print(f"表情: {self.current_emotion}")
        print(f"音量: {self.current_volume}%")
        print("===============\n")

    def start_keyboard_listener(self):
        """启动键盘监听"""
        pass

    def stop_keyboard_listener(self):
        """停止键盘监听"""
        pass