"""Qt/QML 多语言桥接：提供响应式字符串映射与免重启热切换通知."""

from __future__ import annotations

from PySide6.QtCore import Property, QObject, Qt, Signal, Slot

from src.i18n import (
    get_i18n,
    get_locale,
    off_locale_changed,
    on_locale_changed,
    t,
)


class I18nBridge(QObject):
    """注入 QML 根上下文的 `i18n` 对象.

    QML 用法:
        text: i18n.s["settings.title"]
        text: i18n.s["settings.mcp.plugins_header"].replace("{count}", count)
        addLog(i18n.tr("settings.audio.log_loaded"))
    切换语言时自动发出 `localeChanged`，所有绑定 `i18n.s[...]` 的 QML 元素即时重绘。
    """

    localeChanged = Signal()
    _localeChangeRequested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._closed = False
        self._rev = 0
        self._strings: dict[str, str] = get_i18n().merged_strings()
        self._localeChangeRequested.connect(
            self._apply_locale_change, Qt.ConnectionType.QueuedConnection
        )
        on_locale_changed(self._on_locale_changed)

    def _on_locale_changed(self, locale_code: str) -> None:
        if self._closed:
            return
        try:
            self._localeChangeRequested.emit(locale_code)
        except RuntimeError:
            pass

    @Slot(str)
    def _apply_locale_change(self, _locale_code: str) -> None:
        if self._closed:
            return
        self._strings = get_i18n().merged_strings()
        self._rev += 1
        self.localeChanged.emit()

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            off_locale_changed(self._on_locale_changed)

    @Property("QVariantMap", notify=localeChanged)
    def s(self) -> dict[str, str]:
        return self._strings

    @Property(int, notify=localeChanged)
    def rev(self) -> int:
        return self._rev

    @Property(str, notify=localeChanged)
    def locale(self) -> str:
        return get_locale()

    @Property("QVariantList", notify=localeChanged)
    def languageOptions(self) -> list[dict[str, str]]:
        return get_i18n().language_options()

    @Slot(str, result=str)
    def tr(self, key: str) -> str:
        return t(key)

    @Slot(str, "QVariantMap", result=str)
    def fmt(self, key: str, params) -> str:
        if isinstance(params, dict):
            return t(key, **params)
        return t(key)
