"""快捷键配置属性."""


class SettingsShortcutsMixin:
    # ========== 快捷键设置 ==========

    def _get_shortcutsEnabled(self) -> bool:
        return self._get_value("SHORTCUTS.ENABLED", True)

    def _set_shortcutsEnabled(self, value: bool):
        self._set_value("SHORTCUTS.ENABLED", value)

    # 快捷键：手动模式
    def _get_shortcutManualModifier(self) -> str:
        return self._get_value("SHORTCUTS.MANUAL_PRESS.modifier", "ctrl")

    def _set_shortcutManualModifier(self, value: str):
        self._set_value("SHORTCUTS.MANUAL_PRESS.modifier", value)

    def _get_shortcutManualKey(self) -> str:
        return self._get_value("SHORTCUTS.MANUAL_PRESS.key", "j")

    def _set_shortcutManualKey(self, value: str):
        self._set_value("SHORTCUTS.MANUAL_PRESS.key", value)

    # 快捷键：自动模式
    def _get_shortcutAutoModifier(self) -> str:
        return self._get_value("SHORTCUTS.AUTO_TOGGLE.modifier", "ctrl")

    def _set_shortcutAutoModifier(self, value: str):
        self._set_value("SHORTCUTS.AUTO_TOGGLE.modifier", value)

    def _get_shortcutAutoKey(self) -> str:
        return self._get_value("SHORTCUTS.AUTO_TOGGLE.key", "k")

    def _set_shortcutAutoKey(self, value: str):
        self._set_value("SHORTCUTS.AUTO_TOGGLE.key", value)

    # 快捷键：中断
    def _get_shortcutAbortModifier(self) -> str:
        return self._get_value("SHORTCUTS.ABORT.modifier", "ctrl")

    def _set_shortcutAbortModifier(self, value: str):
        self._set_value("SHORTCUTS.ABORT.modifier", value)

    def _get_shortcutAbortKey(self) -> str:
        return self._get_value("SHORTCUTS.ABORT.key", "q")

    def _set_shortcutAbortKey(self, value: str):
        self._set_value("SHORTCUTS.ABORT.key", value)

    # 快捷键：模式切换
    def _get_shortcutModeModifier(self) -> str:
        return self._get_value("SHORTCUTS.MODE_TOGGLE.modifier", "ctrl")

    def _set_shortcutModeModifier(self, value: str):
        self._set_value("SHORTCUTS.MODE_TOGGLE.modifier", value)

    def _get_shortcutModeKey(self) -> str:
        return self._get_value("SHORTCUTS.MODE_TOGGLE.key", "m")

    def _set_shortcutModeKey(self, value: str):
        self._set_value("SHORTCUTS.MODE_TOGGLE.key", value)

    # 快捷键：窗口显示/隐藏
    def _get_shortcutWindowModifier(self) -> str:
        return self._get_value("SHORTCUTS.WINDOW_TOGGLE.modifier", "ctrl")

    def _set_shortcutWindowModifier(self, value: str):
        self._set_value("SHORTCUTS.WINDOW_TOGGLE.modifier", value)

    def _get_shortcutWindowKey(self) -> str:
        return self._get_value("SHORTCUTS.WINDOW_TOGGLE.key", "w")

    def _set_shortcutWindowKey(self, value: str):
        self._set_value("SHORTCUTS.WINDOW_TOGGLE.key", value)

