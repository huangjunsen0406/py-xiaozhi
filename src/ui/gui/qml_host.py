"""QML 引擎宿主：加载、上下文注入、根窗口操作."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine

from src.logging import get_logger

logger = get_logger()


class QmlAppHost:
    """只负责 QML 引擎生命周期与根对象访问，不碰业务逻辑."""

    def __init__(self) -> None:
        self._engine: QQmlApplicationEngine | None = None

    @property
    def engine(self) -> QQmlApplicationEngine | None:
        return self._engine

    def create_engine(self) -> QQmlApplicationEngine:
        self._engine = QQmlApplicationEngine()
        return self._engine

    def inject_context(self, properties: dict) -> None:
        if not self._engine:
            raise RuntimeError("QML engine not created")
        ctx = self._engine.rootContext()
        for name, obj in properties.items():
            ctx.setContextProperty(name, obj)
        logger.debug("QmlAppHost: 已注入 QML 上下文 %s", list(properties))

    def load_main(self) -> None:
        if not self._engine:
            raise RuntimeError("QML engine not created")
        qml_dir = Path(__file__).parent / "qml"
        self._engine.addImportPath(str(qml_dir))
        main_qml = qml_dir / "main.qml"
        self._engine.load(QUrl.fromLocalFile(str(main_qml)))
        if not self._engine.rootObjects():
            logger.error("QmlAppHost: QML 加载失败")
            raise RuntimeError("Failed to load QML")
        logger.debug("QmlAppHost: 已加载 %s", main_qml)

    def root_window(self):
        if not self._engine:
            return None
        roots = self._engine.rootObjects()
        return roots[0] if roots else None

    def show_root(self) -> None:
        window = self.root_window()
        if window is None:
            return
        window.show()
        window.raise_()
        window.requestActivate()

    def toggle_root_visible(self) -> None:
        window = self.root_window()
        if window is None:
            return
        if window.isVisible():
            window.hide()
        else:
            self.show_root()

    def shutdown(self) -> None:
        if self._engine:
            self._engine.deleteLater()
            self._engine = None
