import json
import logging
import threading
import time
import pyaudio
import os
import sys
import vosk
import platform

from src.constants.constants import AudioConfig

def add_dll_directory(path):
    """跨平台的dll目录添加函数"""
    if platform.system() == 'Windows':
        if hasattr(os, 'add_dll_directory'):
            os.add_dll_directory(path)
    # 在Mac/Linux上，可以使用LD_LIBRARY_PATH环境变量
    else:
        library_path = os.environ.get('LD_LIBRARY_PATH', '')
        if path not in library_path:
            os.environ['LD_LIBRARY_PATH'] = f"{path}:{library_path}"

# 尝试导入 vosk 及相关组件
try:
    # 先定位 vosk 的 DLL 目录
    if getattr(sys, 'frozen', False):
        # 在打包环境中
        vosk_dir = os.path.join(sys._MEIPASS, 'vosk')
        if os.path.exists(vosk_dir):
            # 添加 vosk 目录到 DLL 搜索路径
            add_dll_directory(vosk_dir)
            logging.getLogger("Application").info(f"已添加 Vosk DLL 目录: {vosk_dir}")
    
    from vosk import Model, KaldiRecognizer, SetLogLevel
    from pypinyin import lazy_pinyin
    VOSK_AVAILABLE = True
except ImportError as e:
    logging.getLogger("Application").error(f"导入 Vosk 失败: {e}")
    VOSK_AVAILABLE = False
except Exception as e:
    logging.getLogger("Application").error(f"初始化 Vosk 失败: {e}")
    import traceback
    logging.getLogger("Application").error(traceback.format_exc())
    VOSK_AVAILABLE = False

from src.utils.config_manager import ConfigManager

# 配置日志
logger = logging.getLogger("Application")

vosk_path = os.path.dirname(vosk.__file__)
print(f"Vosk 路径: {vosk_path}")

