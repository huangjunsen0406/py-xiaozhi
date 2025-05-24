import asyncio
import json
import platform
import sys
import time
import threading
from pathlib import Path
from typing import Optional, Callable, Any

from src.utils.logging_config import get_logger
from src.utils.opus_loader import setup_opus
from src.constants.constants import (
    DeviceState, EventType, AudioConfig,
    AbortReason, ListeningMode
)
from src.display import gui_display, cli_display
from src.utils.config_manager import ConfigManager
from src.utils.common_utils import handle_verification_code

setup_opus()

logger = get_logger(__name__)

# 导入 opuslib 和相关模块
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
    """异步版本的Application类，使用纯异步架构"""

    _instance: Optional['Application'] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> 'Application':
        """获取单例实例（线程安全）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    logger.debug("创建Application单例实例")
                    cls._instance = Application()
        return cls._instance

    def __init__(self):
        """初始化应用程序"""
        if Application._instance is not None:
            raise Exception("Application是单例类，请使用get_instance()获取实例")
        Application._instance = self

        logger.debug("初始化Application实例")

        # 配置管理器
        self.config = ConfigManager.get_instance()
        self.config._initialize_mqtt_info()

        # 状态变量
        self.device_state = DeviceState.IDLE
        self.voice_detected = False
        self.keep_listening = False
        self.aborted = False
        self.current_text = ""
        self.current_emotion = "neutral"

        # 实时聊天模式配置（参考C++中的realtime_chat_enabled_）
        # 默认启用实时聊天模式，可以通过配置文件控制
        self.realtime_chat_enabled = self.config.get_config("SYSTEM_OPTIONS.REALTIME_CHAT_ENABLED", True)

        # 当前监听模式（参考C++中的listening_mode_）
        self.listening_mode = ListeningMode.AUTO_STOP

        # 时间戳队列管理（参考C++中的timestamp相关变量）
        # 用于音频包的时间戳同步，特别是在使用服务器端AEC时
        self.timestamp_queue = []  # 对应C++中的timestamp_queue_
        self.timestamp_lock = asyncio.Lock()  # 对应C++中的timestamp_mutex_
        self.last_output_timestamp = 0  # 对应C++中的last_output_timestamp_
        self.use_server_aec = self.config.get_config(
            "AUDIO.USE_SERVER_AEC", False
        )

        # 音频处理相关
        self.audio_codec = None
        self._tts_lock = asyncio.Lock()
        self.is_tts_playing = False

        # 异步任务和事件
        self.running = False
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: set[asyncio.Task] = set()
        self._audio_input_task: Optional[asyncio.Task] = None
        self._audio_output_task: Optional[asyncio.Task] = None

        # 状态管理锁
        self._state_lock = asyncio.Lock()

        # 协议实例
        self.protocol = None

        # 回调函数
        self.on_state_changed_callbacks: list[Callable] = []

        # 显示界面
        self.display = None

        # 唤醒词检测器
        self.wake_word_detector = None

        logger.debug("Application实例初始化完成")

    def _add_task(self, coro):
        """添加任务并自动清理完成的任务"""
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def run(self, **kwargs):
        """启动应用程序"""
        logger.info("启动应用程序，参数: %s", kwargs)
        mode = kwargs.get('mode', 'gui')
        protocol = kwargs.get('protocol', 'websocket')

        try:
            # 设置事件循环
            self.loop = asyncio.get_running_loop()
            logger.debug("已设置事件循环")

            # 设置协议类型
            logger.debug("设置协议类型: %s", protocol)
            await self.set_protocol_type(protocol)

            # 初始化应用程序组件
            logger.debug("初始化应用程序组件")
            await self._initialize_without_connect()

            # 初始化物联网设备
            await self._initialize_iot_devices()

            # 设置显示类型
            logger.debug("设置显示类型: %s", mode)
            await self.set_display_type(mode)

            # 启动显示界面
            logger.debug("启动显示界面")
            self.display.start()

            # 启动音频处理任务
            await self._start_audio_tasks()

            self.running = True
            logger.info("Application启动完成")

        except Exception as e:
            logger.error("启动应用程序失败: %s", e, exc_info=True)
            raise

    async def set_protocol_type(self, protocol_type: str):
        """设置协议类型"""
        logger.debug("设置协议类型: %s", protocol_type)
        if protocol_type == 'mqtt':
            self.protocol = MqttProtocol(asyncio.get_event_loop())
            logger.debug("已创建MQTT协议实例")
        else:  # websocket
            self.protocol = WebsocketProtocol()
            logger.debug("已创建WebSocket协议实例")

    async def set_display_type(self, mode: str):
        """初始化显示界面"""
        logger.debug("设置显示界面类型: %s", mode)
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
                abort_callback=self._create_abort_callback(),
                send_text_callback=self._create_send_text_callback()
            )
        else:
            self.display = cli_display.CliDisplay()
            logger.debug("已创建CLI显示界面")
            self.display.set_callbacks(
                auto_callback=self._create_auto_callback(),
                abort_callback=self._create_abort_callback(),
                status_callback=self._get_status_text,
                text_callback=self._get_current_text,
                emotion_callback=self._get_current_emotion,
                send_text_callback=self._create_send_text_callback()
            )
        logger.debug("显示界面回调函数设置完成")

    def _create_auto_callback(self):
        """创建自动对话回调函数（同步版本，用于CLI线程调用）"""
        def auto_callback():
            try:
                if self.loop and self.loop.is_running() and not self.loop.is_closed():
                    # 使用线程安全的方式调度异步任务
                    future = asyncio.run_coroutine_threadsafe(
                        self._toggle_chat_state_impl(), self.loop
                    )
                    # 可选：等待一小段时间确保任务被调度
                    try:
                        future.result(timeout=0.1)
                    except Exception:
                        # 忽略超时或其他异常，任务已经被调度
                        pass
                else:
                    logger.warning("事件循环未运行或已关闭，无法执行自动对话操作")
            except Exception as e:
                logger.error(f"执行自动对话回调时出错: {e}", exc_info=True)
        return auto_callback

    def _create_abort_callback(self):
        """创建中止回调函数（同步版本，用于GUI线程调用）"""
        def abort_callback():
            try:
                if self.loop and self.loop.is_running() and not self.loop.is_closed():
                    # 使用线程安全的方式调度异步任务
                    future = asyncio.run_coroutine_threadsafe(
                        self.abort_speaking(AbortReason.WAKE_WORD_DETECTED),
                        self.loop
                    )
                    # 可选：等待一小段时间确保任务被调度
                    try:
                        future.result(timeout=0.1)
                    except Exception:
                        # 忽略超时或其他异常，任务已经被调度
                        pass
                else:
                    logger.warning("事件循环未运行或已关闭，无法执行中止操作")
            except Exception as e:
                logger.error(f"执行中止回调时出错: {e}", exc_info=True)
        return abort_callback

    def _create_send_text_callback(self):
        """创建发送文本回调函数（同步版本，用于GUI线程调用）"""
        def send_text_callback(text: str):
            try:
                if self.loop and self.loop.is_running() and not self.loop.is_closed():
                    # 使用线程安全的方式调度异步任务
                    future = asyncio.run_coroutine_threadsafe(
                        self._send_text_tts(text), self.loop
                    )
                    # 可选：等待一小段时间确保任务被调度
                    try:
                        future.result(timeout=0.1)
                    except Exception:
                        # 忽略超时或其他异常，任务已经被调度
                        pass
                else:
                    logger.warning("事件循环未运行或已关闭，无法发送文本")
            except Exception as e:
                logger.error(f"执行发送文本回调时出错: {e}", exc_info=True)
        return send_text_callback

    async def _initialize_without_connect(self):
        """初始化应用程序组件（不建立连接）"""
        logger.info("正在初始化应用程序组件...")

        # 设置设备状态为待命
        logger.debug("设置初始设备状态为IDLE")
        await self.set_device_state(DeviceState.IDLE)

        # 初始化音频编解码器
        logger.debug("初始化音频编解码器")
        await self._initialize_audio()

        # 初始化并启动唤醒词检测
        await self._initialize_wake_word_detector()

        # 设置协议回调
        logger.debug("设置协议回调函数")
        self.protocol.on_network_error = self._on_network_error
        self.protocol.on_incoming_audio = self._on_incoming_audio
        self.protocol.on_incoming_json = self._on_incoming_json
        self.protocol.on_audio_channel_opened = self._on_audio_channel_opened
        self.protocol.on_audio_channel_closed = self._on_audio_channel_closed

        logger.info("应用程序组件初始化完成")

    async def _initialize_audio(self):
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
            raise

    async def set_is_tts_playing(self, value: bool):
        """设置TTS播放状态"""
        async with self._tts_lock:
            self.is_tts_playing = value

    async def get_is_tts_playing(self) -> bool:
        """获取TTS播放状态（异步版本）"""
        async with self._tts_lock:
            return self.is_tts_playing

    def get_is_tts_playing_sync(self) -> bool:
        """获取TTS播放状态（同步版本，用于兼容性）"""
        # 注意：这是同步版本，无法使用异步锁，但布尔值读取是原子操作
        # 在实际使用中应该优先使用异步版本 get_is_tts_playing()
        return self.is_tts_playing

    def schedule(self, callback):
        """调度任务到异步事件循环（兼容性方法）"""
        try:
            # 检查是否有运行中的事件循环
            if self.loop and self.loop.is_running():
                # 检查当前线程是否是事件循环线程
                try:
                    # 尝试获取当前线程的事件循环
                    current_loop = asyncio.get_running_loop()
                    if current_loop == self.loop:
                        # 在事件循环线程中，直接创建任务
                        asyncio.create_task(self._run_scheduled_callback(callback))
                    else:
                        # 在其他线程中，使用 call_soon_threadsafe
                        self.loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(self._run_scheduled_callback(callback))
                        )
                except RuntimeError:
                    # 当前线程没有运行的事件循环，使用 call_soon_threadsafe
                    self.loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._run_scheduled_callback(callback))
                    )
            else:
                # 如果事件循环未运行，直接执行
                try:
                    if asyncio.iscoroutinefunction(callback):
                        logger.warning("尝试在没有事件循环的情况下调用异步函数，跳过执行")
                    else:
                        callback()
                except Exception as e:
                    logger.error(f"执行调度任务时出错: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"调度任务时出错: {e}", exc_info=True)

    async def _run_scheduled_callback(self, callback):
        """运行调度的回调函数"""
        try:
            # 如果回调是协程函数，使用await
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                # 如果是普通函数，直接调用
                result = callback()
                # 检查返回值是否是协程对象
                if asyncio.iscoroutine(result):
                    await result
        except Exception as e:
            logger.error(f"执行调度任务时出错: {e}", exc_info=True)

    async def _start_audio_tasks(self):
        """启动音频处理任务"""
        if self._audio_input_task is None:
            self._audio_input_task = asyncio.create_task(self._audio_input_loop())
            self._tasks.add(self._audio_input_task)
            logger.info("已启动音频输入任务")

        if self._audio_output_task is None:
            self._audio_output_task = asyncio.create_task(self._audio_output_loop())
            self._tasks.add(self._audio_output_task)
            logger.info("已启动音频输出任务")

    async def _audio_input_loop(self):
        """音频输入循环"""
        error_count = 0
        max_errors = 10

        while self.running:
            try:
                # 在实时模式下，即使在SPEAKING状态也要继续录音和发送
                should_send_audio = (
                    (self.device_state == DeviceState.LISTENING) or
                    (self.device_state == DeviceState.SPEAKING and
                     self.listening_mode == ListeningMode.REALTIME)
                )

                if (should_send_audio and
                    self.audio_codec and
                    self.protocol and
                    self.protocol.is_audio_channel_opened()):

                    # 读取并发送音频数据
                    encoded_data = self.audio_codec.read_audio()
                    if encoded_data:
                        # 处理时间戳（参考C++实现）
                        timestamp = await self._get_audio_timestamp()
                        await self.protocol.send_audio(encoded_data, timestamp)

                # 控制循环频率
                sleep_time = min(20, AudioConfig.FRAME_DURATION) / 1000
                await asyncio.sleep(sleep_time)

                # 重置错误计数
                error_count = 0

            except Exception as e:
                error_count += 1
                logger.error("音频输入循环错误 (%d/%d): %s",
                           error_count, max_errors, e, exc_info=True)

                if error_count >= max_errors:
                    logger.critical("音频输入错误过多，停止循环")
                    break

                # 指数退避策略
                delay = min(2 ** error_count * 0.1, 5.0)
                await asyncio.sleep(delay)

    async def _audio_output_loop(self):
        """音频输出循环"""
        error_count = 0
        max_errors = 10

        while self.running:
            try:
                if (self.device_state == DeviceState.SPEAKING and
                    self.audio_codec and
                    not self.audio_codec.audio_decode_queue.empty()):

                    await self.set_is_tts_playing(True)
                    # 播放音频数据（参考C++实现的OnAudioOutput）
                    self.audio_codec.play_audio()

                await asyncio.sleep(0.02)

                # 重置错误计数
                error_count = 0

            except Exception as e:
                error_count += 1
                logger.error("音频输出循环错误 (%d/%d): %s",
                           error_count, max_errors, e, exc_info=True)

                if error_count >= max_errors:
                    logger.critical("音频输出错误过多，停止循环")
                    break

                # 指数退避策略
                delay = min(2 ** error_count * 0.1, 5.0)
                await asyncio.sleep(delay)

    def _on_network_error(self, error_message=None):
        """网络错误回调"""
        if error_message:
            logger.error(f"网络错误: {error_message}")

        self.keep_listening = False
        asyncio.create_task(self.set_device_state(DeviceState.IDLE))

        # 恢复唤醒词检测
        if self.wake_word_detector and self.wake_word_detector.paused:
            self.wake_word_detector.resume()

        if self.device_state != DeviceState.CONNECTING:
            logger.info("检测到连接断开")
            asyncio.create_task(self.set_device_state(DeviceState.IDLE))

            # 关闭现有连接
            if self.protocol:
                asyncio.create_task(self.protocol.close_audio_channel())

    def _on_incoming_audio(self, data):
        """接收音频数据回调"""
        if self.device_state == DeviceState.SPEAKING and self.audio_codec:
            self.audio_codec.write_audio(data)

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
                asyncio.create_task(self._handle_tts_message(data))
            elif msg_type == "stt":
                asyncio.create_task(self._handle_stt_message(data))
            elif msg_type == "llm":
                asyncio.create_task(self._handle_llm_message(data))
            elif msg_type == "iot":
                asyncio.create_task(self._handle_iot_message(data))
            else:
                logger.warning(f"收到未知类型的消息: {msg_type}")

        except Exception as e:
            logger.error(f"处理JSON消息时出错: {e}", exc_info=True)

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
                await self.set_chat_message("assistant", text)

                # 检查是否包含验证码信息
                import re
                match = re.search(r'((?:\d\s*){6,})', text)
                if match:
                    handle_verification_code(text)

    async def _handle_tts_start(self):
        """处理TTS开始事件"""
        self.aborted = False
        await self.set_is_tts_playing(True)

        # 清空可能存在的旧音频数据
        if self.audio_codec:
            self.audio_codec.clear_audio_queue()

        if self.device_state in (DeviceState.IDLE, DeviceState.LISTENING):
            await self.set_device_state(DeviceState.SPEAKING)

    async def _handle_tts_stop(self):
        """处理TTS停止事件"""
        if self.device_state == DeviceState.SPEAKING:
            # 等待音频队列清空
            max_wait_time = 3.0  # 最大等待时间
            wait_interval = 0.1
            elapsed_time = 0

            while (self.audio_codec and
                   not self.audio_codec.audio_decode_queue.empty() and
                   elapsed_time < max_wait_time):
                await asyncio.sleep(wait_interval)
                elapsed_time += wait_interval

            # 确保所有数据都被播放出来
            if await self.get_is_tts_playing():
                await asyncio.sleep(0.5)

            # 设置TTS播放状态为False
            await self.set_is_tts_playing(False)

            # 强制重新初始化输入流（Linux特定）
            if platform.system() == "Linux" and self.audio_codec:
                try:
                    self.audio_codec._reinitialize_input_stream()
                except Exception as e:
                    logger.error(f"强制重新初始化失败: {e}", exc_info=True)
                    await self.set_device_state(DeviceState.IDLE)
                    if self.wake_word_detector and self.wake_word_detector.paused:
                        self.wake_word_detector.resume()
                    return

            # 状态转换（参考C++实现）
            if self.listening_mode == ListeningMode.MANUAL:
                # 手动模式下，TTS结束后回到IDLE状态
                await self.set_device_state(DeviceState.IDLE)
            else:
                # 其他模式（包括REALTIME和AUTO_STOP）下，TTS结束后回到LISTENING状态
                await self.set_device_state(DeviceState.LISTENING)

    async def _handle_stt_message(self, data):
        """处理STT消息"""
        text = data.get("text", "")
        if text:
            logger.info(f">> {text}")
            await self.set_chat_message("user", text)

    async def _handle_llm_message(self, data):
        """处理LLM消息"""
        emotion = data.get("emotion", "")
        if emotion:
            await self.set_emotion(emotion)

    async def _on_audio_channel_opened(self):
        """音频通道打开回调"""
        logger.info("音频通道已打开")
        await self._start_audio_streams()

        # 发送物联网设备描述符
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()
        await self.protocol.send_iot_descriptors(thing_manager.get_descriptors_json())
        await self._update_iot_states(False)

    async def _start_audio_streams(self):
        """启动音频流"""
        try:
            # 确保音频流处于活跃状态
            if (self.audio_codec.input_stream and
                not self.audio_codec.input_stream.is_active()):
                try:
                    self.audio_codec.input_stream.start_stream()
                except Exception as e:
                    logger.warning(f"启动输入流时出错: {e}")
                    try:
                        self.audio_codec._reinitialize_input_stream()
                    except Exception as reinit_error:
                        logger.error(f"重新初始化输入流失败: {reinit_error}",
                                   exc_info=True)
                        raise

            if (self.audio_codec.output_stream and
                not self.audio_codec.output_stream.is_active()):
                try:
                    self.audio_codec.output_stream.start_stream()
                except Exception as e:
                    logger.warning(f"启动输出流时出错: {e}")
                    try:
                        self.audio_codec._reinitialize_output_stream()
                    except Exception as reinit_error:
                        logger.error(f"重新初始化输出流失败: {reinit_error}",
                                   exc_info=True)
                        raise

            logger.info("音频流已启动")
        except Exception as e:
            logger.error(f"启动音频流失败: {e}", exc_info=True)
            raise

    async def _on_audio_channel_closed(self):
        """音频通道关闭回调"""
        logger.info("音频通道已关闭")
        await self.set_device_state(DeviceState.IDLE)
        self.keep_listening = False

        # 确保唤醒词检测正常工作
        if self.wake_word_detector:
            if not self.wake_word_detector.is_running():
                logger.info("在空闲状态下启动唤醒词检测")
                if self.audio_codec:
                    self.wake_word_detector.start(self.audio_codec)
                else:
                    self.wake_word_detector.start()
            elif self.wake_word_detector.paused:
                logger.info("在空闲状态下恢复唤醒词检测")
                self.wake_word_detector.resume()

    async def set_device_state(self, state: DeviceState):
        """设置设备状态（线程安全）"""
        async with self._state_lock:
            if self.device_state == state:
                return

            self.device_state = state

        # 根据状态执行相应操作
        if state == DeviceState.IDLE:
            if self.display:
                self.display.update_status("待命")
            await self.set_emotion("neutral")
            # 恢复唤醒词检测
            if (self.wake_word_detector and
                hasattr(self.wake_word_detector, 'paused') and
                self.wake_word_detector.paused):
                self.wake_word_detector.resume()
                logger.info("唤醒词检测已恢复")
            # 恢复音频输入流
            if self.audio_codec and self.audio_codec.is_input_paused():
                self.audio_codec.resume_input()

        elif state == DeviceState.CONNECTING:
            if self.display:
                self.display.update_status("连接中...")
            # 清空时间戳队列（参考C++实现）
            await self._clear_timestamp_queue()

        elif state == DeviceState.LISTENING:
            if self.display:
                self.display.update_status("聆听中...")
            await self.set_emotion("neutral")
            await self._update_iot_states(True)
            # 在非实时模式下暂停唤醒词检测
            if (self.listening_mode != ListeningMode.REALTIME and
                self.wake_word_detector and
                hasattr(self.wake_word_detector, 'is_running') and
                self.wake_word_detector.is_running()):
                self.wake_word_detector.pause()
                logger.info("唤醒词检测已暂停（非实时模式）")
            # 确保音频输入流活跃
            if self.audio_codec and self.audio_codec.is_input_paused():
                self.audio_codec.resume_input()

        elif state == DeviceState.SPEAKING:
            if self.display:
                self.display.update_status("说话中...")
            # 根据监听模式决定是否恢复唤醒词检测（参考C++实现）
            if self.listening_mode != ListeningMode.REALTIME:
                # 非实时模式下，在说话时恢复唤醒词检测
                if (self.wake_word_detector and
                    hasattr(self.wake_word_detector, 'paused') and
                    self.wake_word_detector.paused):
                    self.wake_word_detector.resume()
                    logger.info("唤醒词检测已恢复（非实时模式）")
            # 在实时模式下，保持当前唤醒词检测状态

        # 通知状态变化
        for callback in self.on_state_changed_callbacks:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"执行状态变化回调时出错: {e}", exc_info=True)

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
        # 如果表情没有变化，直接返回缓存的路径
        if (hasattr(self, '_last_emotion') and
            self._last_emotion == self.current_emotion):
            return self._last_emotion_path

        # 获取基础路径
        if getattr(sys, 'frozen', False):
            # 打包环境
            if hasattr(sys, '_MEIPASS'):
                base_path = Path(sys._MEIPASS)
            else:
                base_path = Path(sys.executable).parent
        else:
            # 开发环境
            base_path = Path(__file__).parent.parent

        emotion_dir = base_path / "assets" / "emojis"

        emotions = {
            "neutral": str(emotion_dir / "neutral.gif"),
            "happy": str(emotion_dir / "happy.gif"),
            "laughing": str(emotion_dir / "laughing.gif"),
            "funny": str(emotion_dir / "funny.gif"),
            "sad": str(emotion_dir / "sad.gif"),
            "angry": str(emotion_dir / "angry.gif"),
            "crying": str(emotion_dir / "crying.gif"),
            "loving": str(emotion_dir / "loving.gif"),
            "embarrassed": str(emotion_dir / "embarrassed.gif"),
            "surprised": str(emotion_dir / "surprised.gif"),
            "shocked": str(emotion_dir / "shocked.gif"),
            "thinking": str(emotion_dir / "thinking.gif"),
            "winking": str(emotion_dir / "winking.gif"),
            "cool": str(emotion_dir / "cool.gif"),
            "relaxed": str(emotion_dir / "relaxed.gif"),
            "delicious": str(emotion_dir / "delicious.gif"),
            "kissy": str(emotion_dir / "kissy.gif"),
            "confident": str(emotion_dir / "confident.gif"),
            "sleepy": str(emotion_dir / "sleepy.gif"),
            "silly": str(emotion_dir / "silly.gif"),
            "confused": str(emotion_dir / "confused.gif")
        }

        # 保存当前表情和对应的路径
        self._last_emotion = self.current_emotion
        self._last_emotion_path = emotions.get(
            self.current_emotion,
            str(emotion_dir / "neutral.gif")
        )

        logger.debug(f"表情路径: {self._last_emotion_path}")
        return self._last_emotion_path

    async def set_chat_message(self, role: str, message: str):
        """设置聊天消息"""
        # role 参数保留用于未来扩展，当前仅使用 message
        self.current_text = message
        # 更新显示
        if self.display:
            self.display.update_text(message)

    async def set_emotion(self, emotion: str):
        """设置表情"""
        self.current_emotion = emotion
        # 更新显示
        if self.display:
            try:
                self.display.update_emotion(self._get_current_emotion())
            except Exception as e:
                logger.debug(f"更新表情显示时出错（可能是GUI未完全初始化）: {e}")

    def start_listening(self):
        """开始监听"""
        asyncio.create_task(self._start_listening_impl())

    async def _start_listening_impl(self):
        """开始监听的实现"""
        if not self.protocol:
            logger.error("协议未初始化")
            return

        self.keep_listening = False

        # 检查唤醒词检测器是否存在
        if self.wake_word_detector:
            self.wake_word_detector.pause()

        if self.device_state == DeviceState.IDLE:
            await self.set_device_state(DeviceState.CONNECTING)

            # 检查是否已经连接，如果没有则尝试连接
            if not self.protocol.is_audio_channel_opened():
                # 尝试连接服务器
                if not await self.protocol.connect():
                    logger.error("连接服务器失败")
                    self.alert("错误", "连接服务器失败")
                    await self.set_device_state(DeviceState.IDLE)
                    # 恢复唤醒词检测
                    if self.wake_word_detector:
                        self.wake_word_detector.resume()
                    return

                # 尝试打开音频通道
                try:
                    success = await self.protocol.open_audio_channel()
                    if not success:
                        self.alert("错误", "打开音频通道失败")
                        await self.set_device_state(DeviceState.IDLE)
                        # 恢复唤醒词检测
                        if self.wake_word_detector:
                            self.wake_word_detector.resume()
                        return
                except Exception as e:
                    logger.error(f"打开音频通道时发生错误: {e}", exc_info=True)
                    self.alert("错误", f"打开音频通道失败: {str(e)}")
                    await self.set_device_state(DeviceState.IDLE)
                    # 恢复唤醒词检测
                    if self.wake_word_detector:
                        self.wake_word_detector.resume()
                    return

            # 智能重新初始化输入流（只在必要时进行）
            try:
                if self.audio_codec:
                    # 使用健康检查方法，更快速准确
                    if not self.audio_codec.is_input_stream_healthy():
                        logger.info("输入流不健康，进行重新初始化")
                        self.audio_codec._reinitialize_input_stream()
                    else:
                        logger.debug("输入流健康，跳过重新初始化")
                else:
                    logger.warning("音频编解码器未初始化")
            except Exception as e:
                logger.error(f"音频流检查失败: {e}", exc_info=True)
                await self.set_device_state(DeviceState.IDLE)
                if self.wake_word_detector and self.wake_word_detector.paused:
                    self.wake_word_detector.resume()
                return

            self.listening_mode = ListeningMode.MANUAL
            await self.protocol.send_start_listening(self.listening_mode)
            await self.set_device_state(DeviceState.LISTENING)

        elif self.device_state == DeviceState.SPEAKING:
            if not self.aborted:
                await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    def stop_listening(self):
        """停止监听"""
        asyncio.create_task(self._stop_listening_impl())

    async def _stop_listening_impl(self):
        """停止监听的实现"""
        if self.device_state == DeviceState.LISTENING:
            await self.protocol.send_stop_listening()
            await self.set_device_state(DeviceState.IDLE)

    def toggle_chat_state(self):
        """切换聊天状态"""
        # 检查唤醒词检测器是否存在
        if self.wake_word_detector:
            self.wake_word_detector.pause()
        asyncio.create_task(self._toggle_chat_state_impl())

    async def _toggle_chat_state_impl(self):
        """切换聊天状态的具体实现"""
        if not self.protocol:
            logger.error("协议未初始化")
            return

        if self.device_state == DeviceState.IDLE:
            await self.set_device_state(DeviceState.CONNECTING)

            # 尝试打开音频通道
            if not self.protocol.is_audio_channel_opened():
                try:
                    success = await self.protocol.open_audio_channel()
                    if not success:
                        self.alert("错误", "打开音频通道失败")
                        await self.set_device_state(DeviceState.IDLE)
                        return
                except Exception as e:
                    logger.error(f"打开音频通道时发生错误: {e}", exc_info=True)
                    self.alert("错误", f"打开音频通道失败: {str(e)}")
                    await self.set_device_state(DeviceState.IDLE)
                    return

            self.keep_listening = True
            # 根据realtime_chat_enabled选择监听模式（参考C++实现）
            self.listening_mode = ListeningMode.REALTIME if self.realtime_chat_enabled else ListeningMode.AUTO_STOP
            await self.protocol.send_start_listening(self.listening_mode)
            await self.set_device_state(DeviceState.LISTENING)

        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.NONE)

        elif self.device_state == DeviceState.LISTENING:
            try:
                await self.protocol.close_audio_channel()
            except Exception as e:
                logger.error(f"关闭音频通道时发生错误: {e}", exc_info=True)
            await self.set_device_state(DeviceState.IDLE)

    async def abort_speaking(self, reason: AbortReason):
        """中止语音输出"""
        if self.aborted:
            logger.debug(f"已经中止，忽略重复的中止请求: {reason}")
            return

        logger.info(f"中止语音输出，原因: {reason}")
        self.aborted = True

        # 设置TTS播放状态为False
        await self.set_is_tts_playing(False)

        # 立即清空音频队列
        if self.audio_codec:
            self.audio_codec.clear_audio_queue()

        # 如果是因为唤醒词中止语音，先暂停唤醒词检测器
        if (reason == AbortReason.WAKE_WORD_DETECTED and
            self.wake_word_detector and
            hasattr(self.wake_word_detector, 'is_running') and
            self.wake_word_detector.is_running()):
            self.wake_word_detector.pause()
            logger.debug("暂时暂停唤醒词检测器以避免并发处理")
            await asyncio.sleep(0.1)

        # 发送中止指令
        try:
            await self.protocol.send_abort_speaking(reason)
        except Exception as e:
            logger.error(f"发送中止指令时出错: {e}", exc_info=True)

        # 设置状态
        await self.set_device_state(DeviceState.IDLE)

        # 如果是唤醒词触发的中止，并且启用了自动聆听，则自动进入录音模式
        if (reason == AbortReason.WAKE_WORD_DETECTED and
            self.keep_listening and
            self.protocol.is_audio_channel_opened()):
            await asyncio.sleep(0.1)
            asyncio.create_task(self._toggle_chat_state_impl())

    def alert(self, title: str, message: str):
        """显示警告信息"""
        logger.warning(f"警告: {title}, {message}")
        # 在GUI上显示警告
        if self.display:
            self.display.update_text(f"{title}: {message}")

    def on_state_changed(self, callback: Callable):
        """注册状态变化回调"""
        self.on_state_changed_callbacks.append(callback)

    async def _send_text_tts(self, text: str):
        await self.protocol.send_wake_word_detected(text)

    def is_realtime_chat_enabled(self) -> bool:
        """获取实时聊天模式状态"""
        return self.realtime_chat_enabled

    def set_realtime_chat_enabled(self, enabled: bool):
        """设置实时聊天模式状态"""
        self.realtime_chat_enabled = enabled
        logger.info(f"实时聊天模式已{'启用' if enabled else '禁用'}")
        # 更新配置文件
        self.config.update_config("SYSTEM_OPTIONS.REALTIME_CHAT_ENABLED", enabled)

    async def _get_audio_timestamp(self) -> int:
        """获取音频包的时间戳（参考C++实现）"""
        if not self.use_server_aec:
            return 0

        async with self.timestamp_lock:
            if self.timestamp_queue:
                timestamp = self.timestamp_queue.pop(0)
                return timestamp
            else:
                return 0

    async def _add_output_timestamp(self, timestamp: int):
        """添加输出音频的时间戳到队列（参考C++实现）"""
        if not self.use_server_aec:
            return

        async with self.timestamp_lock:
            self.timestamp_queue.append(timestamp)
            self.last_output_timestamp = timestamp

            # 限制队列长度为3（参考C++实现）
            if len(self.timestamp_queue) > 3:
                self.timestamp_queue.pop(0)

    async def _clear_timestamp_queue(self):
        """清空时间戳队列（参考C++实现）"""
        async with self.timestamp_lock:
            self.timestamp_queue.clear()
            self.last_output_timestamp = 0

    def _on_mode_changed(self, auto_mode: bool) -> bool:
        """处理对话模式变更"""
        # 只有在IDLE状态下才允许切换模式
        if self.device_state != DeviceState.IDLE:
            self.alert("提示", "只有在待命状态下才能切换对话模式")
            return False

        self.keep_listening = auto_mode
        logger.info(f"对话模式已切换为: {'自动' if auto_mode else '手动'}")
        return True

    async def _initialize_wake_word_detector(self):
        """初始化唤醒词检测器"""
        # 首先检查配置中是否启用了唤醒词功能
        if not self.config.get_config('WAKE_WORD_OPTIONS.USE_WAKE_WORD', False):
            logger.info("唤醒词功能已在配置中禁用，跳过初始化")
            self.wake_word_detector = None
            return

        try:
            from src.audio_processing.wake_word_detect import WakeWordDetector

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
            self.wake_word_detector.on_error = self._handle_wake_word_error

            logger.info("唤醒词检测器初始化成功")

            # 启动唤醒词检测器
            await self._start_wake_word_detector()

        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}", exc_info=True)
            # 禁用唤醒词功能，但不影响程序其他功能
            self.config.update_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)
            logger.info("由于初始化失败，唤醒词功能已禁用，但程序将继续运行")
            self.wake_word_detector = None

    def _handle_wake_word_error(self, error):
        """处理唤醒词检测器错误"""
        logger.error(f"唤醒词检测错误: {error}")
        # 尝试重新启动检测器
        if self.device_state == DeviceState.IDLE:
            # 由于此回调可能在其他线程中调用，需要使用 run_coroutine_threadsafe
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._restart_wake_word_detector(),
                    self.loop
                )
            else:
                logger.error("事件循环未运行，无法重启唤醒词检测器")

    async def _start_wake_word_detector(self):
        """启动唤醒词检测器"""
        if not self.wake_word_detector:
            return

        # 确保音频编解码器已初始化
        if self.audio_codec:
            logger.info("使用音频编解码器启动唤醒词检测器")
            self.wake_word_detector.start(self.audio_codec)
        else:
            # 如果没有音频编解码器，使用独立模式
            logger.info("使用独立模式启动唤醒词检测器")
            self.wake_word_detector.start()

    def _on_wake_word_detected(self, wake_word: str, full_text: str):
        """唤醒词检测回调"""
        logger.info(f"检测到唤醒词: {wake_word} (完整文本: {full_text})")
        # 由于此回调可能在其他线程中调用，需要使用 run_coroutine_threadsafe
        if self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._handle_wake_word_detected(wake_word),
                self.loop
            )
        else:
            logger.error("事件循环未运行，无法处理唤醒词检测事件")

    async def _handle_wake_word_detected(self, wake_word: str):
        """处理唤醒词检测事件"""
        if self.device_state == DeviceState.IDLE:
            # 暂停唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.pause()

            # 开始连接并监听
            await self.set_device_state(DeviceState.CONNECTING)
            await self._connect_and_start_listening(wake_word)

        elif self.device_state == DeviceState.SPEAKING:
            await self.abort_speaking(AbortReason.WAKE_WORD_DETECTED)

    async def _connect_and_start_listening(self, wake_word: str):
        """连接服务器并开始监听"""
        # 首先尝试连接服务器
        if not await self.protocol.connect():
            logger.error("连接服务器失败")
            self.alert("错误", "连接服务器失败")
            await self.set_device_state(DeviceState.IDLE)
            # 恢复唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.resume()
            return

        # 然后尝试打开音频通道
        if not await self.protocol.open_audio_channel():
            logger.error("打开音频通道失败")
            await self.set_device_state(DeviceState.IDLE)
            self.alert("错误", "打开音频通道失败")
            # 恢复唤醒词检测
            if self.wake_word_detector:
                self.wake_word_detector.resume()
            return

        await self.protocol.send_wake_word_detected(wake_word)
        # 根据realtime_chat_enabled选择监听模式（参考C++实现）
        self.keep_listening = True
        self.listening_mode = ListeningMode.REALTIME if self.realtime_chat_enabled else ListeningMode.AUTO_STOP
        await self.protocol.send_start_listening(self.listening_mode)
        await self.set_device_state(DeviceState.LISTENING)

    async def _restart_wake_word_detector(self):
        """重新启动唤醒词检测器"""
        logger.info("尝试重新启动唤醒词检测器")
        try:
            # 停止现有的检测器
            if self.wake_word_detector:
                self.wake_word_detector.stop()
                await asyncio.sleep(0.5)  # 给予一些时间让资源释放

            # 直接使用音频编解码器
            if self.audio_codec:
                self.wake_word_detector.start(self.audio_codec)
                logger.info("使用音频编解码器重新启动唤醒词检测器")
            else:
                # 如果没有音频编解码器，使用独立模式
                self.wake_word_detector.start()
                logger.info("使用独立模式重新启动唤醒词检测器")

            logger.info("唤醒词检测器重新启动成功")
        except Exception as e:
            logger.error(f"重新启动唤醒词检测器失败: {e}", exc_info=True)

    async def _initialize_iot_devices(self):
        """初始化物联网设备"""
        from src.iot.thing_manager import ThingManager
        from src.iot.things.lamp import Lamp
        from src.iot.things.speaker import Speaker
        from src.iot.things.music_player import MusicPlayer
        from src.iot.things.CameraVL.Camera import Camera
        from src.iot.things.ha_control import (
            HomeAssistantLight, HomeAssistantSwitch,
            HomeAssistantNumber, HomeAssistantButton
        )
        from src.iot.things.countdown_timer import CountdownTimer

        # 获取物联网设备管理器实例
        thing_manager = ThingManager.get_instance()

        # 添加设备
        thing_manager.add_thing(Lamp())
        thing_manager.add_thing(Speaker())
        thing_manager.add_thing(MusicPlayer())
        thing_manager.add_thing(Camera())
        thing_manager.add_thing(CountdownTimer())
        logger.info("已添加倒计时器设备,用于计时执行命令用")

        # 添加Home Assistant设备
        ha_devices = self.config.get_config("HOME_ASSISTANT.DEVICES", [])
        for device in ha_devices:
            entity_id = device.get("entity_id")
            friendly_name = device.get("friendly_name")
            if entity_id:
                # 根据实体ID判断设备类型
                if entity_id.startswith("light."):
                    thing_manager.add_thing(HomeAssistantLight(entity_id, friendly_name))
                    logger.info(f"已添加Home Assistant灯设备: {friendly_name or entity_id}")
                elif entity_id.startswith("switch."):
                    thing_manager.add_thing(HomeAssistantSwitch(entity_id, friendly_name))
                    logger.info(f"已添加Home Assistant开关设备: {friendly_name or entity_id}")
                elif entity_id.startswith("number."):
                    thing_manager.add_thing(HomeAssistantNumber(entity_id, friendly_name))
                    logger.info(f"已添加Home Assistant数值设备: {friendly_name or entity_id}")
                elif entity_id.startswith("button."):
                    thing_manager.add_thing(HomeAssistantButton(entity_id, friendly_name))
                    logger.info(f"已添加Home Assistant按钮设备: {friendly_name or entity_id}")
                else:
                    # 默认作为灯设备处理
                    thing_manager.add_thing(HomeAssistantLight(entity_id, friendly_name))
                    logger.info(f"已添加Home Assistant设备(默认作为灯处理): {friendly_name or entity_id}")

        logger.info("物联网设备初始化完成")

    async def _handle_iot_message(self, data):
        """处理物联网消息"""
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()

        commands = data.get("commands", [])
        print("收到物联网命令:", commands)
        for command in commands:
            try:
                result = thing_manager.invoke(command)
                logger.info(f"执行物联网命令结果: {result}")
            except Exception as e:
                logger.error(f"执行物联网命令失败: {e}", exc_info=True)

    async def _update_iot_states(self, delta=None):
        """更新物联网设备状态"""
        from src.iot.thing_manager import ThingManager
        thing_manager = ThingManager.get_instance()

        # 处理向下兼容
        if delta is None:
            # 保持原有行为：获取所有状态并发送
            states_json = thing_manager.get_states_json_str()
            await self.protocol.send_iot_states(states_json)
            logger.info("物联网设备状态已更新")
            return

        # 使用新方法获取状态
        changed, states_json = thing_manager.get_states_json(delta=delta)
        # delta=False总是发送，delta=True只在有变化时发送
        if not delta or changed:
            await self.protocol.send_iot_states(states_json)
            if delta:
                logger.info("物联网设备状态已更新(增量)")
            else:
                logger.info("物联网设备状态已更新(完整)")
        else:
            logger.debug("物联网设备状态无变化，跳过更新")

    async def shutdown(self):
        """关闭应用程序"""
        logger.info("正在关闭应用程序...")
        self.running = False

        # 取消所有任务
        for task in list(self._tasks):
            if not task.done():
                task.cancel()

        # 等待任务完成（设置超时）
        if self._tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("任务关闭超时，强制终止")

        # 关闭音频编解码器
        if self.audio_codec:
            try:
                self.audio_codec.close()
            except Exception as e:
                logger.error(f"关闭音频编解码器时出错: {e}", exc_info=True)

        # 关闭协议
        if self.protocol:
            try:
                await asyncio.wait_for(
                    self.protocol.close_audio_channel(),
                    timeout=3.0
                )
            except asyncio.TimeoutError:
                logger.warning("协议关闭超时")
            except Exception as e:
                logger.error(f"关闭协议时出错: {e}", exc_info=True)

        # 停止唤醒词检测
        if self.wake_word_detector:
            try:
                self.wake_word_detector.stop()
            except Exception as e:
                logger.error(f"停止唤醒词检测时出错: {e}", exc_info=True)

        logger.info("应用程序已关闭")
