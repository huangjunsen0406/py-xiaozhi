"""i18n 语言包一致性、QML/Python 键校验与三语免重启热切换回归测试."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from src.constants.constants import DeviceState
from src.i18n import (
    DEFAULT_LOCALE,
    SUPPORTED_LOCALES,
    detect_system_locale,
    get_locale,
    normalize_locale,
    set_language,
    t,
)
from src.media.events import MediaStateData
from src.plugins.ui_presenter import UiPresenter
from src.plugins.ui_session import SessionActions
from src.utils.config_manager import ConfigManager

ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "src" / "i18n" / "locales"
QML_DIR = ROOT / "src" / "ui" / "gui" / "qml"
SRC_DIR = ROOT / "src"

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_QML_KEY_RE = re.compile(
    r'i18n\.(?:s\["([a-zA-Z0-9_.]+)"\]|(?:tr|fmt)\("([a-zA-Z0-9_.]+)")'
)
_PY_T_KEY_RE = re.compile(r"""\bt\(\s*["']([a-zA-Z0-9_.]+)["']""")


@pytest.fixture(autouse=True)
def _restore_default_locale():
    set_language(DEFAULT_LOCALE)
    try:
        yield
    finally:
        set_language(DEFAULT_LOCALE)


def _load_catalog(code: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{code}.json"
    assert path.is_file(), f"缺少语言包: {path}"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_all_locale_catalogs_have_identical_keys_and_placeholders():
    base = _load_catalog("zh_CN")
    assert len(base) > 100
    base_keys = set(base.keys())

    for code in SUPPORTED_LOCALES:
        cat = _load_catalog(code)
        keys = set(cat.keys())
        missing = sorted(base_keys - keys)
        extra = sorted(keys - base_keys)
        assert not missing, f"{code} 缺少键: {missing}"
        assert not extra, f"{code} 多出键: {extra}"
        for k, v in cat.items():
            assert isinstance(v, str) and v.strip(), f"{code}[{k}] 为空"
            base_ph = set(_PLACEHOLDER_RE.findall(base[k]))
            cur_ph = set(_PLACEHOLDER_RE.findall(v))
            assert cur_ph == base_ph, (
                f"{code}[{k}] 占位符不一致: 期望 {base_ph}，实际 {cur_ph}"
            )


def test_qml_has_no_hardcoded_cjk_and_all_keys_exist():
    base = _load_catalog("zh_CN")
    hardcoded: list[tuple[str, int, str]] = []
    missing_keys: list[tuple[str, str]] = []

    for qml in sorted(QML_DIR.rglob("*.qml")):
        rel = str(qml.relative_to(ROOT))
        text = qml.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith(("//", "/*", "*")):
                continue
            code_part = line.split("//", 1)[0]
            if _CJK_RE.search(code_part) and ('"' in code_part or "'" in code_part):
                hardcoded.append((rel, idx, stripped))
        for m in _QML_KEY_RE.finditer(text):
            key = m.group(1) or m.group(2)
            if key not in base:
                missing_keys.append((rel, key))

    assert not hardcoded, f"QML 中仍有硬编码中文: {hardcoded}"
    assert not missing_keys, f"QML 引用了不存在的 i18n 键: {missing_keys}"


def test_python_t_calls_reference_existing_keys():
    base = _load_catalog("zh_CN")
    missing: list[tuple[str, str]] = []
    for py in sorted(SRC_DIR.rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        if "from src.i18n" not in text:
            continue
        for m in _PY_T_KEY_RE.finditer(text):
            key = m.group(1)
            if key not in base:
                missing.append((str(py.relative_to(ROOT)), key))
    assert not missing, f"Python 引用了不存在的 i18n 键: {missing}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("zh", "zh_CN"),
        ("zh-CN", "zh_CN"),
        ("zh_CN.UTF-8", "zh_CN"),
        ("en", "en_US"),
        ("en-GB", "en_US"),
        ("vi", "vi_VN"),
        ("vi-VN", "vi_VN"),
        ("vi_VN.UTF-8", "vi_VN"),
        ("auto", None),
        ("C", None),
        ("POSIX", None),
        ("", None),
    ],
)
def test_normalize_locale(raw, expected):
    assert normalize_locale(raw) == expected


def test_detect_system_locale_priority(monkeypatch):
    for var in ("XIAOZHI_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr("locale.getlocale", lambda: (None, None))
    assert detect_system_locale() == "zh_CN"

    monkeypatch.setenv("LANG", "vi_VN.UTF-8")
    assert detect_system_locale() == "vi_VN"

    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    assert detect_system_locale() == "en_US"

    monkeypatch.setenv("XIAOZHI_LANG", "zh_CN")
    assert detect_system_locale() == "zh_CN"


def test_presenter_and_session_hot_switch_across_three_locales():
    class FakeViewport:
        def __init__(self):
            self.status = ""
            self.connected = False
            self.media = ""
            self.button = ""

        def set_status(self, status, connected=True):
            self.status = status
            self.connected = connected

        def set_emotion(self, _emotion):
            pass

        def set_media_line(self, text):
            self.media = text

        def set_button_text(self, text):
            self.button = text

        def set_auto_mode(self, _auto):
            pass

    vp = FakeViewport()
    presenter = UiPresenter(vp)
    session = SessionActions(
        ctx=AsyncMock(), cmd=AsyncMock(), presenter=presenter
    )

    presenter.show_device_state(DeviceState.LISTENING)
    presenter.show_media_state(MediaStateData(state="playing", title="Demo"))
    session.refresh_locale()
    assert vp.status == "聆听中..."
    assert vp.media == "正在播放: Demo"
    assert vp.button == "按住后说话"

    set_language("en_US")
    presenter.refresh_locale()
    session.refresh_locale()
    assert vp.status == "Listening..."
    assert vp.media == "Playing: Demo"
    assert vp.button == "Hold to Talk"

    set_language("vi_VN")
    presenter.refresh_locale()
    session.refresh_locale()
    assert vp.status == "Đang nghe..."
    assert vp.media == "Đang phát: Demo"
    assert vp.button == "Giữ để nói"


def test_settings_model_language_live_preview_and_discard():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication.instance() or QCoreApplication([])
    from src.ui.gui.models.settings_model import SettingsModel

    cfg = ConfigManager.from_dict({"SYSTEM_OPTIONS": {"LANGUAGE": "zh_CN"}})
    model = SettingsModel(config_manager=cfg)
    try:
        assert model.language == "zh_CN"
        assert get_locale() == "zh_CN"

        # 下拉即时预览越南语
        model.language = "vi_VN"
        assert get_locale() == "vi_VN"
        assert t("settings.title") == "Cài đặt"

        # 取消（discard）恢复已保存语言
        model.discard()
        assert model.language == "zh_CN"
        assert get_locale() == "zh_CN"

        # 再次切换并保存持久化
        model.language = "en_US"
        assert model.save() is True
        assert cfg.get_config("SYSTEM_OPTIONS.LANGUAGE") == "en_US"
        assert get_locale() == "en_US"
        app.processEvents()
    finally:
        model.close()


def test_qml_i18n_bridge_hot_retranslates_live_binding():
    pytest.importorskip("PySide6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    from src.ui.gui.i18n_bridge import I18nBridge

    app = QGuiApplication.instance() or QGuiApplication([])
    engine = QQmlEngine()
    bridge = I18nBridge()
    engine.rootContext().setContextProperty("i18n", bridge)

    qml_source = b"""
    import QtQuick
    QtObject {
        property string titleText: i18n.s["settings.title"]
        property string headerText: i18n.s["settings.mcp.plugins_header"].replace("{count}", 3)
    }
    """
    component = QQmlComponent(engine)
    component.setData(qml_source, engine.baseUrl())
    obj = component.create()
    assert obj is not None, component.errorString()

    try:
        assert obj.property("titleText") == "参数设置"
        assert obj.property("headerText") == "外挂插件 (3)"

        set_language("en_US")
        app.processEvents()
        assert obj.property("titleText") == "Settings"
        assert obj.property("headerText") == "External Plugins (3)"

        set_language("vi_VN")
        app.processEvents()
        assert obj.property("titleText") == "Cài đặt"
        assert obj.property("headerText") == "Plugin mở rộng (3)"
    finally:
        bridge.close()
        obj.deleteLater()
        app.processEvents()


def test_tui_app_accepts_localized_reactive_state_before_mount():
    """在 Textual 挂载屏幕前设置任意语言的 status_text 不应抛出 ScreenStackError."""
    pytest.importorskip("textual")
    from src.ui.tui.app import XiaozhiTuiApp

    set_language("vi_VN")
    tui_app = XiaozhiTuiApp()
    tui_app.status_text = t("main.status.idle")
    tui_app.connected = False
    tui_app.auto_mode = True
    assert tui_app.status_text == "Sẵn sàng"


def test_tray_service_updates_qaction_texts_on_locale_change(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QCoreApplication

    from src.ui.gui.services import tray_service as mod

    app = QCoreApplication.instance() or QCoreApplication([])

    class FakeSignal:
        def connect(self, _cb):
            pass

    class FakeAction:
        def __init__(self, text, _parent=None):
            self._text = text
            self.triggered = FakeSignal()

        def text(self):
            return self._text

        def setText(self, text):
            self._text = text

    class FakeMenu:
        def __init__(self):
            self.actions = []

        def addAction(self, action):
            self.actions.append(action)

        def addSeparator(self):
            pass

    class FakeTray:
        @staticmethod
        def isSystemTrayAvailable():
            return True

        def __init__(self, _parent=None):
            self.activated = FakeSignal()

        def setIcon(self, _icon):
            pass

        def setContextMenu(self, _menu):
            pass

        def show(self):
            pass

        def hide(self):
            pass

    monkeypatch.setattr(mod, "QSystemTrayIcon", FakeTray)
    monkeypatch.setattr(mod, "QMenu", FakeMenu)
    monkeypatch.setattr(mod, "QAction", FakeAction)
    monkeypatch.setattr(mod, "QIcon", lambda _path: None)

    tray = mod.TrayService()
    try:
        assert tray.setup(on_show=lambda: None, on_quit=lambda: None) is True
        assert tray._show_action.text() == "显示窗口"
        assert tray._quit_action.text() == "退出"

        set_language("vi_VN")
        app.processEvents()
        assert tray._show_action.text() == "Hiện cửa sổ"
        assert tray._quit_action.text() == "Thoát"

        set_language("en_US")
        app.processEvents()
        assert tray._show_action.text() == "Show Window"
        assert tray._quit_action.text() == "Quit"
    finally:
        tray.hide()
