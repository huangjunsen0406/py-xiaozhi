# PySide6 / QML 规范

> GUI 模式运行 PySide6 + QtQuick(QML),由 `qasync` 提供 asyncio 兼容的事件循环。CLI / GPIO 模式不加载任何 Qt 代码。Qt 相关代码全部在 `src/ui/` 与 `src/views/` 下。

本规范是 **标准**。`src/ui/shared/` 下若干旧文件早于这套规则,需要在接触时一并清理 —— 不允许在新代码里复刻。

---

## 架构 (V → VM → Bus)

```
QML (View)
  ↕  (signal、contextProperty、slot 调用)
ViewModel  (QObject + Signal + @Property)         ← src/ui/shared/models/
  ↕  (set_xxx → emit *Changed)
EventBridge (QObject)                             ← src/ui/shared/bridge/event_bridge.py
  ↕  (loop.call_soon_threadsafe → EventBus.emit)
EventBus (asyncio)                                ← src/core/event_bus.py
  ↕
Plugin / 核心服务
```

三个角色的职责不可破:

- **ViewModel** 只持有状态,通过 `@Property` 暴露给 QML。无业务逻辑、无 I/O。
- **EventBridge** 把 QML slot 调用翻译成 EventBus 事件,反向同理。无状态。
- **ViewManager**(`src/ui/gui/manager.py`)持有 QML 引擎、注册 context object、串起 bridge。

**不要** 在 Qt slot 里 `await ...`。**不要** 在 ViewModel 里 `EventBus.emit(...)`。**不要** 在 `src/core/`、`src/plugins/`、`src/protocols/`、`src/audio_*/`、`src/mcp/` 里 `import PySide6.*`。

---

## ViewModel 规则

ViewModel 在 `src/ui/shared/models/`,继承 `BaseModel`(`src/ui/shared/models/base_model.py`)。

### 用 `@Property`,不要用 `@property`

QML 只能看到通过 PySide6 `Property` 暴露的属性。Python 内置 `@property` 装饰器对 QML **不可见**。

```python
# 正确 —— QML 读 mainModel.ttsText,绑定到 ttsTextChanged
@Property(str, notify=ttsTextChanged)
def ttsText(self) -> str:
    return self._tts_text
```

```python
# 错误 —— QML 看不到任何东西
@property
def loading(self) -> bool:        # src/ui/shared/models/base_model.py:19  (遗留)
    return self._loading
```

`BaseModel.loading` 当前用 Python `@property`,这是反面教材。新增 ViewModel 属性必须 `@Property(type, notify=signal)`。

### Setter 约定

每个 `@Property` 配套:

1. 后备字段 `_xxx`。
2. 信号 `xxxChanged = Signal()`。
3. 显式 setter `set_xxx(value)`,内部:
   - 先比较再赋值: `if self._xxx != value:`,避免 QML 收到无意义变更。
   - 更新字段。
   - emit 信号。

参考 `MainModel.set_tts_text`、`set_status`(`src/ui/shared/models/main_model.py`)。

### 信号命名

- ViewModel 通知信号: `xxxChanged`(camelCase)。作为 `@Property` 的 `notify=` 参数。
- EventBridge 上的跨域信号: 同样 camelCase(`statusChanged`、`showSettingsWindow`)。
- 用 `arguments=[...]` 让 QML 绑定到具名参数: `Signal(str, bool, arguments=["status", "connected"])` —— 见 `EventBridge.statusChanged`。

### 不暴露可变结构

`@Property` 的 getter **不要** 返回可变 list/dict 而不拷贝 —— QML 可能持有引用。返回不可变值(`str`、`int`、`bool`、`tuple`)或 deep copy。

---

## Slot 规则

```python
@Slot()                # 无参
@Slot(str)             # 一个 string 参数
@Slot(str, result=bool)  # 参数 + 返回类型(QML 读返回值时)
def onSendText(self, text: str) -> bool: ...
```

- 凡是 QML 调用的方法都必须装饰 `@Slot`。不装饰在简单场景能跑,但 signal/connection / 跨线程时会出问题。
- Slot 体是 **同步** 的,跑在 Qt 线程上。**不要** 在里面 `await`。需要 async 工作时走下面的桥模式。

---

## QML ↔ asyncio 桥

### Qt slot → EventBus

`EventBridge` 是 Qt 回调进入 asyncio loop 的 **唯一** 路径。期望模式:

```python
class EventBridge(QObject):
    def __init__(self, event_bus: EventBus, loop: asyncio.AbstractEventLoop, parent=None):
        super().__init__(parent)
        self._event_bus = event_bus
        self._loop = loop                # 构造时在 asyncio 线程上抓

    def _emit_event(self, event: str, data=None):
        if self._loop.is_closed():
            return
        # call_soon_threadsafe → EventBus.emit 在 asyncio 线程上跑
        self._loop.call_soon_threadsafe(
            lambda: tasks.spawn(self._event_bus.emit(event, data), name=f"bridge:{event}")
        )
```

