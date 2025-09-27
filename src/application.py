import asyncio
import json
import signal
import sys
import threading
import time
import typing as _t  # noqa: F401
from typing import Set

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.mcp.mcp_server import McpServer
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.common_utils import handle_verification_code
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger
from src.utils.opus_loader import setup_opus

logger = get_logger(__name__)


def setup_signal_handler(sig, handler, description):
    """
    统一的信号处理器设置函数（跨平台尽力而为）.
    """
    try:
        signal.signal(sig, handler)
    except (AttributeError, ValueError) as e:
        print(f"注意: 无法设置{description}处理器: {e}")


def handle_sigint(signum, frame):
    app = Application.get_instance()
    if not app:
        sys.exit(0)

    # 使用app的主循环，更稳定且跨线程安全
    loop = app._main_loop
    if loop and not loop.is_closed():
        # 直接创建task在指定的循环中
        def create_shutdown_task():
            try:
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(app.shutdown(), loop)
                else:
                    loop.create_task(app.shutdown())
            except Exception as e:
                print(f"创建shutdown任务失败: {e}")
                sys.exit(0)

        loop.call_soon_threadsafe(create_shutdown_task)
    else:
        # 主循环未就绪或已关闭，直接退出
        sys.exit(0)


# 设置信号处理器：所有平台尽量设置 SIGINT；支持则设置 SIGTERM；若存在 SIGTRAP 则忽略它
setup_signal_handler(signal.SIGINT, handle_sigint, "SIGINT")
if hasattr(signal, "SIGTERM"):
    setup_signal_handler(signal.SIGTERM, handle_sigint, "SIGTERM")
if hasattr(signal, "SIGTRAP"):
    setup_signal_handler(signal.SIGTRAP, signal.SIG_IGN, "SIGTRAP")

