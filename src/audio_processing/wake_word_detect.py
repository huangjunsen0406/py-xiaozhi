import asyncio
import json
import os
import time
from pathlib import Path
from typing import Callable, Optional

from pypinyin import Style, lazy_pinyin
from vosk import KaldiRecognizer, Model, SetLogLevel

from src.constants.constants import AudioConfig
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """唤醒词检测器 - 持续监听模式"""

    def __init__(self):
        self.audio_codec = None
        self.is_running_flag = False
        self.detection_task = None
        self.last_detection_time = 0
        self.detection_cooldown = 2.0
        self.on_detected_callback: Optional[Callable] = None
        self.on_error: Optional[Callable] = None

        # 配置检查 - 如果禁用就直接抛出异常
        config = ConfigManager.get_instance()
        if not config.get_config("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False):
            raise RuntimeError("唤醒词功能已禁用")

        self.sample_rate = AudioConfig.INPUT_SAMPLE_RATE

        # 唤醒词配置
        self.wake_words = config.get_config(
            "WAKE_WORD_OPTIONS.WAKE_WORDS",
            ["你好小明", "你好小智", "你好小天", "小爱同学", "贾维斯"],
        )

        # 预计算拼音
        self.wake_word_pinyins = {
            word: "".join(lazy_pinyin(word, style=Style.NORMAL)).lower()
            for word in self.wake_words
        }

        self.similarity_threshold = config.get_config(
            "WAKE_WORD_OPTIONS.SIMILARITY_THRESHOLD", 0.8
        )

        # 初始化模型
        self._init_model(config)

    def _init_model(self, config):
        """
        初始化语音识别模型.
        """
        model_path = self._get_model_path(config)
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型路径不存在: {model_path}")

        logger.info(f"加载语音识别模型: {model_path}")
        SetLogLevel(-1)
        self.model = Model(model_path=model_path)
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True)
        logger.info(f"模型加载完成，已配置 {len(self.wake_words)} 个唤醒词")

    def _get_model_path(self, config):
        """
        获取模型路径.
        """
        from src.utils.resource_finder import resource_finder

        model_name = config.get_config(
            "WAKE_WORD_OPTIONS.MODEL_PATH", "vosk-model-small-cn-0.22"
        )

        model_path = Path(model_name)

        # 如果是绝对路径，直接返回
        if model_path.is_absolute():
            return str(model_path)

        # 如果只是文件名，添加models前缀
        if len(model_path.parts) == 1:
            search_path = Path("models") / model_name
        else:
            search_path = model_path

        # 使用resource_finder查找，未找到返回默认路径
        found_path = resource_finder.find_directory(search_path)
        return (
            str(found_path)
            if found_path
            else str(resource_finder.get_project_root() / search_path)
        )

    def _calculate_similarity(self, text1, text2):
        """
        计算相似度.
        """
        text1, text2 = text1.lower(), text2.lower()

        # 精确匹配
        if text2 in text1:
            return 1.0

        # 字符重叠度
        set1, set2 = set(text1), set(text2)
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def on_detected(self, callback: Callable):
        """
        设置检测回调.
        """
        self.on_detected_callback = callback

    async def start(self, audio_codec) -> bool:
        """
        启动检测器.
        """
        self.audio_codec = audio_codec
        self.is_running_flag = True
        self.detection_task = asyncio.create_task(self._detection_loop())
        logger.info("唤醒词检测器启动成功")
        return True

    async def _detection_loop(self):
        """
        主检测循环.
        """
        while self.is_running_flag:
            try:
                if not self.audio_codec:
                    await asyncio.sleep(0.1)
                    continue

                await self._process_audio()
                await asyncio.sleep(0.02)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"检测循环错误: {e}")
                if self.on_error and self.is_running_flag:
                    await self._call_callback(self.on_error, e)
                await asyncio.sleep(0.5)

    async def _process_audio(self):
        """
        处理音频数据.
        """
        try:
            # 使用AudioCodec的公开接口获取音频数据
            if not self.audio_codec:
                return

            # 获取原始音频数据用于唤醒词检测
            data = await self.audio_codec.get_raw_audio_for_detection()
            if not data:
                return

            # 语音识别
            if self.recognizer.AcceptWaveform(data):
                result = json.loads(self.recognizer.Result())
                if text := result.get("text", "").strip():
                    if len(text) >= 3:
                        await self._check_wake_word(text)

        except Exception as e:
            logger.debug(f"音频处理错误: {e}")

    async def _check_wake_word(self, text):
        """
        检查唤醒词.
        """
        # 防重复触发
        current_time = time.time()
        if current_time - self.last_detection_time < self.detection_cooldown:
            return

        # 转换拼音
        text_pinyin = "".join(lazy_pinyin(text, style=Style.NORMAL)).lower()

        # 寻找最佳匹配
        best_match = None
        best_similarity = 0.0

        for wake_word, wake_word_pinyin in self.wake_word_pinyins.items():
            # 原文匹配
            similarity = self._calculate_similarity(text, wake_word)
            if similarity >= self.similarity_threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = wake_word

            # 拼音匹配
            pinyin_similarity = self._calculate_similarity(
                text_pinyin, wake_word_pinyin
            )
            if (
                pinyin_similarity >= self.similarity_threshold
                and pinyin_similarity > best_similarity
            ):
                best_similarity = pinyin_similarity
                best_match = wake_word

        # 触发检测
        if best_match:
            self.last_detection_time = current_time
            logger.info(f"检测到唤醒词 '{best_match}' (相似度: {best_similarity:.3f})")
            await self._call_callback(self.on_detected_callback, best_match, text)
            self.recognizer.Reset()

    async def _call_callback(self, callback, *args):
        """
        调用回调函数.
        """
        if not callback:
            return

        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(*args)
            else:
                callback(*args)
        except Exception as e:
            logger.error(f"回调执行失败: {e}")

    async def stop(self):
        """
        停止检测器.
        """
        self.is_running_flag = False

        if self.detection_task:
            self.detection_task.cancel()
            try:
                await self.detection_task
            except asyncio.CancelledError:
                pass

        logger.info("唤醒词检测器已停止")
