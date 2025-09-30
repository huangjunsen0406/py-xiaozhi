from typing import Any, Optional

from src.constants.constants import AbortReason, DeviceState
from src.plugins.base import Plugin


class UIPlugin(Plugin):
    name = "ui"

    def __init__(self, mode: Optional[str] = None) -> None:
        super().__init__()
        self.app = None
        self.mode = (mode or "cli").lower()
        self.display = None  # CliDisplay | GuiDisplay
        self._is_gui = False
        self.is_first = True

    async def setup(self, app: Any) -> None:
        self.app = app

        # 通过配置决定模式（可选）
        try:
            cfg_mode = app.config.get_config("SYSTEM_OPTIONS.UI.MODE", None)
            if cfg_mode:
                self.mode = str(cfg_mode).lower()
        except Exception:
            pass

        # 选择显示实现
        if self.mode == "gui":

            from src.display.gui_display import GuiDisplay

            self.display = GuiDisplay()
            self._is_gui = True
        else:
            from src.display.cli_display import CliDisplay

            self.display = CliDisplay()
            self._is_gui = False

        # 告知应用：UI自身处理输入，禁用应用内控制台输入
        try:
            if hasattr(self.app, "use_console_input"):
                self.app.use_console_input = False
        except Exception:
            pass

    async def start(self) -> None:
        if not self.display:
            return

        # 绑定回调
        try:
            if self._is_gui:
                # GUI：部分回调是同步信号（press/release/abort/auto），需要包一层调度；
                # 发送文本是协程，直接传递以便GUI内部 create_task。
                def _sched(coro):
                    try:
                        if self.app:
                            self.app.spawn(coro, name="ui:callback")
                    except Exception:
                        pass

                await self.display.set_callbacks(
                    press_callback=lambda: _sched(self._press()),
                    release_callback=lambda: _sched(self._release()),
                    auto_callback=lambda: _sched(self._auto_toggle()),
                    abort_callback=lambda: _sched(self._abort()),
                    send_text_callback=self._send_text,
                )
            else:
                # CLI显示会await回调，直接传协程函数
                await self.display.set_callbacks(
                    mode_callback=None,
                    auto_callback=self._auto_toggle,
                    abort_callback=self._abort,
                    send_text_callback=self._send_text,
                )
        except Exception:
            pass

        # 启动显示（作为任务，避免阻塞）
        try:
            self.app.spawn(self.display.start(), name=f"ui:{self.mode}:start")
        except Exception:
            pass

    async def on_incoming_json(self, message: Any) -> None:
        if not self.display or not isinstance(message, dict):
            return
        try:
            msg_type = message.get("type")
            if msg_type == "tts":
                text = message.get("text")
                if text:
                    await self.display.update_text(text)
            elif msg_type == "stt":
                text = message.get("text")
                if text:
                    await self.display.update_text(text)
            elif msg_type == "llm":
                emotion = message.get("emotion")
                if emotion:
                    await self.display.update_emotion(emotion)
        except Exception:
            pass

    async def on_device_state_changed(self, state: Any) -> None:
        if not self.display:
            return
        try:
            if self.is_first:
                self.is_first = False
                return
            await self.display.update_emotion("neutral")
            if state == DeviceState.IDLE:
                await self.display.update_status("待命", True)
            elif state == DeviceState.LISTENING:
                await self.display.update_status("聆听中...", True)
            elif state == DeviceState.SPEAKING:
                await self.display.update_status("说话中...", True)
        except Exception:
            pass

    async def stop(self) -> None:
        """
        停止 UI 插件（暂不关闭窗口，等待 shutdown）
        """
        # 保留 display 引用，避免重复关闭

    async def shutdown(self) -> None:
        """
        清理 UI 资源，关闭窗口.
        """
        if self.display:
            try:
                await self.display.close()
                self.display = None  # 清空引用
            except Exception:
                pass

    # ===== callbacks =====
    async def _send_text(self, text: str):
        try:
            ok = await self.app.connect_protocol()
            if not ok:
                return
            await self.app.protocol.send_wake_word_detected(text)
        except Exception:
            pass

    async def _press(self):
        try:
            await self.app.start_listening_manual()
        except Exception:
            pass

    async def _release(self):
        try:
            await self.app.stop_listening_manual()
        except Exception:
            pass

    async def _auto_toggle(self):
        try:
            await self.app.start_auto_conversation()
        except Exception:
            pass

    async def _abort(self):
        await self.app.abort_speaking(AbortReason.USER_INTERRUPTION)
