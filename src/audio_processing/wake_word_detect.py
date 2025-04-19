import json
import threading
import time
import os
import sys
from vosk import Model, KaldiRecognizer, SetLogLevel
from pypinyin import lazy_pinyin
import pyaudio

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

class WakeWordDetector:
    """唤醒词检测类（集成AudioCodec优化版）"""

    def __init__(self, 
                 sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                 buffer_size=AudioConfig.INPUT_FRAME_SIZE,
                 audio_codec=None):
        """
        初始化唤醒词检测器
        
        参数:
            audio_codec: AudioCodec实例（新增）
            sample_rate: 音频采样率
            buffer_size: 音频缓冲区大小
        """
        # 初始化音频编解码器引用
        self.audio_codec = audio_codec
        
        # 初始化基本属性
        self.on_detected_callbacks = []
        self.running = False
        self.detection_thread = None
        self.paused = False
        self.audio = None
        self.stream = None
        self.external_stream = False
        self.stream_lock = threading.Lock()
        self.on_error = None

        # 配置检查
        config = ConfigManager.get_instance()
        if not config.get_config('WAKE_WORD_OPTIONS.USE_WAKE_WORD', False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return

        # 基本参数初始化
        self.enabled = True
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.sensitivity = config.get_config("WAKE_WORD_OPTIONS.SENSITIVITY", 0.5)

        # 唤醒词配置
        self.wake_words = config.get_config('WAKE_WORD_OPTIONS.WAKE_WORDS', [
            "你好小明", "你好小智", "你好小天", "小爱同学", "贾维斯"
        ])
        self.wake_words_pinyin = [''.join(lazy_pinyin(word)) for word in self.wake_words]

        # 模型初始化
        try:
            model_path = self._get_model_path(config)
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型路径不存在: {model_path}")

            logger.info(f"加载语音识别模型: {model_path}")
            SetLogLevel(-1)
            self.model = Model(model_path=model_path)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)
            logger.info("模型加载完成")

            # 调试日志
            logger.info(f"已配置 {len(self.wake_words)} 个唤醒词")
            for idx, (word, pinyin) in enumerate(zip(self.wake_words, self.wake_words_pinyin)):
                logger.debug(f"唤醒词 {idx+1}: {word.ljust(8)} => {pinyin}")
                
        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            self.enabled = False

    def _get_model_path(self, config):
        """获取模型路径（优化多环境支持）"""
        model_path = config.get_config('WAKE_WORD_OPTIONS.MODEL_PATH', 'models/vosk-model-small-cn-0.22')
        
        # 处理相对路径
        if not os.path.isabs(model_path):
            base_path = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            model_path = os.path.join(base_path, model_path)
        
        logger.debug(f"解析模型路径: {model_path}")
        return model_path

    def start(self, audio_codec_or_stream=None):
        """启动检测（支持音频编解码器或直接流传入）"""
        if not self.enabled:
            logger.warning("唤醒词功能未启用")
            return False

        # 检查参数类型，区分音频编解码器和流对象
        if audio_codec_or_stream:
            # 检查是否是流对象
            if hasattr(audio_codec_or_stream, 'read') and hasattr(audio_codec_or_stream, 'is_active'):
                # 是流对象，使用直接流模式
                self.stream = audio_codec_or_stream
                self.external_stream = True
                return self._start_with_external_stream()
            else:
                # 是AudioCodec对象，使用AudioCodec模式
                self.audio_codec = audio_codec_or_stream

        # 优先使用audio_codec的流
        if self.audio_codec:
            return self._start_with_audio_codec()
        else:
            return self._start_standalone()

    def _start_with_audio_codec(self):
        """使用AudioCodec的输入流（直接访问）"""
        try:
            # 直接访问input_stream属性
            if not self.audio_codec or not self.audio_codec.input_stream:
                logger.error("音频编解码器无效或输入流不可用")
                return False

            # 直接使用AudioCodec的输入流
            self.stream = self.audio_codec.input_stream
            self.external_stream = True  # 标记为外部流，避免错误关闭

            # 配置流参数
            self.sample_rate = AudioConfig.INPUT_SAMPLE_RATE
            self.buffer_size = AudioConfig.INPUT_FRAME_SIZE

            # 启动检测线程
            self.running = True
            self.paused = False
            self.detection_thread = threading.Thread(
                target=self._audio_codec_detection_loop,
                daemon=True,
                name="WakeWordDetector-AudioCodec"
            )
            self.detection_thread.start()

            logger.info("唤醒词检测已启动（直接使用AudioCodec输入流）")
            return True
        except Exception as e:
            logger.error(f"通过AudioCodec启动失败: {e}")
            return False

    def _start_standalone(self):
        """独立音频模式"""
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=AudioConfig.CHANNELS,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.buffer_size
            )

            self.running = True
            self.paused = False
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name="WakeWordDetector-Standalone"
            )
            self.detection_thread.start()

            logger.info("唤醒词检测已启动（独立音频模式）")
            return True
        except Exception as e:
            logger.error(f"独立模式启动失败: {e}")
            return False

    def _start_with_external_stream(self):
        """使用外部提供的音频流"""
        try:
            # 设置参数
            self.sample_rate = AudioConfig.INPUT_SAMPLE_RATE
            self.buffer_size = AudioConfig.INPUT_FRAME_SIZE
            
            # 启动检测线程
            self.running = True
            self.paused = False
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name="WakeWordDetector-ExternalStream"
            )
            self.detection_thread.start()
            
            logger.info("唤醒词检测已启动（使用外部音频流）")
            return True
        except Exception as e:
            logger.error(f"使用外部流启动失败: {e}")
            return False

    def _audio_codec_detection_loop(self):
        """AudioCodec专用检测循环（优化直接访问）"""
        logger.info("进入AudioCodec检测循环")
        error_count = 0
        MAX_ERRORS = 5
        STREAM_TIMEOUT = 3.0  # 流等待超时时间

        while self.running:
            try:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # 直接访问AudioCodec的输入流
                if not self.audio_codec or not hasattr(self.audio_codec, 'input_stream'):
                    logger.warning("AudioCodec不可用，等待中...")
                    time.sleep(STREAM_TIMEOUT)
                    continue
                    
                # 直接使用当前流引用
                stream = self.audio_codec.input_stream
                if not stream or not stream.is_active():
                    logger.debug("AudioCodec输入流不活跃，等待恢复...")
                    try:
                        # 尝试重新激活或等待AudioCodec恢复流
                        if stream and hasattr(stream, 'start_stream'):
                            stream.start_stream()
                        else:
                            time.sleep(0.5)
                            continue
                    except Exception as e:
                        logger.warning(f"激活流失败: {e}")
                        time.sleep(0.5)
                        continue

                # 读取音频数据
                data = self._read_audio_data_direct(stream)
                if not data:
                    continue

                # 处理数据
                self._process_audio_data(data)
                error_count = 0  # 重置错误计数

            except Exception as e:
                error_count += 1
                logger.error(f"检测循环错误({error_count}/{MAX_ERRORS}): {str(e)}")
                
                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    self.stop()
                time.sleep(0.5)

    def _read_audio_data_direct(self, stream):
        """直接从流读取数据（简化版）"""
        try:
            with self.stream_lock:
                # 检查可用数据
                if hasattr(stream, 'get_read_available'):
                    available = stream.get_read_available()
                    if available < self.buffer_size:
                        return None

                # 精确读取
                return stream.read(self.buffer_size, exception_on_overflow=False)
        except OSError as e:
            error_msg = str(e)
            logger.warning(f"音频流错误: {error_msg}")
            
            # 关键错误处理
            critical_errors = ["Input overflowed", "Device unavailable"]
            if any(msg in error_msg for msg in critical_errors) and self.audio_codec:
                logger.info("触发音频流重置...")
                try:
                    # 直接调用AudioCodec的重置方法
                    self.audio_codec._reinitialize_input_stream()
                except Exception as re:
                    logger.error(f"流重置失败: {re}")
                    
            time.sleep(0.5)
            return None
        except Exception as e:
            logger.error(f"读取音频数据异常: {e}")
            return None

    def _detection_loop(self):
        """标准检测循环（用于外部流或独立模式）"""
        logger.info("进入标准检测循环")
        error_count = 0
        MAX_ERRORS = 5

        while self.running:
            try:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # 读取音频数据（带锁保护）
                try:
                    with self.stream_lock:
                        if not self.stream:
                            logger.warning("音频流不可用")
                            time.sleep(0.5)
                            continue
                            
                        # 确保流是活跃的
                        if not self.stream.is_active():
                            try:
                                self.stream.start_stream()
                            except Exception as e:
                                logger.error(f"启动音频流失败: {e}")
                                time.sleep(0.5)
                                continue
                        
                        # 读取数据
                        data = self.stream.read(
                            self.buffer_size, 
                            exception_on_overflow=False
                        )
                except Exception as e:
                    logger.error(f"读取音频数据失败: {e}")
                    time.sleep(0.5)
                    continue

                # 处理音频数据
                if data and len(data) > 0:
                    self._process_audio_data(data)
                    error_count = 0  # 重置错误计数
                    
            except Exception as e:
                error_count += 1
                logger.error(f"检测循环错误({error_count}/{MAX_ERRORS}): {e}")
                
                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    self.stop()
                time.sleep(0.5)
                
    def stop(self):
        """停止检测（优化资源释放）"""
        if self.running:
            logger.info("正在停止唤醒词检测...")
            self.running = False

            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=1.0)

            # 仅清理自有资源，不清理外部传入的流
            if not self.external_stream and not self.audio_codec and self.stream:
                try:
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    logger.error(f"关闭音频流失败: {e}")
                    
            # 清理PyAudio实例
            if self.audio:
                try:
                    self.audio.terminate()
                except Exception as e:
                    logger.error(f"终止音频设备失败: {e}")

            # 重置状态
            self.stream = None
            self.audio = None
            self.external_stream = False
            logger.info("唤醒词检测已停止")
            
    def is_running(self):
        """检查唤醒词检测是否正在运行"""
        return self.running and not self.paused
        
    def update_stream(self, new_stream):
        """更新唤醒词检测器使用的音频流"""
        if not self.running:
            logger.warning("唤醒词检测器未运行，无法更新流")
            return False

        with self.stream_lock:
            # 如果当前不是使用外部流或AudioCodec，先清理现有资源
            if not self.external_stream and not self.audio_codec and self.stream:
                try:
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                except Exception as e:
                    logger.warning(f"关闭旧流时出错: {e}")

            # 更新为新的流
            self.stream = new_stream
            self.external_stream = True
            logger.info("已更新唤醒词检测器的音频流")
        return True

    def _process_audio_data(self, data):
        """处理音频数据（优化日志）"""
        if self.recognizer.AcceptWaveform(data):
            result = json.loads(self.recognizer.Result())
            if text := result.get('text', ''):
                logger.debug(f"完整识别: {text}")
                self._check_wake_word(text)

        partial = json.loads(self.recognizer.PartialResult()).get('partial', '')
        if partial:
            logger.debug(f"部分识别: {partial}")
            self._check_wake_word(partial, is_partial=True)

    def _check_wake_word(self, text, is_partial=False):
        """唤醒词检查（优化拼音匹配）"""
        text_pinyin = ''.join(lazy_pinyin(text)).replace(' ', '')
        for word, pinyin in zip(self.wake_words, self.wake_words_pinyin):
            if pinyin in text_pinyin:
                logger.info(f"检测到唤醒词 '{word}' (匹配拼音: {pinyin})")
                self._trigger_callbacks(word, text)
                self.recognizer.Reset()
                return

    def pause(self):
        """暂停检测"""
        if self.running and not self.paused:
            self.paused = True
            logger.info("检测已暂停")

    def resume(self):
        """恢复检测"""
        if self.running and self.paused:
            self.paused = False
            logger.info("检测已恢复")

    def on_detected(self, callback):
        """注册回调"""
        self.on_detected_callbacks.append(callback)

    def _trigger_callbacks(self, wake_word, text):
        """触发回调（带异常处理）"""
        for cb in self.on_detected_callbacks:
            try:
                cb(wake_word, text)
            except Exception as e:
                logger.error(f"回调执行失败: {e}", exc_info=True)

    def __del__(self):
        self.stop()