"""视图管理器 - PySide6 + QtQuick 统一入口."""

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtQml import QQmlApplicationEngine

from src.core.event_bus import EventBus, Events
from src.core.task_manager import TaskManager
from src.logging import get_logger
from src.ui.gui.services import EmotionService, TrayService
from src.ui.shared.bridge import EventBridge
from src.ui.shared.models import ActivationModel, MainModel

logger = get_logger()


class ViewManager(QObject):
    """视图管理器 - 管理所有 UI 组件的生命周期."""

    def __init__(self, event_bus: EventBus, task_manager: TaskManager | None = None):
        super().__init__()
        self._event_bus = event_bus
        self._engine: QQmlApplicationEngine | None = None
        self._running = False

        # 优先使用容器注入的 TaskManager，便于统一 cancel / 追踪
        self._owns_tasks = task_manager is None
        if task_manager is not None:
            self._tasks = task_manager
        else:
            self._tasks = TaskManager()
            self._tasks.initialize()

        # 桥接层
        self._bridge = EventBridge(event_bus, task_manager=self._tasks)

        # Models（SettingsModel 懒加载：避免插件 setup 阶段 import sounddevice/cv2）
        self._activation_model = ActivationModel()
        self._main_model = MainModel()
        self._settings_model = None

        # Services
        self._emotion_service = EmotionService()
        self._tray_service: TrayService | None = None

        # 激活服务引用
        self._activation_service = None

        # 设置激活码获取器
        self._bridge.set_activation_code_getter(self._get_activation_code)

        # 订阅事件
        self._subscribe_events()

    def _ensure_settings_model(self):
        """懒创建 SettingsModel（首次注入 QML / 打开设置时）."""
        if self._settings_model is None:
            from src.ui.shared.models import SettingsModel

            self._settings_model = SettingsModel()
            self._settings_model.configSaved.connect(self._on_config_saved)
            logger.debug("ViewManager: SettingsModel 已懒加载")
        return self._settings_model

    def _subscribe_events(self):
        self._event_bus.on(Events.UI_TOGGLE_WINDOW, self._on_toggle_window)
        logger.debug("ViewManager: 已订阅窗口切换事件")

    def _on_config_saved(self):
        """配置保存后触发热重载事件."""
        logger.info("ViewManager: 配置已保存，触发热重载事件")
        self._tasks.spawn(self._event_bus.emit(Events.CONFIG_CHANGED), name="ui:config_changed")

    async def _on_toggle_window(self, data=None):
        """处理窗口切换事件."""
        logger.debug("ViewManager: 收到窗口切换事件")
        self.toggle_window()

    async def start(self, mode: str = "gui"):
        """启动视图.

        Args:
            mode: 运行模式 - "gui" 或 "cli"
        """
        if mode == "cli":
            logger.info("ViewManager: CLI 模式，跳过 GUI 初始化")
            return

        logger.info("ViewManager: 启动 GUI...")
        self._running = True

        # 创建 QML 引擎
        self._engine = QQmlApplicationEngine()

        # 注入 Python 对象到 QML
        self._inject_context()

        # 加载主 QML
        self._load_qml()

        # 设置系统托盘
        self._setup_tray()

        # 设置默认表情
        url = self._emotion_service.get_emotion_url("neutral")
        self._main_model.set_emotion_url(url)

        logger.info("ViewManager: GUI 启动完成")

    def _inject_context(self):
        """注入 Python 对象到 QML 上下文."""
        ctx = self._engine.rootContext()
        ctx.setContextProperty("eventBridge", self._bridge)
        ctx.setContextProperty("activationModel", self._activation_model)
        ctx.setContextProperty("mainModel", self._main_model)
        ctx.setContextProperty("settingsModel", self._ensure_settings_model())
        ctx.setContextProperty("emotionService", self._emotion_service)
        logger.debug("ViewManager: 已注入 QML 上下文对象")

    def _load_qml(self):
        """加载主 QML 文件."""
        qml_dir = Path(__file__).parent / "qml"
        self._engine.addImportPath(str(qml_dir))

        main_qml = qml_dir / "main.qml"
        self._engine.load(QUrl.fromLocalFile(str(main_qml)))

        if not self._engine.rootObjects():
            logger.error("ViewManager: QML 加载失败")
            raise RuntimeError("Failed to load QML")

        logger.debug(f"ViewManager: 已加载 QML: {main_qml}")

    def _setup_tray(self):
        """设置系统托盘."""
        root_objects = self._engine.rootObjects()
        if root_objects:
            self._tray_service = TrayService(root_objects[0])
            self._tray_service.setup(
                on_show=self._show_window,
                on_quit=self._request_quit,
            )

    def _show_window(self):
        """显示主窗口."""
        root_objects = self._engine.rootObjects()
        if root_objects:
            window = root_objects[0]
            window.show()
            window.raise_()
            window.requestActivate()

    def _request_quit(self):
        """请求退出应用."""
        self._tasks.spawn(self._event_bus.emit(Events.UI_QUIT_REQUEST), name="ui:quit_request")

    async def close(self):
        """关闭视图."""
        logger.info("ViewManager: 正在关闭...")
        self._running = False

        if self._tray_service:
            self._tray_service.hide()

        if self._engine:
            self._engine.deleteLater()
            self._engine = None

        logger.info("ViewManager: 已关闭")

    # ========== 公共 API（与 CLI/GPIO ViewManager 对齐的 facade） ==========

    @property
    def activation_model(self) -> ActivationModel:
        """获取激活模型."""
        return self._activation_model

    @property
    def main_model(self) -> MainModel:
        """给 QML 绑的主模型."""
        return self._main_model

    @property
    def is_running(self) -> bool:
        return self._running

    def set_chat_text(self, text: str) -> None:
        self._main_model.set_chat_text(text)

    def set_music_line(self, text: str) -> None:
        self._main_model.set_music_line(text)

    def set_emotion(self, emotion: str) -> None:
        url = self._emotion_service.get_emotion_url(emotion)
        self._main_model.set_emotion_url(url)

    def set_status(self, status: str, connected: bool = True) -> None:
        self._main_model.set_status(status, connected)

    def set_button_text(self, text: str) -> None:
        self._main_model.set_button_text(text)

    def set_auto_mode(self, auto_mode: bool) -> None:
        self._main_model.set_auto_mode(auto_mode)

    def is_auto_mode(self) -> bool:
        return bool(self._main_model._auto_mode)

    @Slot()
    def toggle_mode(self):
        # 真状态在 Session 里改，这里只发事件
        self._tasks.spawn(self._event_bus.emit(Events.UI_AUTO_TOGGLE), name="ui:auto_toggle")

    @Slot()
    def toggle_window(self):
        """切换窗口可见性."""
        root_objects = self._engine.rootObjects() if self._engine else []
        if root_objects:
            window = root_objects[0]
            if window.isVisible():
                window.hide()
            else:
                self._show_window()

    def open_settings(self):
        """打开设置窗口 - 通过信号通知 QML.

        此时才枚举音频设备 / 摄像头（见 SettingsModel.reload），
        避免应用冷启动时 OpenCV 扫 0–9 拖慢首屏。
        """
        if not self._engine:
            logger.warning("ViewManager: 引擎未初始化，无法打开设置")
            return

        # 重新加载配置并按需枚举设备
        self._ensure_settings_model().reload()

        # 通过 EventBridge 信号通知 QML 显示设置窗口
        self._bridge.showSettingsWindow.emit()
        logger.debug("ViewManager: 已发送打开设置窗口信号")

    @property
    def settings_model(self):
        """获取设置模型（懒加载）."""
        return self._ensure_settings_model()

    # ========== 激活相关 ==========

    def _get_activation_code(self) -> str:
        """获取当前激活码."""
        code = self._activation_model.activationCode
        return code if code != "------" else ""

    def set_activation_service(self, service):
        """设置激活服务引用."""
        self._activation_service = service

    def update_activation_device_info(self, serial_number: str = None, mac_address: str = None):
        """更新激活界面的设备信息."""
        self._activation_model.update_device_info(serial_number, mac_address)

    def update_activation_code(self, code: str):
        """更新激活码."""
        self._activation_model.update_activation_code(code)

    def update_activation_status(self, status: dict):
        """根据激活状态更新界面.

        Args:
            status: 包含 local_activated, server_activated, status_consistent 的字典
        """
        local = status.get("local_activated", False)
        server = status.get("server_activated", False)
        consistent = status.get("status_consistent", True)

        if not consistent:
            self._activation_model.set_status_inconsistent(local, server)
        elif local and server:
            self._activation_model.set_status_activated()
        else:
            self._activation_model.set_status_not_activated()

    def on_activation_completed(self, success: bool):
        """激活完成回调."""
        if success:
            self._activation_model.set_status_activated()
        else:
            self._activation_model.set_status_not_activated()
        self._bridge.activationCompleted.emit(success)

    def show_activation_window(self):
        """显示激活窗口."""
        self._bridge.showActivationWindow.emit()
