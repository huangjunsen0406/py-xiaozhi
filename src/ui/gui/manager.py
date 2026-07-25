"""GUI ViewManager：组合 QmlAppHost / 主界面 / 设置控制器，实现 ViewPort."""

from PySide6.QtCore import QObject, Slot

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.ui.gui.main_controller import MainWindowController
from src.ui.gui.qml_host import QmlAppHost
from src.ui.gui.services import TrayService
from src.ui.gui.settings_controller import SettingsController
from src.ui.shared.bridge import EventBridge

logger = get_logger()


class GuiViewManager(QObject):
    """GUI 界面入口（ViewPort + 设置辅助）.

    设备激活在容器启动前由 GuiActivation 独立窗口完成，主界面不再挂激活 Model/API。
    """

    def __init__(self, event_bus: EventBus, task_manager: TaskManager | None = None):
        super().__init__()
        self._event_bus = event_bus
        self._running = False

        self._owns_tasks = task_manager is None
        if task_manager is not None:
            self._tasks = task_manager
        else:
            self._tasks = TaskManager()
            self._tasks.initialize()

        self._bridge = EventBridge(event_bus, task_manager=self._tasks)
        self._host = QmlAppHost()
        self._main = MainWindowController()
        self._settings = SettingsController(event_bus, self._tasks, self._bridge)
        self._tray_service: TrayService | None = None

        self._event_bus.on(Events.UI_TOGGLE_WINDOW, self._on_toggle_window)
        logger.debug("GuiViewManager: 已订阅窗口切换事件")

    async def start(self, mode: str = "gui"):
        if mode == "cli":
            logger.info("GuiViewManager: CLI 模式，跳过 GUI 初始化")
            return

        logger.info("GuiViewManager: 启动 GUI...")
        self._running = True

        self._host.create_engine()
        self._host.inject_context(
            {
                "eventBridge": self._bridge,
                "mainModel": self._main.main_model,
                "settingsModel": self._settings.ensure_model(),
                "emotionService": self._main.emotion_service,
            }
        )
        self._host.load_main()
        self._setup_tray()
        self._main.set_neutral_emotion()
        logger.info("GuiViewManager: GUI 启动完成")

    async def close(self):
        logger.info("GuiViewManager: 正在关闭...")
        self._running = False
        if self._tray_service:
            self._tray_service.hide()
        self._host.shutdown()
        logger.info("GuiViewManager: 已关闭")

    def _setup_tray(self) -> None:
        root = self._host.root_window()
        if root is None:
            return
        self._tray_service = TrayService(root)
        self._tray_service.setup(
            on_show=self._host.show_root,
            on_quit=self._request_quit,
        )

    def _request_quit(self) -> None:
        self._tasks.spawn(
            self._event_bus.emit(Events.UI_QUIT_REQUEST), name="ui:quit_request"
        )

    async def _on_toggle_window(self, data=None):
        logger.debug("GuiViewManager: 收到窗口切换事件")
        self.toggle_window()

    # ----- ViewPort -----

    @property
    def is_running(self) -> bool:
        return self._running

    def set_chat_text(self, text: str) -> None:
        self._main.set_chat_text(text)

    def set_music_line(self, text: str) -> None:
        self._main.set_music_line(text)

    def set_emotion(self, emotion: str) -> None:
        self._main.set_emotion(emotion)

    def set_status(self, status: str, connected: bool = True) -> None:
        self._main.set_status(status, connected)

    def set_button_text(self, text: str) -> None:
        self._main.set_button_text(text)

    def set_auto_mode(self, auto_mode: bool) -> None:
        self._main.set_auto_mode(auto_mode)

    def is_auto_mode(self) -> bool:
        return self._main.is_auto_mode()

    # ----- 设置 / 窗口 -----

    @property
    def main_model(self):
        return self._main.main_model

    @property
    def settings_model(self):
        return self._settings.settings_model

    @Slot()
    def toggle_mode(self):
        self._tasks.spawn(
            self._event_bus.emit(Events.UI_AUTO_TOGGLE), name="ui:auto_toggle"
        )

    @Slot()
    def toggle_window(self):
        self._host.toggle_root_visible()

    def open_settings(self):
        if not self._host.engine:
            logger.warning("GuiViewManager: 引擎未初始化，无法打开设置")
            return
        self._settings.open_settings()
