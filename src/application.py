import asyncio
import json
import logging
import threading
import time
import sys
from src.utils.system_info import setup_opus


# 在导入 opuslib 之前处理 opus 动态库
setup_opus()

# 现在导入 opuslib
try:
    import opuslib
except Exception as e:
    print(f"导入 opuslib 失败: {e}")
    print("请确保 opus 动态库已正确安装或位于正确的位置")
    sys.exit(1)

from src.protocols.mqtt_protocol import MqttProtocol
from src.constants.constants import DeviceState, EventType, AudioConfig, AbortReason, ListeningMode
from src.display import gui_display,cli_display
from src.protocols.websocket_protocol import WebsocketProtocol
from src.utils.config_manager import ConfigManager

# 配置日志
logger = logging.getLogger("Application")


class Application:
    """智能音箱应用程序主类"""
    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = Application()
        return cls._instance

    def __init__(self):
        """初始化应用程序"""
        # 确保单例模式
        if Application._instance is not None:
            raise Exception("Application是单例类，请使用get_instance()获取实例")
        Application._instance = self

        # 获取配置管理器实例
        self.config = ConfigManager.get_instance()

        # 状态变量
        self.device_state = DeviceState.IDLE
        self.voice_detected = False
        self.keep_listening = False
        self.aborted = False
        self.current_text = ""
        self.current_emotion = "neutral"

        # 音频处理相关
        self.audio_codec = None  # 将在 _initialize_audio 中初始化

        # 事件循环和线程
        self.loop = asyncio.new_event_loop()
        self.loop_thread = None
        self.running = False

        # 任务队列和锁
        self.main_tasks = []
        self.mutex = threading.Lock()

        # 协议实例
        self.protocol = None

        # 回调函数
        self.on_state_changed_callbacks = []

        # 初始化事件对象
        self.events = {
            EventType.SCHEDULE_EVENT: threading.Event(),
            EventType.AUDIO_INPUT_READY_EVENT: threading.Event(),
            EventType.AUDIO_OUTPUT_READY_EVENT: threading.Event()
        }

        # 创建显示界面
        self.display = None

        # 添加唤醒词检测器
        self.wake_word_detector = None
        self._initialize_wake_word_detector()

    def run(self, **kwargs):
        """启动应用程序"""
        print(kwargs)
        mode = kwargs.get('mode', 'gui')
        protocol = kwargs.get('protocol', 'websocket')

        self.set_protocol_type(protocol)

        # 创建并启动事件循环线程
        self.loop_thread = threading.Thread(target=self._run_event_loop)
        self.loop_thread.daemon = True
        self.loop_thread.start()

        # 等待事件循环准备就绪
        time.sleep(0.1)

        # 初始化应用程序（移除自动连接）
        asyncio.run_coroutine_threadsafe(self._initialize_without_connect(), self.loop)

        # 初始化物联网设备
        self._initialize_iot_devices()

        # 启动主循环线程
        main_loop_thread = threading.Thread(target=self._main_loop)
        main_loop_thread.daemon = True
        main_loop_thread.start()
        self.set_display_type(mode)
        # 启动GUI
        self.display.start()

    def _run_event_loop(self):
        """运行事件循环的线程函数"""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _initialize_without_connect(self):
        """初始化应用程序组件（不建立连接）"""
        logger.info("正在初始化应用程序...")

        # 设置设备状态为待命
        self.set_device_state(DeviceState.IDLE)

        # 初始化音频编解码器
        self._initialize_audio()

        # 初始化并启动唤醒词检测
        self._initialize_wake_word_detector()
        if self.wake_word_detector:
            self.wake_word_detector.start()

        # 设置协议回调
        self.protocol.on_network_error = self._on_network_error
        self.protocol.on_incoming_audio = self._on_incoming_audio
        self.protocol.on_incoming_json = self._on_incoming_json
        self.protocol.on_audio_channel_opened = self._on_audio_channel_opened
        self.protocol.on_audio_channel_closed = self._on_audio_channel_closed

        logger.info("应用程序初始化完成")

    def _initialize_audio(self):
        """初始化音频设备和编解码器"""
        try:
            from src.audio_codecs.audio_codec import AudioCodec
            self.audio_codec = AudioCodec()
            logger.info("音频编解码器初始化成功")
            
            # 记录音量控制状态
            if hasattr(self.display, 'volume_controller') and self.display.volume_controller:
                logger.info("系统音量控制已启用")
            else:
                logger.info("系统音量控制未启用，将使用模拟音量控制")
            
        except Exception as e:
            logger.error(f"初始化音频设备失败: {e}")
            self.alert("错误", f"初始化音频设备失败: {e}")

    def _initialize_display(self):
        """初始化显示界面"""
        self.display = gui_display.GuiDisplay()

        # 设置回调函数
        self.display.set_callbacks(
            press_callback=self.start_listening,
            release_callback=self.stop_listening,
            status_callback=self._get_status_text,
            text_callback=self._get_current_text,
            emotion_callback=self._get_current_emotion,
            mode_callback=self._on_mode_changed,
            auto_callback=self.toggle_chat_state,
            abort_callback=lambda: self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
        )

    def _initialize_cli(self):
        self.display = cli_display.CliDisplay()
        self.display.set_callbacks(
            auto_callback=self.toggle_chat_state,
            abort_callback=lambda: self.abort_speaking(AbortReason.WAKE_WORD_DETECTED),
            status_callback=self._get_status_text,
            text_callback=self._get_current_text,
            emotion_callback=self._get_current_emotion
        )

    def set_protocol_type(self, protocol_type: str):
        """设置协议类型"""
        if protocol_type == 'mqtt':
            self.protocol = MqttProtocol(self.loop)
        else:  # websocket
            self.protocol = WebsocketProtocol()

    def set_display_type(self, mode: str):
        if mode == 'gui':
            self._initialize_display()
        else:
            self._initialize_cli()

    def _main_loop(self):
        """应用程序主循环"""
        logger.info("主循环已启动")
        self.running = True

        while self.running:
            # 等待事件
            for event_type, event in self.events.items():
                if event.is_set():
                    event.clear()

                    if event_type == EventType.AUDIO_INPUT_READY_EVENT:
                        self._handle_input_audio()
                    elif event_type == EventType.AUDIO_OUTPUT_READY_EVENT:
                        self._handle_output_audio()
                    elif event_type == EventType.SCHEDULE_EVENT:
                        self._process_scheduled_tasks()

            # 短暂休眠以避免CPU占用过高
            time.sleep(0.01)

    def _process_scheduled_tasks(self):
        """处理调度任务"""
        with self.mutex:
            tasks = self.main_tasks.copy()
            self.main_tasks.clear()

        for task in tasks:
            try:
                task()
            except Exception as e:
                logger.error(f"执行调度任务时出错: {e}")

    def schedule(self, callback):
        """调度任务到主循环"""
        with self.mutex:
            # 如果是中止语音的任务，检查是否已经存在相同类型的任务
            if 'abort_speaking' in str(callback):
                # 如果已经有中止任务在队列中，就不再添加
                if any('abort_speaking' in str(task) for task in self.main_tasks):
                    return
            self.main_tasks.append(callback)
        self.events[EventType.SCHEDULE_EVENT].set()

    def _handle_input_audio(self):
        """处理音频输入"""
        if self.device_state != DeviceState.LISTENING:
            return

        encoded_data = self.audio_codec.read_audio()
        if encoded_data and self.protocol and self.protocol.is_audio_channel_opened():
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_audio(encoded_data),
                self.loop
            )

    def _handle_output_audio(self):
        """处理音频输出"""
        if self.device_state != DeviceState.SPEAKING:
            return

        self.audio_codec.play_audio()

    def _on_network_error(self, message):
        """网络错误回调"""
        self.keep_listening = False
        self.set_device_state(DeviceState.IDLE)
        self.wake_word_detector.resume()
        if self.device_state != DeviceState.CONNECTING:
            logger.info("检测到连接断开")
            self.set_device_state(DeviceState.IDLE)

            # 关闭现有连接
            if self.protocol:
                asyncio.run_coroutine_threadsafe(
                    self.protocol.close_audio_channel(),
                    self.loop
                )

    def _attempt_reconnect(self):
        """尝试重新连接服务器"""
        if self.device_state != DeviceState.CONNECTING:
            logger.info("检测到连接断开，尝试重新连接...")
            self.set_device_state(DeviceState.CONNECTING)

            # 关闭现有连接
            if self.protocol:
                asyncio.run_coroutine_threadsafe(
                    self.protocol.close_audio_channel(),
                    self.loop
                )

            # 延迟一秒后尝试重新连接
            def delayed_reconnect():
                time.sleep(1)
                asyncio.run_coroutine_threadsafe(self._reconnect(), self.loop)

            threading.Thread(target=delayed_reconnect, daemon=True).start()

    async def _reconnect(self):
        """重新连接到服务器"""

        # 设置协议回调
        self.protocol.on_network_error = self._on_network_error
        self.protocol.on_incoming_audio = self._on_incoming_audio
        self.protocol.on_incoming_json = self._on_incoming_json
        self.protocol.on_audio_channel_opened = self._on_audio_channel_opened
        self.protocol.on_audio_channel_closed = self._on_audio_channel_closed

        # 连接到服务器
        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            logger.info(f"尝试重新连接 (尝试 {retry_count + 1}/{max_retries})...")
            if await self.protocol.connect():
                logger.info("重新连接成功")
                self.set_device_state(DeviceState.IDLE)
                return True

            retry_count += 1
            await asyncio.sleep(2)  # 等待2秒后重试

        logger.error(f"重新连接失败，已尝试 {max_retries} 次")
        self.schedule(lambda: self.alert("连接错误", "无法重新连接到服务器"))
        self.set_device_state(DeviceState.IDLE)
        return False

    def _on_incoming_audio(self, data):
        """接收音频数据回调"""
        if self.device_state == DeviceState.SPEAKING:
            self.audio_codec.write_audio(data)
            self.events[EventType.AUDIO_OUTPUT_READY_EVENT].set()

    def _on_incoming_json(self, json_data):
        """接收JSON数据回调"""
        try:
            if not json_data:
                return

            # 解析JSON数据
            if isinstance(json_data, str):
                data = json.loads(json_data)
            else:
                data = json_data

            # 处理不同类型的消息
            msg_type = data.get("type", "")
            if msg_type == "tts":
                self._handle_tts_message(data)
            elif msg_type == "stt":
                self._handle_stt_message(data)
            elif msg_type == "llm":
                self._handle_llm_message(data)
            elif msg_type == "iot":
                self._handle_iot_message(data)
            else:
                logger.warning(f"收到未知类型的消息: {msg_type}")
        except Exception as e:
            logger.error(f"处理JSON消息时出错: {e}")

    def _handle_tts_message(self, data):
        """处理TTS消息"""
        state = data.get("state", "")
        if state == "start":
            self.schedule(lambda: self._handle_tts_start())
        elif state == "stop":
            self.schedule(lambda: self._handle_tts_stop())
        elif state == "sentence_start":
            text = data.get("text", "")
            if text:
                logger.info(f"<< {text}")
                self.schedule(lambda: self.set_chat_message("assistant", text))

                # 检查是否包含验证码信息
                if "请登录到控制面板添加设备，输入验证码" in text:
                    self.schedule(lambda: self._handle_verification_code(text))

    def _handle_tts_start(self):
        """处理TTS开始事件"""
        self.aborted = False

        # 清空可能存在的旧音频数据
        self.audio_codec.clear_audio_queue()

        if self.device_state == DeviceState.IDLE or self.device_state == DeviceState.LISTENING:
            self.set_device_state(DeviceState.SPEAKING)

    def _handle_tts_stop(self):
        """处理TTS停止事件"""
        if self.device_state == DeviceState.SPEAKING:
            # 给音频播放一个缓冲时间，确保所有音频都播放完毕
            def delayed_state_change():
                # 等待音频队列清空
                self.audio_codec.wait_for_audio_complete()

                # 状态转换
                if self.keep_listening:
                    asyncio.run_coroutine_threadsafe(
                        self.protocol.send_start_listening(ListeningMode.AUTO_STOP),
                        self.loop
                    )
                    self.set_device_state(DeviceState.LISTENING)
                else:
                    self.set_device_state(DeviceState.IDLE)

            # 安排延迟执行
            threading.Thread(target=delayed_state_change, daemon=True).start()

    def _handle_stt_message(self, data):
        """处理STT消息"""
        text = data.get("text", "")
        if text:
            logger.info(f">> {text}")
            self.schedule(lambda: self.set_chat_message("user", text))

    def _handle_llm_message(self, data):
        """处理LLM消息"""
        emotion = data.get("emotion", "")
        if emotion:
            self.schedule(lambda: self.set_emotion(emotion))

    async def _on_audio_channel_opened(self):
        """音频通道打开回调"""
        logger.info("音频通道已打开")
        self.schedule(lambda: self._start_audio_streams())
        
        # 发送物联网设备描述符
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()
        asyncio.run_coroutine_threadsafe(
            self.protocol.send_iot_descriptors(thing_manager.get_descriptors_json()),
            self.loop
        )

    def _start_audio_streams(self):
        """启动音频流"""
        try:
            # 确保流已关闭后再重新打开
            if self.audio_codec.input_stream and self.audio_codec.input_stream.is_active():
                self.audio_codec.input_stream.stop_stream()

            # 重新打开流
            self.audio_codec.input_stream.start_stream()

            if self.audio_codec.output_stream and self.audio_codec.output_stream.is_active():
                self.audio_codec.output_stream.stop_stream()

            # 重新打开流
            self.audio_codec.output_stream.start_stream()

            # 设置事件触发器
            threading.Thread(target=self._audio_input_event_trigger, daemon=True).start()
            threading.Thread(target=self._audio_output_event_trigger, daemon=True).start()

            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")

    def _audio_input_event_trigger(self):
        """音频输入事件触发器"""
        while self.running:
            try:
                if self.audio_codec.input_stream and self.audio_codec.input_stream.is_active():
                    self.events[EventType.AUDIO_INPUT_READY_EVENT].set()
            except OSError as e:
                logger.error(f"音频输入流错误: {e}")
                # 如果流已关闭，尝试重新打开或者退出循环
                if "Stream not open" in str(e):
                    break
            except Exception as e:
                logger.error(f"音频输入事件触发器错误: {e}")

            time.sleep(AudioConfig.FRAME_DURATION / 1000)  # 按帧时长触发

    def _audio_output_event_trigger(self):
        """音频输出事件触发器"""
        while self.running and self.audio_codec.output_stream and self.audio_codec.output_stream.is_active():
            # 当队列中有数据时才触发事件
            if not self.audio_codec.audio_decode_queue.empty():  # 修改为使用 audio_codec 的队列
                self.events[EventType.AUDIO_OUTPUT_READY_EVENT].set()
            time.sleep(0.02)  # 稍微延长检查间隔

    async def _on_audio_channel_closed(self):
        """音频通道关闭回调"""
        logger.info("音频通道已关闭")
        self.set_device_state(DeviceState.IDLE)
        self.keep_listening = False
        # 在空闲状态下启动唤醒词检测
        if self.wake_word_detector:
            if not self.wake_word_detector.is_running():
                logger.info("在空闲状态下启动唤醒词检测")
                self.wake_word_detector.start()
            elif self.wake_word_detector.paused:
                logger.info("在空闲状态下恢复唤醒词检测")
                self.wake_word_detector.resume()
        self.schedule(lambda: self._stop_audio_streams())

    def _stop_audio_streams(self):
        """停止音频流"""
        try:
            if self.audio_codec.input_stream and self.audio_codec.input_stream.is_active():
                self.audio_codec.input_stream.stop_stream()

            if self.audio_codec.output_stream and self.audio_codec.output_stream.is_active():
                self.audio_codec.output_stream.stop_stream()

            logger.info("音频流已停止")
        except Exception as e:
            logger.error(f"停止音频流失败: {e}")

    def set_device_state(self, state):
        """设置设备状态"""
        if self.device_state == state:
            return

        old_state = self.device_state

        # 如果从 SPEAKING 状态切换出去，确保音频播放完成
        if old_state == DeviceState.SPEAKING:
            self.audio_codec.wait_for_audio_complete()

        self.device_state = state
        logger.info(f"状态变更: {old_state} -> {state}")

        # 根据状态执行相应操作
        if state == DeviceState.IDLE:
            self.display.update_status("待命")
            self.display.update_emotion("😶")
            # 停止输出流但不关闭它
            if self.audio_codec.output_stream and self.audio_codec.output_stream.is_active():
                try:
                    self.audio_codec.output_stream.stop_stream()
                except Exception as e:
                    logger.warning(f"停止输出流时出错: {e}")
        elif state == DeviceState.CONNECTING:
            self.display.update_status("连接中...")
        elif state == DeviceState.LISTENING:
            self.display.update_status("聆听中...")
            self.display.update_emotion("🙂")
            if self.audio_codec.input_stream and not self.audio_codec.input_stream.is_active():
                try:
                    self.audio_codec.input_stream.start_stream()
                except Exception as e:
                    logger.warning(f"启动输入流时出错: {e}")
                    # 使用 AudioCodec 类中的方法重新初始化
                    self.audio_codec._reinitialize_input_stream()
        elif state == DeviceState.SPEAKING:
            self.display.update_status("说话中...")
            # 确保输出流处于活跃状态
            if self.audio_codec.output_stream:
                if not self.audio_codec.output_stream.is_active():
                    try:
                        self.audio_codec.output_stream.start_stream()
                    except Exception as e:
                        logger.warning(f"启动输出流时出错: {e}")
                        # 使用 AudioCodec 类中的方法重新初始化
                        self.audio_codec._reinitialize_output_stream()
            # 停止输入流
            if self.audio_codec.input_stream and self.audio_codec.input_stream.is_active():
                try:
                    self.audio_codec.input_stream.stop_stream()
                except Exception as e:
                    logger.warning(f"停止输入流时出错: {e}")
            # 非空闲状态暂停唤醒词检测
            if self.wake_word_detector and self.wake_word_detector.is_running():
                self.wake_word_detector.pause()

        # 通知状态变化
        for callback in self.on_state_changed_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"执行状态变化回调时出错: {e}")

    def _get_status_text(self):
        """获取当前状态文本"""
        states = {
            DeviceState.IDLE: "待命",
            DeviceState.CONNECTING: "连接中...",
            DeviceState.LISTENING: "聆听中...",
            DeviceState.SPEAKING: "说话中..."
        }
        return states.get(self.device_state, "未知")

    def _get_current_text(self):
        """获取当前显示文本"""
        return self.current_text

    def _get_current_emotion(self):
        """获取当前表情"""
        emotions = {
            "neutral": "😶",
            "happy": "🙂",
            "laughing": "😆",
            "funny": "😂",
            "sad": "😔",
            "angry": "😠",
            "crying": "😭",
            "loving": "😍",
            "embarrassed": "😳",
            "surprised": "😲",
            "shocked": "😱",
            "thinking": "🤔",
            "winking": "😉",
            "cool": "😎",
            "relaxed": "😌",
            "delicious": "🤤",
            "kissy": "😘",
            "confident": "😏",
            "sleepy": "😴",
            "silly": "😜",
            "confused": "🙄"
        }
        return emotions.get(self.current_emotion, "😶")

    def set_chat_message(self, role, message):
        """设置聊天消息"""
        self.current_text = message
        # 更新显示
        if self.display:
            self.display.update_text(message)

    def set_emotion(self, emotion):
        """设置表情"""
        self.current_emotion = emotion
        # 更新显示
        if self.display:
            self.display.update_emotion(self._get_current_emotion())

    def start_listening(self):
        """开始监听"""
        self.schedule(self._start_listening_impl)

    def _start_listening_impl(self):
        """开始监听的实现"""
        if not self.protocol:
            logger.error("协议未初始化")
            return

        self.keep_listening = False

        # 检查唤醒词检测器是否存在
        if self.wake_word_detector:
            self.wake_word_detector.pause()

        if self.device_state == DeviceState.IDLE:
            self.set_device_state(DeviceState.CONNECTING)  # 设置设备状态为连接中

            # 尝试打开音频通道
            if not self.protocol.is_audio_channel_opened():
                try:
                    # 等待异步操作完成
                    future = asyncio.run_coroutine_threadsafe(
                        self.protocol.open_audio_channel(),
                        self.loop
                    )
                    # 等待操作完成并获取结果
                    success = future.result(timeout=10.0)  # 添加超时时间
                    
                    if not success:
                        self.alert("错误", "打开音频通道失败")  # 弹出错误提示
                        self.set_device_state(DeviceState.IDLE)  # 设置设备状态为空闲
                        return
                        
                except Exception as e:
                    logger.error(f"打开音频通道时发生错误: {e}")
                    self.alert("错误", f"打开音频通道失败: {str(e)}")
                    self.set_device_state(DeviceState.IDLE)
                    return

            asyncio.run_coroutine_threadsafe(
                self.protocol.send_start_listening(ListeningMode.MANUAL),
                self.loop
            )
            self.set_device_state(DeviceState.LISTENING)  # 设置设备状态为监听中
        elif self.device_state == DeviceState.SPEAKING:
            if not self.aborted:
                self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def _open_audio_channel_and_start_manual_listening(self):
        """打开音频通道并开始手动监听"""
        if not await self.protocol.open_audio_channel():
            self.set_device_state(DeviceState.IDLE)
            self.alert("错误", "打开音频通道失败")
            return

        await self.protocol.send_start_listening(ListeningMode.MANUAL)
        self.set_device_state(DeviceState.LISTENING)

    def toggle_chat_state(self):
        """切换聊天状态"""
        # 检查唤醒词检测器是否存在
        if self.wake_word_detector:
            self.wake_word_detector.pause()
        self.schedule(self._toggle_chat_state_impl)

    def _toggle_chat_state_impl(self):
        """切换聊天状态的具体实现"""
        # 检查协议是否已初始化
        if not self.protocol:
            logger.error("协议未初始化")
            return

        # 如果设备当前处于空闲状态，尝试连接并开始监听
        if self.device_state == DeviceState.IDLE:
            self.set_device_state(DeviceState.CONNECTING)  # 设置设备状态为连接中

            # 尝试打开音频通道
            if not self.protocol.is_audio_channel_opened():
                try:
                    # 等待异步操作完成
                    future = asyncio.run_coroutine_threadsafe(
                        self.protocol.open_audio_channel(),
                        self.loop
                    )
                    # 等待操作完成并获取结果
                    success = future.result(timeout=10.0)  # 添加超时时间
                    
                    if not success:
                        self.alert("错误", "打开音频通道失败")  # 弹出错误提示
                        self.set_device_state(DeviceState.IDLE)  # 设置设备状态为空闲
                        return
                        
                except Exception as e:
                    logger.error(f"打开音频通道时发生错误: {e}")
                    self.alert("错误", f"打开音频通道失败: {str(e)}")
                    self.set_device_state(DeviceState.IDLE)
                    return

            self.keep_listening = True  # 开始监听
            # 启动自动停止的监听模式
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_start_listening(ListeningMode.AUTO_STOP),
                self.loop
            )
            self.set_device_state(DeviceState.LISTENING)  # 设置设备状态为监听中

        # 如果设备正在说话，停止当前说话
        elif self.device_state == DeviceState.SPEAKING:
            self.abort_speaking(AbortReason.NONE)  # 中止说话

        # 如果设备正在监听，关闭音频通道
        elif self.device_state == DeviceState.LISTENING:
            asyncio.run_coroutine_threadsafe(
                self.protocol.close_audio_channel(),
                self.loop
            )

    def stop_listening(self):
        """停止监听"""
        self.schedule(self._stop_listening_impl)

    def _stop_listening_impl(self):
        """停止监听的实现"""
        if self.device_state == DeviceState.LISTENING:
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_stop_listening(),
                self.loop
            )
            self.set_device_state(DeviceState.IDLE)

    def abort_speaking(self, reason):
        """中止语音输出"""
        logger.info(f"中止语音输出，原因: {reason}")
        self.aborted = True
        asyncio.run_coroutine_threadsafe(
            self.protocol.send_abort_speaking(reason),
            self.loop
        )
        self.set_device_state(DeviceState.IDLE)

        # 添加此代码：当用户主动打断时自动进入录音模式
        if reason == AbortReason.WAKE_WORD_DETECTED and self.keep_listening:
            # 短暂延迟确保abort命令被处理
            def start_listening_after_abort():
                time.sleep(0.2)  # 短暂延迟
                self.set_device_state(DeviceState.IDLE)
                self.schedule(lambda: self.toggle_chat_state())

            threading.Thread(target=start_listening_after_abort, daemon=True).start()

    def alert(self, title, message):
        """显示警告信息"""
        logger.warning(f"警告: {title}, {message}")
        # 在GUI上显示警告
        if self.display:
            self.display.update_text(f"{title}: {message}")

    def on_state_changed(self, callback):
        """注册状态变化回调"""
        self.on_state_changed_callbacks.append(callback)

    def shutdown(self):
        """关闭应用程序"""
        logger.info("正在关闭应用程序...")
        self.running = False

        # 关闭音频编解码器
        if self.audio_codec:
            self.audio_codec.close()

        # 关闭协议
        if self.protocol:
            asyncio.run_coroutine_threadsafe(
                self.protocol.close_audio_channel(),
                self.loop
            )

        # 停止事件循环
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        # 等待事件循环线程结束
        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=1.0)

        # 停止唤醒词检测
        if self.wake_word_detector:
            self.wake_word_detector.stop()

        logger.info("应用程序已关闭")

    def _handle_verification_code(self, text):
        """处理验证码信息"""
        try:
            # 提取验证码
            import re
            verification_code = re.search(r'验证码：(\d+)', text)
            if verification_code:
                code = verification_code.group(1)

                # 尝试复制到剪贴板
                try:
                    import pyperclip
                    pyperclip.copy(code)
                    logger.info(f"验证码 {code} 已复制到剪贴板")
                except Exception as e:
                    logger.warning(f"无法复制验证码到剪贴板: {e}")

                # 尝试打开浏览器
                try:
                    import webbrowser
                    if webbrowser.open("https://xiaozhi.me/login"):
                        logger.info("已打开登录页面")
                    else:
                        logger.warning("无法打开浏览器")
                except Exception as e:
                    logger.warning(f"打开浏览器时出错: {e}")

                # 无论如何都显示验证码
                self.alert("验证码", f"您的验证码是: {code}")

        except Exception as e:
            logger.error(f"处理验证码时出错: {e}")

    def _on_mode_changed(self, auto_mode):
        """处理对话模式变更"""
        # 只有在IDLE状态下才允许切换模式
        if self.device_state != DeviceState.IDLE:
            self.alert("提示", "只有在待命状态下才能切换对话模式")
            return False

        self.keep_listening = auto_mode
        logger.info(f"对话模式已切换为: {'自动' if auto_mode else '手动'}")
        return True

    def _initialize_wake_word_detector(self):
        """初始化唤醒词检测器"""
        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector
            self.wake_word_detector = WakeWordDetector(wake_words=self.config.get_config("WAKE_WORDS"),model_path=self.config.get_config("WAKE_WORD_MODEL_PATH"))
            # 注册唤醒词检测回调
            self.wake_word_detector.on_detected(self._on_wake_word_detected)
            logger.info("唤醒词检测器初始化成功")

            # 添加错误处理回调
            def on_error(error):
                logger.error(f"唤醒词检测错误: {error}")
                # 尝试重新启动检测器
                if self.device_state == DeviceState.IDLE:
                    self.schedule(lambda: self._restart_wake_word_detector())

            self.wake_word_detector.on_error = on_error

        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            self.wake_word_detector = None

    def _on_wake_word_detected(self, wake_word, full_text):
        """唤醒词检测回调"""
        logger.info(f"检测到唤醒词: {wake_word} (完整文本: {full_text})")
        self.schedule(lambda: self._handle_wake_word_detected(wake_word))

    def _handle_wake_word_detected(self, wake_word):
        """处理唤醒词检测事件"""
        if self.device_state == DeviceState.IDLE:
            # 暂停唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.pause()

            # 开始连接并监听
            self.set_device_state(DeviceState.CONNECTING)

            # 尝试连接并打开音频通道
            asyncio.run_coroutine_threadsafe(
                self._connect_and_start_listening(wake_word),
                self.loop
            )

    async def _connect_and_start_listening(self,wake_word):
        """连接服务器并开始监听"""
        # 首先尝试连接服务器
        if not await self.protocol.connect():
            logger.error("连接服务器失败")
            self.alert("错误", "连接服务器失败")
            self.set_device_state(DeviceState.IDLE)
            # 恢复唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.resume()
            return

        # 然后尝试打开音频通道
        if not await self.protocol.open_audio_channel():
            logger.error("打开音频通道失败")
            self.set_device_state(DeviceState.IDLE)
            self.alert("错误", "打开音频通道失败")
            # 恢复唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.resume()
            return

        await self.protocol.send_wake_word_detected(wake_word)
        # 设置为自动监听模式
        self.keep_listening = True
        await self.protocol.send_start_listening(ListeningMode.AUTO_STOP)
        self.set_device_state(DeviceState.LISTENING)

    def _restart_wake_word_detector(self):
        """重新启动唤醒词检测器"""
        logger.info("尝试重新启动唤醒词检测器")
        if self.wake_word_detector:
            self.wake_word_detector.stop()
            time.sleep(0.5)  # 给予一些时间让资源释放
            try:
                self.wake_word_detector.start()
                logger.info("唤醒词检测器重新启动成功")
            except Exception as e:
                logger.error(f"重新启动唤醒词检测器失败: {e}")

    def _initialize_iot_devices(self):
        """初始化物联网设备"""
        from src.iot.thing_manager import ThingManager
        from src.iot.things.lamp import Lamp
        from src.iot.things.speaker import Speaker
        from src.iot.things.music_player import MusicPlayer
        # 获取物联网设备管理器实例
        thing_manager = ThingManager.get_instance()
        
        # 添加设备
        thing_manager.add_thing(Lamp())
        thing_manager.add_thing(Speaker())
        thing_manager.add_thing(MusicPlayer())
        logger.info("物联网设备初始化完成")

    def _handle_iot_message(self, data):
        """处理物联网消息"""
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()
        
        commands = data.get("commands", [])
        print(commands)
        for command in commands:
            try:
                result = thing_manager.invoke(command)
                logger.info(f"执行物联网命令结果: {result}")
                
                # 命令执行后更新设备状态
                self.schedule(lambda: self._update_iot_states())
            except Exception as e:
                logger.error(f"执行物联网命令失败: {e}")

    def _update_iot_states(self):
        """更新物联网设备状态"""
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()
        
        # 获取当前设备状态
        states_json = thing_manager.get_states_json()
        
        # 发送状态更新
        asyncio.run_coroutine_threadsafe(
            self.protocol.send_iot_states(states_json),
            self.loop
        )
        logger.info("物联网设备状态已更新")
