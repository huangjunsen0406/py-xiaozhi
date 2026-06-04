# asyncio 规范

> 整个运行时以 asyncio 为底座。GUI 模式跑在 `qasync.QEventLoop`(Qt 兼容的 asyncio loop),CLI / GPIO 模式跑在原生 `asyncio.run(...)`。同一份 async 代码必须在两种模式下都能工作。

本规范是 **标准**。仓库里仍有部分调用点不符合,在下面以反模式形式列出。

---

## 创建任务: 必须可追踪

应用拥有生命周期的任务统一走 **`TaskManager.spawn(coro, name)`**(`src/core/task_manager.py`):

- 把任务放入集合,`cancel_all()` 关闭时统一取消。
- 通过 `add_done_callback` 自动记录异常。
- 在 `request_shutdown()` 之后拒绝新任务。

```python
# 正确 —— 由应用持有,关停时被取消,异常会被记录
self._task_manager.spawn(self._heartbeat_loop(), name="ws:heartbeat")
self._task_manager.spawn(self._event_bus.emit(Events.NETWORK_ERROR, msg), name="emit:network_error")
```

```python
# 错误 —— fire-and-forget;GC 收掉后协程静默消失,
# 没异常日志,关闭时也不会被取消
asyncio.create_task(self._event_bus.emit(Events.NETWORK_ERROR, msg))
```

仓库里目前存在未追踪的 `asyncio.create_task(...)` 调用点:

- `src/core/protocol_manager.py:66, 69, 74, 78`
- `src/ui/gui/manager.py:66, 172, 209`
- `src/ui/cli/manager.py:132-137`
- `src/ui/gpio/manager.py:156-161`

接触到这些文件时,迁移到 `TaskManager.spawn(...)`。`TaskManager` 通过构造器透传,**不要** 通过全局变量取。

### 何时可以裸用 `asyncio.create_task(...)`

只在调用方把返回值存到 `self._xxx_task` 上、并自己负责 await / cancel 时允许。仓库里的合法示例:

- `src/core/task_manager.py:91` —— TaskManager 自身,实现根。
- `src/protocols/websocket_protocol.py:103` `self._message_task = asyncio.create_task(self._message_handler())` —— 在 `disconnect` 里显式 await/cancel。
- `src/audio_codecs/music_decoder.py:125` `self._decode_task = asyncio.create_task(...)` —— 同形态。

如果你不能给出 `self._xxx_task` 引用,**必须** 用 `TaskManager.spawn(...)`。

---

## 拿事件循环

在对象构造时(在 asyncio 线程上)抓一次:

```python
self._loop = asyncio.get_running_loop()
```

这是项目标准,见 `TaskManager.initialize`、`CLIDisplay`、`CLIViewManager`、`GPIOViewManager`、`ProtocolManager`、`ShortcutManager`。

### 禁止: `asyncio.get_event_loop()`

Python 3.10+ 起,无运行 loop 时该 API 已被弃用,3.12 起更不再自动创建。仓库里仍出现在:

- `src/ui/shared/bridge/event_bridge.py:53`
- `src/ui/gui/activation.py:41`

二者都需要改为构造时抓 loop;在 slot / callback / 非 async 方法里读 `self._loop`。

### 禁止: `asyncio.ensure_future(...)`

用 `asyncio.create_task(coro)`(实现根)或 `TaskManager.spawn(coro, name)`(其余位置)。`ensure_future` 接收任意 awaitable,曾经因为静默包装非协程导致问题。

仓库里目前在 `src/ui/shared/bridge/event_bridge.py:55`,接触时替换。

---

## 跨线程桥

合法的"非 loop 线程进入 asyncio"场景就三类:

| 外部线程 | 位置 | 桥 |
|---|---|---|
| pynput / lgpio 按键监听 | `src/plugins/shortcuts/*`、`src/ui/gpio/*` | 协程: `asyncio.run_coroutine_threadsafe(coro, loop)`;同步: `loop.call_soon_threadsafe(fn, *args)` |
| 音频设备探测(`threading.Thread`) | `src/ui/shared/models/settings_model.py` | 线程 → emit Qt `Signal` 给 GUI 线程 |
| Qt slot 在非 GUI 线程触发(罕见) | — | emit `Signal`(Qt 自动 queued connection),**不要** 直接调 asyncio |

```python
# 正确 —— 从非 loop 线程把协程调度到 asyncio loop
asyncio.run_coroutine_threadsafe(self._event_bus.emit(event, data), self._loop)
```

```python
# 正确 —— Qt slot 跑在 GUI 线程(qasync 下就是 loop 线程),
# 可以直接 TaskManager.spawn,因为已经在 loop 上
self._task_manager.spawn(self._event_bus.emit(event, data), name="ui:event")
```

