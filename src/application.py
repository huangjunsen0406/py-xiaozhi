import asyncio
import json
import signal
import sys
import weakref
from typing import Set

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.core.resource_manager import (
    ResourceType,
    get_resource_manager,
    shutdown_all_resources,
)
from src.display import gui_display

# MCP服务器
from src.mcp.mcp_server import McpServer
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.common_utils import handle_verification_code
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

# 处理opus动态库
from src.utils.opus_loader import setup_opus

setup_opus()

logger = get_logger(__name__)

try:
    import opuslib  # noqa: F401
except Exception as e:
    logger.critical("导入 opuslib 失败: %s", e, exc_info=True)
    logger.critical("请确保 opus 动态库已正确安装或位于正确的位置")
    sys.exit(1)


class Application:
    """基于纯asyncio的应用程序架构"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            logger.debug("创建Application单例实例")
            cls._instance = Application()
        return cls._instance

    def __init__(self):
        """初始化应用程序"""
        if Application._instance is not None:
            logger.error("尝试创建Application的多个实例")
            raise Exception("Application是单例类，请使用get_instance()获取实例")
        Application._instance = self

        logger.debug("初始化Application实例")

        # 配置管理
        self.config = ConfigManager.get_instance()
        # self.config._initialize_mqtt_info()

        # 状态管理
        self.device_state = DeviceState.IDLE
        self.voice_detected = False
        self.keep_listening = False
        self.aborted = False
        self.current_text = ""
        self.current_emotion = "neutral"
        self.is_tts_playing = False

        # 异步组件
        self.audio_codec = None
        self.protocol = None
        self.display = None
        self.wake_word_detector = None

        # 任务管理
        self.running = False
        self._main_tasks: Set[asyncio.Task] = set()
        self._background_tasks: Set[asyncio.Task] = set()

        # 事件队列（替代threading.Event）
        self.audio_input_queue: asyncio.Queue = asyncio.Queue()
        self.audio_output_queue: asyncio.Queue = asyncio.Queue()
        self.command_queue: asyncio.Queue = asyncio.Queue()

        # 任务取消事件
        self._shutdown_event = asyncio.Event()

        # 保存主线程的事件循环（稍后在run方法中设置）
        self._main_loop = None

        # MCP服务器
        self.mcp_server = McpServer.get_instance()

        logger.debug("Application实例初始化完成")

    async def run(self, **kwargs):
        """启动应用程序"""
        logger.info("启动应用程序，参数: %s", kwargs)

        mode = kwargs.get("mode", "gui")
        protocol = kwargs.get("protocol", "websocket")
        skip_activation = kwargs.get("skip_activation", False)

        if mode == "gui":
            # GUI模式：需要创建Qt应用和qasync事件循环
            return await self._run_gui_mode(protocol, skip_activation)
        else:
            # CLI模式：使用标准asyncio
            return await self._run_cli_mode(protocol, skip_activation)

    async def _run_gui_mode(self, protocol: str, skip_activation: bool):
        """在GUI模式下运行应用程序"""
        try:
            import qasync
            from PyQt5.QtWidgets import QApplication
        except ImportError:
            logger.error("GUI模式需要qasync和PyQt5库，请安装: pip install qasync PyQt5")
            return 1

        try:
            # 创建QApplication
            app = QApplication(sys.argv)

            # 创建qasync事件循环
            loop = qasync.QEventLoop(app)
            asyncio.set_event_loop(loop)

            # 在qasync环境中运行应用程序
            with loop:
                try:
                    task = self._run_application_core(protocol, "gui", skip_activation)
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

    async def _run_cli_mode(self, protocol: str, skip_activation: bool):
        """在CLI模式下运行应用程序"""
        try:
            return await self._run_application_core(protocol, "cli", skip_activation)
        except Exception as e:
            logger.error(f"CLI应用程序异常退出: {e}", exc_info=True)
            return 1

    async def _run_application_core(
        self, protocol: str, mode: str, skip_activation: bool
    ):
        """应用程序核心运行逻辑"""
        try:
            # 处理激活流程
            if not skip_activation:
                if not await self._handle_activation_process(mode):
                    logger.error("设备激活失败，程序退出")
                    return 1
            else:
                logger.warning("跳过激活流程（调试模式）")

            self.running = True

            # 保存主线程的事件循环
            self._main_loop = asyncio.get_running_loop()

            # 设置信号处理
            self._setup_signal_handlers()

            # 初始化组件
            await self._initialize_components(mode, protocol)

            # 启动核心任务
            await self._start_core_tasks()

            # 启动全局快捷键服务并注册到资源管理器
            await self._start_global_shortcuts()

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

    async def _handle_activation_process(self, mode: str) -> bool:
        """处理激活流程"""
        logger.info("检查设备激活状态...")

        # 检查是否已激活
        if await self._check_activation_status():
            logger.info("设备已激活，直接启动应用程序")
            return True

        logger.info("设备未激活，启动激活流程...")

        # 根据模式选择激活方式
        if mode == "gui":
            activation_success = await self._run_gui_activation_process()
        else:  # CLI模式
            activation_success = await self._run_cli_activation_process()

        return activation_success

    async def _check_activation_status(self) -> bool:
        """检查激活状态"""
        try:
            from src.utils.device_fingerprint import DeviceFingerprint

            device_fp = DeviceFingerprint.get_instance()
            is_activated = device_fp.is_activated()

            logger.info(f"设备激活状态: {'已激活' if is_activated else '未激活'}")
            return is_activated

        except Exception as e:
            logger.error(f"检查激活状态失败: {e}", exc_info=True)
            return False

    async def _run_gui_activation_process(self) -> bool:
        """运行GUI激活流程"""
        try:
            from src.views.activation.activation_window import ActivationWindow

            logger.info("开始GUI设备激活流程")

            # 创建激活窗口
            activation_window = ActivationWindow()

            # 创建Future来等待激活完成
            activation_future = asyncio.Future()

            # 设置激活完成回调
            def on_activation_completed(success: bool):
                logger.info(f"GUI激活流程完成: 成功={success}")
                if not activation_future.done():
                    activation_future.set_result(success)

            # 设置窗口关闭回调
            def on_window_closed():
                logger.info("激活窗口被关闭")
                if not activation_future.done():
                    activation_future.set_result(False)

            # 连接信号
            activation_window.activation_completed.connect(on_activation_completed)
            activation_window.window_closed.connect(on_window_closed)

            # 显示激活窗口
            activation_window.show()

            # 等待激活完成
            activation_success = await activation_future

            # 关闭窗口
            activation_window.close()

            logger.info(f"GUI设备激活{'成功' if activation_success else '失败'}")
            return activation_success

        except Exception as e:
            logger.error(f"GUI激活流程异常: {e}", exc_info=True)
            return False

    async def _run_cli_activation_process(self) -> bool:
        """运行CLI激活流程"""
        try:
            from src.views.activation.cli_activation import CLIActivation

            logger.info("开始CLI设备激活流程")

            # 创建CLI激活处理器
            cli_activation = CLIActivation()

            # 运行激活流程
            activation_success = await cli_activation.run_activation_process()

            logger.info(f"CLI设备激活{'成功' if activation_success else '失败'}")
            return activation_success

        except Exception as e:
            logger.error(f"CLI激活流程异常: {e}", exc_info=True)
            return False

    def _setup_signal_handlers(self):
        """设置信号处理器"""

        def signal_handler():
            logger.info("接收到中断信号，开始关闭...")
            asyncio.create_task(self.shutdown())

        # 设置信号处理
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGINT, signal_handler)
            loop.add_signal_handler(signal.SIGTERM, signal_handler)
        except NotImplementedError:
            # Windows不支持add_signal_handler
            signal.signal(signal.SIGINT, lambda s, f: signal_handler())

    async def _initialize_components(self, mode: str, protocol: str):
        """初始化应用程序组件"""
        logger.info("正在初始化应用程序组件...")

        # 设置显示类型（必须在设备状态设置之前）
        self._set_display_type(mode)

        # 设置设备状态
        await self._set_device_state(DeviceState.IDLE)

        # 初始化物联网设备
        await self._initialize_iot_devices()

        # 初始化MCP服务器
        self._initialize_mcp_server()

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

        logger.info("应用程序组件初始化完成")

    async def _initialize_audio(self):
        """初始化音频编解码器"""
        try:
            logger.debug("开始初始化音频编解码器")
            from src.audio_codecs.audio_codec import AudioCodec

            self.audio_codec = AudioCodec()
            await self.audio_codec.initialize()

            # 注册到资源管理器
            resource_manager = get_resource_manager()
            await resource_manager.register_resource(
                resource_id="audio_codec",
                resource=self.audio_codec,
                cleanup_func=self.audio_codec.close,
                resource_type=ResourceType.AUDIO_CODEC,
                name="音频编解码器",
                priority=10,
                is_async=True,
            )

            logger.info("音频编解码器初始化成功")

        except Exception as e:
            logger.error("初始化音频设备失败: %s", e, exc_info=True)
            await self._alert("错误", f"初始化音频设备失败: {e}")

    def _set_protocol_type(self, protocol_type: str):
        """设置协议类型"""
        logger.debug("设置协议类型: %s", protocol_type)
        if protocol_type == "mqtt":
            self.protocol = MqttProtocol(asyncio.get_running_loop())
        else:
            self.protocol = WebsocketProtocol()

        # 注册到资源管理器
        resource_manager = get_resource_manager()
        asyncio.create_task(resource_manager.register_resource(
            resource_id="protocol",
            resource=self.protocol,
            cleanup_func=self.protocol.close_audio_channel,
            resource_type=ResourceType.PROTOCOL,
            name=f"{protocol_type}协议",
            priority=5,
            is_async=True,
        ))

    def _set_display_type(self, mode: str):
        """设置显示界面类型"""
        logger.debug("设置显示界面类型: %s", mode)

        if mode == "gui":
            self.display = gui_display.GuiDisplay()
            self._setup_gui_callbacks()
        else:
            from src.display.cli_display import CliDisplay

            self.display = CliDisplay()
            self._setup_cli_callbacks()

    def _setup_gui_callbacks(self):
        """设置GUI回调函数"""
        asyncio.create_task(
            self.display.set_callbacks(
                press_callback=lambda: asyncio.create_task(self.start_listening()),
                release_callback=lambda: asyncio.create_task(self.stop_listening()),
                mode_callback=self._on_mode_changed,
                auto_callback=lambda: asyncio.create_task(self.toggle_chat_state()),
                abort_callback=lambda: asyncio.create_task(
                    self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
                ),
                send_text_callback=self._send_text_tts,
            )
        )

    def _setup_cli_callbacks(self):
        """设置CLI回调函数"""
        asyncio.create_task(
            self.display.set_callbacks(
                auto_callback=lambda: asyncio.create_task(self.toggle_chat_state()),
                abort_callback=lambda: asyncio.create_task(
                    self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
                ),
                send_text_callback=self._send_text_tts,
            )
        )

    def _setup_protocol_callbacks(self):
        """设置协议回调函数"""
        self.protocol.on_network_error(self._on_network_error)
        self.protocol.on_incoming_audio(self._on_incoming_audio)
        self.protocol.on_incoming_json(self._on_incoming_json)
        self.protocol.on_audio_channel_opened(self._on_audio_channel_opened)
        self.protocol.on_audio_channel_closed(self._on_audio_channel_closed)

    async def _start_core_tasks(self):
        """启动核心任务"""
        logger.debug("启动核心任务")

        # 音频处理任务
        self._create_task(self._audio_input_processor(), "音频输入处理")
        self._create_task(self._audio_output_processor(), "音频输出处理")

        # 命令处理任务
        self._create_task(self._command_processor(), "命令处理")

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """创建并管理任务"""
        task = asyncio.create_task(coro, name=name)
        self._main_tasks.add(task)

        # 异步注册到资源管理器
        task_id = f"task_{name}_{id(task)}"
        register_task = self._register_task_to_resource_manager(task, task_id, name)
        asyncio.create_task(register_task)

        # 使用弱引用避免循环引用
        weak_tasks = weakref.ref(self._main_tasks)

        def done_callback(t):
            tasks = weak_tasks()
            if tasks is not None:
                tasks.discard(t)

            # 异步注销资源
            unregister_task = self._unregister_task_from_resource_manager(task_id)
            asyncio.create_task(unregister_task)

            if not t.cancelled() and t.exception():
                logger.error(f"任务 {name} 异常结束: {t.exception()}", exc_info=True)

        task.add_done_callback(done_callback)
        return task

    async def _register_task_to_resource_manager(
        self, task: asyncio.Task, task_id: str, name: str
    ):
        """异步注册任务到资源管理器"""
        try:
            resource_manager = get_resource_manager()
            await resource_manager.register_resource(
                resource_id=task_id,
                resource=task,
                cleanup_func=lambda: task.cancel(),
                resource_type=ResourceType.TASK,
                name=f"任务-{name}",
                priority=20,
                is_async=False,
            )
        except Exception as e:
            logger.warning(f"注册任务到资源管理器失败: {e}")

    async def _unregister_task_from_resource_manager(self, task_id: str):
        """异步注销任务从资源管理器"""
        try:
            resource_manager = get_resource_manager()
            await resource_manager.unregister_resource(task_id)
        except Exception as e:
            logger.warning(f"从资源管理器注销任务失败: {e}")

    async def _audio_input_processor(self):
        """音频输入处理器"""
        while self.running:
            try:
                if (
                    self.device_state == DeviceState.LISTENING
                    and self.audio_codec
                    and self.protocol
                    and self.protocol.is_audio_channel_opened()
                ):

                    # 批量读取和发送音频数据，提高实时性
                    audio_sent = False
                    for _ in range(5):  # 一次循环最多处理5帧音频
                        encoded_data = await self.audio_codec.read_audio()
                        if encoded_data:
                            await self.protocol.send_audio(encoded_data)
                            audio_sent = True
                        else:
                            break

                    # 如果发送了音频数据，稍微降低睡眠时间
                    if audio_sent:
                        await asyncio.sleep(0.005)  # 5ms
                    else:
                        await asyncio.sleep(0.01)  # 10ms
                else:
                    await asyncio.sleep(0.02)  # 20ms

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"音频输入处理错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _audio_output_processor(self):
        """音频输出处理器"""
        while self.running:
            try:
                if self.device_state == DeviceState.SPEAKING and self.audio_codec:
                    self.is_tts_playing = True
                    await self.audio_codec.play_audio()

                await asyncio.sleep(0.02)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"音频输出处理错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _command_processor(self):
        """命令处理器"""
        while self.running:
            try:
                # 等待命令，超时后继续循环检查running状态
                try:
                    command = await asyncio.wait_for(
                        self.command_queue.get(), timeout=1.0
                    )
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
        """启动GUI显示"""
        # 在qasync环境中，GUI可以直接在主线程启动
        try:
            await self.display.start()
        except Exception as e:
            logger.error(f"GUI显示错误: {e}", exc_info=True)

    async def _start_cli_display(self):
        """启动CLI显示"""
        self._create_task(self.display.start(), "CLI显示")

    async def _start_global_shortcuts(self):
        """启动全局快捷键服务"""
        try:
            from src.views.components.shortcut_manager import (
                start_global_shortcuts_async,
            )

            shortcut_manager = await start_global_shortcuts_async(logger)

            if shortcut_manager:
                # 注册到资源管理器
                resource_manager = get_resource_manager()
                await resource_manager.register_resource(
                    resource_id="shortcut_manager",
                    resource=shortcut_manager,
                    cleanup_func=shortcut_manager.stop_async,
                    resource_type=ResourceType.SHORTCUT_MANAGER,
                    name="全局快捷键管理器",
                    priority=15,
                    is_async=True,
                )
                logger.info("全局快捷键服务已启动并注册")
            else:
                logger.warning("全局快捷键服务启动失败")

        except Exception as e:
            logger.error(f"启动全局快捷键服务失败: {e}", exc_info=True)

    async def schedule_command(self, command):
        """调度命令到命令队列"""
        await self.command_queue.put(command)

    async def start_listening(self):
        """开始监听"""
        await self.schedule_command(self._start_listening_impl)

    async def _start_listening_impl(self):
        """开始监听的实现"""
        if not self.protocol:
            logger.error("协议未初始化")
            return

        self.keep_listening = False

        if self.wake_word_detector:
            await self.wake_word_detector.pause()

        if self.device_state == DeviceState.IDLE:
            await self._set_device_state(DeviceState.CONNECTING)

            try:
                if not self.protocol.is_audio_channel_opened():
                    success = await self.protocol.open_audio_channel()
                    if not success:
                        await self._alert("错误", "打开音频通道失败")
                        await self._set_device_state(DeviceState.IDLE)
                        return

                # 清空缓冲区并重新初始化音频流
                if self.audio_codec:
                    await self.audio_codec.clear_audio_queue()
                    await self.audio_codec.reinitialize_stream(is_input=True)

                await self.protocol.send_start_listening(ListeningMode.MANUAL)
                await self._set_device_state(DeviceState.LISTENING)

            except Exception as e:
                logger.error(f"开始监听时出错: {e}")
                await self._alert("错误", f"开始监听失败: {str(e)}")
                await self._set_device_state(DeviceState.IDLE)

        elif self.device_state == DeviceState.SPEAKING:
            if not self.aborted:
                await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def stop_listening(self):
        """停止监听"""
        await self.schedule_command(self._stop_listening_impl)

    async def _stop_listening_impl(self):
        """停止监听的实现"""
        if self.device_state == DeviceState.LISTENING:
            await self.protocol.send_stop_listening()
            await self._set_device_state(DeviceState.IDLE)

    async def toggle_chat_state(self):
        """切换聊天状态"""
        await self.schedule_command(self._toggle_chat_state_impl)

    async def _toggle_chat_state_impl(self):
        """切换聊天状态的实现"""
        if not self.protocol:
            logger.error("协议未初始化")
            return

        if self.wake_word_detector:
            await self.wake_word_detector.pause()

        if self.device_state == DeviceState.IDLE:
            await self._set_device_state(DeviceState.CONNECTING)

            try:
                if not self.protocol.is_audio_channel_opened():
                    success = await self.protocol.open_audio_channel()
                    if not success:
                        await self._alert("错误", "打开音频通道失败")
                        await self._set_device_state(DeviceState.IDLE)
                        return

                # 清空缓冲区确保干净的开始
                if self.audio_codec:
                    await self.audio_codec.clear_audio_queue()

                self.keep_listening = True
                await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
                await self._set_device_state(DeviceState.LISTENING)

            except Exception as e:
                logger.error(f"切换聊天状态时出错: {e}")
                await self._alert("错误", f"切换聊天状态失败: {str(e)}")
                await self._set_device_state(DeviceState.IDLE)

        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.NONE)
        elif self.device_state == DeviceState.LISTENING:
            await self.protocol.close_audio_channel()
            await self._set_device_state(DeviceState.IDLE)

    async def abort_speaking(self, reason):
        """中止语音输出"""
        if self.aborted:
            logger.debug(f"已经中止，忽略重复的中止请求: {reason}")
            return

        logger.info(f"中止语音输出，原因: {reason}")
        self.aborted = True
        self.is_tts_playing = False

        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        if reason == AbortReason.WAKE_WORD_DETECTED and self.wake_word_detector:
            await self.wake_word_detector.pause()
            await asyncio.sleep(0.1)

        try:
            await self.protocol.send_abort_speaking(reason)
            await self._set_device_state(DeviceState.IDLE)

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
        """设置设备状态"""
        if self.device_state == state:
            return

        self.device_state = state

        # 根据状态执行相应操作并更新显示
        if state == DeviceState.IDLE:
            self._handle_idle_state()
        elif state == DeviceState.CONNECTING:
            asyncio.create_task(self.display.update_status("连接中..."))
        elif state == DeviceState.LISTENING:
            self._handle_listening_state()
        elif state == DeviceState.SPEAKING:
            asyncio.create_task(self.display.update_status("说话中..."))
            await self._manage_wake_word_detector("resume")

    def _handle_idle_state(self):
        """处理空闲状态"""
        if self.display:
            asyncio.create_task(self.display.update_status("待命"))
        self.set_emotion("neutral")
        asyncio.create_task(self._manage_wake_word_detector("resume"))
        asyncio.create_task(self._manage_audio_input("resume"))

    def _handle_listening_state(self):
        """处理监听状态"""
        if self.display:
            asyncio.create_task(self.display.update_status("聆听中..."))
        self.set_emotion("neutral")
        asyncio.create_task(self._update_iot_states(True))
        asyncio.create_task(self._manage_wake_word_detector("pause"))
        asyncio.create_task(self._manage_audio_input("resume"))
        # 确保进入监听状态时缓冲区是干净的
        if self.audio_codec:
            asyncio.create_task(self.audio_codec.clear_audio_queue())

    async def _manage_wake_word_detector(self, action):
        """管理唤醒词检测器"""
        if not self.wake_word_detector:
            return

        if action == "pause":
            await self.wake_word_detector.pause()
        elif action == "resume":
            await self.wake_word_detector.resume()

    async def _manage_audio_input(self, action):
        """管理音频输入"""
        if not self.audio_codec:
            return

        # 现在只需要确保音频输入始终活跃，不再暂停
        if action == "resume":
            await self.audio_codec.resume_input()

    async def _send_text_tts(self, text):
        """发送文本进行TTS"""
        if not self.protocol.is_audio_channel_opened():
            await self.protocol.open_audio_channel()

        await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
        await self.protocol.send_wake_word_detected(text)

    def set_chat_message(self, role, message):
        """设置聊天消息"""
        self.current_text = message
        if self.display:
            asyncio.create_task(self.display.update_text(message))

    def set_emotion(self, emotion):
        """设置表情"""
        self.current_emotion = emotion
        if self.display:
            asyncio.create_task(self.display.update_emotion(emotion))

    async def _alert(self, title, message):
        """显示警告信息"""
        logger.warning(f"警告: {title}, {message}")
        if self.display:
            asyncio.create_task(self.display.update_text(f"{title}: {message}"))

    # 协议回调方法
    def _on_network_error(self, error_message=None):
        """网络错误回调"""
        if error_message:
            logger.error(error_message)

        asyncio.create_task(self._handle_network_error())

    async def _handle_network_error(self):
        """处理网络错误"""
        self.keep_listening = False
        await self._set_device_state(DeviceState.IDLE)

        if self.wake_word_detector:
            await self.wake_word_detector.resume()

        if self.protocol:
            await self.protocol.close_audio_channel()

    def _on_incoming_audio(self, data):
        """接收音频数据回调"""
        if self.device_state == DeviceState.SPEAKING and self.audio_codec:
            asyncio.create_task(self.audio_codec.write_audio(data))

    def _on_incoming_json(self, json_data):
        """接收JSON数据回调"""
        asyncio.create_task(self._handle_incoming_json(json_data))

    async def _handle_incoming_json(self, json_data):
        """处理JSON消息"""
        try:
            if not json_data:
                return

            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data
            msg_type = data.get("type", "")
            if msg_type == "tts":
                await self._handle_tts_message(data)
            elif msg_type == "stt":
                await self._handle_stt_message(data)
            elif msg_type == "llm":
                await self._handle_llm_message(data)
            elif msg_type == "iot":
                await self._handle_iot_message(data)
            elif msg_type == "mcp":
                await self._handle_mcp_message(data)
            else:
                logger.warning(f"收到未知类型的消息: {msg_type}")

        except Exception as e:
            logger.error(f"处理JSON消息时出错: {e}")

    async def _handle_tts_message(self, data):
        """处理TTS消息"""
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
        """处理TTS开始事件"""
        logger.info(f"TTS开始，当前状态: {self.device_state}")
        self.aborted = False
        self.is_tts_playing = True

        # 清空音频队列避免录制TTS声音，但不暂停输入（保持唤醒词检测工作）
        if self.audio_codec:
            await self.audio_codec.clear_audio_queue()

        if self.device_state in [DeviceState.IDLE, DeviceState.LISTENING]:
            await self._set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self):
        """处理TTS停止事件"""
        if self.device_state == DeviceState.SPEAKING:
            # 等待音频播放完成
            if self.audio_codec:
                await self.audio_codec.wait_for_audio_complete()

            self.is_tts_playing = False

            # 清空输入缓冲区确保干净的状态
            if self.audio_codec:
                try:
                    # 清空可能录制的TTS声音和环境音
                    await self.audio_codec.clear_audio_queue()
                    # 等待一小段时间让缓冲区稳定
                    await asyncio.sleep(0.1)
                    await self.audio_codec.clear_audio_queue()
                except Exception as e:
                    logger.warning(f"清空音频缓冲区失败: {e}")
                    await self.audio_codec.reinitialize_stream(is_input=True)

            # 状态转换
            if self.keep_listening:
                await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
                await self._set_device_state(DeviceState.LISTENING)
            else:
                await self._set_device_state(DeviceState.IDLE)

    async def _handle_stt_message(self, data):
        """处理STT消息"""
        text = data.get("text", "")
        if text:
            logger.info(f">> {text}")
            self.set_chat_message("user", text)

    async def _handle_llm_message(self, data):
        """处理LLM消息"""
        emotion = data.get("emotion", "")
        if emotion:
            self.set_emotion(emotion)

    async def _on_audio_channel_opened(self):
        """音频通道打开回调"""
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
        """音频通道关闭回调"""
        logger.info("音频通道已关闭")
        await self._set_device_state(DeviceState.IDLE)
        self.keep_listening = False

        if self.wake_word_detector:
            await self.wake_word_detector.resume()

    async def _initialize_wake_word_detector(self):
        """初始化唤醒词检测器"""
        if not self.config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            logger.info("唤醒词功能已在配置中禁用，跳过初始化")
            return

        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

            self.wake_word_detector = WakeWordDetector()

            if not getattr(self.wake_word_detector, "enabled", True):
                logger.warning("唤醒词检测器被禁用")
                self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
                self.wake_word_detector = None
                return

            # 设置回调
            self.wake_word_detector.on_detected(self._on_wake_word_detected)
            self.wake_word_detector.on_error = self._handle_wake_word_error

            await self._start_wake_word_detector()

            # 注册到资源管理器
            resource_manager = get_resource_manager()
            await resource_manager.register_resource(
                resource_id="wake_word_detector",
                resource=self.wake_word_detector,
                cleanup_func=self.wake_word_detector.stop,
                resource_type=ResourceType.WAKE_WORD_DETECTOR,
                name="唤醒词检测器",
                priority=8,
                is_async=True,
            )

            logger.info("唤醒词检测器初始化成功")

        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
            self.wake_word_detector = None

    async def _start_wake_word_detector(self):
        """启动唤醒词检测器"""
        if self.wake_word_detector and self.audio_codec:
            await self.wake_word_detector.start(self.audio_codec)

    async def _on_wake_word_detected(self, wake_word, full_text):
        """唤醒词检测回调"""
        logger.info(f"检测到唤醒词: {wake_word} (完整文本: {full_text})")
        await self._handle_wake_word_detected(wake_word)

    async def _handle_wake_word_detected(self, wake_word):
        """处理唤醒词检测事件"""
        if self.device_state == DeviceState.IDLE:
            if self.wake_word_detector:
                await self.wake_word_detector.pause()

            await self._set_device_state(DeviceState.CONNECTING)
            await self._connect_and_start_listening(wake_word)
        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def _connect_and_start_listening(self, wake_word):
        """连接服务器并开始监听"""
        try:
            if not await self.protocol.connect():
                logger.error("连接服务器失败")
                await self._alert("错误", "连接服务器失败")
                await self._set_device_state(DeviceState.IDLE)
                if self.wake_word_detector:
                    await self.wake_word_detector.resume()
                return

            if not await self.protocol.open_audio_channel():
                logger.error("打开音频通道失败")
                await self._set_device_state(DeviceState.IDLE)
                await self._alert("错误", "打开音频通道失败")
                if self.wake_word_detector:
                    await self.wake_word_detector.resume()
                return

            await self.protocol.send_wake_word_detected("唤醒")
            self.keep_listening = True
            await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
            await self._set_device_state(DeviceState.LISTENING)

        except Exception as e:
            logger.error(f"连接和启动监听失败: {e}")
            await self._set_device_state(DeviceState.IDLE)

    def _handle_wake_word_error(self, error):
        """处理唤醒词检测器错误"""
        logger.error(f"唤醒词检测错误: {error}")
        if self.device_state == DeviceState.IDLE:
            asyncio.create_task(self._restart_wake_word_detector())

    async def _restart_wake_word_detector(self):
        """重新启动唤醒词检测器"""
        logger.info("尝试重新启动唤醒词检测器")
        try:
            if self.wake_word_detector:
                await self.wake_word_detector.stop()
                await asyncio.sleep(0.5)

            if self.audio_codec:
                await self.wake_word_detector.start(self.audio_codec)
                logger.info("唤醒词检测器重新启动成功")
            else:
                logger.error("音频编解码器不可用，无法重新启动唤醒词检测器")
                self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
                self.wake_word_detector = None

        except Exception as e:
            logger.error(f"重新启动唤醒词检测器失败: {e}")
            self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
            self.wake_word_detector = None

    async def _initialize_iot_devices(self):
        """初始化物联网设备"""
        from src.iot.thing_manager import ThingManager

        thing_manager = ThingManager.get_instance()

        await thing_manager.initialize_iot_devices(self.config)
        logger.info("物联网设备初始化完成")

    async def _handle_iot_message(self, data):
        """处理物联网消息"""
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
        """更新物联网设备状态"""
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
        """处理对话模式变更"""
        if self.device_state != DeviceState.IDLE:
            asyncio.create_task(self._alert("提示", "只有在待命状态下才能切换对话模式"))
            return False

        self.keep_listening = not self.keep_listening
        return True

    async def shutdown(self):
        """关闭应用程序"""
        if not self.running:
            return

        logger.info("正在关闭异步应用程序...")
        self.running = False

        # 设置关闭事件
        self._shutdown_event.set()

        try:
            # 使用资源管理器统一关闭所有资源
            success = await shutdown_all_resources(timeout=5.0)

            if success:
                logger.info("所有资源已成功关闭")
            else:
                logger.warning("部分资源关闭失败，但应用程序将继续退出")

        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}", exc_info=True)

    def _initialize_mcp_server(self):
        """初始化MCP服务器"""
        logger.info("初始化MCP服务器")
        # 设置发送回调
        self.mcp_server.set_send_callback(
            lambda msg: asyncio.create_task(self.send_mcp_message(msg))
        )
        # 添加通用工具
        self.mcp_server.add_common_tools()

    async def send_mcp_message(self, payload):
        """发送MCP消息"""
        if self.protocol:
            await self.protocol.send_mcp_message(payload)

    async def _handle_mcp_message(self, data):
        """处理MCP消息"""
        payload = data.get("payload")
        if payload:
            await self.mcp_server.parse_message(payload)

    async def _start_calendar_reminder_service(self):
        """启动日程提醒服务"""
        try:
            logger.info("启动日程提醒服务")
            from src.core.resource_manager import ResourceType, get_resource_manager
            from src.mcp.tools.calendar import get_reminder_service

            # 获取提醒服务实例（通过单例模式）
            reminder_service = get_reminder_service()

            # 启动提醒服务（服务内部会自动处理初始化和日程检查）
            await reminder_service.start()

            # 注册到资源管理器
            resource_manager = get_resource_manager()
            await resource_manager.register_resource(
                resource_id="calendar_reminder_service",
                resource=reminder_service,
                cleanup_func=reminder_service.stop,
                resource_type=ResourceType.OTHER,
                name="日程提醒服务",
                priority=25,
                is_async=True,
            )

            logger.info("日程提醒服务已启动")

        except Exception as e:
            logger.error(f"启动日程提醒服务失败: {e}", exc_info=True)
