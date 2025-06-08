import asyncio
import difflib
import json
import os
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Callable, Optional

from pypinyin import Style, lazy_pinyin
from vosk import KaldiRecognizer, Model, SetLogLevel

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """异步唤醒词检测器 - 完整实现"""

    def __init__(self):
        """初始化唤醒词检测器"""
        # 初始化基本属性
        self.audio_codec = None
        self.is_running_flag = False
        self.paused = False
        self.detection_task = None
        
        # 防重复触发机制
        self.last_detection_time = 0
        self.detection_cooldown = 3.0  # 3秒冷却时间
        
        # 回调函数
        self.on_detected_callback: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 配置检查
        config = ConfigManager.get_instance()
        if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            logger.info("唤醒词功能已禁用")
            self.enabled = False
            return

        # 基本参数初始化
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
            "WAKE_WORD_OPTIONS.SIMILARITY_THRESHOLD", 0.85
        )
        self.max_edit_distance = config.get_config(
            "WAKE_WORD_OPTIONS.MAX_EDIT_DISTANCE", 1
        )

        # 性能优化：缓存最近的识别结果
        self._recent_texts = []
        self._max_recent_cache = 10

        # 模型初始化
        self._init_model(config)

        # 验证配置
        self._validate_config()

    def _init_model(self, config):
        """初始化语音识别模型"""
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
        """获取模型路径"""
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

    def _build_wake_word_patterns(self):
        """构建唤醒词的拼音模式，包括多种变体"""
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
        """计算文本与唤醒词模式的相似度"""
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
                    similarity = max(similarity, 0.80)

            if similarity > max_similarity:
                max_similarity = similarity
                best_match_type = variant_type

        return max_similarity, best_match_type

    def _levenshtein_distance(self, s1, s2):
        """计算编辑距离"""
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
        """检查pattern是否为text的子序列"""
        i = 0
        for char in text:
            if i < len(pattern) and char == pattern[i]:
                i += 1
        return i == len(pattern)

    def on_detected(self, callback: Callable):
        """设置检测到唤醒词的回调函数"""
        self.on_detected_callback = callback

    async def start(self, audio_codec) -> bool:
        """启动唤醒词检测器"""
        if not self.enabled:
            logger.warning("唤醒词功能未启用")
            return False

        try:
            self.audio_codec = audio_codec
            self.is_running_flag = True
            self.paused = False
            
            # 启动检测任务
            self.detection_task = asyncio.create_task(self._detection_loop())
            
            logger.info("异步唤醒词检测器启动成功")
            return True
        except Exception as e:
            logger.error(f"启动异步唤醒词检测器失败: {e}")
            self.enabled = False
            return False

    async def _detection_loop(self):
        """检测循环"""
        error_count = 0
        MAX_ERRORS = 5
        
        while self.is_running_flag:
            try:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                if not self.audio_codec:
                    await asyncio.sleep(0.5)
                    continue

                # 从音频编解码器获取数据并处理
                await self._check_wake_word()
                
                # 短暂延迟避免过度占用CPU
                await asyncio.sleep(0.02)
                error_count = 0
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                error_count += 1
                logger.error(f"唤醒词检测循环错误({error_count}/{MAX_ERRORS}): {e}")
                if self.on_error:
                    await self._call_error_callback(e)
                
                if error_count >= MAX_ERRORS:
                    logger.critical("达到最大错误次数，停止检测")
                    break
                    
                await asyncio.sleep(1)  # 错误后延迟重试

    async def _check_wake_word(self):
        """检查唤醒词（异步实现）"""
        try:
            if not self.audio_codec:
                return

            # 优先使用专门的唤醒词缓冲区
            if hasattr(self.audio_codec, "_wake_word_buffer"):
                if self.audio_codec._wake_word_buffer.empty():
                    return
                try:
                    audio_data = self.audio_codec._wake_word_buffer.get_nowait()
                except Exception:
                    return
            # 后备选择：使用普通输入缓冲区
            elif hasattr(self.audio_codec, "_input_buffer"):
                if self.audio_codec._input_buffer.empty():
                    return
                try:
                    audio_data = self.audio_codec._input_buffer.get_nowait()
                except Exception:
                    return
            else:
                return

            # 转换为bytes格式
            if hasattr(audio_data, "tobytes"):
                data = audio_data.tobytes()
            elif hasattr(audio_data, "astype"):
                data = audio_data.astype("int16").tobytes()
            else:
                data = audio_data

            if not data:
                return

            # 处理音频数据
            await self._process_audio_data(data)

        except Exception as e:
            logger.debug(f"检查唤醒词时出错: {e}")

    async def _process_audio_data(self, data):
        """异步处理音频数据"""
        try:
            # 处理完整识别结果
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                if text := result.get("text", "").strip():
                    # 过滤过短的文本以减少误触发
                    if len(text) >= 3:
                        await self._check_wake_word_text(text)

            # 处理部分识别结果（降低频率）
            if hasattr(self, "_partial_check_counter"):
                self._partial_check_counter += 1
            else:
                self._partial_check_counter = 0

            # 每3次才检查一次部分结果
            if self._partial_check_counter % 3 == 0:
                partial = (
                    json.loads(self.recognizer.PartialResult())
                    .get("partial", "")
                    .strip()
                )
                if partial and len(partial) >= 3:
                    await self._check_wake_word_text(partial)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析错误: {e}")
        except Exception as e:
            logger.error(f"音频数据处理错误: {e}")

    async def _check_wake_word_text(self, text):
        """检查文本中的唤醒词"""
        if not text or not text.strip():
            return

        # 防重复触发检查
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
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
            self.last_detection_time = current_time
            logger.info(
                f"检测到唤醒词 '{best_match}' "
                f"(相似度: {best_similarity:.3f}, 匹配类型: {best_match_info})"
            )

            logger.debug(f"原始文本: '{text}', 拼音变体: {text_variants}")
            await self._trigger_callbacks(best_match, text)
            self.recognizer.Reset()
            # 清空缓存避免重复触发
            self._recent_texts.clear()

    async def _trigger_callbacks(self, wake_word, text):
        """触发回调函数"""
        if self.on_detected_callback:
            try:
                if asyncio.iscoroutinefunction(self.on_detected_callback):
                    await self.on_detected_callback(wake_word, text)
                else:
                    self.on_detected_callback(wake_word, text)
            except Exception as e:
                logger.error(f"唤醒词回调执行失败: {e}")

    async def _call_error_callback(self, error):
        """调用错误回调"""
        try:
            if self.on_error:
                if asyncio.iscoroutinefunction(self.on_error):
                    await self.on_error(error)
                else:
                    self.on_error(error)
        except Exception as e:
            logger.error(f"执行错误回调时失败: {e}")

    async def pause(self):
        """暂停检测"""
        self.paused = True
        
    async def resume(self):
        """恢复检测"""
        self.paused = False

    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.is_running_flag and not self.paused

    async def stop(self):
        """停止检测器"""
        self.is_running_flag = False
        
        if self.detection_task:
            self.detection_task.cancel()
            try:
                await self.detection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("异步唤醒词检测器已停止")

    def _validate_config(self):
        """验证配置参数"""
        if not self.enabled:
            return

        # 验证相似度阈值
        if not 0.1 <= self.similarity_threshold <= 1.0:
            logger.warning(
                f"相似度阈值 {self.similarity_threshold} 超出合理范围，重置为0.85"
            )
            self.similarity_threshold = 0.85

        # 验证编辑距离
        if self.max_edit_distance < 0 or self.max_edit_distance > 5:
            logger.warning(
                f"最大编辑距离 {self.max_edit_distance} 超出合理范围，重置为1"
            )
            self.max_edit_distance = 1

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
        """获取性能统计信息"""
        cache_info = self._get_text_pinyin_variants.cache_info()
        return {
            "enabled": self.enabled,
            "wake_words_count": (
                len(self.wake_words) if hasattr(self, 'wake_words') else 0
            ),
            "similarity_threshold": (
                self.similarity_threshold 
                if hasattr(self, 'similarity_threshold') else 0
            ),
            "max_edit_distance": (
                self.max_edit_distance 
                if hasattr(self, 'max_edit_distance') else 0
            ),
            "cache_hits": cache_info.hits,
            "cache_misses": cache_info.misses,
            "cache_size": cache_info.currsize,
            "recent_texts_count": len(self._recent_texts),
        }

    def clear_cache(self):
        """清空缓存"""
        self._get_text_pinyin_variants.cache_clear()
        self._recent_texts.clear()
        logger.info("缓存已清空")

    def __del__(self):
        """析构函数"""
        if hasattr(self, 'is_running_flag') and self.is_running_flag:
            asyncio.create_task(self.stop()) 