```python
# 错误 —— 在 worker 线程里调 create_task(那线程上没有运行 loop)
def worker_thread_callback():
    asyncio.create_task(some_coro())   # RuntimeError: no running event loop
```

"调度一个同步 callable,callable 内部启动协程"这种习惯用法,项目已经有验证过的实现 `TaskManager.schedule_nowait`,优先用它,不要自行手写 `call_soon_threadsafe(lambda: create_task(...))`。

---

## 同步原语

| 原语 | 何时用 | 参考 |
|---|---|---|
| `asyncio.Lock` | 协程之间互斥。"同一时刻只能一个协程"的默认选择。 | `EventBus._lock`、`StateManager._lock`、`ProtocolManager._connect_lock` |
| `asyncio.Queue` | 协程间生产者/消费者。 | `CLIDisplay._command_queue`、`MusicDecoder` PCM 流 |
| `asyncio.Event` | 生命周期 / 关停信号。 | `TaskManager._shutdown_event` |
| `threading.Lock` | **仅** 当数据被非 loop 线程访问(音频 worker、sherpa-onnx 回调)。 | `AudioCodec._listeners_lock`、`WakeWordDetect._onnx_lock`、`Camera._lock` |

不要混用: 永远不在 async 协程和外部线程之间共享同一个 `asyncio.Lock`。如果数据两边都访问,改设计或者用 `threading.Lock` —— 但持有 `threading.Lock` 时不能 `await`。

---

## 并发: gather

并行启动同辈协程: `asyncio.gather(*coros, return_exceptions=True)`。**默认带** `return_exceptions=True` —— 一个失败不应取消兄弟任务,这是项目惯例(见 `EventBus.emit`、`TaskManager.cancel_all`)。

```python
await asyncio.gather(
    *[self._safe_call(handler, data) for handler in handlers],
    return_exceptions=True,
)
```

**仅在** 想要 fail-fast(首个异常取消兄弟任务)时用裸 `gather(*coros)`,且必须在注释里说明为什么。

---

## 取消

- 协程必须能被取消。需要释放资源时 `try/finally`。
- 不要静默吞 `asyncio.CancelledError`。如果接住了就 re-raise:

  ```python
  try:
      await something()
  except asyncio.CancelledError:
      raise
  except Exception as e:
      logger.error(f"...: {e}", exc_info=True)
  ```

- 关停统一走 `TaskManager.cancel_all()`,它已经做了 gather + `return_exceptions=True`。不要自己迭代 `_tasks` 重写一遍。

---

## 睡眠与超时

- `await asyncio.sleep(seconds)` —— async 代码里 **绝不允许** `time.sleep`。
- 限时操作: `async with asyncio.timeout(seconds):`(Python 3.11+)或 `asyncio.wait_for(coro, timeout=seconds)`。**不要** 手写 `while True: await asyncio.sleep(0.1); if ...: break`。

---

## async 与 Qt 的特殊情况

GUI 模式下 asyncio loop **就是** Qt event loop(`qasync.QEventLoop`)。后果:

- Qt slot 跑在 loop 线程,**可以** 直接 `TaskManager.spawn(...)`。但 slot 自身是同步的,**不能** `await`。
- slot 里 `asyncio.create_task` 在技术上能跑(我们已经在 loop 上),但仍优先 `TaskManager.spawn`,得到追踪。
- `qasync` 关停时抛出的 `RuntimeError("Event loop stopped before Future completed")` 是 **正常情况** —— `main.py` 已经过滤。如果你嵌入自己的 `loop.run_until_complete(...)`,沿用同一过滤。

**整个进程只有一个 loop**。不要 `asyncio.new_event_loop()`。

---

## 禁止

- `asyncio.get_event_loop()`(已弃用,改在 `__init__` 里抓)。
- `asyncio.ensure_future(...)`(用 `create_task` 或 `TaskManager.spawn`)。
- 实现根之外的未追踪 `asyncio.create_task(...)`。
- async 函数里的 `time.sleep(...)`。
- 跨线程共用 `asyncio.Lock`。
- 静默吞 `asyncio.CancelledError`。
- `loop = asyncio.new_event_loop()`(已经有 qasync 或 `asyncio.run` 创建好了)。

---

## 回调注册: async/sync 必须与调用方一致

`Protocol` 基类 (`src/protocols/protocol.py`) 定义了回调接口 (`_on_network_error`, `_on_audio_channel_opened` 等)。子类和 `ProtocolTransport` 注册回调，基类负责调用。**注册方和调用方对签名的假设必须一致**，否则运行时崩溃。

