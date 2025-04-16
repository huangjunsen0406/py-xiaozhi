import asyncio
import json
import logging
import threading
import time
import sys
import traceback
from pathlib import Path

from src.utils.logging_config import get_logger
# 在导入 opuslib 之前处理 opus 动态库
from src.utils.system_info import setup_opus
from src.constants.constants import (
    DeviceState, EventType, AudioConfig, 
    AbortReason, ListeningMode
)
from src.display import gui_display, cli_display
from src.utils.config_manager import ConfigManager

setup_opus()

# 配置日志
logger = get_logger(__name__)

# 现在导入 opuslib
try:
    import opuslib  # noqa: F401
    from src.utils.tts_utility import TtsUtility
except Exception as e:
    logger.critical("导入 opuslib 失败: %s", e, exc_info=True)
    logger.critical("请确保 opus 动态库已正确安装或位于正确的位置")
    sys.exit(1)

from src.protocols.mqtt_protocol import MqttProtocol
from src.protocols.websocket_protocol import WebsocketProtocol


class Application:
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
        # 确保单例模式
        if Application._instance is not None:
            logger.error("尝试创建Application的多个实例")
            raise Exception("Application是单例类，请使用get_instance()获取实例")
        Application._instance = self

        logger.debug("初始化Application实例")
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
        self.is_tts_playing = False  # 因为Display的播放状态只是GUI使用，不方便Music_player使用，所以加了这个标志位表示是TTS在说话

        # 事件循环和线程
        self.loop = asyncio.new_event_loop()
        self.loop_thread = None
        self.running = False
        self.input_event_thread = None
        self.output_event_thread = None

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
        logger.debug("Application实例初始化完成")

    def run(self, **kwargs):
        """启动应用程序"""
        logger.info("启动应用程序，参数: %s", kwargs)
        mode = kwargs.get('mode', 'gui')
        protocol = kwargs.get('protocol', 'websocket')

        # 启动主循环线程
        logger.debug("启动主循环线程")
        main_loop_thread = threading.Thread(target=self._main_loop)
        main_loop_thread.daemon = True
        main_loop_thread.start()

        # 初始化通信协议
        logger.debug("设置协议类型: %s", protocol)
        self.set_protocol_type(protocol)

        # 创建并启动事件循环线程
        logger.debug("启动事件循环线程")
        self.loop_thread = threading.Thread(target=self._run_event_loop)
        self.loop_thread.daemon = True
        self.loop_thread.start()

        # 等待事件循环准备就绪
        time.sleep(0.1)

        # 初始化应用程序（移除自动连接）
        logger.debug("初始化应用程序组件")
        asyncio.run_coroutine_threadsafe(
            self._initialize_without_connect(), 
            self.loop
        )

        # 初始化物联网设备
        self._initialize_iot_devices()

        logger.debug("设置显示类型: %s", mode)
        self.set_display_type(mode)
        # 启动GUI
        logger.debug("启动显示界面")
        self.display.start()

    def _run_event_loop(self):
        """运行事件循环的线程函数"""
        logger.debug("设置并启动事件循环")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _initialize_without_connect(self):
        """初始化应用程序组件（不建立连接）"""
        logger.info("正在初始化应用程序组件...")

        # 设置设备状态为待命
        logger.debug("设置初始设备状态为IDLE")
        self.set_device_state(DeviceState.IDLE)

        # 初始化音频编解码器
        logger.debug("初始化音频编解码器")
        self._initialize_audio()

        # 初始化并启动唤醒词检测
        self._initialize_wake_word_detector()
        
        # 设置联网协议回调（MQTT AND WEBSOCKET）
        logger.debug("设置协议回调函数")
        self.protocol.on_network_error = self._on_network_error
        self.protocol.on_incoming_audio = self._on_incoming_audio
        self.protocol.on_incoming_json = self._on_incoming_json
        self.protocol.on_audio_channel_opened = self._on_audio_channel_opened
        self.protocol.on_audio_channel_closed = self._on_audio_channel_closed

        logger.info("应用程序组件初始化完成")

    def _initialize_audio(self):
        """初始化音频设备和编解码器"""
        try:
            logger.debug("开始初始化音频编解码器")
            from src.audio_codecs.audio_codec import AudioCodec
            self.audio_codec = AudioCodec()
            logger.info("音频编解码器初始化成功")

            # 记录音量控制状态
            has_volume_control = (
                hasattr(self.display, 'volume_controller') and
                self.display.volume_controller
            )
            if has_volume_control:
                logger.info("系统音量控制已启用")
            else:
                logger.info("系统音量控制未启用，将使用模拟音量控制")

        except Exception as e:
            logger.error("初始化音频设备失败: %s", e, exc_info=True)
            self.alert("错误", f"初始化音频设备失败: {e}")

    def set_protocol_type(self, protocol_type: str):
        """设置协议类型"""
        logger.debug("设置协议类型: %s", protocol_type)
        if protocol_type == 'mqtt':
            self.protocol = MqttProtocol(self.loop)
            logger.debug("已创建MQTT协议实例")
        else:  # websocket
            self.protocol = WebsocketProtocol()
            logger.debug("已创建WebSocket协议实例")

    def set_display_type(self, mode: str):
        """初始化显示界面"""
        logger.debug("设置显示界面类型: %s", mode)
        # 通过适配器的概念管理不同的显示模式
        if mode == 'gui':
            self.display = gui_display.GuiDisplay()
            logger.debug("已创建GUI显示界面")
            self.display.set_callbacks(
                press_callback=self.start_listening,
                release_callback=self.stop_listening,
                status_callback=self._get_status_text,
                text_callback=self._get_current_text,
                emotion_callback=self._get_current_emotion,
                mode_callback=self._on_mode_changed,
                auto_callback=self.toggle_chat_state,
                abort_callback=lambda: self.abort_speaking(
                    AbortReason.WAKE_WORD_DETECTED
                )
            )
        else:
            self.display = cli_display.CliDisplay()
            logger.debug("已创建CLI显示界面")
            self.display.set_callbacks(
                auto_callback=self.toggle_chat_state,
                abort_callback=lambda: self.abort_speaking(
                    AbortReason.WAKE_WORD_DETECTED
                ),
                status_callback=self._get_status_text,
                text_callback=self._get_current_text,
                emotion_callback=self._get_current_emotion,
                send_text_callback=self._send_text_tts
            )
        logger.debug("显示界面回调函数设置完成")

    def _main_loop(self):
        """应用程序主循环"""
        logger.info("主循环已启动")
        self.running = True

        while self.running:
            # 等待事件
            for event_type, event in self.events.items():
                if event.is_set():
                    event.clear()
                    logger.debug("处理事件: %s", event_type)

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

        logger.debug("处理%d个调度任务", len(tasks))
        for task in tasks:
            try:
                task()
            except Exception as e:
                logger.error("执行调度任务时出错: %s", e, exc_info=True)

    def schedule(self, callback):
        """调度任务到主循环"""
        with self.mutex:
            self.main_tasks.append(callback)
        self.events[EventType.SCHEDULE_EVENT].set()

    def _handle_input_audio(self):
        """处理音频输入"""
        if self.device_state != DeviceState.LISTENING:
            return

        # 读取并发送音频数据
        encoded_data = self.audio_codec.read_audio()
        if (encoded_data and self.protocol and
                self.protocol.is_audio_channel_opened()):
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_audio(encoded_data),
                self.loop
            )

    async def _send_text_tts(self, text):
        """将文本转换为语音并发送"""
        try:
            tts_utility = TtsUtility(AudioConfig)

            # 生成 Opus 音频数据包
            opus_frames = await tts_utility.text_to_opus_audio(text)

            # 尝试打开音频通道
            if (not self.protocol.is_audio_channel_opened() and
                    DeviceState.IDLE == self.device_state):
                # 打开音频通道
                success = await self.protocol.open_audio_channel()
                if not success:
                    logger.error("打开音频通道失败")
                    return

            # 确认 opus 帧生成成功
            if opus_frames:
                logger.info(f"生成了 {len(opus_frames)} 个 Opus 音频帧")

                # 设置状态为说话中
                self.set_device_state(DeviceState.SPEAKING)

                # 发送音频数据
                for i, frame in enumerate(opus_frames):
                    await self.protocol.send_audio(frame)
                    await asyncio.sleep(0.06)

                # 设置聊天消息
                self.set_chat_message("user", text)
                await self.protocol.send_text(
                    json.dumps({"session_id": "", "type": "listen", "state": "stop"}))
                await self.protocol.send_text(b'')

                return True
            else:
                logger.error("生成音频失败")
                return False

        except Exception as e:
            logger.error(f"发送文本到TTS时出错: {e}")
            logger.error(traceback.format_exc())
            return False

    def _handle_output_audio(self):
        """处理音频输出"""
        if self.device_state != DeviceState.SPEAKING:
            return
        self.is_tts_playing = True
        self.audio_codec.play_audio()

    def _on_network_error(self, error_message=None):
        """网络错误回调"""
        if error_message:
            logger.error(f"网络错误: {error_message}")
            
        self.keep_listening = False
        self.set_device_state(DeviceState.IDLE)
        # 恢复唤醒词检测
        if self.wake_word_detector and self.wake_word_detector.paused:
            self.wake_word_detector.resume()

        if self.device_state != DeviceState.CONNECTING:
            logger.info("检测到连接断开")
            self.set_device_state(DeviceState.IDLE)

            # 关闭现有连接，但不关闭音频流
            if self.protocol:
                asyncio.run_coroutine_threadsafe(
                    self.protocol.close_audio_channel(),
                    self.loop
                )

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
        self.is_tts_playing = True
        # 清空可能存在的旧音频数据
        self.audio_codec.clear_audio_queue()

        if self.device_state == DeviceState.IDLE or self.device_state == DeviceState.LISTENING:
            self.set_device_state(DeviceState.SPEAKING)

        # 注释掉恢复VAD检测器的代码
        # if hasattr(self, 'vad_detector') and self.vad_detector:
        #     self.vad_detector.resume()

    def _handle_tts_stop(self):
        """处理TTS停止事件"""
        if self.device_state == DeviceState.SPEAKING:
            # 给音频播放一个缓冲时间，确保所有音频都播放完毕
            def delayed_state_change():
                # 等待音频队列清空
                # 增加等待重试次数，确保音频可以完全播放完毕
                max_wait_attempts = 30  # 增加等待尝试次数
                wait_interval = 0.1  # 每次等待的时间间隔
                attempts = 0

                # 等待直到队列为空或超过最大尝试次数
                while (not self.audio_codec.audio_decode_queue.empty() and 
                       attempts < max_wait_attempts):
                    time.sleep(wait_interval)
                    attempts += 1

                # 确保所有数据都被播放出来
                # 再额外等待一点时间确保最后的数据被处理
                if self.is_tts_playing:
                    time.sleep(0.5)

                # 设置TTS播放状态为False
                self.is_tts_playing = False

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
        self._update_iot_states(False)


    def _start_audio_streams(self):
        """启动音频流"""
        try:
            # 不再关闭和重新打开流，只确保它们处于活跃状态
            if self.audio_codec.input_stream and not self.audio_codec.input_stream.is_active():
                try:
                    self.audio_codec.input_stream.start_stream()
                except Exception as e:
                    logger.warning(f"启动输入流时出错: {e}")
                    # 只有在出错时才重新初始化
                    self.audio_codec._reinitialize_input_stream()

            if self.audio_codec.output_stream and not self.audio_codec.output_stream.is_active():
                try:
                    self.audio_codec.output_stream.start_stream()
                except Exception as e:
                    logger.warning(f"启动输出流时出错: {e}")
                    # 只有在出错时才重新初始化
                    self.audio_codec._reinitialize_output_stream()

            # 设置事件触发器
            if self.input_event_thread is None or not self.input_event_thread.is_alive():
                self.input_event_thread = threading.Thread(
                    target=self._audio_input_event_trigger, daemon=True)
                self.input_event_thread.start()
                logger.info("已启动输入事件触发线程")

            # 检查输出事件线程
            if self.output_event_thread is None or not self.output_event_thread.is_alive():
                self.output_event_thread = threading.Thread(
                    target=self._audio_output_event_trigger, daemon=True)
                self.output_event_thread.start()
                logger.info("已启动输出事件触发线程")

            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}")

    def _audio_input_event_trigger(self):
        """音频输入事件触发器"""
        while self.running:
            try:
                # 只有在主动监听状态下才触发输入事件
                if self.device_state == DeviceState.LISTENING and self.audio_codec.input_stream:
                    self.events[EventType.AUDIO_INPUT_READY_EVENT].set()
            except OSError as e:
                logger.error(f"音频输入流错误: {e}")
                # 不要退出循环，继续尝试
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"音频输入事件触发器错误: {e}")
                time.sleep(0.5)
            
            # 确保触发频率足够高，即使帧长度较大
            # 使用20ms作为最大触发间隔，确保即使帧长度为60ms也能有足够的采样率
            sleep_time = min(20, AudioConfig.FRAME_DURATION) / 1000
            time.sleep(sleep_time)  # 按帧时长触发，但确保最小触发频率

    def _audio_output_event_trigger(self):
        """音频输出事件触发器"""
        while self.running:
            try:
                # 确保输出流是活跃的
                if (self.device_state == DeviceState.SPEAKING and
                    self.audio_codec and
                    self.audio_codec.output_stream):

                    # 如果输出流不活跃，尝试重新激活
                    if not self.audio_codec.output_stream.is_active():
                        try:
                            self.audio_codec.output_stream.start_stream()
                        except Exception as e:
                            logger.warning(f"启动输出流失败，尝试重新初始化: {e}")
                            self.audio_codec._reinitialize_output_stream()

                    # 当队列中有数据时才触发事件
                    if not self.audio_codec.audio_decode_queue.empty():
                        self.events[EventType.AUDIO_OUTPUT_READY_EVENT].set()
            except Exception as e:
                logger.error(f"音频输出事件触发器错误: {e}")

            time.sleep(0.02)  # 稍微延长检查间隔

    async def _on_audio_channel_closed(self):
        """音频通道关闭回调"""
        logger.info("音频通道已关闭")
        # 设置为空闲状态但不关闭音频流
        self.set_device_state(DeviceState.IDLE)
        self.keep_listening = False

        # 确保唤醒词检测正常工作
        if self.wake_word_detector:
            if not self.wake_word_detector.is_running():
                logger.info("在空闲状态下启动唤醒词检测")
                # 获取最新的共享流
                if hasattr(self, 'audio_codec') and self.audio_codec:
                    shared_stream = self.audio_codec.get_shared_input_stream()
                    if shared_stream:
                        self.wake_word_detector.start(shared_stream)
                    else:
                        self.wake_word_detector.start()
                else:
                    self.wake_word_detector.start()
            elif self.wake_word_detector.paused:
                logger.info("在空闲状态下恢复唤醒词检测")
                self.wake_word_detector.resume()

    def set_device_state(self, state):
        """设置设备状态"""
        if self.device_state == state:
            return

        self.device_state = state

        # 根据状态执行相应操作
        if state == DeviceState.IDLE:
            self.display.update_status("待命")
            self.display.update_emotion("😶")
            # 恢复唤醒词检测（添加安全检查）
            if self.wake_word_detector and hasattr(self.wake_word_detector, 'paused') and self.wake_word_detector.paused:
                self.wake_word_detector.resume()
                logger.info("唤醒词检测已恢复")
            # 恢复音频输入流
            if self.audio_codec and self.audio_codec.is_input_paused():
                self.audio_codec.resume_input()
        elif state == DeviceState.CONNECTING:
            self.display.update_status("连接中...")
        elif state == DeviceState.LISTENING:
            self.display.update_status("聆听中...")
            self.display.update_emotion("🙂")
            self._update_iot_states(True)
            # 暂停唤醒词检测（添加安全检查）
            if self.wake_word_detector and hasattr(self.wake_word_detector, 'is_running') and self.wake_word_detector.is_running():
                self.wake_word_detector.pause()
                logger.info("唤醒词检测已暂停")
            # 确保音频输入流活跃
            if self.audio_codec:
                if self.audio_codec.is_input_paused():
                    self.audio_codec.resume_input()
        elif state == DeviceState.SPEAKING:
            self.display.update_status("说话中...")
            if self.wake_word_detector and hasattr(self.wake_word_detector, 'paused') and self.wake_word_detector.paused:
                self.wake_word_detector.resume()
            # 暂停唤醒词检测（添加安全检查）
            # if self.wake_word_detector and hasattr(self.wake_word_detector, 'is_running') and self.wake_word_detector.is_running():
                # self.wake_word_detector.pause()
                # logger.info("唤醒词检测已暂停")
            # 暂停音频输入流以避免自我监听
            # if self.audio_codec and not self.audio_codec.is_input_paused():
            #     self.audio_codec.pause_input()

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

            # 使用线程来处理连接操作，避免阻塞
            def connect_and_listen():
                # 尝试打开音频通道
                if not self.protocol.is_audio_channel_opened():
                    try:
                        # 等待异步操作完成
                        future = asyncio.run_coroutine_threadsafe(
                            self.protocol.open_audio_channel(),
                            self.loop
                        )
                        # 等待操作完成并获取结果，使用较短的超时时间
                        try:
                            success = future.result(timeout=5.0)
                        except asyncio.TimeoutError:
                            logger.error("打开音频通道超时")
                            self.set_device_state(DeviceState.IDLE)
                            self.alert("错误", "打开音频通道超时")
                            return
                        except Exception as e:
                            logger.error(f"打开音频通道时发生未知错误: {e}")
                            self.set_device_state(DeviceState.IDLE)
                            self.alert("错误", f"打开音频通道失败: {str(e)}")
                            return

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
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.protocol.send_start_listening(ListeningMode.AUTO_STOP),
                        self.loop
                    )
                    self.set_device_state(DeviceState.LISTENING)  # 设置设备状态为监听中
                except Exception as e:
                    logger.error(f"启动监听时发生错误: {e}")
                    self.set_device_state(DeviceState.IDLE)
                    self.alert("错误", f"启动监听失败: {str(e)}")

            # 启动连接线程
            threading.Thread(target=connect_and_listen, daemon=True).start()

        # 如果设备正在说话，停止当前说话
        elif self.device_state == DeviceState.SPEAKING:
            self.abort_speaking(AbortReason.NONE)  # 中止说话

        # 如果设备正在监听，关闭音频通道
        elif self.device_state == DeviceState.LISTENING:
            # 使用线程处理关闭操作，避免阻塞
            def close_audio_channel():
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.protocol.close_audio_channel(),
                        self.loop
                    )
                    future.result(timeout=3.0)  # 使用较短的超时
                except Exception as e:
                    logger.error(f"关闭音频通道时发生错误: {e}")
            
            threading.Thread(target=close_audio_channel, daemon=True).start()
            # 立即设置为空闲状态，不等待关闭完成
            self.set_device_state(DeviceState.IDLE)

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
        # 如果已经中止，不要重复处理
        if self.aborted:
            logger.debug(f"已经中止，忽略重复的中止请求: {reason}")
            return

        logger.info(f"中止语音输出，原因: {reason}")
        self.aborted = True

        # 设置TTS播放状态为False
        self.is_tts_playing = False
        
        # 立即清空音频队列
        if self.audio_codec:
            self.audio_codec.clear_audio_queue()

        # 注释掉确保VAD检测器暂停的代码
        # if hasattr(self, 'vad_detector') and self.vad_detector:
        #     self.vad_detector.pause()

        # 使用线程来处理状态变更和异步操作，避免阻塞主线程
        def process_abort():
            # 先发送中止指令
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.protocol.send_abort_speaking(reason),
                    self.loop
                )
                # 使用较短的超时确保不会长时间阻塞
                future.result(timeout=1.0)
            except Exception as e:
                logger.error(f"发送中止指令时出错: {e}")
            
            # 然后设置状态
            self.set_device_state(DeviceState.IDLE)
            
            # 如果是唤醒词触发的中止，并且启用了自动聆听，则自动进入录音模式
            if (reason == AbortReason.WAKE_WORD_DETECTED and 
                    self.keep_listening and 
                    self.protocol.is_audio_channel_opened()):
                # 短暂延迟确保abort命令被处理
                time.sleep(0.1)  # 缩短延迟时间
                self.schedule(lambda: self.toggle_chat_state())
        
        # 启动处理线程
        threading.Thread(target=process_abort, daemon=True).start()

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

        # 关闭VAD检测器
        # if hasattr(self, 'vad_detector') and self.vad_detector:
        #     self.vad_detector.stop()

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
        # 首先检查配置中是否启用了唤醒词功能
        if not self.config.get_config('WAKE_WORD_OPTIONS.USE_WAKE_WORD', False):
            logger.info("唤醒词功能已在配置中禁用，跳过初始化")
            self.wake_word_detector = None
            return

        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

            # 获取模型路径配置
            model_path_config = self.config.get_config(
                "WAKE_WORD_OPTIONS.MODEL_PATH",
                "models/vosk-model-small-cn-0.22"
            )

            # 确定基础路径和模型路径
            if getattr(sys, 'frozen', False):
                # 打包环境
                if hasattr(sys, '_MEIPASS'):
                    base_path = Path(sys._MEIPASS)
                else:
                    base_path = Path(sys.executable).parent
            else:
                # 开发环境
                base_path = Path(__file__).parent.parent
            
            model_path = base_path / model_path_config  # 使用Path操作符
            logger.info(f"使用模型路径: {model_path}")

            # 检查模型路径
            if not model_path.exists():
                logger.error(f"模型路径不存在: {model_path}")
                # 自动禁用唤醒词功能
                self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
                self.wake_word_detector = None
                return

            # 创建检测器实例
            self.wake_word_detector = WakeWordDetector()

            # 如果唤醒词检测器被禁用（内部故障），则更新配置
            if not getattr(self.wake_word_detector, 'enabled', True):
                logger.warning("唤醒词检测器被禁用（内部故障）")
                self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
                self.wake_word_detector = None
                return

            # 注册唤醒词检测回调和错误处理
            self.wake_word_detector.on_detected(self._on_wake_word_detected)
            
            # 使用lambda捕获self，而不是单独定义函数
            self.wake_word_detector.on_error = lambda error: (
                self._handle_wake_word_error(error)
            )
            
            logger.info("唤醒词检测器初始化成功")

            # 启动唤醒词检测器
            self._start_wake_word_detector()

        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            # 禁用唤醒词功能，但不影响程序其他功能
            self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
            logger.info("由于初始化失败，唤醒词功能已禁用，但程序将继续运行")
            self.wake_word_detector = None

    def _handle_wake_word_error(self, error):
        """处理唤醒词检测器错误"""
        logger.error(f"唤醒词检测错误: {error}")
        # 尝试重新启动检测器
        if self.device_state == DeviceState.IDLE:
            self.schedule(lambda: self._restart_wake_word_detector())

    def _start_wake_word_detector(self):
        """启动唤醒词检测器"""
        if not self.wake_word_detector:
            return
        
        # 确保音频编解码器已初始化
        if hasattr(self, 'audio_codec') and self.audio_codec:
            shared_stream = self.audio_codec.get_shared_input_stream()
            if shared_stream:
                logger.info("使用共享的音频输入流启动唤醒词检测器")
                self.wake_word_detector.start(shared_stream)

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
        elif self.device_state == DeviceState.SPEAKING:
            self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def _connect_and_start_listening(self, wake_word):
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
        try:
            # 停止现有的检测器
            if self.wake_word_detector:
                self.wake_word_detector.stop()
                time.sleep(0.5)  # 给予一些时间让资源释放

            # 确保使用最新的共享音频输入流
            if hasattr(self, 'audio_codec') and self.audio_codec:
                shared_stream = self.audio_codec.get_shared_input_stream()
                if shared_stream:
                    self.wake_word_detector.start(shared_stream)
                    logger.info("使用共享的音频流重新启动唤醒词检测器")
                else:
                    # 如果无法获取共享流，尝试让检测器创建自己的流
                    self.wake_word_detector.start()
                    logger.info("使用独立的音频流重新启动唤醒词检测器")
            else:
                self.wake_word_detector.start()
                logger.info("使用独立的音频流重新启动唤醒词检测器")

            logger.info("唤醒词检测器重新启动成功")
        except Exception as e:
            logger.error(f"重新启动唤醒词检测器失败: {e}")

    def _initialize_iot_devices(self):
        """初始化物联网设备"""
        from src.iot.thing_manager import ThingManager
        from src.iot.things.lamp import Lamp
        from src.iot.things.speaker import Speaker
        from src.iot.things.music_player import MusicPlayer
        # from src.iot.things.new_music_player import NewMusicPlayer
        from src.iot.things.CameraVL.Camera import Camera
        from src.iot.things.query_bridge_rag import QueryBridgeRAG
        from src.iot.things.temperature_sensor import TemperatureSensor
        # 获取物联网设备管理器实例
        thing_manager = ThingManager.get_instance()

        # 添加设备
        thing_manager.add_thing(Lamp())
        thing_manager.add_thing(Speaker())
        thing_manager.add_thing(MusicPlayer())
        # thing_manager.add_thing(NewMusicPlayer())
        # 默认不启用以下示例
        # thing_manager.add_thing(Camera())
        # thing_manager.add_thing(QueryBridgeRAG())
        # thing_manager.add_thing(TemperatureSensor())
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
            except Exception as e:
                logger.error(f"执行物联网命令失败: {e}")

    def _update_iot_states(self, delta=None):
        """
        更新物联网设备状态

        Args:
            delta: 是否只发送变化的部分
                   - None: 使用原始行为，总是发送所有状态
                   - True: 只发送变化的部分
                   - False: 发送所有状态并重置缓存
        """
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()

        # 处理向下兼容
        if delta is None:
            # 保持原有行为：获取所有状态并发送
            states_json = thing_manager.get_states_json_str()  # 调用旧方法

            # 发送状态更新
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_iot_states(states_json),
                self.loop
            )
            logger.info("物联网设备状态已更新")
            return

        # 使用新方法获取状态
        changed, states_json = thing_manager.get_states_json(delta=delta)

        # delta=False总是发送，delta=True只在有变化时发送
        if not delta or changed:
            asyncio.run_coroutine_threadsafe(
                self.protocol.send_iot_states(states_json),
                self.loop
            )
            if delta:
                logger.info("物联网设备状态已更新(增量)")
            else:
                logger.info("物联网设备状态已更新(完整)")
        else:
            logger.debug("物联网设备状态无变化，跳过更新")

    def _update_wake_word_detector_stream(self):
        """更新唤醒词检测器的音频流"""
        if self.wake_word_detector and self.audio_codec:
            shared_stream = self.audio_codec.get_shared_input_stream()
            if shared_stream and self.wake_word_detector.is_running():
                self.wake_word_detector.update_stream(shared_stream)
                logger.info("已更新唤醒词检测器的音频流")