当前 `event_bridge.py:49-62` 在 `QTimer.singleShot(0, ...)` 内调 `asyncio.get_event_loop()` + `asyncio.ensure_future()`,两者都被弃用。接触此文件时迁移: 构造时抓 loop,通过 `loop.call_soon_threadsafe` 调度,任务用 `TaskManager.spawn(...)` 创建(详见 `asyncio-guidelines.md`)。

### asyncio → QML

QML **绝不** 直接 await 协程。asyncio 侧调用 `viewmodel.set_xxx(...)`(同步)→ ViewModel emit Qt `Signal` → Qt 队列连接送到 GUI 线程。

`ViewManager` 里的 async EventBus handler 沿用此模式:

```python
async def _on_update_text(self, data):                  # asyncio 侧
    text = data.text if hasattr(data, "text") else str(data)
    self._main_model.set_tts_text(text)                 # 同步 VM 调用 → emit Signal
```

**不要** 从非 GUI 线程的 `async def` 里直接调 QML / `QQmlApplicationEngine` API。停留在 asyncio 线程,改 ViewModel,让信号去带变更。

---

## QML 加载与 context

`ViewManager` 与 `GUIActivation` 各自持有 engine:

```python
self._engine = QQmlApplicationEngine()

ctx = self._engine.rootContext()
ctx.setContextProperty("eventBridge", self._bridge)
ctx.setContextProperty("mainModel", self._main_model)
ctx.setContextProperty("settingsModel", self._settings_model)

qml_dir = Path(__file__).parent / "qml"
self._engine.addImportPath(str(qml_dir))
self._engine.load(QUrl.fromLocalFile(str(qml_dir / "main.qml")))

if not self._engine.rootObjects():
    raise RuntimeError("Failed to load QML")
```

规则:

- QML 路径从 `Path(__file__).parent / "qml"` 解析,保证 PyInstaller 打包后能找到。**不要** 写绝对路径或 `os.getcwd()`。
- `load()` 之后必须检查 `engine.rootObjects()`;失败抛 `RuntimeError`(现有代码已经这么做,保持)。
- 所有需要的对象都在 `load()` **之前** 经 `setContextProperty` 注入。load 后再加 context property 不可靠。
- 由 QML 内部实例化的类型用 `qmlRegisterType(...)`;Python 侧创建的单例用 `setContextProperty(...)`。当前代码全用 `setContextProperty` —— ViewModel 这样可以接受。

---

## 生命周期与所有权

- QObject 子对象有 parent 时通过 `parent=` 传(`__init__(self, ..., parent: Optional[QObject] = None)`,匹配 `EventBridge`、`GUIActivation`)。
- 关停时用 `engine.deleteLater()` + `engine = None`,**不要** `del`。见 `ViewManager.close()`。
- 已经 `setContextProperty` 注入的 ViewModel,Python 侧 **不要** 再持长引用 —— Qt 已经通过 engine 持有。

---

## 线程与 Qt

- 在 qasync 下,GUI 线程 **就是** asyncio loop 线程。只有 Qt 之外的工作线程(pynput / lgpio backend、音频 worker、`settings_model.py` 里设备探测起的 `threading.Thread`)才需要跨线程桥。
- 非 GUI 线程 **绝不** 直接调 Qt 方法。要么:
  - emit Qt `Signal`(Qt 自动 queued connection);或
  - `loop.call_soon_threadsafe(...)` 弹回 asyncio/GUI 线程。
- `QTimer.singleShot(0, fn)` **不会** 让 `fn` 跨线程安全。它在 QObject 自己的线程上调度。

---

## Qt 代码禁止

- `# -*- coding: utf-8 -*-` 头 —— Python 3 默认 UTF-8。`src/ui/shared/` 下大量遗留,接触即删。
- slot / callback 里的 `asyncio.get_event_loop()`。改成 `__init__` 抓。
- `asyncio.ensure_future(coro)` —— 用 `TaskManager.spawn(coro, name)`。
- 暴露给 QML 的类用 `@property`(QML 看不到)。
- 非 UI 包 import `PySide6`。
- 用 `qApp.processEvents()` "刷新" Qt 等 asyncio。qasync loop 已经在泵 Qt 事件。

---

## 参考文件

- `src/ui/gui/manager.py` —— `ViewManager`,引擎装配的标准范本。
- `src/ui/gui/activation.py` —— 第二个 engine 实例(独立窗口)。
- `src/ui/shared/bridge/event_bridge.py` —— bridge 模式(当前代码需要按上文清理)。
- `src/ui/shared/models/base_model.py`、`main_model.py`、`activation_model.py`、`settings_model.py` —— ViewModel 模式。
- `src/ui/gui/services/` —— 仅 Qt 用的服务(托盘、表情)。