### 规则

1. **先看调用方**：打开基类/调用方代码，确认每个回调是 `await` 调用还是直接调用。
2. **注册方匹配**：
   - 调用方用 `await` → 注册 `async def`，内部用 `await`（不用 `create_task` 逃逸）
   - 调用方不用 `await` → 注册 `def`，内部用 `asyncio.create_task` 或 `run_coroutine_threadsafe`
3. **所有子类调用点统一**：websocket 和 mqtt 协议子类中对同一回调的调用方式必须与基类约定一致。

### 正确示例

```python
# 基类 (protocol.py) —— 调用方用 await
async def _handle_connection_loss(self, reason: str):
    if self._on_network_error:
        await self._on_network_error(f"连接丢失: {reason}")  # ← await

# ProtocolTransport —— 注册方必须是 async def
async def _on_network_error(self, error_message: str = None) -> None:
    if error_message:
        logger.error(f"网络错误: {error_message}")
    await self._event_bus.emit(Events.NETWORK_ERROR, error_message)  # ← await

# websocket_protocol.py —— 子类调用点也要 await
if self._on_network_error:
    await self._on_network_error("等待响应超时")  # ← await，不是直接调用
```

```python
# mqtt_protocol.py —— 跨线程场景，用 create_task 包装
self.loop.call_soon_threadsafe(
    lambda: asyncio.create_task(                 # ← create_task 包装
        self._on_network_error(error_msg)
    )
)
```

### 错误示例

```python
# 错误 —— 基类 await 了，但注册方是 sync def
def _on_network_error(self, error_message: str = None) -> None:
    asyncio.create_task(...)      # 返回 None
# → await None → TypeError: object NoneType can't be used in 'await' expression

# 错误 —— 注册方改为 async def 后，子类调用点没加 await
if self._on_network_error:
    self._on_network_error("超时")  # 返回 coroutine 但未等待
# → RuntimeWarning: coroutine was never awaited，错误通知静默丢失

# 错误 —— call_soon_threadsafe 里直接返回协程
self.loop.call_soon_threadsafe(
    lambda: self._on_network_error(error_msg)  # lambda 返回 coroutine，永不执行
)
```

### 现有回调矩阵

| 回调 | 基类调用方式 | ProtocolTransport 注册 | websocket 调用 | mqtt 调用 |
|------|-------------|----------------------|---------------|----------|
| `_on_network_error` | `await` | `async def` + `await` | `await` | `await` 或 `create_task`(跨线程) |
| `_on_audio_channel_opened` | `await` | `async def` + `await` | `await` | `create_task`(跨线程) |
| `_on_audio_channel_closed` | `await` | `async def` + `await` | `await` | `await` 或 `run_coroutine_threadsafe` |
| `_on_incoming_json` | 直接调用 | `def` + `create_task` | 直接调用 | 直接调用(跨线程) |
| `_on_incoming_audio` | 直接调用 | `def` + `create_task` | 直接调用 | 直接调用(跨线程) |
| `_on_connection_state_changed` | 直接调用 | 未注册(保持 `None`) | 直接调用 | 直接调用 |
| `_on_reconnecting` | 直接调用 | 未注册(保持 `None`) | — | — |

> **新增回调时**：先决定调用约定（`await` vs 直接），在上表中注册，确保 3 层（基类、ProtocolTransport、子类）一致。

---

## 容器禁止直接访问插件内部属性

`ServiceContainer` 不应直接引用插件实例的内部属性（如 `self.audio_codec`）。插件实例由 `PluginManager` 管理，通过 `get_plugin(name)` 获取。

```python
# 正确 —— 通过 PluginManager 获取，带 None 检查
audio_plugin = self.plugins.get_plugin("audio")
if audio_plugin and audio_plugin.codec:
    await audio_plugin.codec.clear_audio_queue()

# 错误 —— 直接访问不存在的属性
await self.audio_codec.clear_audio_queue()
# → AttributeError: 'ServiceContainer' object has no attribute 'audio_codec'
```

---

## 参考文件

- `src/core/task_manager.py` —— `spawn`、`schedule_nowait`、`cancel_all`、`request_shutdown`。
- `src/core/event_bus.py` —— `emit` + `gather(..., return_exceptions=True)` 模板。
- `src/core/protocol_manager.py` —— `_connect_lock` 生命周期 + 当前需要迁移的 emit pattern。
- `src/protocols/websocket_protocol.py`、`mqtt_protocol.py` —— 长生命周期任务通过 `self._xxx_task` 持有的范本。
- `src/plugins/shortcuts/__init__.py` —— 外部线程下的 `run_coroutine_threadsafe` 范本。
