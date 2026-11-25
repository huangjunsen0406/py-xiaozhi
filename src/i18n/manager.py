"""纯标准库多语言管理器：加载 JSON 语言包、解析系统语言并支持热切换广播."""

from __future__ import annotations

import json
import locale
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from src.logging import get_logger

logger = get_logger()

SUPPORTED_LOCALES: tuple[str, ...] = ("zh_CN", "en_US", "vi_VN")
LANGUAGE_CHOICES: tuple[str, ...] = ("auto", *SUPPORTED_LOCALES)
DEFAULT_LOCALE: str = "zh_CN"

NATIVE_LOCALE_NAMES: dict[str, str] = {
    "zh_CN": "简体中文",
    "en_US": "English",
    "vi_VN": "Tiếng Việt",
}

_LOCALES_DIR = Path(__file__).resolve().parent / "locales"


def normalize_locale(raw: str | None) -> str | None:
    """将任意 locale 写法归一到受支持的代码，未知或 auto 返回 None."""
    if not raw or not isinstance(raw, str):
        return None
    cleaned = raw.strip()
    if not cleaned:
        return None
    low = cleaned.lower().replace("-", "_")
    if low in {"auto", "c", "posix", "default"}:
        return None
    # 去掉编码后缀，如 zh_CN.UTF-8 / vi_VN.UTF-8
    low = low.split(".", 1)[0].split("@", 1)[0]
    if low.startswith("zh") or "chinese" in low:
        return "zh_CN"
    if low.startswith("vi") or "vietnamese" in low:
        return "vi_VN"
    if low.startswith("en") or "english" in low:
        return "en_US"
    return None


def detect_system_locale() -> str:
    """按环境变量与系统 locale 推断默认语言；非中/越语环境默认英文."""
    # 1. 显式环境变量优先
    env_lang = os.environ.get("XIAOZHI_LANG")
    if env_lang:
        if normalized := normalize_locale(env_lang):
            return normalized

    # 2. POSIX 环境变量（macOS / Linux）
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(var)
        if not val:
            continue
        low = val.strip().lower().split(".", 1)[0]
        if low in {"", "c", "posix"}:
            continue
        if normalized := normalize_locale(val):
            return normalized
        return "en_US"

    # 3. Python locale（Windows / macOS / Linux）
    try:
        sys_loc = locale.getlocale()[0]
    except Exception:
        sys_loc = None
    if sys_loc:
        if normalized := normalize_locale(sys_loc):
            return normalized
        low = sys_loc.strip().lower()
        if low not in {"c", "posix"}:
            return "en_US"

    return DEFAULT_LOCALE


def _load_locale_file(code: str) -> dict[str, str]:
    path = _LOCALES_DIR / f"{code}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:
        logger.warning("加载语言包失败 %s: %s", path, exc)
    return {}


class I18nManager:
    """进程内多语言管理器（线程安全，支持监听热切换）."""

    def __init__(self, initial_locale: str = DEFAULT_LOCALE) -> None:
        self._lock = threading.RLock()
        self._locale = normalize_locale(initial_locale) or DEFAULT_LOCALE
        self._setting = self._locale
        self._catalogs: dict[str, dict[str, str]] = {}
        self._listeners: list[Callable[[str], None]] = []

    def _get_catalog(self, code: str) -> dict[str, str]:
        with self._lock:
            cat = self._catalogs.get(code)
            if cat is None:
                cat = _load_locale_file(code)
                self._catalogs[code] = cat
            return cat

    @property
    def locale(self) -> str:
        with self._lock:
            return self._locale

    @property
    def setting(self) -> str:
        with self._lock:
            return self._setting

    def set_language(self, lang: str | None) -> str:
        """设置语言（支持 'auto' / 'zh_CN' / 'en_US' / 'vi_VN'），变化时广播通知."""
        raw = (lang or "auto").strip()
        if raw.lower() == "auto":
            resolved = detect_system_locale()
            setting = "auto"
        else:
            resolved = normalize_locale(raw) or DEFAULT_LOCALE
            setting = resolved

        listeners: list[Callable[[str], None]] = []
        changed = False
        with self._lock:
            self._setting = setting
            if self._locale != resolved:
                self._locale = resolved
                changed = True
                listeners = list(self._listeners)

        if changed:
            logger.info("界面语言已切换为: %s (setting=%s)", resolved, setting)
            for cb in listeners:
                try:
                    cb(resolved)
                except Exception as exc:
                    logger.debug("i18n 回调执行失败: %s", exc)
        return resolved

    def apply_from_config(self, config: Any) -> str:
        """根据环境变量 XIAOZHI_LANG 或配置 SYSTEM_OPTIONS.LANGUAGE 应用语言."""
        env_lang = os.environ.get("XIAOZHI_LANG")
        if env_lang and env_lang.strip():
            return self.set_language(env_lang)
        get_cfg = getattr(config, "get_config", None)
        if not callable(get_cfg):
            return self.locale
        configured = get_cfg("SYSTEM_OPTIONS.LANGUAGE", "auto")
        return self.set_language(str(configured or "auto"))

    def on_change(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def off_change(self, callback: Callable[[str], None]) -> None:
        with self._lock:
            self._listeners = [cb for cb in self._listeners if cb is not callback]

    def merged_strings(self, locale_code: str | None = None) -> dict[str, str]:
        """返回已按回退链合并好的完整译文字典（zh_CN <- en_US <- target）."""
        target = normalize_locale(locale_code) or self.locale
        merged: dict[str, str] = {}
        merged.update(self._get_catalog(DEFAULT_LOCALE))
        if target != DEFAULT_LOCALE:
            if target != "en_US":
                merged.update(self._get_catalog("en_US"))
            merged.update(self._get_catalog(target))
        return merged

    def translate(self, key: str, **kwargs: Any) -> str:
        """按回退链查询译文并安全格式化占位符."""
        code = self.locale
        text = self._get_catalog(code).get(key)
        if text is None and code != "en_US":
            text = self._get_catalog("en_US").get(key)
        if text is None and code != DEFAULT_LOCALE:
            text = self._get_catalog(DEFAULT_LOCALE).get(key)
        if text is None:
            text = key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError, IndexError):
                return text
        return text

    def language_options(self) -> list[dict[str, str]]:
        """返回用于下拉框的语言选项（自动项随当前语言翻译，其余用母语名）."""
        options = [{"value": "auto", "label": self.translate("settings.system.language_auto")}]
        for code in SUPPORTED_LOCALES:
            options.append({"value": code, "label": NATIVE_LOCALE_NAMES[code]})
        return options


_default_manager = I18nManager(DEFAULT_LOCALE)


def get_i18n() -> I18nManager:
    return _default_manager


def get_locale() -> str:
    return _default_manager.locale


def set_language(lang: str | None) -> str:
    return _default_manager.set_language(lang)


def apply_language_from_config(config: Any) -> str:
    return _default_manager.apply_from_config(config)


def on_locale_changed(callback: Callable[[str], None]) -> None:
    _default_manager.on_change(callback)


def off_locale_changed(callback: Callable[[str], None]) -> None:
    _default_manager.off_change(callback)


def t(key: str, **kwargs: Any) -> str:
    return _default_manager.translate(key, **kwargs)
