import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Set

from src.constants.constants import AbortReason
from src.plugins.base import Plugin
from src.utils.config_manager import ConfigManager
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ShortcutConfig:
    modifier: str
    key: str
    description: str = ""


class _AppAdapter:
    def __init__(self, app: Any):
        self._app = app

    async def start_listening(self):
        try:
            await self._app.start_listening_manual()
        except Exception:
            pass

    async def stop_listening(self):
        try:
            await self._app.stop_listening_manual()
        except Exception:
            pass

    async def toggle_chat_state(self):
        try:
            await self._app.start_auto_conversation()
        except Exception:
            pass

    async def abort_speaking(self, reason):
        try:
            await self._app.abort_speaking(reason)
        except Exception:
            pass


class PluginShortcutManager:
    """
    插件内置的全局快捷键管理器（替代 views/components/shortcut_manager.py）。
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop]):
        self._main_loop = loop
        self.config = ConfigManager.get_instance()
        self.shortcuts_config = self.config.get_config("SHORTCUTS", {}) or {}
        self.enabled = bool(self.shortcuts_config.get("ENABLED", True))

        self.pressed_keys: Set[str] = set()
        self.manual_press_active = False
        self.running = False
        self._listener = None
        self._health_check_task = None
        self._restart_in_progress = False
        self._last_activity_time = 0.0

        # 应用与显示引用（由插件注入）
        self.application = None
        self.display = None

        self.key_mapping = {
            "\x17": "w",
            "\x01": "a",
            "\x13": "s",
            "\x04": "d",
            "\x05": "e",
            "\x12": "r",
            "\x14": "t",
            "\x06": "f",
            "\x07": "g",
            "\x08": "h",
            "\x0a": "j",
            "\x0b": "k",
            "\x0c": "l",
            "\x1a": "z",
            "\x18": "x",
            "\x03": "c",
            "\x16": "v",
            "\x02": "b",
            "\x0e": "n",
            "\x0d": "m",
            "\x11": "q",
        }

        self.shortcuts: Dict[str, ShortcutConfig] = {}
        self._load_shortcuts()

    def _load_shortcuts(self):
        self.shortcuts.clear()
        for name in [
            "MANUAL_PRESS",
            "AUTO_TOGGLE",
            "ABORT",
            "MODE_TOGGLE",
            "WINDOW_TOGGLE",
        ]:
            cfg = self.shortcuts_config.get(name, {}) or {}
            modifier = str(cfg.get("modifier", "ctrl")).lower()
            key = str(cfg.get("key", "")).lower()
            self.shortcuts[name] = ShortcutConfig(modifier=modifier, key=key)

    async def start(self) -> bool:
        if not self.enabled:
            logger.info("全局快捷键已禁用")
            return False
        try:
            from pynput import keyboard
        except Exception as e:
            logger.error(f"未安装pynput库: {e}")
            return False

        self._listener = keyboard.Listener(
            on_press=self._on_key_press, on_release=self._on_key_release
        )
        try:
            self._listener.start()
            self.running = True
            self._start_health_check_task()
            logger.info("全局快捷键监听已启动")
            return True
        except Exception as e:
            logger.error(f"启动全局快捷键监听失败: {e}")
            return False

    async def stop(self):
        self.running = False
        self.manual_press_active = False
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await asyncio.wrap_future(self._health_check_task)
            except Exception:
                pass
            self._health_check_task = None
        try:
            if self._listener:
                self._listener.stop()
                self._listener = None
        except Exception:
            pass
        logger.info("全局快捷键监听已停止")

    async def reload_from_config(self):
        try:
            self.config.reload_config()
            self.shortcuts_config = self.config.get_config("SHORTCUTS", {}) or {}
            self.enabled = bool(self.shortcuts_config.get("ENABLED", True))
            self._load_shortcuts()
            logger.info("快捷键配置已重新加载")
        except Exception as e:
            logger.error(f"重新加载快捷键配置失败: {e}")

    # --- 内部回调 ---
    def _on_key_press(self, key):
        if not self.running:
            return
        self._last_activity_time = time.time()
        name = self._get_key_name(key)
        if not name:
            return
        self.pressed_keys.add(name)
        self._check_shortcuts(True)

    def _on_key_release(self, key):
        if not self.running:
            return
        self._last_activity_time = time.time()
        name = self._get_key_name(key)
        if not name:
            return
        if name in self.pressed_keys:
            self.pressed_keys.remove(name)
        # 释放时停止按住说话
        if (
            self.manual_press_active
            and len(self.pressed_keys) == 0
            and self.application
        ):
            self._run_coroutine_threadsafe(self.application.stop_listening())
            self.manual_press_active = False
        self._check_shortcuts(False)

    def _get_key_name(self, key) -> Optional[str]:
        try:
            if hasattr(key, "name"):
                if key.name in ["ctrl_l", "ctrl_r"]:
                    return "ctrl"
                if key.name in ["alt_l", "alt_r"]:
                    return "alt"
                if key.name in ["shift_l", "shift_r"]:
                    return "shift"
                if key.name == "cmd":
                    return "cmd"
                if key.name == "esc":
                    return "esc"
                if key.name == "enter":
                    return "enter"
                return key.name.lower()
            elif hasattr(key, "char") and key.char:
                if key.char == "\n":
                    return "enter"
                if key.char in self.key_mapping:
                    return self.key_mapping[key.char]
                return key.char.lower()
        except Exception:
            pass
        return None

    def _check_shortcuts(self, is_press: bool):
        if not self.shortcuts:
            return
        ctrl = any(
            k in self.pressed_keys for k in ["ctrl", "control", "ctrl_l", "ctrl_r"]
        )
        alt = any(k in self.pressed_keys for k in ["alt", "option", "alt_l", "alt_r"])
        shift = any(k in self.pressed_keys for k in ["shift", "shift_l", "shift_r"])
        cmd = "cmd" in self.pressed_keys

        for kind, cfg in self.shortcuts.items():
            if self._match(cfg, ctrl, alt, shift, cmd):
                self._handle(kind, is_press)

    def _match(
        self, cfg: ShortcutConfig, ctrl: bool, alt: bool, shift: bool, cmd: bool
    ) -> bool:
        if cfg.modifier == "ctrl" and not ctrl:
            return False
        if cfg.modifier == "alt" and not alt:
            return False
        if cfg.modifier == "shift" and not shift:
            return False
        if cfg.modifier == "cmd" and not cmd:
            return False
        return cfg.key in {k.lower() for k in self.pressed_keys}

    def _handle(self, kind: str, is_press: bool):
        if kind == "MANUAL_PRESS":
            if is_press and not self.manual_press_active and self.application:
                self._run_coroutine_threadsafe(self.application.start_listening())
                self.manual_press_active = True
            elif (not is_press) and self.manual_press_active and self.application:
                self._run_coroutine_threadsafe(self.application.stop_listening())
                self.manual_press_active = False
            return

        if kind == "ABORT":
            if is_press and self.application:
                self._run_coroutine_threadsafe(
                    self.application.abort_speaking(AbortReason.NONE)
                )
            return

        if kind == "AUTO_TOGGLE" and is_press and self.application:
            self._run_coroutine_threadsafe(self.application.toggle_chat_state())
            return

        if kind == "MODE_TOGGLE" and is_press and self.display:
            self._run_coroutine_threadsafe(self.display.toggle_mode())
            return

        if kind == "WINDOW_TOGGLE" and is_press and self.display:
            print("显示隐藏界面")
            self._run_coroutine_threadsafe(self.display.toggle_window_visibility())
            return

    def _run_coroutine_threadsafe(self, coro):
        try:
            if self._main_loop and self.running:
                asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        except Exception:
            pass

    def _start_health_check_task(self):
        if self._main_loop and not self._health_check_task:
            self._health_check_task = asyncio.run_coroutine_threadsafe(
                self._health_check_loop(), self._main_loop
            )

    async def _health_check_loop(self):
        while self.running and not self._restart_in_progress:
            await asyncio.sleep(30)
            # 这里只做轻量心跳；如需重启逻辑可扩展


class ShortcutsPlugin(Plugin):
    name = "shortcuts"

    def __init__(self) -> None:
        super().__init__()
        self.app: Any = None
        self._manager: Optional[PluginShortcutManager] = None
        self._adapter: Optional[_AppAdapter] = None

    async def setup(self, app: Any) -> None:
        self.app = app
        self._adapter = _AppAdapter(app)
        self._manager = PluginShortcutManager(getattr(app, "_main_loop", None))

    async def start(self) -> None:
        if not self._manager:
            return
        # 注入应用与显示引用
        self._manager.application = self._adapter
        try:
            display_obj = None
            if hasattr(self.app, "plugins"):
                ui_plugin = self.app.plugins.get_plugin("ui")
                if ui_plugin is not None:
                    display_obj = getattr(ui_plugin, "display", None)
            self._manager.display = display_obj
        except Exception:
            pass
        await self._manager.start()

    async def stop(self) -> None:
        if self._manager:
            await self._manager.stop()

    async def shutdown(self) -> None:
        if self._manager:
            await self._manager.stop()

    async def reload_from_config(self) -> None:
        if self._manager:
            await self._manager.reload_from_config()
