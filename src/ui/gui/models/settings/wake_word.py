"""唤醒词配置与 keywords 保存."""

from PySide6.QtCore import Slot

from src.audio_processing.keyword_converters import convert_wake_word
from src.logging import get_logger

logger = get_logger()


class SettingsWakeWordMixin:
    # ========== 唤醒词设置 ==========

    def _get_wakeWordEnabled(self) -> bool:
        return self._get_value("WAKE_WORD_OPTIONS.USE_WAKE_WORD", False)

    def _set_wakeWordEnabled(self, value: bool):
        self._set_value("WAKE_WORD_OPTIONS.USE_WAKE_WORD", value)

    def _get_modelPath(self) -> str:
        return self._get_value("WAKE_WORD_OPTIONS.MODEL_PATH", "models")

    def _set_modelPath(self, value: str):
        self._set_value("WAKE_WORD_OPTIONS.MODEL_PATH", value)

    def _get_numThreads(self) -> int:
        return self._get_value("WAKE_WORD_OPTIONS.NUM_THREADS", 4)

    def _set_numThreads(self, value: int):
        self._set_value("WAKE_WORD_OPTIONS.NUM_THREADS", value)

    def _get_keywordsScore(self) -> float:
        return self._get_value("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", 1.8)

    def _set_keywordsScore(self, value: float):
        self._set_value("WAKE_WORD_OPTIONS.KEYWORDS_SCORE", value)

    def _get_keywordsThreshold(self) -> float:
        return self._get_value("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", 0.2)

    def _set_keywordsThreshold(self, value: float):
        self._set_value("WAKE_WORD_OPTIONS.KEYWORDS_THRESHOLD", value)

    # 唤醒词文本
    def _load_wake_word(self, update_preview: bool = True):
        """从配置加载唤醒词.

        Args:
            update_preview: 是否立即转换拼音预览（转换可能触发额外 import）
        """
        self._wake_word = self._get_value("WAKE_WORD_OPTIONS.WAKE_WORD", "")
        self._wake_word_lang = self._get_value("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", "zh")
        if update_preview:
            self._update_wake_word_preview()
        else:
            self._wake_word_preview = ""

    def _update_wake_word_preview(self):
        """更新唤醒词预览."""
        if not self._wake_word:
            self._wake_word_preview = ""
            return

        try:
            keyword_line, lang, _ = convert_wake_word(self._wake_word)
            self._wake_word_preview = keyword_line
            self._wake_word_lang = lang
        except Exception as e:
            logger.error(f"转换唤醒词失败: {e}", exc_info=True)
            self._wake_word_preview = f"转换失败: {e}"

    def _get_wakeWord(self) -> str:
        return self._wake_word

    def _set_wakeWord(self, value: str):
        if self._wake_word != value:
            self._wake_word = value
            self._update_wake_word_preview()
            self.wakeWordChanged.emit()

    def _get_wakeWordLang(self) -> str:
        return self._wake_word_lang

    def _get_wakeWordPreview(self) -> str:
        return self._wake_word_preview

    @Slot(result=bool)
    def saveWakeWord(self) -> bool:
        """保存唤醒词并生成 keywords.txt.

        Returns:
            是否保存成功
        """
        if not self._wake_word:
            self.statusMessage.emit("请输入唤醒词")
            return False

        try:
            # 转换唤醒词
            keyword_line, lang, model_path = convert_wake_word(self._wake_word)

            # 更新配置
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD", self._wake_word)
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", lang)
            self._set_value("WAKE_WORD_OPTIONS.MODEL_PATH", model_path)

            # 写入 keywords.txt 到用户数据目录
            from src.utils.resource_finder import get_keywords_dir, get_user_data_dir

            keywords_dir = get_keywords_dir()
            keywords_dir.mkdir(parents=True, exist_ok=True)
            keywords_path = keywords_dir / f"{lang}_keywords.txt"

            with open(keywords_path, "w", encoding="utf-8") as f:
                f.write(keyword_line + "\n")

            logger.info(f"唤醒词已保存: {self._wake_word} -> {keywords_path}")
            self.statusMessage.emit(f"唤醒词已保存 ({lang.upper()})")

            # 保存到文件
            self.save()
            return True

        except Exception as e:
            logger.error(f"保存唤醒词失败: {e}", exc_info=True)
            self.statusMessage.emit(f"保存失败: {e}")
            return False

