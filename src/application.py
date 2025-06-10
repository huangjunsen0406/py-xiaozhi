import asyncio
import json
import signal
import sys
import weakref
from typing import Set

from src.constants.constants import AbortReason, DeviceState, ListeningMode
from src.display import gui_display
from src.input.shortcut_manager import ShortcutManager
from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.common_utils import handle_verification_code
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

# 处理opus动态库
from src.utils.opus_loader import setup_opus
from src.utils.resource_finder import find_assets_dir

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
        self.config._initialize_mqtt_info()
        
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
        
        # 回调函数
        self.on_state_changed_callbacks = []
        
        # 任务取消事件
        self._shutdown_event = asyncio.Event()
        
        # 保存主线程的事件循环（稍后在run方法中设置）
        self._main_loop = None

        # 初始化快捷键管理器
        self.shortcut_manager = ShortcutManager(
            logger=logger,
            manual_press_callback=self._shortcut_start_listening,
            manual_release_callback=self._shortcut_stop_listening,
            auto_toggle_callback=self._shortcut_toggle_chat_state,
            abort_callback=self._shortcut_abort_speaking_sync,
            mode_toggle_callback=self._shortcut_toggle_mode,
            window_toggle_callback=self._shortcut_toggle_window_visibility,
        )

        logger.debug("Application实例初始化完成")

    async def run(self, **kwargs):
        """启动应用程序"""
        logger.info("启动异步应用程序，参数: %s", kwargs)
        
        mode = kwargs.get("mode", "gui")
        protocol = kwargs.get("protocol", "websocket")
        
        try:
            self.running = True
            
            # 保存主线程的事件循环
            self._main_loop = asyncio.get_running_loop()
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            # 初始化组件
            await self._initialize_components(mode, protocol)
            
            # 启动核心任务
            await self._start_core_tasks()
            
            # 启动显示界面
            if mode == "gui":
                await self._start_gui_display()
            else:
                await self._start_cli_display()
                
            # 启动快捷键监听
            self.shortcut_manager.start_listener()
            
        except Exception as e:
            logger.error(f"启动应用程序失败: {e}", exc_info=True)
            await self.shutdown()
            raise

    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler():
            logger.info("接收到中断信号，开始关闭...")
            # 确保在正确的事件循环中执行shutdown
            if self._main_loop and not self._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(self.shutdown(), self._main_loop)
            else:
                # 如果事件循环不可用，强制退出
                import os
                os._exit(0)
        
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
        
        # 设置设备状态
        await self._set_device_state(DeviceState.IDLE)
        
        # 初始化音频编解码器
        await self._initialize_audio()
        
        # 设置协议（改为异步）
        await self._set_protocol_type(protocol)
        
        # 设置显示类型
        self._set_display_type(mode)
        
        # 初始化唤醒词检测
        await self._initialize_wake_word_detector()
        
        # 初始化物联网设备
        self._initialize_iot_devices()
        
        # 设置协议回调
        self._setup_protocol_callbacks()
        
        logger.info("应用程序组件初始化完成")

    async def _initialize_audio(self):
        """初始化音频编解码器"""
        try:
            logger.debug("开始初始化音频编解码器")
            from src.audio_codecs.audio_codec import AudioCodec
            
            self.audio_codec = AudioCodec()
            await self.audio_codec.initialize()
            logger.info("音频编解码器初始化成功")
            
        except Exception as e:
            logger.error("初始化音频设备失败: %s", e, exc_info=True)
            await self._alert("错误", f"初始化音频设备失败: {e}")

    async def _set_protocol_type(self, protocol_type: str):
        """设置协议类型"""
        logger.debug("设置协议类型: %s", protocol_type)
        
        # 如果已有协议，先清理
        if self.protocol:
            try:
                await self.protocol.close_audio_channel()
                if hasattr(self.protocol, '_cleanup_connections'):
                    await self.protocol._cleanup_connections()
            except Exception as e:
                logger.warning(f"清理旧协议时出错: {e}")
        
        # 创建新协议
        if protocol_type == "mqtt":
            self.protocol = MqttProtocol(asyncio.get_running_loop())
        else:
            self.protocol = WebsocketProtocol()
        
        logger.info(f"协议 {protocol_type} 初始化完成")

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
        self.display.set_callbacks(
            press_callback=lambda: asyncio.create_task(self.start_listening()),
            release_callback=lambda: asyncio.create_task(self.stop_listening()),
            status_callback=self._get_status_text,
            text_callback=self._get_current_text,
            emotion_callback=self._get_current_emotion,
            mode_callback=self._on_mode_changed,
            auto_callback=lambda: asyncio.create_task(self.toggle_chat_state()),
            abort_callback=lambda: asyncio.create_task(
                self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
            ),
            send_text_callback=self._send_text_tts,
        )

    def _setup_cli_callbacks(self):
        """设置CLI回调函数"""
        self.display.set_callbacks(
            auto_callback=lambda: asyncio.create_task(self.toggle_chat_state()),
            abort_callback=lambda: asyncio.create_task(
                self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
            ),
            status_callback=self._get_status_text,
            text_callback=self._get_current_text,
            emotion_callback=self._get_current_emotion,
            send_text_callback=self._send_text_tts,
        )

    def _setup_protocol_callbacks(self):
        """设置协议回调函数"""
        self.protocol.on_network_error = self._on_network_error
        self.protocol.on_incoming_audio = self._on_incoming_audio
        self.protocol.on_incoming_json = self._on_incoming_json
        self.protocol.on_audio_channel_opened = self._on_audio_channel_opened
        self.protocol.on_audio_channel_closed = self._on_audio_channel_closed

    async def _start_core_tasks(self):
        """启动核心任务"""
        logger.debug("启动核心任务")
        
        # 音频处理任务
        self._create_task(self._audio_input_processor(), "音频输入处理")
        self._create_task(self._audio_output_processor(), "音频输出处理")
        
        # 命令处理任务
        self._create_task(self._command_processor(), "命令处理")
        
        # 状态更新任务
        self._create_task(self._status_updater(), "状态更新")

    def _create_task(self, coro, name: str) -> asyncio.Task:
        """创建并管理任务"""
        task = asyncio.create_task(coro, name=name)
        self._main_tasks.add(task)
        
        # 使用弱引用避免循环引用
        weak_tasks = weakref.ref(self._main_tasks)
        
        def done_callback(t):
            tasks = weak_tasks()
            if tasks is not None:
                tasks.discard(t)
            
            if not t.cancelled() and t.exception():
                logger.error(f"任务 {name} 异常结束: {t.exception()}", exc_info=True)
        
        task.add_done_callback(done_callback)
        return task

    async def _audio_input_processor(self):
        """音频输入处理器"""
        while self.running:
            try:
                if (self.device_state == DeviceState.LISTENING and
                        self.audio_codec and
                        self.protocol and
                        self.protocol.is_audio_channel_opened()):
                    
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
                        await asyncio.sleep(0.01)   # 10ms
                else:
                    await asyncio.sleep(0.02)       # 20ms
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"音频输入处理错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _audio_output_processor(self):
        """音频输出处理器"""
        while self.running:
            try:
                if (self.device_state == DeviceState.SPEAKING and 
                        self.audio_codec):
                    
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

    async def _status_updater(self):
        """状态更新器"""
        last_status = None
        while self.running:
            try:
                current_status = self._get_status_text()
                
                # 只在状态真正改变时更新
                if current_status != last_status:
                    if self.display:
                        self.display.update_status(current_status)
                    last_status = current_status
                
                # 定期更新文本和表情（频率较低）
                if self.display:
                    self.display.update_text(self._get_current_text())
                    self.display.update_emotion(self._get_current_emotion())
                
                await asyncio.sleep(0.05)  # 更频繁的状态检查
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"状态更新错误: {e}", exc_info=True)
                await asyncio.sleep(0.1)

    async def _start_gui_display(self):
        """启动GUI显示"""
        # 在qasync环境中，GUI可以直接在主线程启动
        try:
            # 直接调用start方法，不使用asyncio.to_thread
            # 因为现在我们在正确的线程中（主线程+qasync）
            self.display.start()
        except Exception as e:
            logger.error(f"GUI显示错误: {e}", exc_info=True)

    async def _start_cli_display(self):
        """启动CLI显示"""
        self._create_task(self.display.start(), "CLI显示")

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
            
            if (reason == AbortReason.WAKE_WORD_DETECTED and 
                    self.keep_listening and 
                    self.protocol.is_audio_channel_opened()):
                await asyncio.sleep(0.1)
                await self.toggle_chat_state()
                
        except Exception as e:
            logger.error(f"中止语音时出错: {e}")

    async def _set_device_state(self, state):
        """设置设备状态"""
        if self.device_state == state:
            return

        self.device_state = state

        # 根据状态执行相应操作
        if state == DeviceState.IDLE:
            self._handle_idle_state()
        elif state == DeviceState.CONNECTING:
            if self.display:
                self.display.update_status("连接中...")
        elif state == DeviceState.LISTENING:
            self._handle_listening_state()
        elif state == DeviceState.SPEAKING:
            if self.display:
                self.display.update_status("说话中...")
            await self._manage_wake_word_detector("resume")

        # 通知状态变化
        for callback in self.on_state_changed_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(state)
                else:
                    callback(state)
            except Exception as e:
                logger.error(f"执行状态变化回调时出错: {e}", exc_info=True)

    def _handle_idle_state(self):
        """处理空闲状态"""
        if self.display:
            self.display.update_status("待命")
        self.current_emotion = "neutral"
        asyncio.create_task(self._manage_wake_word_detector("resume"))
        asyncio.create_task(self._manage_audio_input("resume"))

    def _handle_listening_state(self):
        """处理监听状态"""
        if self.display:
            self.display.update_status("聆听中...")
        self.current_emotion = "neutral"
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

    # 状态获取方法
    def _get_status_text(self):
        """获取当前状态文本"""
        states = {
            DeviceState.IDLE: "待命",
            DeviceState.CONNECTING: "连接中...",
            DeviceState.LISTENING: "聆听中...",
            DeviceState.SPEAKING: "说话中...",
        }
        return states.get(self.device_state, "未知")

    def _get_current_text(self):
        """获取当前显示文本"""
        return self.current_text

    def _get_current_emotion(self):
        """获取当前表情"""
        if getattr(self, '_last_emotion', None) == self.current_emotion:
            return getattr(self, '_last_emotion_path', None)
    
        assets_dir = find_assets_dir()
        if not assets_dir:
            logger.error("无法找到assets目录")
            self._last_emotion = self.current_emotion
            self._last_emotion_path = "😊"
            return self._last_emotion_path
                
        emotion_dir = assets_dir / "emojis"
        emotion_path = str(emotion_dir / f"{self.current_emotion}.gif")
        
        if not (emotion_dir / f"{self.current_emotion}.gif").exists():
            emotion_path = str(emotion_dir / "neutral.gif")
            if not (emotion_dir / "neutral.gif").exists():
                emotion_path = "😊"
    
        self._last_emotion = self.current_emotion
        self._last_emotion_path = emotion_path
        
        return emotion_path

    async def _send_text_tts(self, text):
        """发送文本进行TTS"""
        if not self.protocol.is_audio_channel_opened():
            await self.protocol.open_audio_channel()
        await self.protocol.send_wake_word_detected(text)

    def set_chat_message(self, role, message):
        """设置聊天消息"""
        self.current_text = message
        if self.display:
            self.display.update_text(message)

    def set_emotion(self, emotion):
        """设置表情"""
        self.current_emotion = emotion
        if self.display:
            self.display.update_emotion(self._get_current_emotion())

    async def _alert(self, title, message):
        """显示警告信息"""
        logger.warning(f"警告: {title}, {message}")
        if self.display:
            self.display.update_text(f"{title}: {message}")

    # 协议回调方法
    async def _on_network_error(self, error_message=None):
        """网络错误回调"""
        if error_message:
            logger.error(error_message)
        
        await self._handle_network_error()

    async def _handle_network_error(self):
        """处理网络错误"""
        self.keep_listening = False
        await self._set_device_state(DeviceState.IDLE)
        
        if self.wake_word_detector:
            await self.wake_word_detector.resume()

        if self.protocol:
            await self.protocol.close_audio_channel()

    async def _on_incoming_audio(self, data):
        """接收音频数据回调"""
        if self.device_state == DeviceState.SPEAKING and self.audio_codec:
            await self.audio_codec.write_audio(data)

    async def _on_incoming_json(self, json_data):
        """接收JSON数据回调"""
        await self._handle_incoming_json(json_data)

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
            if self.keep_listening and self.protocol.is_audio_channel_opened():
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
        await self.protocol.send_iot_descriptors(thing_manager.get_descriptors_json())
        await self._update_iot_states(False)

    async def _on_audio_channel_closed(self):
        """音频通道关闭回调"""
        logger.info("音频通道已关闭")
        await self._set_device_state(DeviceState.IDLE)
        self.keep_listening = False

        if self.wake_word_detector:
            await self.wake_word_detector.resume()

    # 其他方法...
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

    def _initialize_iot_devices(self):
        """初始化物联网设备"""
        from src.iot.thing_manager import ThingManager
        from src.iot.things.CameraVL.Camera import Camera
        from src.iot.things.countdown_timer import CountdownTimer
        from src.iot.things.lamp import Lamp

        # from src.iot.things.music_player import MusicPlayer
        from src.iot.things.speaker import Speaker

        thing_manager = ThingManager.get_instance()

        # 添加设备
        thing_manager.add_thing(Lamp())
        thing_manager.add_thing(Speaker())
        # thing_manager.add_thing(MusicPlayer())
        thing_manager.add_thing(Camera())
        thing_manager.add_thing(CountdownTimer())
        
        # 添加异步设备示例
        try:
            from src.iot.things.robot_arm import RobotArm
            thing_manager.add_thing(RobotArm())
        except ImportError:
            logger.info("机械臂模块未找到，跳过注册")

        # Home Assistant设备
        if self.config.get_config("HOME_ASSISTANT.TOKEN"):
            from src.iot.things.ha_control import (
                HomeAssistantButton,
                HomeAssistantLight,
                HomeAssistantNumber,
                HomeAssistantSwitch,
            )

            ha_devices = self.config.get_config("HOME_ASSISTANT.DEVICES", [])
            for device in ha_devices:
                entity_id = device.get("entity_id")
                friendly_name = device.get("friendly_name")
                if entity_id:
                    if entity_id.startswith("light."):
                        thing_manager.add_thing(
                            HomeAssistantLight(entity_id, friendly_name)
                        )
                    elif entity_id.startswith("switch."):
                        thing_manager.add_thing(
                            HomeAssistantSwitch(entity_id, friendly_name)
                        )
                    elif entity_id.startswith("number."):
                        thing_manager.add_thing(
                            HomeAssistantNumber(entity_id, friendly_name)
                        )
                    elif entity_id.startswith("button."):
                        thing_manager.add_thing(
                            HomeAssistantButton(entity_id, friendly_name)
                        )
                    else:
                        thing_manager.add_thing(
                            HomeAssistantLight(entity_id, friendly_name)
                        )

        logger.info("物联网设备初始化完成")

    async def _handle_iot_message(self, data):
        """处理物联网消息"""
        from src.iot.thing_manager import ThingManager
        
        thing_manager = ThingManager.get_instance()
        commands = data.get("commands", [])
        
        for command in commands:
            try:
                # 优先使用异步调用
                if hasattr(thing_manager, 'invoke_async'):
                    result = await thing_manager.invoke_async(command)
                else:
                    # 兼容原有同步调用
                    result = await asyncio.to_thread(thing_manager.invoke, command)
                logger.info(f"执行物联网命令结果: {result}")
            except Exception as e:
                logger.error(f"执行物联网命令失败: {e}")

    async def _update_iot_states(self, delta=None):
        """更新物联网设备状态"""
        from src.iot.thing_manager import ThingManager
        
        thing_manager = ThingManager.get_instance()
        
        if delta is None:
            states_json = thing_manager.get_states_json_str()
            await self.protocol.send_iot_states(states_json)
        else:
            changed, states_json = thing_manager.get_states_json(delta=delta)
            if not delta or changed:
                await self.protocol.send_iot_states(states_json)

    def _on_mode_changed(self, auto_mode):
        """处理对话模式变更"""
        if self.device_state != DeviceState.IDLE:
            asyncio.create_task(self._alert("提示", "只有在待命状态下才能切换对话模式"))
            return False

        self.keep_listening = auto_mode
        logger.info(f"对话模式已切换为: {'自动' if auto_mode else '手动'}")
        return True

    def on_state_changed(self, callback):
        """注册状态变化回调"""
        self.on_state_changed_callbacks.append(callback)

    def _toggle_mode(self):
        """切换对话模式(手动↔自动)"""
        try:
            # 检查当前状态是否允许切换
            if self.device_state != DeviceState.IDLE:
                logger.warning("只有在待命状态下才能切换对话模式")
                return
            
            # 切换keep_listening状态
            self.keep_listening = not self.keep_listening
            
            mode_name = "自动对话" if self.keep_listening else "手动对话"
            logger.info(f"对话模式已切换为: {mode_name}")
            
            # 通知显示层更新
            if self.display and hasattr(self.display, 'auto_mode'):
                self.display.auto_mode = self.keep_listening
                # 更新UI显示
                asyncio.create_task(self.schedule_command(
                    lambda: self.display.update_mode_button_status(mode_name)
                ))
                
        except Exception as e:
            logger.error(f"切换对话模式失败: {e}", exc_info=True)

    def _toggle_window_visibility(self):
        """显示/隐藏主窗口 (仅GUI模式)"""
        try:
            if not self.display:
                logger.warning("显示组件未初始化")
                return
                
            # 检查是否为GUI模式
            if not hasattr(self.display, 'root'):
                logger.info("当前为CLI模式，窗口切换功能不可用")
                return
                
            # 切换窗口显示状态
            if hasattr(self.display, 'root') and self.display.root:
                if self.display.root.isVisible():
                    self.display.root.hide()
                    logger.info("主窗口已隐藏")
                else:
                    self.display.root.show()
                    self.display.root.activateWindow()
                    self.display.root.raise_()
                    logger.info("主窗口已显示")
            else:
                logger.warning("GUI窗口不可用")
                
        except Exception as e:
            logger.error(f"切换窗口显示状态失败: {e}", exc_info=True)

    def _shortcut_start_listening(self):
        """快捷键回调：开始监听（同步）"""
        try:
            if self._main_loop and not self._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.start_listening(), self._main_loop
                )
            else:
                logger.warning("主事件循环不可用，无法执行快捷键操作")
        except Exception as e:
            logger.error(f"快捷键开始监听失败: {e}", exc_info=True)

    def _shortcut_stop_listening(self):
        """快捷键回调：停止监听（同步）"""
        try:
            if self._main_loop and not self._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(self.stop_listening(), self._main_loop)
            else:
                logger.warning("主事件循环不可用，无法执行快捷键操作")
        except Exception as e:
            logger.error(f"快捷键停止监听失败: {e}", exc_info=True)

    def _shortcut_toggle_chat_state(self):
        """快捷键回调：切换聊天状态（同步）"""
        try:
            if self._main_loop and not self._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self.toggle_chat_state(), self._main_loop
                )
            else:
                logger.warning("主事件循环不可用，无法执行快捷键操作")
        except Exception as e:
            logger.error(f"快捷键切换聊天状态失败: {e}", exc_info=True)

    def _shortcut_abort_speaking_sync(self):
        """快捷键回调：中止语音输出（同步）"""
        try:
            if self._main_loop and not self._main_loop.is_closed():
                from src.constants.constants import AbortReason
                asyncio.run_coroutine_threadsafe(
                    self.abort_speaking(AbortReason.WAKE_WORD_DETECTED), 
                    self._main_loop
                )
            else:
                logger.warning("主事件循环不可用，无法执行快捷键操作")
        except Exception as e:
            logger.error(f"快捷键中止语音输出失败: {e}", exc_info=True)

    def _shortcut_toggle_mode(self):
        """快捷键回调：切换对话模式（同步）"""
        try:
            # 这是一个同步操作，直接调用
            self._toggle_mode()
        except Exception as e:
            logger.error(f"快捷键切换对话模式失败: {e}", exc_info=True)

    def _shortcut_toggle_window_visibility(self):
        """快捷键回调：切换窗口显示（同步）"""
        try:
            # 这是一个同步操作，直接调用
            self._toggle_window_visibility()
        except Exception as e:
            logger.error(f"快捷键切换窗口显示失败: {e}", exc_info=True)

    async def shutdown(self):
        """关闭应用程序"""
        if not self.running:
            return
            
        logger.info("正在关闭异步应用程序...")
        self.running = False
        
        # 设置关闭事件
        self._shutdown_event.set()
        
        try:
            # 取消所有任务
            all_tasks = self._main_tasks.union(self._background_tasks)
            for task in all_tasks:
                if not task.done():
                    task.cancel()
            
            # 等待任务完成
            if all_tasks:
                await asyncio.gather(*all_tasks, return_exceptions=True)
            
            # 关闭组件
            if self.audio_codec:
                await self.audio_codec.close()
            
            if self.protocol:
                try:
                    await self.protocol.close_audio_channel()
                    # 使用异步上下文管理器清理
                    if hasattr(self.protocol, '_cleanup_connections'):
                        await self.protocol._cleanup_connections()
                except Exception as e:
                    logger.warning(f"关闭协议时出错: {e}")
            
            if self.wake_word_detector:
                await self.wake_word_detector.stop()
            
            # 停止快捷键监听
            if self.shortcut_manager:
                self.shortcut_manager.stop_listener()
            
            logger.info("异步应用程序已关闭")
            
        except Exception as e:
            logger.error(f"关闭应用程序时出错: {e}", exc_info=True)