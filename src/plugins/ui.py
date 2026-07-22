"""UI 插件：起界面、转展示、接用户操作."""

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
    priority = 60

    def __init__(
        self,
        mode: Optional[str] = None,
        task_manager: Optional["TaskManager"] = None,
    ) -> None:
        super().__init__()
        self.mode = (mode or "cli").lower()
        self._task_manager = task_manager
        self.viewport: Optional["ViewPort"] = None
        self._presenter = UiPresenter()
        self._session: Optional[SessionActions] = None
        self.is_first = True

    async def setup(self, ctx: "PluginContext", cmd: "PluginCommands") -> None:
        await super().setup(ctx, cmd)
        self.viewport = create_viewport(
            self.mode,
            event_bus=self._ctx.event_bus,
            task_manager=self._task_manager,
        )
        self._presenter.bind(self.viewport)
        self._session = SessionActions(self._ctx, self._cmd, self._presenter)

    async def start(self) -> None:
        from src.core.event_bus import Events

        bus = self._ctx.event_bus
        bus.on(Events.NETWORK_ERROR, self._on_network_error)
        bus.on(Events.SYSTEM_NOTICE, self._on_system_notice)
        bus.on(Events.MUSIC_STATE_CHANGED, self._on_music_state_changed)
        bus.on(Events.MUSIC_LYRICS_UPDATE, self._on_music_lyrics_update)
        logger.info("UIPlugin 已订阅音乐/网络/系统提示事件")

        if self._session:
            self._session.subscribe(bus)

        if self.viewport:
            self._cmd.spawn(
                self.viewport.start(mode=self.mode),
                name=f"ui:{self.mode}:start",
            )

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
            pool.register("ui.viewport", self.viewport.close)

    async def _on_music_state_changed(self, data) -> None:
        self._presenter.show_music_state(data)

    async def _on_music_lyrics_update(self, data) -> None:
        self._presenter.show_music_lyrics(data)