class WakeWordDetector:
    """唤醒词检测类"""

    def __init__(self,
                 wake_words=None,
                 model_path=None,
                 sensitivity=0.5,
                 sample_rate=AudioConfig.SAMPLE_RATE,
                 buffer_size=AudioConfig.FRAME_SIZE):
        """
        初始化唤醒词检测器

        参数:
            wake_words: 唤醒词列表，默认包含常用唤醒词
            model_path: Vosk模型路径，默认使用项目根目录下的中文小模型
            sensitivity: 检测灵敏度 (0.0-1.0)
            sample_rate: 音频采样率
            buffer_size: 音频缓冲区大小
        """
        # 初始化基本属性
        self.on_detected_callbacks = []
        self.running = False
        self.detection_thread = None
        self.audio_stream = None
        
        # 初始化状态变量（始终创建，不管是否启用）
        self.paused = False
        self.audio = None
        self.stream = None
        self.external_stream = False
        self.stream_lock = threading.Lock()  # 添加流操作锁
        self.on_error = None  # 添加错误处理回调
        
        # 检查是否启用唤醒词功能
        config = ConfigManager.get_instance()
        if not config.get_config('USE_WAKE_WORD', False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return
            
        self.enabled = True
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.sensitivity = sensitivity

        # 设置默认唤醒词
        self.wake_words = wake_words or config.get_config('WAKE_WORDS', [
            "你好小明", "你好小智", "你好小天", "你好小美", "贾维斯", "傻妞",
            "嗨乐鑫", "小爱同学", "你好小智", "小美同学", "嗨小星",
            "喵喵同学", "嗨Joy", "嗨丽丽", "嗨琳琳", "嗨Telly",
            "嗨泰力", "嗨喵喵", "嗨小冰", "小冰"
        ])

        # 预先计算唤醒词的拼音
        self.wake_words_pinyin = [''.join(lazy_pinyin(word)) for word in self.wake_words]

        # 初始化模型
        try:
            if model_path is None:
                model_path_config = config.get_config('WAKE_WORD_MODEL_PATH', 'models/vosk-model-small-cn-0.22')
                
                # 对于打包环境
                if getattr(sys, 'frozen', False):
                    base_path = os.path.dirname(sys.executable) if not hasattr(sys, '_MEIPASS') else sys._MEIPASS
                    model_path = os.path.join(base_path, model_path_config)
                    logger.info(f"打包环境下使用模型路径: {model_path}")
                else:
                    # 开发环境
                    base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    model_path = os.path.join(base_path, model_path_config)
                    logger.info(f"开发环境下使用模型路径: {model_path}")

            # 检查模型路径
            if not os.path.exists(model_path):
                error_msg = f"模型路径不存在: {model_path}"
                logger.error(error_msg)
                self.enabled = False
                raise FileNotFoundError(error_msg)

            # 回调函数
            self.on_error = None  # 添加错误处理回调

            # 初始化模型
            logger.info(f"正在加载语音识别模型: {model_path}")
            # 设置 Vosk 日志级别为 -1 (SILENT)
            SetLogLevel(-1)
            self.model = Model(model_path=model_path)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)
            logger.info("模型加载完成")

            # 调试信息
            logger.info(f"已配置 {len(self.wake_words)} 个唤醒词")
            for i, word in enumerate(self.wake_words):
                logger.debug(f"唤醒词 {i + 1}: {word} (拼音: {self.wake_words_pinyin[i]})")

            # 共享的音频流和是否为外部流标志
            self.external_stream = False
            self.stream_lock = threading.Lock()  # 添加流操作锁
            
        except Exception as e:
            logger.error(f"初始化唤醒词检测器失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.enabled = False

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
                    with self.stream_lock:
                        if not self.stream:
                            if stream_error_time is None:
                                stream_error_time = time.time()
                                logger.error("音频流不可用，等待恢复")
                            elif time.time() - stream_error_time > 5.0:  # 5秒后尝试获取新流
                                if self.on_error:
                                    self.on_error("音频流长时间不可用，需要重新获取")
                                stream_error_time = None
                            time.sleep(0.5)
                            continue
                            
                        # 尝试检查流状态
                        try:
                            if not self.stream.is_active() and not self.external_stream:
                                self.stream.start_stream()
                        except Exception:
                            pass
                            
                        data = self.stream.read(self.buffer_size // 2, exception_on_overflow=False)
                        
                    # 重置流错误时间
                    stream_error_time = None
                    
                except OSError as e:
                    error_str = str(e)
                    if "Stream not open" in error_str or "Stream closed" in error_str or "Stream is stopped" in error_str:
                        error_count += 1
                        logger.warning(f"音频流问题 ({error_count}/{max_errors}): {e}")
                        time.sleep(0.5)
                        if error_count >= max_errors:
                            if self.on_error:
                                self.on_error(f"音频流多次出错: {e}")
                            error_count = 0  # 重置计数，允许继续尝试
                            time.sleep(1.0)  # 等待时间长一些
                        continue
                    else:
                        error_count += 1
                        logger.error(f"读取音频失败 ({error_count}/{max_errors}): {e}")
                        if error_count >= max_errors:
                            if self.on_error:
                                self.on_error(f"连续读取音频失败 {max_errors} 次: {e}")
                            error_count = 0  # 重置计数，允许继续尝试
                        time.sleep(0.5)
                        continue
                except Exception as e:
                    error_count += 1
                    logger.error(f"读取音频异常 ({error_count}/{max_errors}): {e}")
                    if error_count >= max_errors:
                        if self.on_error:
                            self.on_error(f"连续读取音频失败 {max_errors} 次: {e}")
                        error_count = 0  # 重置计数，允许继续尝试
                    time.sleep(0.5)
                    continue

                if len(data) == 0:
                    continue

                error_count = 0  # 重置错误计数

                # 处理音频数据
                is_final = self.recognizer.AcceptWaveform(data)
                
                # 处理部分结果，实现实时唤醒词检测
                partial_result = json.loads(self.recognizer.PartialResult())
                partial_text = partial_result.get('partial', '')
                if partial_text.strip():
                    detected, wake_word = self._check_wake_word(partial_text)
                    if detected:
                        logger.info(f"实时检测到唤醒词: '{wake_word}' (部分文本: {partial_text})")
                        # 触发回调
                        for callback in self.on_detected_callbacks:
                            try:
                                callback(wake_word, partial_text)
                            except Exception as e:
                                logger.error(f"执行唤醒词检测回调时出错: {e}")
                        # 重置识别器，准备下一轮检测
                        self.recognizer.Reset()
                        continue  # 跳过后续处理

                # 处理最终结果
                if is_final:
                    result = json.loads(self.recognizer.Result())
                    if "text" in result and result["text"].strip():
                        text = result["text"]
                        logger.debug(f"识别文本: {text}")

                        # 检查是否包含唤醒词
                        detected, wake_word = self._check_wake_word(text)
                        if detected:
                            logger.info(f"检测到唤醒词: '{wake_word}' (完整文本: {text})")

                            # 触发回调
                            for callback in self.on_detected_callbacks:
                                try:
                                    callback(wake_word, text)
                                except Exception as e:
                                    logger.error(f"执行唤醒词检测回调时出错: {e}")
                            # 重置识别器，准备下一轮检测
                            self.recognizer.Reset()

            except Exception as e:
                logger.error(f"唤醒词检测循环出错: {e}")
                if self.on_error:
                    self.on_error(str(e))
                time.sleep(0.5)  # 增加等待时间，减少CPU使用