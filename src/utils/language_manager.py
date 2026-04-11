"""
Language Manager - Handles translator loading and runtime language switching.
"""

import os
from typing import List, Optional

from PyQt5.QtCore import QCoreApplication, QLocale, QTranslator

from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger
from src.utils.resource_finder import resource_finder

logger = get_logger(__name__)


class LanguageManager:
    """Manages runtime language switching with Qt translator support."""

    AVAILABLE_LANGUAGES = ["zh_CN", "en_US", "ru_RU"]
    FALLBACK_CHAIN = ["en_US", "zh_CN"]
    CONFIG_KEY = "SYSTEM_OPTIONS.LANGUAGE"
    TRANSLATION_PREFIX = "xiaozhi_"
    TRANSLATION_DIR = "i18n/translations/"

    _instance: Optional["LanguageManager"] = None
    _current_translator: Optional[QTranslator] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config_manager = ConfigManager.get_instance()
        self._current_language: Optional[str] = None
        self._load_saved_language()

    def _load_saved_language(self) -> None:
        """Load the saved language preference from ConfigManager."""
        saved_lang = self._config_manager.get_config(self.CONFIG_KEY)
        if saved_lang and saved_lang in self.AVAILABLE_LANGUAGES:
            self._current_language = saved_lang
            logger.debug(f"Loaded saved language preference: {saved_lang}")
            # Load and install the translation file
            self.set_language(saved_lang)

    def _get_translation_dir(self) -> str:
        """Get the translation directory path."""
        translations_path = resource_finder.find_directory(self.TRANSLATION_DIR)
        if translations_path:
            return str(translations_path)

        project_root = resource_finder.get_project_root()
        return str(project_root / self.TRANSLATION_DIR)

    def _get_qm_path(self, lang_code: str) -> str:
        """Get the full path to a .qm file for the given language code."""
        translation_dir = self._get_translation_dir()
        filename = f"{self.TRANSLATION_PREFIX}{lang_code}.qm"
        return os.path.join(translation_dir, filename)

    def set_language(self, lang_code: str) -> bool:
        """
        Set the application language.

        Args:
            lang_code: Language code (e.g., "zh_CN", "en_US", "ru_RU")

        Returns:
            bool: True if language was set successfully, False otherwise
        """
        if lang_code not in self.AVAILABLE_LANGUAGES:
            logger.warning(f"Unsupported language code: {lang_code}")
            return False

        fallback_chain = [lang_code] + self.FALLBACK_CHAIN

        seen = set()
        unique_chain = []
        for lang in fallback_chain:
            if lang not in seen:
                seen.add(lang)
                unique_chain.append(lang)

        translator = None
        loaded_lang = None

        for lang in unique_chain:
            qm_path = self._get_qm_path(lang)
            logger.debug(f"Trying to load translation from: {qm_path}")

            if os.path.exists(qm_path):
                temp_translator = QTranslator()
                if temp_translator.load(qm_path):
                    translator = temp_translator
                    loaded_lang = lang
                    logger.info(f"Loaded translation file: {qm_path}")
                    break
                del temp_translator
            else:
                logger.debug(f"Translation file not found: {qm_path}")

        if translator is None:
            logger.warning(f"Could not load any translation file for {lang_code}")
            return False

        app = QCoreApplication.instance()
        if app is None:
            logger.error("QCoreApplication instance not available")
            return False

        if self._current_translator is not None:
            app.removeTranslator(self._current_translator)
            logger.debug("Removed old translator")

        app.installTranslator(translator)
        logger.info(f"Installed translator for language: {loaded_lang}")

        success = self._config_manager.update_config(self.CONFIG_KEY, lang_code)
        if success:
            self._current_language = lang_code
            logger.info(f"Language preference saved: {lang_code}")
        else:
            logger.warning(f"Failed to save language preference: {lang_code}")

        self._current_translator = translator

        return True

    def get_language(self) -> str:
        """
        Get the current language code.

        Returns:
            str: Current language code, or system default if not set
        """
        if self._current_language:
            return self._current_language

        system_lang = QLocale.system().name()
        logger.debug(
            f"No saved language preference, using system default: {system_lang}"
        )
        return system_lang

    def get_available_languages(self) -> List[str]:
        """
        Get list of available language codes.

        Returns:
            list: List of available language codes
        """
        return self.AVAILABLE_LANGUAGES.copy()

    @classmethod
    def get_instance(cls) -> "LanguageManager":
        """
        Get the LanguageManager singleton instance.

        Returns:
            LanguageManager: The singleton instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
