import asyncio
import os
import platform
from typing import Optional, Callable
import concurrent.futures

from src.display.base_display import BaseDisplay

# 根据不同操作系统处理 pynput 导入
try:
    if platform.system() == 'Windows':
        from pynput import keyboard as pynput_keyboard
    elif os.environ.get('DISPLAY'):
        from pynput import keyboard as pynput_keyboard
    else:
        pynput_keyboard = None
except ImportError:
    pynput_keyboard = None

from src.utils.logging_config import get_logger


class CliDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()  # 调用父类初始化
        """初始化CLI显示"""
        self.logger = get_logger(__name__)
        self.running = True

        # 状态相关
        self.current_status = "未连接"
        self.current_text = "待命"
        self.current_emotion = "😊"
        self.current_volume = 0  # 添加当前音量属性

        # 回调函数
        self.auto_callback = None
        self.status_callback = None
        self.text_callback = None
        self.emotion_callback = None
        self.abort_callback = None
        self.send_text_callback = None
        # 按键状态
        self.is_r_pressed = False
        # 添加组合键支持
        self.pressed_keys = set()

        # 状态缓存
        self.last_status = None
        self.last_text = None
        self.last_emotion = None
        self.last_volume = None

        # 键盘监听器
        self.keyboard_listener = None

        # 异步相关
        self.loop = None
        self.executor = None
        self.update_task = None
        self.keyboard_task = None
        self._main_task = None

    def set_callbacks(self,
                      press_callback: Optional[Callable] = None,
                      release_callback: Optional[Callable] = None,
                      status_callback: Optional[Callable] = None,
                      text_callback: Optional[Callable] = None,
                      emotion_callback: Optional[Callable] = None,
                      mode_callback: Optional[Callable] = None,
                      auto_callback: Optional[Callable] = None,
                      abort_callback: Optional[Callable] = None,
                      send_text_callback: Optional[Callable] = None):
        """设置回调函数"""
        self.status_callback = status_callback
        self.text_callback = text_callback
        self.emotion_callback = emotion_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback
        self.send_text_callback = send_text_callback

    def _run_callback_safely(self, callback):
        """安全地运行回调函数，支持异步回调"""
        try:
            if callback is None:
                return

            # 检查是否是Application实例
            try:
                from src.async_application import AsyncApplication
                app = AsyncApplication.get_instance()
            except ImportError:
                # 如果没有AsyncApplication，尝试使用普通Application
                from src.application import Application
                app = Application.get_instance()

            if app and hasattr(app, 'loop') and app.loop:
                # 如果是AsyncApplication，使用其事件循环来调度回调
                def safe_callback():
                    try:
                        callback()
                    except Exception as e:
                        self.logger.error(f"回调函数执行失败: {e}")

                # 在AsyncApplication的事件循环中调度回调
                app.loop.call_soon_threadsafe(safe_callback)
            else:
                # 如果不是AsyncApplication或没有事件循环，直接调用
                callback()
        except Exception as e:
            self.logger.error(f"回调函数执行失败: {e}")

    def update_button_status(self, text: str):
        """更新按钮状态"""
        print(f"按钮状态: {text}")

    def update_status(self, status: str):
        """更新状态文本"""
        if status != self.current_status:
            self.current_status = status
            self._print_current_status()

    def update_text(self, text: str):
        """更新TTS文本"""
        if text != self.current_text:
            self.current_text = text
            self._print_current_status()

    def update_emotion(self, emotion_path: str):
        """更新表情
        emotion_path: GIF文件路径或表情字符串
        """
        if emotion_path != self.current_emotion:
            # 如果是gif文件路径，提取文件名作为表情名
            if emotion_path.endswith(".gif"):
                # 从路径中提取文件名，去掉.gif后缀
                emotion_name = os.path.basename(emotion_path)
                emotion_name = emotion_name.replace(".gif", "")
                self.current_emotion = f"[{emotion_name}]"
            else:
                # 如果不是gif路径，则直接使用
                self.current_emotion = emotion_path

            self._print_current_status()

    def is_combo(self, *keys):
        """判断是否同时按下了一组按键"""
        return all(k in self.pressed_keys for k in keys)

    def start_keyboard_listener(self):
        """启动键盘监听"""
        # 如果 pynput 不可用，记录警告并返回
        if pynput_keyboard is None:
            self.logger.warning("键盘监听不可用：pynput 库未能正确加载。将使用基本的命令行输入。")
            return

        try:
            def on_press(key):
                try:
                    # 记录按下的键
                    if (key == pynput_keyboard.Key.alt_l or
                            key == pynput_keyboard.Key.alt_r):
                        self.pressed_keys.add('alt')
                    elif (key == pynput_keyboard.Key.shift_l or
                          key == pynput_keyboard.Key.shift_r):
                        self.pressed_keys.add('shift')
                    elif hasattr(key, 'char') and key.char:
                        self.pressed_keys.add(key.char.lower())

                    # 自动对话模式 - Alt+Shift+A
                    if (self.is_combo('alt', 'shift', 'a') and
                            self.auto_callback):
                        self._run_callback_safely(self.auto_callback)

                    # 打断对话 - Alt+Shift+X
                    if (self.is_combo('alt', 'shift', 'x') and
                            self.abort_callback):
                        self._run_callback_safely(self.abort_callback)

                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            def on_release(key):
                try:
                    # 清除释放的键
                    if (key == pynput_keyboard.Key.alt_l or
                            key == pynput_keyboard.Key.alt_r):
                        self.pressed_keys.discard('alt')
                    elif (key == pynput_keyboard.Key.shift_l or
                          key == pynput_keyboard.Key.shift_r):
                        self.pressed_keys.discard('shift')
                    elif hasattr(key, 'char') and key.char:
                        self.pressed_keys.discard(key.char.lower())
                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            # 创建并启动监听器
            self.keyboard_listener = pynput_keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.keyboard_listener.start()
            self.logger.info("键盘监听器初始化成功")
        except Exception as e:
            self.logger.error(f"键盘监听器初始化失败: {e}")

    def stop_keyboard_listener(self):
        """停止键盘监听"""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                self.logger.info("键盘监听器已停止")
            except Exception as e:
                self.logger.error(f"停止键盘监听器失败: {e}")

    def start(self):
        """启动CLI显示"""
        self._print_help()

        # 获取当前事件循环
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            # 如果没有运行的事件循环，创建一个新的
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        # 创建线程池执行器用于阻塞操作
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

        # 启动异步更新任务
        self.update_task = asyncio.create_task(self._async_update_loop())

        # 启动异步键盘监听任务
        self.keyboard_task = asyncio.create_task(
            self._async_keyboard_listener()
        )

        # 启动键盘监听
        self.start_keyboard_listener()

        # 启动异步主循环任务
        self._main_task = asyncio.create_task(self._async_main_loop())

    async def _async_main_loop(self):
        """异步主循环"""
        try:
            while self.running:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            await self.on_close()

    async def on_close(self):
        """关闭CLI显示"""
        self.running = False
        print("\n正在关闭应用...")

        # 取消异步任务
        if self.update_task and not self.update_task.done():
            self.update_task.cancel()
            try:
                await self.update_task
            except asyncio.CancelledError:
                pass

        if self.keyboard_task and not self.keyboard_task.done():
            self.keyboard_task.cancel()
            try:
                await self.keyboard_task
            except asyncio.CancelledError:
                pass

        if self._main_task and not self._main_task.done():
            self._main_task.cancel()
            try:
                await self._main_task
            except asyncio.CancelledError:
                pass

        # 关闭线程池执行器
        if self.executor:
            self.executor.shutdown(wait=False)

        self.stop_keyboard_listener()

    def on_close_sync(self):
        """同步关闭方法，用于非异步环境"""
        self.running = False
        print("\n正在关闭应用...")

        # 关闭线程池执行器
        if self.executor:
            self.executor.shutdown(wait=False)

        self.stop_keyboard_listener()

    def _print_help(self):
        """打印帮助信息"""
        print("\n=== 小智Ai命令行控制 ===")
        print("可用命令：")
        print("  r     - 开始/停止对话")
        print("  x     - 打断当前对话")
        print("  s     - 显示当前状态")
        print("  v 数字 - 设置音量(0-100)")
        print("  q     - 退出程序")
        print("  h     - 显示此帮助信息")
        print("快捷键：")
        print("  Alt+Shift+A - 自动对话模式")
        print("  Alt+Shift+X - 打断当前对话")
        print("=====================\n")

    async def _async_update_loop(self):
        """异步状态更新循环"""
        while self.running:
            try:
                # 更新状态
                if self.status_callback:
                    status = self.status_callback()
                    if status and status != self.current_status:
                        self.update_status(status)

                # 更新文本
                if self.text_callback:
                    text = self.text_callback()
                    if text and text != self.current_text:
                        self.update_text(text)

                # 更新表情
                if self.emotion_callback:
                    emotion = self.emotion_callback()
                    if emotion and emotion != self.current_emotion:
                        self.update_emotion(emotion)

            except Exception as e:
                self.logger.error(f"状态更新错误: {e}")

            await asyncio.sleep(0.1)

    async def _async_keyboard_listener(self):
        """异步键盘监听"""
        try:
            while self.running:
                # 在线程池中运行阻塞的 input() 操作
                cmd = await self.loop.run_in_executor(
                    self.executor, lambda: input().lower().strip()
                )

                if cmd == 'q':
                    # 使用同步关闭方法
                    self.on_close_sync()
                    break
                elif cmd == 'h':
                    self._print_help()
                elif cmd == 'r':
                    if self.auto_callback:
                        self._run_callback_safely(self.auto_callback)
                elif cmd == 'x':
                    if self.abort_callback:
                        self._run_callback_safely(self.abort_callback)
                elif cmd == 's':
                    self._print_current_status()
                elif cmd.startswith('v '):  # 添加音量命令处理
                    try:
                        volume = int(cmd.split()[1])  # 获取音量值
                        if 0 <= volume <= 100:
                            self.update_volume(volume)
                            print(f"音量已设置为: {volume}%")
                        else:
                            print("音量必须在0-100之间")
                    except (IndexError, ValueError):
                        print("无效的音量值，格式：v <0-100>")
                else:
                    if self.send_text_callback:
                        # 使用安全的回调调用方法
                        self._run_callback_safely(
                            lambda: self.send_text_callback(cmd)
                        )
        except Exception as e:
            self.logger.error(f"键盘监听错误: {e}")

    def _print_current_status(self):
        """打印当前状态"""
        # 检查是否有状态变化
        status_changed = (
            self.current_status != self.last_status or
            self.current_text != self.last_text or
            self.current_emotion != self.last_emotion or
            self.current_volume != self.last_volume
        )

        if status_changed:
            print("\n=== 当前状态 ===")
            print(f"状态: {self.current_status}")
            print(f"文本: {self.current_text}")
            print(f"表情: {self.current_emotion}")
            print(f"音量: {self.current_volume}%")
            print("===============\n")

            # 更新缓存
            self.last_status = self.current_status
            self.last_text = self.current_text
            self.last_emotion = self.current_emotion
            self.last_volume = self.current_volume