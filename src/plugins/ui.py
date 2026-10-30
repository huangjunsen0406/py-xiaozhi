"""UI 插件：起界面、转展示、接用户操作."""

import asyncio
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional

from src.logging import get_logger
from src.plugins.base import Plugin
from src.plugins.ui_presenter import UiPresenter
from src.plugins.ui_session import SessionActions
from src.ui.shared.factory import create_viewport

if TYPE_CHECKING:
    from src.bootstrap.protocols import PluginCommands, PluginContext
    from src.core.task_manager import TaskManager
    from src.ui.shared.viewport import ViewPort

logger = get_logger()


class UIPlugin(Plugin):
    """界面插件."""

    name = "ui"

    def __init__(
        self,
        mode: str | None = None,
        task_manager: Optional["TaskManager"] = None,
        runtime_tool_names: Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        super().__init__()
        self.mode = (mode or "cli").lower()
        self._task_manager = task_manager
        self._runtime_tool_names = runtime_tool_names
        self.viewport: ViewPort | None = None
        self._presenter = UiPresenter()
        self._session: SessionActions | None = None
        self.is_first = True
        self._viewport_task: asyncio.Task | None = None
        self._stopping = False
        self._viewport_closed = False
        self._subscriptions = []

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self.viewport = create_viewport(
            self.mode,
            event_bus=self._ctx.event_bus,
            task_manager=self._task_manager,
            config_manager=self._ctx.get_config(),
            runtime_tool_names=self._runtime_tool_names,
        )
        self._presenter.bind(self.viewport)
        self._session = SessionActions(self._ctx, self._cmd, self._presenter)

    async def start(self) -> None:
        from src.core.event_bus import Events

        bus = self._ctx.event_bus
        for event, handler in (
            (Events.NETWORK_ERROR, self._on_network_error),
            (Events.SYSTEM_NOTICE, self._on_system_notice),
            (Events.MUSIC_STATE_CHANGED, self._on_music_state_changed),
            (Events.MUSIC_LYRICS_UPDATE, self._on_music_lyrics_update),
            (Events.NOTIFICATION_SUBTITLE, self._on_notification_subtitle),
        ):
            bus.on(event, handler)
            self._subscriptions.append((event, handler))
        logger.info("UIPlugin 已订阅音乐/通知/网络/系统提示事件")

        if self._session:
            self._session.subscribe(bus)

        if self.viewport:
            self._viewport_task = self._cmd.spawn(
                self._run_viewport(), name=f"ui:{self.mode}:start"
            )
            # Immediate import/QML failures reach the startup health check.
            await asyncio.sleep(0)

    async def _run_viewport(self) -> None:
        try:
            await self.viewport.start(mode=self.mode)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.mark_failed()
            logger.exception("关键界面任务失败: %s", self.mode)
            self._cmd.request_shutdown()
        else:
            # GUI start installs its Qt callbacks and returns; terminal/GPIO
            # start represents the entire interactive lifetime.
            if not self._stopping and self.mode != "gui":
                self._cmd.request_shutdown()

    async def stop(self) -> None:
        self._stopping = True
        self._presenter.bind(None)
        if self._session is not None:
            self._session.unsubscribe()
        if self._ctx is not None:
            for event, handler in self._subscriptions:
                self._ctx.event_bus.off(event, handler)
        self._subscriptions.clear()
        task = self._viewport_task
        self._viewport_task = None
        try:
            if task is not None and task is not asyncio.current_task():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        finally:
            await self._close_viewport()

    async def _close_viewport(self) -> None:
        try:
            if self.viewport is not None and not self._viewport_closed:
                self._viewport_closed = True
                await self.viewport.close()
        finally:
            self._runtime_tool_names = None

    async def on_incoming_json(self, message) -> None:
        self._presenter.show_protocol_message(message)

    async def on_device_state_changed(self, state) -> None:
        if self.is_first:
            self.is_first = False
            return
        if not self.viewport:
            return
        if self._session:
            self._session.on_device_state_changed(state)
        self._presenter.show_device_state(state)

    async def _on_network_error(self, error_message: str = None) -> None:
        self._presenter.show_network_error()

    async def _on_system_notice(self, message: str = None) -> None:
        if message:
            self._presenter.set_status(str(message), connected=True)

    def register_resources(self, pool) -> None:
        if self.viewport:
            pool.register("ui.viewport", self._close_viewport)

    async def _on_music_state_changed(self, data) -> None:
        self._presenter.show_music_state(data)

    async def _on_music_lyrics_update(self, data) -> None:
        self._presenter.show_music_lyrics(data)

    async def _on_notification_subtitle(self, text: str = "") -> None:
        if text:
            self._presenter.set_chat_text(text)
