import difflib
import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

from pypinyin import Style, lazy_pinyin
from vosk import KaldiRecognizer, Model, SetLogLevel

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """唤醒词检测类."""

    def __init__(self):
        """初始化唤醒词检测器."""
        # 初始化基本属性
        self.audio_codec = None
        self.on_detected_callbacks = []
        self.running = False
        self.detection_thread = None
        self.paused = False
        self.stream = None
        self.external_stream = False
        self.stream_lock = threading.Lock()

        # 配置检查
        config = ConfigManager.get_instance()
        if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return

        # 基本参数初始化（直接从配置获取）
        self.enabled = True
        self.sample_rate = AudioConfig.INPUT_SAMPLE_RATE
        self.buffer_size = AudioConfig.INPUT_FRAME_SIZE
        self.sensitivity = config.get_config("WAKE_WORD_OPTIONS.SENSITIVITY", 0.5)

        # 唤醒词配置
        self.wake_words = config.get_config(
            "WAKE_WORD_OPTIONS.WAKE_WORDS",
            ["你好小明", "你好小智", "你好小天", "小爱同学", "贾维斯"],
        )

        # 预计算拼音变体以提升性能
        self.wake_word_patterns = self._build_wake_word_patterns()

        # 匹配参数
        self.similarity_threshold = config.get_config(
            "WAKE_WORD_OPTIONS.SIMILARITY_THRESHOLD", 0.8
        )
        self.max_edit_distance = config.get_config(
            "WAKE_WORD_OPTIONS.MAX_EDIT_DISTANCE", 2
        )

        # 性能优化：缓存最近的识别结果
        self._recent_texts = []
        self._max_recent_cache = 10

        # 模型初始化
        self._init_model(config)

        # 验证配置
        self._validate_config()

    def _init_model(self, config):
        """初始化语音识别模型."""
        try:
            model_path = self._get_model_path(config)
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型路径不存在: {model_path}")

            logger.info(f"加载语音识别模型: {model_path}")
            SetLogLevel(-1)
            self.model = Model(model_path=model_path)
            self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
            self.recognizer.SetWords(True)
            logger.info(f"模型加载完成，已配置 {len(self.wake_words)} 个唤醒词")

        except Exception as e:
            logger.error(f"初始化失败: {e}", exc_info=True)
            self.enabled = False

    def _get_model_path(self, config):
        """获取模型路径."""
        from src.utils.resource_finder import resource_finder

        model_name = config.get_config(
            "WAKE_WORD_OPTIONS.MODEL_PATH", "vosk-model-small-cn-0.22"
        )

        model_path = Path(model_name)

        # 绝对路径直接返回
        if model_path.is_absolute() and model_path.exists():
            return str(model_path)

        # 标准化为models子目录路径
        if len(model_path.parts) == 1:
            model_path = Path("models") / model_path

        # 使用resource_finder查找
        model_dir_path = resource_finder.find_directory(model_path)
        if model_dir_path:
            return str(model_dir_path)

        # 在models目录中查找
        models_dir = resource_finder.find_models_dir()
        if models_dir:
            model_name_only = (
                model_path.name if len(model_path.parts) > 1 else model_path
            )
            direct_model_path = models_dir / model_name_only
            if direct_model_path.exists():
                return str(direct_model_path)

            # 遍历子目录查找
            for item in models_dir.iterdir():
                if item.is_dir() and item.name == model_name_only:
                    return str(item)

        # 使用默认路径
        project_root = resource_finder.get_project_root()
        default_path = project_root / model_path
        logger.warning(f"未找到模型，将使用默认路径: {default_path}")
        return str(default_path)

    def start(self, audio_codec_or_stream=None):
        """启动检测."""
        if not self.enabled:
            logger.warning("唤醒词功能未启用")
            return False

        # 设置音频源
        if audio_codec_or_stream:
            if hasattr(audio_codec_or_stream, "read") and hasattr(
                audio_codec_or_stream, "is_active"
            ):
                # 外部流
                self.stream = audio_codec_or_stream
                self.external_stream = True
                return self._start_detection_thread("ExternalStream")
            else:
                # AudioCodec对象
                self.audio_codec = audio_codec_or_stream
                return self._start_with_audio_codec()

        if self.audio_codec:
            return self._start_with_audio_codec()

        logger.error("需要AudioCodec实例或外部音频流")
        return False

    def _start_with_audio_codec(self):
        """使用AudioCodec启动."""
        if not self.audio_codec or not hasattr(self.audio_codec, "input_stream"):
            logger.error("AudioCodec无效或输入流不可用")
            return False

        self.stream = self.audio_codec.input_stream
        self.external_stream = True
        return self._start_detection_thread("AudioCodec")

    def _start_detection_thread(self, mode_name):
        """启动检测线程."""
        try:
            self.running = True
            self.paused = False
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True,
                name=f"WakeWordDetector-{mode_name}",
            )
            self.detection_thread.start()
            logger.info(f"唤醒词检测已启动（{mode_name}模式）")
            return True
        except Exception as e:
            logger.error(f"启动失败: {e}")
            return False

    def _detection_loop(self):
        """统一的检测循环."""
        error_count = 0
        MAX_ERRORS = 5

        while self.running:
            try:
                if self.paused:
                    time.sleep(0.1)
                    continue

                # 获取音频流
                stream = self._get_active_stream()
                if not stream:
                    time.sleep(0.5)
                    continue

                # 读取音频数据
                data = self._read_audio_data(stream)
                if data:
                    self._process_audio_data(data)
                    error_count = 0

            except Exception as e:
                error_count += 1
                logger.error(f"检测循环错误({error_count}/{MAX_ERRORS}): {e}")

                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    self.stop()
                    break
                time.sleep(0.5)

    def _get_active_stream(self):
        """获取活跃的音频流."""
        if self.audio_codec:
            if not hasattr(self.audio_codec, "input_stream"):
                return None
            stream = self.audio_codec.input_stream
            if stream and stream.is_active():
                return stream
            # 尝试重新激活
            if stream and hasattr(stream, "start_stream"):
                try:
                    stream.start_stream()
                    return stream if stream.is_active() else None
                except Exception:
                    pass
            return None

        return self.stream if self.stream and self.stream.is_active() else None

    def _read_audio_data(self, stream):
        """读取音频数据."""
        try:
            with self.stream_lock:
                # 检查可用数据
                if hasattr(stream, "get_read_available"):
                    if stream.get_read_available() < self.buffer_size:
                        return None
                return stream.read(self.buffer_size, exception_on_overflow=False)
        except OSError as e:
            # 处理关键错误
            error_msg = str(e)
            if (
                any(
                    msg in error_msg
                    for msg in ["Input overflowed", "Device unavailable"]
                )
                and self.audio_codec
            ):
                try:
                    self.audio_codec._reinitialize_stream(is_input=True)
                except Exception:
                    pass
            return None
        except Exception:
            return None

    def _process_audio_data(self, data):
        """优化的音频数据处理."""
        try:
            # 处理完整识别结果
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                if text := result.get("text", "").strip():
                    # 过滤过短的文本以减少误触发
                    if len(text) >= 2:
                        self._check_wake_word(text)

            # 处理部分识别结果（降低频率以提升性能）
            if hasattr(self, "_partial_check_counter"):
                self._partial_check_counter += 1
            else:
                self._partial_check_counter = 0

            # 每3次才检查一次部分结果，减少计算负担
            if self._partial_check_counter % 3 == 0:
                partial = (
                    json.loads(self.recognizer.PartialResult())
                    .get("partial", "")
                    .strip()
                )
                if partial and len(partial) >= 2:
                    self._check_wake_word(partial)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"音频数据处理错误: {e}")

    def _build_wake_word_patterns(self):
        """构建唤醒词的拼音模式，包括多种变体."""
        patterns = {}
        for word in self.wake_words:
            # 标准拼音（无音调）
            standard_pinyin = "".join(lazy_pinyin(word, style=Style.NORMAL))

            # 首字母拼音
            initials_pinyin = "".join(lazy_pinyin(word, style=Style.FIRST_LETTER))

            # 音调拼音
            tone_pinyin = "".join(lazy_pinyin(word, style=Style.TONE))

            # 韵母拼音
            finals_pinyin = "".join(lazy_pinyin(word, style=Style.FINALS))

            patterns[word] = {
                "standard": standard_pinyin.lower(),
                "initials": initials_pinyin.lower(),
                "tone": tone_pinyin.lower(),
                "finals": finals_pinyin.lower(),
                "original": word,
                "length": len(standard_pinyin),
            }

        return patterns

    @lru_cache(maxsize=128)
    def _get_text_pinyin_variants(self, text):
        """获取文本的拼音变体（带缓存）"""
        if not text or not text.strip():
            return {}

        # 清理文本
        cleaned_text = re.sub(r"[^\u4e00-\u9fff\w]", "", text)
        if not cleaned_text:
            return {}

        return {
            "standard": "".join(lazy_pinyin(cleaned_text, style=Style.NORMAL)).lower(),
            "initials": "".join(
                lazy_pinyin(cleaned_text, style=Style.FIRST_LETTER)
            ).lower(),
            "tone": "".join(lazy_pinyin(cleaned_text, style=Style.TONE)).lower(),
            "finals": "".join(lazy_pinyin(cleaned_text, style=Style.FINALS)).lower(),
        }

    def _calculate_similarity(self, text_variants, pattern):
        """计算文本与唤醒词模式的相似度."""
        max_similarity = 0.0
        best_match_type = None

        # 检查各种拼音变体的匹配
        for variant_type in ["standard", "tone", "initials", "finals"]:
            text_variant = text_variants.get(variant_type, "")
            pattern_variant = pattern.get(variant_type, "")

            if not text_variant or not pattern_variant:
                continue

            # 1. 精确匹配（最高优先级）
            if pattern_variant in text_variant:
                return 1.0, f"exact_{variant_type}"

            # 2. 序列匹配器相似度
            similarity = difflib.SequenceMatcher(
                None, text_variant, pattern_variant
            ).ratio()

            # 3. 编辑距离匹配（适用于短文本）
            if len(pattern_variant) <= 10:
                edit_distance = self._levenshtein_distance(
                    text_variant, pattern_variant
                )
                max_allowed_distance = min(
                    self.max_edit_distance, len(pattern_variant) // 2
                )
                if edit_distance <= max_allowed_distance:
                    edit_similarity = 1.0 - (edit_distance / len(pattern_variant))
                    similarity = max(similarity, edit_similarity)

            # 4. 子序列匹配（对于首字母缩写）
            if variant_type == "initials" and len(pattern_variant) >= 2:
                if self._is_subsequence(pattern_variant, text_variant):
                    similarity = max(similarity, 0.85)

            if similarity > max_similarity:
                max_similarity = similarity
                best_match_type = variant_type

        return max_similarity, best_match_type

    def _levenshtein_distance(self, s1, s2):
        """计算编辑距离."""
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _is_subsequence(self, pattern, text):
        """检查pattern是否为text的子序列."""
        i = 0
        for char in text:
            if i < len(pattern) and char == pattern[i]:
                i += 1
        return i == len(pattern)

    def _check_wake_word(self, text):
        """优化的唤醒词检查."""
        if not text or not text.strip():
            return

        # 避免重复处理相同文本
        if text in self._recent_texts:
            return

        # 更新最近文本缓存
        self._recent_texts.append(text)
        if len(self._recent_texts) > self._max_recent_cache:
            self._recent_texts.pop(0)

        # 获取文本的拼音变体
        text_variants = self._get_text_pinyin_variants(text)
        if not text_variants or not any(text_variants.values()):
            return

        best_match = None
        best_similarity = 0.0
        best_match_info = None

        # 检查每个唤醒词模式
        for wake_word, pattern in self.wake_word_patterns.items():
            similarity, match_type = self._calculate_similarity(text_variants, pattern)

            if similarity > best_similarity and similarity >= self.similarity_threshold:
                best_similarity = similarity
                best_match = wake_word
                best_match_info = match_type

        # 触发检测
        if best_match:
            logger.info(
                f"检测到唤醒词 '{best_match}' "
                f"(相似度: {best_similarity:.3f}, 匹配类型: {best_match_info})"
            )

            logger.debug(f"原始文本: '{text}', 拼音变体: {text_variants}")
            self._trigger_callbacks(best_match, text)
            self.recognizer.Reset()
            # 清空缓存避免重复触发
            self._recent_texts.clear()

    def stop(self):
        """停止检测."""
        if self.running:
            self.running = False
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=1.0)
            self.stream = None
            self.external_stream = False
            logger.info("唤醒词检测已停止")

    def is_running(self):
        """检查是否正在运行."""
        return self.running and not self.paused

    def update_stream(self, new_stream):
        """更新音频流."""
        if not self.running:
            return False
        with self.stream_lock:
            self.stream = new_stream
            self.external_stream = True
        return True

    def pause(self):
        """暂停检测."""
        if self.running and not self.paused:
            self.paused = True

    def resume(self):
        """恢复检测."""
        if self.running and self.paused:
            self.paused = False

    def on_detected(self, callback):
        """注册回调."""
        self.on_detected_callbacks.append(callback)

    def _trigger_callbacks(self, wake_word, text):
        """触发回调."""
        for cb in self.on_detected_callbacks:
            try:
                cb(wake_word, text)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")

    def _validate_config(self):
        """验证配置参数."""
        if not self.enabled:
            return

        # 验证相似度阈值
        if not 0.1 <= self.similarity_threshold <= 1.0:
            logger.warning(
                f"相似度阈值 {self.similarity_threshold} 超出合理范围，重置为0.8"
            )
            self.similarity_threshold = 0.8

        # 验证编辑距离
        if self.max_edit_distance < 0 or self.max_edit_distance > 5:
            logger.warning(
                f"最大编辑距离 {self.max_edit_distance} 超出合理范围，重置为2"
            )
            self.max_edit_distance = 2

        # 验证唤醒词
        if not self.wake_words:
            logger.error("未配置唤醒词")
            self.enabled = False
            return

        # 检查唤醒词长度
        for word in self.wake_words:
            if len(word) < 2:
                logger.warning(f"唤醒词 '{word}' 过短，可能导致误触发")
            elif len(word) > 10:
                logger.warning(f"唤醒词 '{word}' 过长，可能影响识别准确度")

        logger.info(
            f"配置验证完成 - 阈值: {self.similarity_threshold}, 编辑距离: {self.max_edit_distance}"
        )

    def get_performance_stats(self):
        """获取性能统计信息."""
        cache_info = self._get_text_pinyin_variants.cache_info()
        return {
            "enabled": self.enabled,
            "wake_words_count": len(self.wake_words),
            "similarity_threshold": self.similarity_threshold,
            "max_edit_distance": self.max_edit_distance,
            "cache_hits": cache_info.hits,
            "cache_misses": cache_info.misses,
            "cache_size": cache_info.currsize,
            "recent_texts_count": len(self._recent_texts),
        }

    def clear_cache(self):
        """清空缓存."""
        self._get_text_pinyin_variants.cache_clear()
        self._recent_texts.clear()
        logger.info("缓存已清空")

    def update_config(self, **kwargs):
        """动态更新配置."""
        updated = False

        if "similarity_threshold" in kwargs:
            new_threshold = kwargs["similarity_threshold"]
            if 0.1 <= new_threshold <= 1.0:
                self.similarity_threshold = new_threshold
                updated = True
                logger.info(f"相似度阈值更新为: {new_threshold}")
            else:
                logger.warning(f"无效的相似度阈值: {new_threshold}")

        if "max_edit_distance" in kwargs:
            new_distance = kwargs["max_edit_distance"]
            if 0 <= new_distance <= 5:
                self.max_edit_distance = new_distance
                updated = True
                logger.info(f"最大编辑距离更新为: {new_distance}")
            else:
                logger.warning(f"无效的编辑距离: {new_distance}")

        if updated:
            # 清空缓存以应用新配置
            self.clear_cache()

        return updated

    def __del__(self):
        self.stop()
