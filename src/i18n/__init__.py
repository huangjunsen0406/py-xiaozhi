"""多语言（i18n）公共入口：纯标准库实现，供 GUI / TUI / 终端共用."""

from src.i18n.manager import (
    DEFAULT_LOCALE,
    LANGUAGE_CHOICES,
    SUPPORTED_LOCALES,
    I18nManager,
    apply_language_from_config,
    detect_system_locale,
    get_i18n,
    get_locale,
    normalize_locale,
    off_locale_changed,
    on_locale_changed,
    set_language,
    t,
)

__all__ = [
    "DEFAULT_LOCALE",
    "LANGUAGE_CHOICES",
    "SUPPORTED_LOCALES",
    "I18nManager",
    "apply_language_from_config",
    "detect_system_locale",
    "get_i18n",
    "get_locale",
    "normalize_locale",
    "off_locale_changed",
    "on_locale_changed",
    "set_language",
    "t",
]