setup_opus()

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
        self.aborted_event = None  # 将在_initialize_async_objects中初始化

        # 监听模式和AEC启用状态
        self.listening_mode = ListeningMode.AUTO_STOP
        self.aec_enabled = self.config.get_config("AEC_OPTIONS.ENABLED", True)

        # 异步组件
        self.audio_codec = None
        self.protocol = None
        self.display = None
        self.wake_word_detector = None
        # 任务管理
        self.running = False
        self._main_tasks: Set[asyncio.Task] = set()
        # 轻量后台任务池（非长期任务），用于关停时统一取消
        self._bg_tasks: Set[asyncio.Task] = set()

        # 运行指标/计数
        self._command_dropped_count = 0

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

        # 并发控制锁 - 将在_initialize_async_objects中初始化
        self._state_lock = None
        self._abort_lock = None

        # 音频与发送并发限制（避免任务风暴）
        try:
            audio_write_cc = int(
                self.config.get_config("APP.AUDIO_WRITE_CONCURRENCY", 4)
            )
        except Exception:
            audio_write_cc = 4
        try:
            send_audio_cc = int(self.config.get_config("APP.SEND_AUDIO_CONCURRENCY", 4))
        except Exception:
            send_audio_cc = 4
        # 保存配置值，在_initialize_async_objects中创建Semaphore
        self._audio_write_cc = audio_write_cc
        self._send_audio_cc = send_audio_cc
        self._audio_write_semaphore = None
        self._send_audio_semaphore = None

        # 最近一次接收到服务端音频的时间（用于应对TTS起止近邻竞态）
        self._last_incoming_audio_at: float = 0.0

        # 音频静默检测（事件驱动取代固定sleep）
        try:
            tail_silence_ms = int(
                self.config.get_config("APP.TTS_TAIL_SILENCE_MS", 150)
            )
        except Exception:
            tail_silence_ms = 150
        try:
            tail_wait_timeout_ms = int(
                self.config.get_config("APP.TTS_TAIL_WAIT_TIMEOUT_MS", 800)
            )
        except Exception:
            tail_wait_timeout_ms = 800
        self._incoming_audio_silence_sec: float = max(0.0, tail_silence_ms / 1000.0)
        self._incoming_audio_tail_timeout_sec: float = max(
            0.1, tail_wait_timeout_ms / 1000.0
        )
        self._incoming_audio_idle_event = None
        self._incoming_audio_idle_handle = None

        logger.debug("Application实例初始化完成")

    async def run(self, **kwargs):
        """
        启动应用程序.
        """
        logger.info("启动应用程序，参数: %s", kwargs)

        mode = kwargs.get("mode", "gui")
        protocol = kwargs.get("protocol", "websocket")

        return await self._run_application_core(protocol, mode)

    def _initialize_async_objects(self):
        """
        初始化异步对象 - 必须在事件循环运行后调用.
        """
        logger.debug("初始化异步对象")
        # 从配置读取命令队列上限，默认 256
        try:
            maxsize = int(self.config.get_config("APP.COMMAND_QUEUE_MAXSIZE", 256))
        except Exception:
            maxsize = 256
        self.command_queue = asyncio.Queue(maxsize=maxsize)
        self._shutdown_event = asyncio.Event()

        # 初始化异步锁
        self._state_lock = asyncio.Lock()
        self._abort_lock = asyncio.Lock()

        # 初始化中止事件
        self.aborted_event = asyncio.Event()
        self.aborted_event.clear()

        # 初始化信号量
        self._audio_write_semaphore = asyncio.Semaphore(self._audio_write_cc)
        self._send_audio_semaphore = asyncio.Semaphore(self._send_audio_cc)

        # 初始化音频静默事件（默认置为已静默，避免无谓等待）
        self._incoming_audio_idle_event = asyncio.Event()
        self._incoming_audio_idle_event.set()

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

            # 等待关闭信号
            await self._shutdown_event.wait()

            return 0

        except Exception as e:
            logger.error(f"启动应用程序失败: {e}", exc_info=True)
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
            import os as _os

            if _os.getenv("XIAOZHI_DISABLE_AUDIO") == "1":
                logger.warning("已通过环境变量禁用音频初始化 (XIAOZHI_DISABLE_AUDIO=1)")
                self.audio_codec = None
                return
            logger.debug("开始初始化音频编解码器")
            from src.audio_codecs.audio_codec import AudioCodec

            self.audio_codec = AudioCodec()
            await self.audio_codec.initialize()

            # 设置实时编码回调 - 关键：确保麦克风数据实时发送
            self.audio_codec.set_encoded_audio_callback(self._on_encoded_audio)

            logger.info("音频编解码器初始化成功")

        except Exception as e:
            logger.error("初始化音频设备失败: %s", e, exc_info=True)
            # 确保初始化失败时audio_codec为None
            self.audio_codec = None

    def _on_encoded_audio(self, encoded_data: bytes):
        """处理编码后的音频数据回调.

        注意：这个回调在音频驱动线程中被调用，需要线程安全地调度到主事件循环。
        关键逻辑：只在LISTENING状态或SPEAKING+REALTIME模式下发送音频数据
        """
        try:
            # 1. LISTENING状态：总是发送（包括实时模式下TTS播放期间）
            # 2. SPEAKING状态：只有在REALTIME模式下才发送（向后兼容）
            should_send = self._should_send_microphone_audio()

            if (
                should_send
                and self.protocol
                and self.protocol.is_audio_channel_opened()
            ):

                # 线程安全地调度到主事件循环
                if self._main_loop and not self._main_loop.is_closed():
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_audio_send, encoded_data
                    )

        except Exception as e:
            logger.error(f"处理编码音频数据回调失败: {e}")

    def _schedule_audio_send(self, encoded_data: bytes):
        """
        在主事件循环中调度音频发送任务.
        """
        try:
            if not self.running or not self.protocol:
                return
            # 再次检查状态（可能在调度期间状态已改变）
            # 核心逻辑：LISTENING状态或SPEAKING+REALTIME模式下发送音频
            should_send = self._should_send_microphone_audio()

            if (
                should_send
                and self.protocol
                and self.protocol.is_audio_channel_opened()
            ):
                # 使用call_soon_threadsafe避免qasync任务重入
                if self._main_loop and not self._main_loop.is_closed():
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_audio_send_task, encoded_data
                    )

        except Exception as e:
            logger.error(f"调度音频发送失败: {e}")

    def _schedule_audio_send_task(self, encoded_data: bytes):
        """
        在主事件循环中创建音频发送任务.
        """
        try:
            if not self.running or not self.protocol:
                return
            
            # 并发限制，避免任务风暴
            async def _send():
                async with self._send_audio_semaphore:
                    await self.protocol.send_audio(encoded_data)

            self._create_background_task(_send(), "发送音频数据")
        except Exception as e:
            logger.error(f"创建音频发送任务失败: {e}", exc_info=True)

    def _schedule_audio_write_task(self, data: bytes):
        """
        在主事件循环中创建音频写入任务.
        """
        try:
            if not self.running or not self.audio_codec:
                return
            
            # 音频数据处理需要实时性，限制并发，避免任务风暴
            async def _write():
                async with self._audio_write_semaphore:
                    await self.audio_codec.write_audio(data)

            self._create_background_task(_write(), "写入音频数据")
        except Exception as e:
            logger.error(f"创建音频写入任务失败: {e}", exc_info=True)

    def _should_send_microphone_audio(self) -> bool:
        """
        是否应发送麦克风编码后的音频数据到协议层。
        """
        return self.device_state == DeviceState.LISTENING or (
            self.device_state == DeviceState.SPEAKING
            and self.aec_enabled
            and self.keep_listening
            and self.listening_mode == ListeningMode.REALTIME
        )

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
            from src.display.gui_display import GuiDisplay
            self.display = GuiDisplay()
            self._setup_gui_callbacks()
        else:
            from src.display.cli_display import CliDisplay

            self.display = CliDisplay()
            self._setup_cli_callbacks()

    def _create_async_callback(self, coro_func, *args):
        """
        创建异步回调函数的辅助方法 - 使用call_soon_threadsafe避免qasync任务重入.
        """

        def _callback():
            try:
                if self._main_loop and not self._main_loop.is_closed():
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_gui_callback, coro_func, args
                    )
            except Exception as e:
                logger.error(f"调度GUI回调失败: {e}", exc_info=True)

        return _callback

    def _schedule_gui_callback(self, coro_func, args):
        """
        在主事件循环中调度GUI回调.
        """
        try:
            if not self.running:
                return
            
            async def _execute():
                await coro_func(*args)
            
            task = asyncio.create_task(_execute())
            
            def _on_done(t):
                if not t.cancelled() and t.exception():
                    logger.error(f"GUI回调任务异常: {t.exception()}", exc_info=True)

            task.add_done_callback(_on_done)
        except Exception as e:
            logger.error(f"执行GUI回调失败: {e}", exc_info=True)

    def _setup_gui_callbacks(self):
        """
        设置GUI回调函数.
        """
        self._create_background_task(
            self.display.set_callbacks(
                press_callback=self._create_async_callback(self.start_listening),
                release_callback=self._create_async_callback(self.stop_listening),
                mode_callback=self._on_mode_changed,
                auto_callback=self._create_async_callback(self.toggle_chat_state),
                abort_callback=self._create_async_callback(
                    self.abort_speaking, AbortReason.WAKE_WORD_DETECTED
                ),
                send_text_callback=self._send_text_tts,
            ),
            "GUI回调注册",
        )

    def _setup_cli_callbacks(self):
        """
        设置CLI回调函数.
        """
        self._create_background_task(
            self.display.set_callbacks(
                auto_callback=self._create_async_callback(self.toggle_chat_state),
                abort_callback=self._create_async_callback(
                    self.abort_speaking, AbortReason.WAKE_WORD_DETECTED
                ),
                send_text_callback=self._send_text_tts,
            ),
            "CLI回调注册",
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

    def _create_background_task(
        self, coro, name: str
    ):  # type: (asyncio.coroutines, str) -> _t.Optional[asyncio.Task]
        """
        创建不纳入 _main_tasks 管理的短期后台任务，并统一记录异常日志。 任务将纳入 _bg_tasks，关停时统一取消。
        """

        # 关停时避免再创建新的后台任务
        if (not self.running) or (
            self._shutdown_event and self._shutdown_event.is_set()
        ):
            logger.debug(f"跳过后台任务创建（应用正在关闭）: {name}")
            return None

        task = asyncio.create_task(coro, name=name)
        self._bg_tasks.add(task)

        def done_callback(t):
            if not t.cancelled() and t.exception():
                logger.error(
                    f"后台任务 {name} 异常结束: {t.exception()}", exc_info=True
                )
            # 从后台任务池移除
            self._bg_tasks.discard(t)

        task.add_done_callback(done_callback)
        return task

    async def _command_processor(self):
        """
        命令处理器.
        """
        while self.running:
            try:
                # 阻塞等待命令；在 shutdown 时通过取消任务立即唤醒
                command = await self.command_queue.get()

                # 关闭过程中若状态已变更，直接退出
                if not self.running:
                    break

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

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"命令处理错误: {e}", exc_info=True)

    async def _start_gui_display(self):
        """
        启动GUI显示.
        """
        # 在qasync环境中，GUI可以直接在主线程启动
        await self.display.start()

    async def _start_cli_display(self):
        """
        启动CLI显示.
        """
        await self.display.start()

    async def schedule_command(self, command):
        """
        调度命令到命令队列.
        """
        self._enqueue_command(command)

    def schedule_command_nowait(self, command) -> None:
        """同步/跨线程安全的命令调度：将入队操作切回主事件循环线程。

        适用于无法 await 的场景（同步回调、其他线程等）。
        """
        try:
            if self._main_loop and not self._main_loop.is_closed():
                self._main_loop.call_soon_threadsafe(self._enqueue_command, command)
            else:
                logger.warning("主事件循环未就绪，拒绝新命令")
        except Exception as e:
            logger.error(f"同步命令调度失败: {e}", exc_info=True)

    def _enqueue_command(self, command) -> None:
        """
        实际的入队实现：仅在事件循环线程中执行。
        """
        # 停机中或未初始化则拒绝
        if (not self.running) or (
            self._shutdown_event and self._shutdown_event.is_set()
        ):
            logger.warning("应用正在关闭，拒绝新命令")
            return
        if self.command_queue is None:
            logger.warning("命令队列未初始化，丢弃命令")
            return

        try:
            # 使用 put_nowait 避免阻塞，如果队列满则记录警告
            self.command_queue.put_nowait(command)
        except asyncio.QueueFull:
            logger.warning("命令队列已满，尝试丢弃最旧命令重新入队")
            try:
                self.command_queue.get_nowait()
                self.command_queue.put_nowait(command)
                self._command_dropped_count += 1
                logger.info(
                    f"清理旧命令后重新添加，累计丢弃: {self._command_dropped_count}"
                )
            except asyncio.QueueEmpty:
                pass

    async def _start_listening_common(self, listening_mode, keep_listening_flag):
        """
        通用的开始监听逻辑.
        """
        async with self._state_lock:
            if self.device_state != DeviceState.IDLE:
                return False

        if not self.protocol:
            logger.error("协议未初始化，无法开始监听")
            return False

        if not self.protocol.is_audio_channel_opened():
            success = await self.protocol.open_audio_channel()
            if not success:
                return False

        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        await self._set_device_state(DeviceState.CONNECTING)

        # 保存监听模式（重要：用于音频发送判断）
        self.listening_mode = listening_mode
        self.keep_listening = keep_listening_flag
        try:
            await self.protocol.send_start_listening(listening_mode)
        except Exception as e:
            logger.error(f"发送开始监听指令失败: {e}", exc_info=True)
            await self._set_device_state(DeviceState.IDLE)
            try:
                await self.protocol.close_audio_channel()
            except Exception:
                pass
            return False
        await self._set_device_state(DeviceState.LISTENING)
        return True

    async def start_listening(self):
        """
        开始监听.
        """
        self.schedule_command_nowait(self._start_listening_impl)

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
        self.schedule_command_nowait(self._stop_listening_impl)

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
        self.schedule_command_nowait(self._toggle_chat_state_impl)

    async def _toggle_chat_state_impl(self):
        """
        切换聊天状态的实现.
        """
        if self.device_state == DeviceState.IDLE:
            # 根据AEC启用状态决定监听模式
            listening_mode = (
                ListeningMode.REALTIME if self.aec_enabled else ListeningMode.AUTO_STOP
            )
            await self._start_listening_common(listening_mode, True)

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
        self.aborted_event.set()
        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        try:
            await self.protocol.send_abort_speaking(reason)
            await self._set_device_state(DeviceState.IDLE)
            restart = (
                reason == AbortReason.WAKE_WORD_DETECTED
                and self.keep_listening
                and self.protocol.is_audio_channel_opened()
            )

        except Exception as e:
            logger.error(f"中止语音时出错: {e}")
            restart = False
        finally:
            self.aborted = False
            self.aborted_event.clear()

        if restart:
            await asyncio.sleep(0.1)
            try:
                # 打断后重新启动监听（使用当前模式）
                await self.protocol.send_start_listening(self.listening_mode)
                await self._set_device_state(DeviceState.LISTENING)
            except Exception as e:
                logger.error(f"恢复监听失败: {e}")

    async def _set_device_state(self, state):
        """
        设置设备状态 - 通过队列确保顺序执行.
        """
        self.schedule_command_nowait(lambda: self._set_device_state_impl(state))

    def _update_display_async(self, update_func, *args):
        """
        异步更新显示的辅助方法 - 使用call_soon_threadsafe避免qasync任务重入.
        """
        if self.display and self._main_loop:
            try:
                # 使用call_soon_threadsafe避免qasync任务重入问题
                self._main_loop.call_soon_threadsafe(
                    self._schedule_display_update, update_func, args
                )
            except Exception as e:
                logger.error(f"调度显示更新失败: {e}", exc_info=True)

    def _schedule_display_update(self, update_func, args):
        """
        在主事件循环中调度显示更新.
        """
        try:
            if not self.running or not self.display:
                return
            
            # 创建后台任务更新显示，避免阻塞
            async def _update():
                await update_func(*args)
            
            self._create_background_task(_update(), "显示更新")
        except Exception as e:
            logger.error(f"调度显示更新失败: {e}", exc_info=True)

    async def _set_device_state_impl(self, state):
        """
        设备状态设置.
        """
        # 在锁内仅完成状态变更与后续动作的选择，避免在锁内执行I/O
        perform_idle = False
        perform_listening = False
        display_update = None

        async with self._state_lock:
            if self.device_state == state:
                return
            logger.debug(f"设备状态变更: {self.device_state} -> {state}")
            self.device_state = state
            if state == DeviceState.IDLE:
                perform_idle = True
            elif state == DeviceState.CONNECTING:
                display_update = ("连接中...", False)
            elif state == DeviceState.LISTENING:
                perform_listening = True
            elif state == DeviceState.SPEAKING:
                display_update = ("说话中...", True)

        # 锁外执行I/O与耗时操作
        if perform_idle:
            await self._handle_idle_state()
        elif perform_listening:
            await self._handle_listening_state()
        if display_update is not None:
            text, connected = display_update
            self._update_display_async(self.display.update_status, text, connected)

    async def _handle_idle_state(self):
        """
        处理空闲状态.
        """
        # UI更新异步执行（待命：默认视为未连接）
        self._update_display_async(self.display.update_status, "待命", False)

        # 设置表情
        self.set_emotion("neutral")

    async def _handle_listening_state(self):
        """
        处理监听状态.
        """
        # UI更新异步执行（聆听中：连接已建立）
        self._update_display_async(self.display.update_status, "聆听中...", True)

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
        self.schedule_command_nowait(self._handle_network_error)

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
        # 在实时模式下，TTS播放时设备状态可能保持LISTENING，也需要播放音频
        should_play_audio = self.device_state == DeviceState.SPEAKING or (
            self.device_state == DeviceState.LISTENING
            and self.listening_mode == ListeningMode.REALTIME
        )

        if should_play_audio and self.audio_codec and self.running:
            # 若是 IDLE，恢复为 SPEAKING（通过命令队列，线程安全、可重入）
            if self.device_state == DeviceState.IDLE:
                self.schedule_command_nowait(
                    lambda: self._set_device_state_impl(DeviceState.SPEAKING)
                )

            try:
                # 记录最近一次收到服务端音频的时间
                self._last_incoming_audio_at = time.monotonic()

                # 标记“非静默”，并重置定时器：在静默期后置位事件
                try:
                    if self._incoming_audio_idle_event:
                        self._incoming_audio_idle_event.clear()
                    # 取消旧的静默计时器
                    if self._incoming_audio_idle_handle:
                        self._incoming_audio_idle_handle.cancel()
                        self._incoming_audio_idle_handle = None
                    # 安排新的静默计时任务（tail_silence_ms 后置位）

                    def _mark_idle():
                        if self._incoming_audio_idle_event:
                            self._incoming_audio_idle_event.set()

                    if self._main_loop and not self._main_loop.is_closed():
                        self._incoming_audio_idle_handle = self._main_loop.call_later(
                            self._incoming_audio_silence_sec,
                            _mark_idle,
                        )
                except Exception:
                    pass

                # 若当前处于IDLE，说明出现了“停止后紧接着开始”的起止竞态，先切到SPEAKING
                if self.device_state == DeviceState.IDLE:
                    self.schedule_command_nowait(
                        lambda: self._set_device_state_impl(DeviceState.SPEAKING)
                    )

                # 使用call_soon_threadsafe避免qasync任务重入
                if self._main_loop and not self._main_loop.is_closed():
                    self._main_loop.call_soon_threadsafe(
                        self._schedule_audio_write_task, data
                    )
            except RuntimeError as e:
                logger.error(f"无法创建音频写入任务: {e}")
            except Exception as e:
                logger.error(f"创建音频写入任务失败: {e}", exc_info=True)

    def _on_incoming_json(self, json_data):
        """
        接收JSON数据回调.
        """
        self.schedule_command_nowait(lambda: self._handle_incoming_json(json_data))

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
        logger.info(
            f"TTS开始，当前状态: {self.device_state}，监听模式: {self.listening_mode}"
        )

        async with self._abort_lock:
            self.aborted = False
            self.aborted_event.clear()

        # 在实时模式下，如果当前处于LISTENING状态，保持LISTENING状态以支持双向对话
        # 只有在IDLE状态或非实时模式下才转换到SPEAKING状态
        if self.device_state == DeviceState.IDLE:
            await self._set_device_state(DeviceState.SPEAKING)
        elif (
            self.device_state == DeviceState.LISTENING
            and self.listening_mode != ListeningMode.REALTIME
        ):
            await self._set_device_state(DeviceState.SPEAKING)
        elif (
            self.device_state == DeviceState.LISTENING
            and self.listening_mode == ListeningMode.REALTIME
        ):
            logger.info("实时模式下TTS开始，保持LISTENING状态以支持双向对话")

    async def _handle_tts_stop(self):
        """
        处理TTS停止事件.
        """
        logger.info(
            f"TTS停止，当前状态: {self.device_state}，监听模式: {self.listening_mode}"
        )

        # 等待音频播放完成
        if self.audio_codec:
            logger.debug("等待TTS音频播放完成...")
            try:
                await self.audio_codec.wait_for_audio_complete()
            except Exception as e:
                logger.warning(f"TTS音频播放等待失败: {e}")
            else:
                logger.debug("TTS音频播放完成")

        # 仅在非打断情况下，等待“静默事件”
        if not self.aborted_event.is_set():
            try:
                if self._incoming_audio_idle_event:
                    # 最长等待一个超时时间，避免异常情况下卡住
                    try:
                        await asyncio.wait_for(
                            self._incoming_audio_idle_event.wait(),
                            timeout=self._incoming_audio_tail_timeout_sec,
                        )
                    except asyncio.TimeoutError:
                        pass
            except Exception:
                pass

        # 状态转换逻辑优化
        if self.device_state == DeviceState.SPEAKING:
            # 传统模式：从SPEAKING转换到LISTENING或IDLE
            if self.keep_listening:
                await self.protocol.send_start_listening(self.listening_mode)
                await self._set_device_state(DeviceState.LISTENING)
            else:
                await self._set_device_state(DeviceState.IDLE)
        elif (
            self.device_state == DeviceState.LISTENING
            and self.listening_mode == ListeningMode.REALTIME
        ):
            # 实时模式：已经在LISTENING状态，无需状态转换，音频流继续
            logger.info("实时模式TTS结束，保持LISTENING状态，音频流继续")

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
        try:
            if self.audio_codec:
                await self.audio_codec.start_streams()

            # 发送物联网设备描述符
            from src.iot.thing_manager import ThingManager

            thing_manager = ThingManager.get_instance()
            descriptors_json = await thing_manager.get_descriptors_json()
            await self.protocol.send_iot_descriptors(descriptors_json)
            await self._update_iot_states(False)
        except Exception as e:
            logger.error(f"音频通道打开回调处理失败: {e}", exc_info=True)

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
            if not await self.protocol.open_audio_channel():
                logger.error("打开音频通道失败")
                await self._set_device_state(DeviceState.IDLE)
                return
            self.keep_listening = True
            # 根据AEC启用状态决定监听模式
            listening_mode = (
                ListeningMode.REALTIME if self.aec_enabled else ListeningMode.AUTO_STOP
            )
            self.listening_mode = listening_mode
            await self.protocol.send_start_listening(listening_mode)
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
        logger.info(f"物联网消息: {commands}")
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

    async def _safe_close_resource(
        self, resource, resource_name: str, close_method: str = "close"
    ):
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
            # 2. 关闭唤醒词检测器
            await self._safe_close_resource(
                self.wake_word_detector, "唤醒词检测器", "stop"
            )

            # 3. 取消所有长期任务
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

            # 4. 取消后台任务（短期任务池）
            try:
                if self._bg_tasks:
                    for t in list(self._bg_tasks):
                        if not t.done():
                            t.cancel()
                    await asyncio.gather(*self._bg_tasks, return_exceptions=True)
                self._bg_tasks.clear()
            except Exception as e:
                logger.warning(f"取消后台任务时出错: {e}")

            # 5. 关闭协议连接（尽早关闭，避免事件循环结束后仍有网络等待）
            if self.protocol:
                try:
                    await self.protocol.close_audio_channel()
                    logger.info("协议连接已关闭")
                except Exception as e:
                    logger.error(f"关闭协议连接失败: {e}")

            # 6. 关闭音频设备（先停流后彻底关闭，缓解C扩展退出竞态）
            if self.audio_codec:
                try:
                    await self.audio_codec.stop_streams()
                except Exception:
                    pass
            # 尽早释放音频资源，避免事件循环关闭后再 awaiting 内部 sleep
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

            # 9. 取消尾静默定时器并置静默事件，避免等待
            try:
                if self._incoming_audio_idle_handle:
                    self._incoming_audio_idle_handle.cancel()
                    self._incoming_audio_idle_handle = None
                if self._incoming_audio_idle_event:
                    self._incoming_audio_idle_event.set()
            except Exception:
                pass

            # 10. 最后停止UI显示
            await self._safe_close_resource(self.display, "显示界面")

            logger.info("应用程序关闭完成")

        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}", exc_info=True)

    def _initialize_mcp_server(self):
        """
        初始化MCP服务器.
        """
        logger.info("初始化MCP服务器")
        # 设置异步发送回调 - MCP服务器期望async回调
        self.mcp_server.set_send_callback(self._send_mcp_message_async)
        # 添加通用工具
        self.mcp_server.add_common_tools()

    async def _send_mcp_message_async(self, msg):
        """
        MCP消息发送回调（异步接口）- 使用call_soon_threadsafe避免qasync任务重入.
        """
        try:
            if not self.protocol or not self._main_loop:
                logger.warning("协议未初始化或事件循环不可用，丢弃MCP消息")
                return
            
            # 使用call_soon_threadsafe安全地调度到主事件循环
            self._main_loop.call_soon_threadsafe(
                self._schedule_mcp_send, msg
            )
            # 确保异步回调快速返回
            await asyncio.sleep(0)
        except Exception as e:
            logger.error(f"调度MCP消息发送失败: {e}", exc_info=True)

    def _schedule_mcp_send(self, msg):
        """
        在主事件循环中调度MCP消息发送.
        """
        try:
            if not self.running or not self.protocol:
                return
            
            # 创建后台任务发送MCP消息，避免阻塞
            async def _send():
                await self.protocol.send_mcp_message(msg)
            
            self._create_background_task(_send(), "发送MCP消息")
        except Exception as e:
            logger.error(f"调度MCP消息发送失败: {e}", exc_info=True)

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
        初始化快捷键管理器.
        """
        try:
            from src.views.components.shortcut_manager import (
                start_global_shortcuts_async,
            )

            shortcut_manager = await start_global_shortcuts_async(logger)
            if shortcut_manager:
                logger.info("快捷键管理器初始化成功")
            else:
                logger.warning("快捷键管理器初始化失败")
        except Exception as e:
            logger.error(f"初始化快捷键管理器失败: {e}", exc_info=True)
