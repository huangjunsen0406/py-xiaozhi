import asyncio
import json
import signal
import sys
import threading
from typing import Set

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.display import gui_display
from src.mcp.mcp_server import McpServer
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.common_utils import handle_verification_code
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger
from src.utils.opus_loader import setup_opus

# 忽略SIGTRAP信号
try:
    signal.signal(signal.SIGTRAP, signal.SIG_IGN)
except (AttributeError, ValueError) as e:
    print(f"注意: 无法设置SIGTRAP处理器: {e}")


def handle_sigint(signum, frame):
    app = Application.get_instance()
    if app:
        # 使用事件循环运行shutdown
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(app.shutdown())
        except RuntimeError:
            # 没有运行中的事件循环，直接退出
            sys.exit(0)


try:
    signal.signal(signal.SIGINT, handle_sigint)
except (AttributeError, ValueError) as e:
    print(f"注意: 无法设置SIGINT处理器: {e}")

setup_opus()

logger = get_logger(__name__)

try:
    import opuslib  # noqa: F401
except Exception as e:
    logger.critical("导入 opuslib 失败: %s", e, exc_info=True)
    logger.critical("请确保 opus 动态库已正确安装或位于正确的位置")
    sys.exit(1)


class Application:
    """
    基于纯asyncio的应用程序架构.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = Application()
        return cls._instance

    def __init__(self):
        """
        初始化应用程序.
        """
        if Application._instance is not None:
            logger.error("尝试创建Application的多个实例")
            raise Exception("Application是单例类，请使用get_instance()获取实例")
        Application._instance = self

        logger.debug("初始化Application实例")

        # 配置管理
        self.config = ConfigManager.get_instance()

        # 状态管理
        self.device_state = DeviceState.IDLE
        self.voice_detected = False
        self.keep_listening = False
        self.aborted = False

        # 异步组件
        self.audio_codec = None
        self.protocol = None
        self.display = None
        self.wake_word_detector = None
        self.shortcut_manager = None
        self.gpio_button_manager = None
        # 任务管理
        self.running = False
        self._main_tasks: Set[asyncio.Task] = set()

        # 命令队列 - 延迟到事件循环运行时初始化
        self.command_queue: asyncio.Queue = None

        # 任务取消事件 - 延迟到事件循环运行时初始化
        self._shutdown_event = None

        # 保存主线程的事件循环（稍后在run方法中设置）
        self._main_loop = None

        # MCP服务器
        self.mcp_server = McpServer.get_instance()

        # 消息处理器映射
        self._message_handlers = {
            "tts": self._handle_tts_message,
            "stt": self._handle_stt_message,
            "llm": self._handle_llm_message,
            "iot": self._handle_iot_message,
            "mcp": self._handle_mcp_message,
        }

        # 并发控制锁
        self._state_lock = asyncio.Lock()
        self._abort_lock = asyncio.Lock()

        logger.debug("Application实例初始化完成")

    async def run(self, **kwargs):
        """
        启动应用程序.
        """
        logger.info("启动应用程序，参数: %s", kwargs)

        mode = kwargs.get("mode", "gui")
        protocol = kwargs.get("protocol", "websocket")

        if mode == "gui":
            # GUI模式：需要创建Qt应用和qasync事件循环
            return await self._run_gui_mode(protocol)
        else:
            # CLI模式：使用标准asyncio
            return await self._run_cli_mode(protocol)

    async def _run_gui_mode(self, protocol: str):
        """
        在GUI模式下运行应用程序.
        """
        try:
            import qasync
            from PyQt5.QtWidgets import QApplication
        except ImportError:
            logger.error("GUI模式需要qasync和PyQt5库，请安装: pip install qasync PyQt5")
            return 1

        try:
            # 检查是否已存在QApplication实例
            app = QApplication.instance()
            if app is None:
                logger.info("创建新的QApplication实例")
                app = QApplication(sys.argv)
            else:
                logger.info("使用已存在的QApplication实例")

            # 确保清理之前的事件循环
            try:
                current_loop = asyncio.get_event_loop()
                if current_loop and not current_loop.is_closed():
                    logger.debug("发现现有事件循环，准备关闭")
                    # 不强制关闭，让它自然完成
            except RuntimeError:
                # 没有现有循环，这是正常的
                pass

            # 创建新的qasync事件循环
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)
            logger.info("已设置qasync事件循环")

            # 在qasync环境中运行应用程序
            with loop:
                try:
                    task = self._run_application_core(protocol, "gui")
                    return loop.run_until_complete(task)
                except RuntimeError as e:
                    error_msg = "Event loop stopped before Future completed"
                    if error_msg in str(e):
                        # 正常退出情况，事件循环被QApplication.quit()停止
                        logger.info("GUI应用程序正常退出")
                        return 0
                    else:
                        # 其他运行时错误
                        raise

        except Exception as e:
            logger.error(f"GUI应用程序异常退出: {e}", exc_info=True)
            return 1
        finally:
            # 确保事件循环正确关闭
            try:
                if "loop" in locals():
                    loop.close()
            except Exception:
                pass

    async def _run_cli_mode(self, protocol: str):
        """
        在CLI模式下运行应用程序.
        """
        try:
            return await self._run_application_core(protocol, "cli")
        except Exception as e:
            logger.error(f"CLI应用程序异常退出: {e}", exc_info=True)
            return 1

    def _initialize_async_objects(self):
        """
        初始化异步对象 - 必须在事件循环运行后调用.
        """
        logger.debug("初始化异步对象")
        self.command_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()

    async def _run_application_core(self, protocol: str, mode: str):
        """
        应用程序核心运行逻辑.
        """
        try:
            self.running = True

            # 保存主线程的事件循环
            self._main_loop = asyncio.get_running_loop()

            # 初始化异步对象 - 必须在事件循环运行后创建
            self._initialize_async_objects()

            # 初始化组件
            await self._initialize_components(mode, protocol)

            # 启动核心任务
            await self._start_core_tasks()

            # 启动显示界面
            if mode == "gui":
                await self._start_gui_display()
            else:
                await self._start_cli_display()

            logger.info("应用程序已启动，按Ctrl+C退出")

            # 等待应用程序运行
            while self.running:
                await asyncio.sleep(1)

            return 0

        except Exception as e:
            logger.error(f"启动应用程序失败: {e}", exc_info=True)
            await self.shutdown()
            return 1
        finally:
            # 确保应用程序正确关闭
            try:
                await self.shutdown()
            except Exception as e:
                logger.error(f"关闭应用程序时出错: {e}")

    async def _initialize_components(self, mode: str, protocol: str):
        """
        初始化应用程序组件.
        """
        logger.info("正在初始化应用程序组件...")

        # 设置显示类型（必须在设备状态设置之前）
        self._set_display_type(mode)

        # 初始化MCP服务器
        self._initialize_mcp_server()

        # 设置设备状态
        await self._set_device_state(DeviceState.IDLE)

        # 初始化物联网设备
        await self._initialize_iot_devices()

        # 初始化音频编解码器
        await self._initialize_audio()

        # 设置协议
        self._set_protocol_type(protocol)

        # 初始化唤醒词检测
        await self._initialize_wake_word_detector()

        # 设置协议回调
        self._setup_protocol_callbacks()

        # 启动日程提醒服务
        await self._start_calendar_reminder_service()

        # 启动倒计时器服务
        await self._start_timer_service()

        # 初始化快捷键管理器
        await self._initialize_shortcuts()

        logger.info("应用程序组件初始化完成")

    async def _initialize_audio(self):
        """
        初始化音频设备和编解码器.
        """
        try:
            logger.debug("开始初始化音频编解码器")
            from src.audio_codecs.audio_codec import AudioCodec

            self.audio_codec = AudioCodec()
            await self.audio_codec.initialize()

            # 设置实时编码回调
            self.audio_codec.set_encoded_audio_callback(self._on_encoded_audio)

            logger.info("音频编解码器初始化成功")

        except Exception as e:
            logger.error("初始化音频设备失败: %s", e, exc_info=True)
            # 确保初始化失败时audio_codec为None
            self.audio_codec = None

    def _on_encoded_audio(self, encoded_data: bytes):
        """
        处理编码后的音频数据回调.

        注意：这个回调在音频驱动线程中被调用，需要线程安全地调度到主事件循环。
        """
        try:
            # 只在监听状态且音频通道打开时发送数据
            if (
                self.device_state == DeviceState.LISTENING
                and self.protocol
                and self.protocol.is_audio_channel_opened()
                and not getattr(self, '_transitioning', False)
            ):

                # 线程安全地调度到主事件循环
                if self._main_loop and not self._main_loop.is_closed():
                    self._main_loop.call_soon_threadsafe(self._schedule_audio_send, encoded_data)

        except Exception as e:
            logger.error(f"处理编码音频数据回调失败: {e}")

    def _schedule_audio_send(self, encoded_data: bytes):
        """
        在主事件循环中调度音频发送任务.
        """
        try:
            # 再次检查状态（可能在调度期间状态已改变）
            if (
                self.device_state == DeviceState.LISTENING
                and self.protocol
                and self.protocol.is_audio_channel_opened()
            ):

                # 创建异步任务发送音频数据
                asyncio.create_task(self.protocol.send_audio(encoded_data))

        except Exception as e:
            logger.error(f"调度音频发送失败: {e}")

    def _set_protocol_type(self, protocol_type: str):
        """
        设置协议类型.
        """
        logger.debug("设置协议类型: %s", protocol_type)
        if protocol_type == "mqtt":
            self.protocol = MqttProtocol(asyncio.get_running_loop())
        else:
            self.protocol = WebsocketProtocol()

    def _set_display_type(self, mode: str):
        """
        设置显示界面类型.
        """
        logger.debug("设置显示界面类型: %s", mode)

        if mode == "gui":
            self.display = gui_display.GuiDisplay()
            self._setup_gui_callbacks()
        else:
            from src.display.cli_display import CliDisplay

            self.display = CliDisplay()
            self._setup_cli_callbacks()

    def _create_async_callback(self, coro_func, *args):
        """
        创建异步回调函数的辅助方法.
        """
        return lambda: asyncio.create_task(coro_func(*args))

    def _setup_gui_callbacks(self):
        """
        设置GUI回调函数.
        """
        asyncio.create_task(
            self.display.set_callbacks(
                press_callback=self._create_async_callback(self.start_listening),
                release_callback=self._create_async_callback(self.stop_listening),
                mode_callback=self._on_mode_changed,
                auto_callback=self._create_async_callback(self.toggle_chat_state),
                abort_callback=self._create_async_callback(
                    self.abort_speaking, AbortReason.WAKE_WORD_DETECTED
                ),
                send_text_callback=self._send_text_tts,
            )
        )

    def _setup_cli_callbacks(self):
        """
        设置CLI回调函数.
        """
        asyncio.create_task(
            self.display.set_callbacks(
                auto_callback=self._create_async_callback(self.toggle_chat_state),
                abort_callback=self._create_async_callback(
                    self.abort_speaking, AbortReason.WAKE_WORD_DETECTED
                ),
                send_text_callback=self._send_text_tts,
            )
        )

    def _setup_protocol_callbacks(self):
        """
        设置协议回调函数.
        """
        self.protocol.on_network_error(self._on_network_error)
        self.protocol.on_incoming_audio(self._on_incoming_audio)
        self.protocol.on_incoming_json(self._on_incoming_json)
        self.protocol.on_audio_channel_opened(self._on_audio_channel_opened)
        self.protocol.on_audio_channel_closed(self._on_audio_channel_closed)

    async def _start_core_tasks(self):
        """
        启动核心任务.
        """
        logger.debug("启动核心任务")

        # 命令处理任务
        self._create_task(self._command_processor(), "命令处理")

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """
        创建并管理任务.
        """
        task = asyncio.create_task(coro, name=name)
        self._main_tasks.add(task)

        def done_callback(t):
            # 任务完成后从集合中移除，防止内存泄漏
            self._main_tasks.discard(t)

            if not t.cancelled() and t.exception():
                logger.error(f"任务 {name} 异常结束: {t.exception()}", exc_info=True)

        task.add_done_callback(done_callback)
        return task

    async def _command_processor(self):
        """
        命令处理器.
        """
        while self.running:
            try:
                # 检查队列是否已初始化
                if self.command_queue is None:
                    await asyncio.sleep(0.1)
                    continue

                # 等待命令，超时后继续循环检查running状态
                try:
                    command = await asyncio.wait_for(self.command_queue.get(), timeout=0.1)
                    # 检查命令是否有效
                    if command is None:
                        logger.warning("收到空命令，跳过执行")
                        continue
                    if not callable(command):
                        logger.warning(f"收到非可调用命令: {type(command)}, 跳过执行")
                        continue

                    # 执行命令
                    result = command()
                    if asyncio.iscoroutine(result):
                        await result
                except asyncio.TimeoutError:
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"命令处理错误: {e}", exc_info=True)

    async def _start_gui_display(self):
        """
        启动GUI显示.
        """
        # 在qasync环境中，GUI可以直接在主线程启动
        try:
            await self.display.start()
        except Exception as e:
            logger.error(f"GUI显示错误: {e}", exc_info=True)

    async def _start_cli_display(self):
        """
        启动CLI显示.
        """
        self._create_task(self.display.start(), "CLI显示")

    async def schedule_command(self, command):
        """
        调度命令到命令队列.
        """
        # 检查队列是否已初始化
        if self.command_queue is None:
            logger.warning("命令队列未初始化，丢弃命令")
            return

        try:
            # 使用 put_nowait 避免阻塞，如果队列满则记录警告
            self.command_queue.put_nowait(command)
        except asyncio.QueueFull:
            logger.warning("命令队列已满，丢弃命令")
            # 可选：清理一些旧命令
            try:
                self.command_queue.get_nowait()
                self.command_queue.put_nowait(command)
                logger.info("清理旧命令后重新添加")
            except asyncio.QueueEmpty:
                pass

    async def _start_listening_common(self, listening_mode, keep_listening_flag):
        """
        通用的开始监听逻辑.
        """
        async with self._state_lock:
            if self.device_state != DeviceState.IDLE:
                return False

        if not self.protocol.is_audio_channel_opened():
            success = await self.protocol.open_audio_channel()
            if not success:
                return False

        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        await self._set_device_state(DeviceState.CONNECTING)

        self.keep_listening = keep_listening_flag
        await self.protocol.send_start_listening(listening_mode)
        await self._set_device_state(DeviceState.LISTENING)
        return True

    async def start_listening(self):
        """
        开始监听.
        """
        await self.schedule_command(self._start_listening_impl)

    async def _start_listening_impl(self):
        """
        开始监听的实现.
        """
        success = await self._start_listening_common(ListeningMode.MANUAL, False)

        if not success and self.device_state == DeviceState.SPEAKING:
            if not self.aborted:
                await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def stop_listening(self):
        """
        停止监听.
        """
        await self.schedule_command(self._stop_listening_impl)

    async def _stop_listening_impl(self):
        """
        停止监听的实现.
        """
        if self.device_state == DeviceState.LISTENING:
            await self.protocol.send_stop_listening()
            await self._set_device_state(DeviceState.IDLE)

    async def toggle_chat_state(self):
        """
        切换聊天状态.
        """
        await self.schedule_command(self._toggle_chat_state_impl)

    async def _toggle_chat_state_impl(self):
        """
        切换聊天状态的实现.
        """
        if self.device_state == DeviceState.IDLE:
            await self._start_listening_common(ListeningMode.AUTO_STOP, True)

        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.NONE)
        elif self.device_state == DeviceState.LISTENING:
            await self.protocol.close_audio_channel()
            await self._set_device_state(DeviceState.IDLE)

    async def abort_speaking(self, reason):
        """
        中止语音输出.
        """
        if self.aborted:
            logger.debug(f"已经中止，忽略重复的中止请求: {reason}")
            return

        logger.info(f"中止语音输出，原因: {reason}")
        self.aborted = True
        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        try:
            await self.protocol.send_abort_speaking(reason)
            await self._set_device_state(DeviceState.IDLE)
            self.aborted = False
            if (
                reason == AbortReason.WAKE_WORD_DETECTED
                and self.keep_listening
                and self.protocol.is_audio_channel_opened()
            ):
                await asyncio.sleep(0.1)
                await self.toggle_chat_state()

        except Exception as e:
            logger.error(f"中止语音时出错: {e}")

    async def _set_device_state(self, state):
        """
        设置设备状态 - 通过队列确保顺序执行.
        """
        await self.schedule_command(lambda: self._set_device_state_impl(state))

    def _update_display_async(self, update_func, *args):
        """
        异步更新显示的辅助方法.
        """
        if self.display:
            asyncio.create_task(update_func(*args))

    async def _set_device_state_impl(self, state):
        """
        设备状态设置.
        """
        async with self._state_lock:
            if self.device_state == state:
                return

            logger.debug(f"设备状态变更: {self.device_state} -> {state}")
            self.device_state = state

            # 根据状态执行相应操作并更新显示
            if state == DeviceState.IDLE:
                await self._handle_idle_state()
            elif state == DeviceState.CONNECTING:
                self._update_display_async(self.display.update_status, "连接中...")
            elif state == DeviceState.LISTENING:
                await self._handle_listening_state()
            elif state == DeviceState.SPEAKING:
                self._update_display_async(self.display.update_status, "说话中...")

    async def _handle_idle_state(self):
        """
        处理空闲状态.
        """
        # UI更新异步执行
        self._update_display_async(self.display.update_status, "待命")

        # 设置表情
        self.set_emotion("neutral")

    async def _handle_listening_state(self):
        """
        处理监听状态.
        """
        # UI更新异步执行
        self._update_display_async(self.display.update_status, "聆听中...")

        # 设置表情
        self.set_emotion("neutral")

        # 更新IoT状态
        await self._update_iot_states(True)

    async def _send_text_tts(self, text):
        """
        发送文本进行TTS.
        """
        if not self.protocol.is_audio_channel_opened():
            await self.protocol.open_audio_channel()

        await self.protocol.send_wake_word_detected(text)

    def set_chat_message(self, role, message):
        """
        设置聊天消息.
        """
        self._update_display_async(self.display.update_text, message)

    def set_emotion(self, emotion):
        """
        设置表情.
        """
        self._update_display_async(self.display.update_emotion, emotion)

    # 协议回调方法
    def _on_network_error(self, error_message=None):
        """
        网络错误回调.
        """
        if error_message:
            logger.error(error_message)

        asyncio.create_task(self.schedule_command(self._handle_network_error))

    async def _handle_network_error(self):
        """
        处理网络错误.
        """
        self.keep_listening = False
        await self._set_device_state(DeviceState.IDLE)

        if self.protocol:
            await self.protocol.close_audio_channel()

    def _on_incoming_audio(self, data):
        """
        接收音频数据回调.
        """
        if self.device_state == DeviceState.SPEAKING and self.audio_codec:
            try:
                # 音频数据处理需要实时性，直接创建任务但添加异常处理
                task = asyncio.create_task(self.audio_codec.write_audio(data))
                task.add_done_callback(
                    lambda t: (
                        logger.error(f"音频写入任务异常: {t.exception()}", exc_info=True)
                        if not t.cancelled() and t.exception()
                        else None
                    )
                )
            except RuntimeError as e:
                logger.error(f"无法创建音频写入任务: {e}")
            except Exception as e:
                logger.error(f"创建音频写入任务失败: {e}", exc_info=True)

    def _on_incoming_json(self, json_data):
        """
        接收JSON数据回调.
        """
        asyncio.create_task(self.schedule_command(lambda: self._handle_incoming_json(json_data)))

    async def _handle_incoming_json(self, json_data):
        """
        处理JSON消息.
        """
        try:
            if not json_data:
                return

            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data
            msg_type = data.get("type", "")

            handler = self._message_handlers.get(msg_type)
            if handler:
                await handler(data)
            else:
                logger.warning(f"收到未知类型的消息: {msg_type}")

        except Exception as e:
            logger.error(f"处理JSON消息时出错: {e}", exc_info=True)

    async def _handle_tts_message(self, data):
        """
        处理TTS消息.
        """
        state = data.get("state", "")
        if state == "start":
            await self._handle_tts_start()
        elif state == "stop":
            await self._handle_tts_stop()
        elif state == "sentence_start":
            text = data.get("text", "")
            if text:
                logger.info(f"<< {text}")
                self.set_chat_message("assistant", text)

                import re

                match = re.search(r"((?:\d\s*){6,})", text)
                if match:
                    await asyncio.to_thread(handle_verification_code, text)

    async def _handle_tts_start(self):
        """
        处理TTS开始事件.
        """
        logger.info(f"TTS开始，当前状态: {self.device_state}")

        async with self._abort_lock:
            self.aborted = False

        if self.device_state in [DeviceState.IDLE, DeviceState.LISTENING]:
            await self._set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self):
        """
        处理TTS停止事件.
        """
        if self.device_state == DeviceState.SPEAKING:
            # 等待音频播放完成（改进：增加等待时间并移除过早的清空操作）
            if self.audio_codec:
                logger.debug("等待TTS音频播放完成...")
                await self.audio_codec.wait_for_audio_complete()
                logger.debug("TTS音频播放完成")

            # 仅在非打断情况下，等待一小段时间让缓冲区稳定
            if not self.aborted:
                await asyncio.sleep(0.2)  # 额外200ms确保尾音播放完整

            # 状态转换
            if self.keep_listening:
                await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
                await self._set_device_state(DeviceState.LISTENING)
            else:
                await self._set_device_state(DeviceState.IDLE)

    async def _handle_stt_message(self, data):
        """
        处理STT消息.
        """
        text = data.get("text", "")
        if text:
            logger.info(f">> {text}")
            self.set_chat_message("user", text)

    async def _handle_llm_message(self, data):
        """
        处理LLM消息.
        """
        emotion = data.get("emotion", "")
        if emotion:
            self.set_emotion(emotion)

    async def _on_audio_channel_opened(self):
        """
        音频通道打开回调.
        """
        logger.info("音频通道已打开")

        if self.audio_codec:
            await self.audio_codec.start_streams()

        # 发送物联网设备描述符
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()
        descriptors_json = await thing_manager.get_descriptors_json()
        await self.protocol.send_iot_descriptors(descriptors_json)
        await self._update_iot_states(False)

    async def _on_audio_channel_closed(self):
        """
        音频通道关闭回调.
        """
        logger.info("音频通道已关闭")
        await self._set_device_state(DeviceState.IDLE)
        self.keep_listening = False

    async def _initialize_wake_word_detector(self):
        """
        初始化唤醒词检测器.
        """
        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

            self.wake_word_detector = WakeWordDetector()

            # 设置回调
            self.wake_word_detector.on_detected(self._on_wake_word_detected)
            self.wake_word_detector.on_error = self._handle_wake_word_error

            await self.wake_word_detector.start(self.audio_codec)

            logger.info("唤醒词检测器初始化成功")

        except RuntimeError as e:
            logger.info(f"跳过唤醒词检测器初始化: {e}")
            self.wake_word_detector = None
        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            self.wake_word_detector = None

    async def _on_wake_word_detected(self, wake_word, full_text):
        """
        唤醒词检测回调.
        """
        logger.info(f"检测到唤醒词: {wake_word}")

        if self.device_state == DeviceState.IDLE:
            await self._set_device_state(DeviceState.CONNECTING)
            await self._connect_and_start_listening(wake_word)
        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def _connect_and_start_listening(self, wake_word):
        """
        连接服务器并开始监听.
        """
        try:
            if not await self.protocol.connect():
                logger.error("连接服务器失败")
                await self._set_device_state(DeviceState.IDLE)
                return

            if not await self.protocol.open_audio_channel():
                logger.error("打开音频通道失败")
                await self._set_device_state(DeviceState.IDLE)
                return

            await self.protocol.send_wake_word_detected("唤醒")
            self.keep_listening = True
            await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
            await self._set_device_state(DeviceState.LISTENING)

        except Exception as e:
            logger.error(f"连接和启动监听失败: {e}")
            await self._set_device_state(DeviceState.IDLE)

    def _handle_wake_word_error(self, error):
        """
        处理唤醒词检测器错误.
        """
        logger.error(f"唤醒词检测错误: {error}")

    async def _initialize_iot_devices(self):
        """
        初始化物联网设备.
        """
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()

        await thing_manager.initialize_iot_devices(self.config)
        logger.info("物联网设备初始化完成")

    async def _handle_iot_message(self, data):
        """
        处理物联网消息.
        """
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()
        commands = data.get("commands", [])
        print(f"物联网消息: {commands}")
        for command in commands:
            try:
                result = await thing_manager.invoke(command)
                logger.info(f"执行物联网命令结果: {result}")
            except Exception as e:
                logger.error(f"执行物联网命令失败: {e}")

    async def _update_iot_states(self, delta=None):
        """
        更新物联网设备状态.
        """
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()

        try:
            if delta is None:
                # 直接使用异步方法获取状态
                states_json = await thing_manager.get_states_json_str()
                await self.protocol.send_iot_states(states_json)
            else:
                # 直接使用异步方法获取状态变化
                changed, states_json = await thing_manager.get_states_json(delta=delta)
                if not delta or changed:
                    await self.protocol.send_iot_states(states_json)
        except Exception as e:
            logger.error(f"更新IoT状态失败: {e}")

    def _on_mode_changed(self):
        """
        处理对话模式变更.
        """
        # 注意：这是一个同步方法，在GUI回调中使用
        # 需要创建临时任务来执行异步锁操作
        try:
            # 快速检查当前状态，避免在GUI线程中执行复杂的异步操作
            if self.device_state != DeviceState.IDLE:
                return False

            self.keep_listening = not self.keep_listening
            return True
        except Exception as e:
            logger.error(f"模式变更检查失败: {e}")
            return False

    async def _safe_close_resource(self, resource, resource_name: str, close_method: str = "close"):
        """
        安全关闭资源的辅助方法.
        """
        if resource:
            try:
                close_func = getattr(resource, close_method, None)
                if close_func:
                    if asyncio.iscoroutinefunction(close_func):
                        await close_func()
                    else:
                        close_func()
                logger.info(f"{resource_name}已关闭")
            except Exception as e:
                logger.error(f"关闭{resource_name}失败: {e}")

    async def shutdown(self):
        """
        关闭应用程序.
        """
        if not self.running:
            return

        logger.info("正在关闭应用程序...")
        self.running = False

        # 设置关闭事件
        if self._shutdown_event is not None:
            self._shutdown_event.set()

        try:
            # 2. 关闭快捷键和GPIO按钮管理器
            await self._safe_close_resource(self.shortcut_manager, "快捷键管理器", "stop")
            await self._safe_close_resource(self.gpio_button_manager, "GPIO按钮管理器", "stop")

            # 3. 关闭唤醒词检测器
            await self._safe_close_resource(self.wake_word_detector, "唤醒词检测器", "stop")

            # 4. 取消所有长期任务
            if self._main_tasks:
                logger.info(f"取消 {len(self._main_tasks)} 个主要任务")
                tasks = list(self._main_tasks)
                for task in tasks:
                    if not task.done():
                        task.cancel()

                try:
                    # 等待任务取消完成
                    await asyncio.wait(tasks, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("部分任务取消超时")
                except Exception as e:
                    logger.warning(f"等待任务完成时出错: {e}")

                self._main_tasks.clear()

            # 5. 关闭协议连接
            if self.protocol:
                try:
                    await self.protocol.close_audio_channel()
                    logger.info("协议连接已关闭")
                except Exception as e:
                    logger.error(f"关闭协议连接失败: {e}")

            # 6. 关闭音频设备
            await self._safe_close_resource(self.audio_codec, "音频设备")

            # 7. 关闭MCP服务器
            await self._safe_close_resource(self.mcp_server, "MCP服务器")

            # 8. 清理队列
            try:
                for q in [
                    self.command_queue,
                ]:
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                logger.info("队列已清空")
            except Exception as e:
                logger.error(f"清空队列失败: {e}")

            # 9. 最后停止UI显示
            await self._safe_close_resource(self.display, "显示界面")

            logger.info("应用程序关闭完成")

        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}", exc_info=True)

    def _initialize_mcp_server(self):
        """
        初始化MCP服务器.
        """
        logger.info("初始化MCP服务器")
        # 设置发送回调
        self.mcp_server.set_send_callback(lambda msg: self.protocol.send_mcp_message(msg))
        # 添加通用工具
        self.mcp_server.add_common_tools()

    async def _handle_mcp_message(self, data):
        """
        处理MCP消息.
        """
        payload = data.get("payload")
        if payload:
            await self.mcp_server.parse_message(payload)

    async def _start_calendar_reminder_service(self):
        """
        启动日程提醒服务.
        """
        try:
            logger.info("启动日程提醒服务")
            from src.mcp.tools.calendar import get_reminder_service

            # 获取提醒服务实例（通过单例模式）
            reminder_service = get_reminder_service()

            # 启动提醒服务（服务内部会自动处理初始化和日程检查）
            await reminder_service.start()

            logger.info("日程提醒服务已启动")

        except Exception as e:
            logger.error(f"启动日程提醒服务失败: {e}", exc_info=True)

    async def _start_timer_service(self):
        """
        启动倒计时器服务.
        """
        try:
            logger.info("启动倒计时器服务")
            from src.mcp.tools.timer.timer_service import get_timer_service

            # 获取倒计时器服务实例（通过单例模式）
            get_timer_service()

            logger.info("倒计时器服务已启动并注册到资源管理器")

        except Exception as e:
            logger.error(f"启动倒计时器服务失败: {e}", exc_info=True)

    async def _initialize_shortcuts(self):
        """
        初始化快捷键管理器和GPIO按钮管理器.
        """
        try:
            # 初始化快捷键管理器
            from src.views.components.shortcut_manager import (
                start_global_shortcuts_async,
            )

            self.shortcut_manager = await start_global_shortcuts_async(logger)
            if self.shortcut_manager:
                logger.info("快捷键管理器初始化成功")
            else:
                logger.warning("快捷键管理器初始化失败")

            # 初始化GPIO按钮管理器（仅在树莓派上）
            try:
                from src.views.components.gpio_button_manager import (
                    start_gpio_button_async,
                )

                # 从配置中获取GPIO设置
                gpio_config = self.config.get_config("GPIO", {})
                pin = gpio_config.get("button_pin", 6)
                led_pin = gpio_config.get("led_pin", 5)
                pull_up = gpio_config.get("pull_up", True)
                debounce_time = gpio_config.get("debounce_time", 0.05)

                self.gpio_button_manager = await start_gpio_button_async(
                    pin=pin, pull_up=pull_up, debounce_time=debounce_time, led_pin=led_pin
                )

                if self.gpio_button_manager:
                    logger.info(f"GPIO按钮管理器初始化成功，监听引脚: {pin}")
                else:
                    logger.info("GPIO按钮管理器初始化跳过（非树莓派环境或初始化失败）")

            except Exception as gpio_e:
                logger.info(f"GPIO按钮管理器初始化跳过: {gpio_e}")
                self.gpio_button_manager = None

        except Exception as e:
            logger.error(f"初始化快捷键管理器失败: {e}", exc_info=True)
