"""设置窗口：SettingsModel 懒加载与打开设置."""

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.ui.shared.bridge import EventBridge

logger = get_logger()


class SettingsController:
    """懒创建 SettingsModel；打开设置时 reload + 通知 QML."""

    def __init__(
        self,
        event_bus: EventBus,
        tasks: TaskManager,
        bridge: EventBridge,
    ) -> None:
        self._event_bus = event_bus
        self._tasks = tasks
        self._bridge = bridge
        self._settings_model = None

    @property
    def settings_model(self):
        return self.ensure_model()

    def ensure_model(self):
        """懒创建 SettingsModel（首次注入 QML / 打开设置时）."""
        if self._settings_model is None:
            from src.ui.gui.models import SettingsModel

            self._settings_model = SettingsModel()
            self._settings_model.configSaved.connect(self._on_config_saved)
            self._settings_model.mcpToolsNeedReconnect.connect(
                self._on_mcp_tools_need_reconnect
            )
            logger.debug("SettingsController: SettingsModel 已懒加载")
        return self._settings_model

    def _on_config_saved(self) -> None:
        logger.info("SettingsController: 配置已保存，触发热重载")
        self._tasks.spawn(
            self._event_bus.emit(Events.CONFIG_CHANGED), name="ui:config_changed"
        )

    def _on_mcp_tools_need_reconnect(self) -> None:
        """MCP 工具黑名单变更：请求会话层断开并重连以刷新服务端 tools/list."""
        logger.info("SettingsController: MCP 工具列表变更，请求协议重连")
        self._tasks.spawn(
            self._event_bus.emit(Events.PROTOCOL_RECONNECT_REQUEST),
            name="ui:protocol_reconnect",
        )

    def open_settings(self) -> None:
        """reload 配置/设备列表，再让 QML 显示设置窗."""
        self.ensure_model().reload()
        self._bridge.showSettingsWindow.emit()
        logger.debug("SettingsController: 已发送打开设置窗口信号")
