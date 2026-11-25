"""唤醒词配置与 keywords 保存."""

from PySide6.QtCore import Slot

from src.audio_processing.keyword_converters import convert_wake_word
from src.i18n import t
from src.logging import get_logger

logger = get_logger()


class SettingsWakeWordMixin:
    # ========== 唤醒词预览与保存 ==========

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
            self._wake_word_preview = t("settings.wake_word.convert_failed", error=e)

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
            self.set_error(t("settings.wake_word.enter_prompt"))
            return False

        try:
            # 转换唤醒词
            keyword_line, lang, model_path = convert_wake_word(self._wake_word)

            # 更新配置
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD", self._wake_word)
            self._set_value("WAKE_WORD_OPTIONS.WAKE_WORD_LANG", lang)
            self._set_value("WAKE_WORD_OPTIONS.MODEL_PATH", model_path)

            from src.utils.keyword_writer import commit_with_keywords

            error = commit_with_keywords(
                self._config_manager,
                self._config,
                lang,
                keyword_line,
                commit=lambda: None if self.save() else self._error,
            )
            if error is not None:
                self.set_error(error)
                return False
            logger.info("唤醒词已保存: %s", self._wake_word)
            self.statusMessage.emit(t("settings.wake_word.saved", lang=lang.upper()))
            return True

        except Exception as e:
            logger.error(f"保存唤醒词失败: {e}", exc_info=True)
            self.set_error(t("settings.wake_word.save_failed", error=e))
            return False

