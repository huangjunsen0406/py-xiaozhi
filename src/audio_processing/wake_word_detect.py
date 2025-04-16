import json
import threading
import time
import pyaudio
import os
import sys
from vosk import Model, KaldiRecognizer, SetLogLevel
from pypinyin import lazy_pinyin

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

# 配置日志
logger = get_logger(__name__)


class WakeWordDetector:
    """唤醒词检测类"""

    def __init__(self,
                 sample_rate=AudioConfig.INPUT_SAMPLE_RATE,
                 buffer_size=AudioConfig.INPUT_FRAME_SIZE):
        """
        初始化唤醒词检测器

        参数:
            sample_rate: 音频采样率
            buffer_size: 音频缓冲区大小
        """
        # 初始化基本属性
        self.on_detected_callbacks = []
        self.running = False
        self.detection_thread = None
        self.audio_stream = None
        self.paused = False
        self.audio = None
        self.stream = None
        self.external_stream = False
        self.stream_lock = threading.Lock()
        self.on_error = None

        # 获取配置
        config = ConfigManager.get_instance()
        if not config.get_config('WAKE_WORD_OPTIONS.USE_WAKE_WORD', False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return

        # 基本初始化
        self.enabled = True
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.sensitivity = config.get_config(
            "WAKE_WORD_OPTIONS.SENSITIVITY", 0.5
        )

        # 设置唤醒词
        self.wake_words = config.get_config('WAKE_WORD_OPTIONS.WAKE_WORDS', [
            "你好小明", "你好小智", "你好小天", "小爱同学", "贾维斯"
        ])
        
        # 预先计算唤醒词的拼音
        self.wake_words_pinyin = []
        for word in self.wake_words:
            self.wake_words_pinyin.append(''.join(lazy_pinyin(word)))

        # 初始化模型
        try:
            # 获取模型路径
            model_path = self._get_model_path(config)
            
            # 检查模型路径
            if not os.path.exists(model_path):
                error_msg = f"模型路径不存在: {model_path}"
                logger.error(error_msg)
                self.enabled = False
                raise FileNotFoundError(error_msg)

            # 初始化模型
            logger.info(f"正在加载语音识别模型: {model_path}")
            SetLogLevel(-1)  # 设置 Vosk 日志级别为静默
            self.model = Model(model_path=model_path)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)
            logger.info("模型加载完成")

            # 调试信息
            logger.info(f"已配置 {len(self.wake_words)} 个唤醒词")
            for i, word in enumerate(self.wake_words):
                pinyin = self.wake_words_pinyin[i]
                logger.debug(f"唤醒词 {i + 1}: {word} (拼音: {pinyin})")
                
        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.enabled = False
    
    def _get_model_path(self, config):
        """获取模型路径，处理不同运行环境"""
        model_path = config.get_config(
            'WAKE_WORD_OPTIONS.MODEL_PATH', 
            'models/vosk-model-small-cn-0.22'
        )
        
        # 转换为绝对路径
        if not os.path.isabs(model_path):
            if getattr(sys, 'frozen', False):
                # 打包环境
                if hasattr(sys, '_MEIPASS'):
                    base_path = sys._MEIPASS
                else:
                    base_path = os.path.dirname(sys.executable)
            else:
                # 开发环境
                base_dir = os.path.dirname
                current_file = os.path.abspath(__file__)
                base_path = base_dir(base_dir(base_dir(current_file)))
            
            model_path = os.path.join(base_path, model_path)
            logger.info(f"使用模型路径: {model_path}")
        
        return model_path

    def start(self, audio_stream=None):
        """启动唤醒词检测"""
        if not getattr(self, 'enabled', True):
            logger.info("唤醒词功能已禁用，无法启动")
            return False

        # 先停止现有的检测
        self.stop()

        try:
            # 初始化音频
            with self.stream_lock:
                if audio_stream:
                    self.stream = audio_stream
                    self.audio = None
                    self.external_stream = True
                    logger.info("唤醒词检测器使用外部音频流")
                else:
                    self.audio = pyaudio.PyAudio()
                    self.stream = self.audio.open(
                        format=pyaudio.paInt16,
                        channels=AudioConfig.CHANNELS,
                        rate=self.sample_rate,
                        input=True,
                        frames_per_buffer=self.buffer_size
                    )
                    self.external_stream = False
                    logger.info("唤醒词检测器使用内部音频流")

            # 启动检测线程
            self.running = True
            self.paused = False
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True
            )
            self.detection_thread.start()

            logger.info("唤醒词检测已启动")
            return True
        except Exception as e:
            error_msg = f"启动唤醒词检测失败: {e}"
            logger.error(error_msg)
            if self.on_error:
                self.on_error(error_msg)
            self._cleanup()
            return False

    def stop(self):
        """停止唤醒词检测"""
        if self.running:
            self.running = False
            self.paused = False

            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=1.0)
                self.detection_thread = None

            # 只有当使用内部流时才关闭
            if not self.external_stream and self.stream:
                try:
                    if self.stream.is_active():
                        self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                except Exception as e:
                    logger.error(f"停止音频流时出错: {e}")
            else:
                # 如果是外部流，只设置为None但不关闭
                self.stream = None

            if self.audio:
                try:
                    self.audio.terminate()
                    self.audio = None
                except Exception as e:
                    logger.error(f"终止音频设备时出错: {e}")

    def pause(self):
        """暂停唤醒词检测"""
        if self.running and not self.paused:
            self.paused = True
            logger.info("唤醒词检测已暂停")

    def resume(self):
        """恢复唤醒词检测"""
        if self.running and self.paused:
            self.paused = False
            # 如果流已关闭，重新启动检测
            if not self.stream or not self.stream.is_active():
                self.start()
            logger.info("唤醒词检测已恢复")

    def is_running(self):
        """检查唤醒词检测是否正在运行"""
        return self.running and not self.paused

    def on_detected(self, callback):
        """
        注册唤醒词检测回调

        回调函数格式: callback(wake_word, full_text)
        """
        self.on_detected_callbacks.append(callback)

    def _cleanup(self):
        """清理资源"""
        # 只有当我们创建了自己的音频流时才关闭它
        if self.audio and self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
                self.audio.terminate()
            except Exception as e:
                logger.error(f"清理音频资源时出错: {e}")

        self.stream = None
        self.audio = None

    def _check_wake_word(self, text):
        """检查文本中是否包含唤醒词（仅使用拼音匹配）"""
        # 将输入文本转换为拼音
        text_pinyin = ''.join(lazy_pinyin(text))
        text_pinyin = text_pinyin.replace(" ", "")  # 移除空格
        # 只进行拼音匹配
        for i, pinyin in enumerate(self.wake_words_pinyin):
            if pinyin in text_pinyin:
                return True, self.wake_words[i]

        return False, None

    def update_stream(self, new_stream):
        """更新唤醒词检测器使用的音频流"""
        if not self.running:
            logger.warning("唤醒词检测器未运行，无法更新流")
            return False

        with self.stream_lock:
            # 如果当前使用的是内部流，需要先清理
            if not self.external_stream and self.stream:
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

    def _detection_loop(self):
        """唤醒词检测主循环"""
        if not getattr(self, 'enabled', True):
            return

        logger.info("唤醒词检测循环已启动")
        error_count = 0
        max_errors = 5  # 错误容忍度
        stream_error_time = None  # 记录流错误的开始时间

        while self.running:
            try:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # 读取音频数据
                try:
                    # 读取并处理音频数据
                    data = self._read_audio_data(
                        error_count, 
                        max_errors,
                        stream_error_time
                    )
                    if data is None:
                        continue
                    # 重置流错误时间
                    stream_error_time = None
                except (OSError, Exception) as e:
                    error_result = self._handle_read_error(
                        e, error_count, max_errors, stream_error_time
                    )
                    error_count, stream_error_time = error_result
                    continue

                if len(data) == 0:
                    continue

                error_count = 0  # 重置错误计数

                # 处理音频数据
                self._process_audio_data(data)

            except Exception as e:
                logger.error(f"唤醒词检测循环出错: {e}")
                if self.on_error:
                    self.on_error(str(e))
                time.sleep(0.5)  # 增加等待时间，减少CPU使用

    def _read_audio_data(self, error_count, max_errors, stream_error_time):
        """读取音频数据"""
        with self.stream_lock:
            if not self.stream:
                if stream_error_time is None:
                    stream_error_time = time.time()
                    logger.error("音频流不可用，等待恢复")
                elif time.time() - stream_error_time > 5.0:
                    # 5秒后尝试获取新流
                    if self.on_error:
                        msg = "音频流长时间不可用，需要重新获取"
                        self.on_error(msg)
                    stream_error_time = None
                time.sleep(0.5)
                return None

            # 尝试检查流状态
            try:
                if not self.stream.is_active() and not self.external_stream:
                    self.stream.start_stream()
            except Exception:
                pass

            # 读取数据
            data = self.stream.read(
                self.buffer_size // 2, 
                exception_on_overflow=False
            )
            return data

    def _handle_read_error(self, error, error_count, max_errors, stream_error_time):
        """处理读取错误"""
        error_count += 1
        
        # 特殊处理流状态错误
        if isinstance(error, OSError):
            error_str = str(error)
            # 检查是否是流状态错误
            stream_errors = [
                "Stream not open", 
                "Stream closed", 
                "Stream is stopped"
            ]
            # 检查是否包含任意流错误信息
            is_stream_error = False
            for msg in stream_errors:
                if msg in error_str:
                    is_stream_error = True
                    break
            
            if is_stream_error:
                logger.warning(f"音频流问题 ({error_count}/{max_errors}): {error}")
            else:
                logger.error(f"读取音频失败 ({error_count}/{max_errors}): {error}")
        else:
            logger.error(f"读取音频异常 ({error_count}/{max_errors}): {error}")
            
        # 处理错误超过阈值
        if error_count >= max_errors:
            if self.on_error:
                err_msg = f"连续读取音频失败 {max_errors} 次: {error}"
                self.on_error(err_msg)
            error_count = 0  # 重置计数，允许继续尝试
            time.sleep(1.0)  # 等待时间长一些
        else:
            time.sleep(0.5)
            
        return error_count, stream_error_time

    def _process_audio_data(self, data):
        """处理音频数据"""
        # 处理音频数据
        is_final = self.recognizer.AcceptWaveform(data)

        # 处理部分结果，实现实时唤醒词检测
        partial_result = json.loads(self.recognizer.PartialResult())
        partial_text = partial_result.get('partial', '')
        if partial_text.strip():
            self._check_and_handle_wake_word(partial_text, is_partial=True)

        # 处理最终结果
        if is_final:
            result = json.loads(self.recognizer.Result())
            if "text" in result and result["text"].strip():
                text = result["text"]
                logger.debug(f"识别文本: {text}")
                self._check_and_handle_wake_word(text, is_partial=False)

    def _check_and_handle_wake_word(self, text, is_partial=False):
        """检查并处理唤醒词"""
        detected, wake_word = self._check_wake_word(text)
        if detected:
            # 日志记录
            text_type = "部分文本" if is_partial else "完整文本"
            log_msg = f"检测到唤醒词: '{wake_word}' ({text_type}: {text})"
            logger.info(log_msg)
            
            # 触发回调
            self._trigger_callbacks(wake_word, text)

    def _trigger_callbacks(self, wake_word, text):
        """触发唤醒词回调"""
        for callback in self.on_detected_callbacks:
            try:
                callback(wake_word, text)
            except Exception as e:
                logger.error(f"执行唤醒词检测回调时出错: {e}")
        # 重置识别器，准备下一轮检测
        self.recognizer.Reset()