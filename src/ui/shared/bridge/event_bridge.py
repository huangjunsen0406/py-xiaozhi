"""EventBus 桥接器 - Python 信号与 QML 信号双向转换."""

import asyncio
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication

from src.core.event_bus import EventBus, Events
from src.logging import get_logger

logger = get_logger()


class EventBridge(QObject):
    """EventBus 与 QML 的双向桥接.

    QML → Python: QML 调用 slot，slot 内部 emit EventBus 事件
    Python → QML: EventBus 事件触发 Python Signal，QML 连接该 Signal
    """

    # ========== Python → QML 信号 ==========

    # 窗口控制
    showWindow = Signal()
    hideWindow = Signal()
    showSettingsWindow = Signal()  # 显示设置窗口
    showActivationWindow = Signal()  # 显示激活窗口

    # 激活相关
    activationCompleted = Signal(bool, arguments=["success"])

    # ========== 构造 ==========

    def __init__(self, event_bus: EventBus, parent: QObject | None = None):
        super().__init__(parent)
        self._event_bus = event_bus
        self._activation_code_getter: Callable[[], str] | None = None

    def _emit_event(self, event: str, data=None):
        """安全地发射 EventBus 事件，使用 QTimer 在主线程中调度."""
        def do_emit():
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(self._event_bus.emit(event, data))
                else:
                    logger.warning(f"EventBridge: 事件循环未运行，跳过事件 {event}")
            except Exception as e:
                logger.warning(f"EventBridge: 发射事件 {event} 失败: {e}")

        # 使用 QTimer.singleShot 确保在 Qt 事件循环中执行
        QTimer.singleShot(0, do_emit)

    # ========== QML → Python (Slots) ==========

    @Slot()
    def onButtonPress(self):
        """手动模式按钮按下."""
        logger.debug("EventBridge: 按钮按下")
        self._emit_event(Events.UI_BUTTON_PRESS)

    @Slot()
    def onButtonRelease(self):
        """手动模式按钮释放."""
        logger.debug("EventBridge: 按钮释放")
        self._emit_event(Events.UI_BUTTON_RELEASE)

    @Slot()
    def onManualToggle(self):
        """手动模式录音切换（点击开始/停止）."""
        logger.debug("EventBridge: 手动录音切换")
        self._emit_event(Events.UI_MANUAL_TOGGLE)

    @Slot()
    def onAutoToggle(self):
        """自动模式切换."""
        logger.debug("EventBridge: 自动模式切换")
        self._emit_event(Events.UI_AUTO_TOGGLE)

    @Slot()
    def onAutoStart(self):
        """自动模式开始监听."""
        logger.debug("EventBridge: 自动模式开始监听")
        self._emit_event(Events.UI_AUTO_START)

    @Slot()
    def onAbort(self):
        """中断请求."""
        logger.debug("EventBridge: 中断请求")
        self._emit_event(Events.UI_ABORT_REQUEST)

    @Slot(str)
    def onSendText(self, text: str):
        """发送文本."""
        if text.strip():
            logger.debug(f"EventBridge: 发送文本: {text[:20]}...")
            from src.ui.shared.models.main_model import UISendTextData
            self._emit_event(Events.UI_SEND_TEXT, UISendTextData(text=text))

    @Slot()
    def onQuitRequest(self):
        """退出请求."""
        logger.info("EventBridge: 退出请求")
        self._emit_event(Events.UI_QUIT_REQUEST)

    @Slot()
    def onOpenSettings(self):
        """打开设置窗口 - 直接发射信号到 QML."""
        logger.debug("EventBridge: 打开设置窗口")
        self.showSettingsWindow.emit()

    # ========== 激活相关 Slots ==========

    @Slot()
    def copyActivationCode(self):
        """复制激活码到剪贴板."""
        if self._activation_code_getter:
            code = self._activation_code_getter()
            if code:
                clipboard = QGuiApplication.clipboard()
                clipboard.setText(code)
                logger.info(f"EventBridge: 已复制激活码: {code}")

    @Slot()
    def openActivationUrl(self):
        """打开激活页面."""
        from src.utils.config_manager import ConfigManager

        try:
            config = ConfigManager.get_instance()
            url = config.get_config("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")
            if url:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices

                QDesktopServices.openUrl(QUrl(url))
                logger.info(f"EventBridge: 已打开激活页面: {url}")
            else:
                logger.warning("EventBridge: 未配置激活 URL")
        except Exception as e:
            logger.error(f"EventBridge: 打开激活页面失败: {e}")

    def set_activation_code_getter(self, getter: Callable[[], str]):
        """设置激活码获取函数."""
        self._activation_code_getter = getter

    # ========== Python → QML (发射信号) ==========
