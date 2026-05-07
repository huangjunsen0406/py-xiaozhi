# 错误处理

> 普通的 try/except。**不存在** 项目级的自定义异常体系。新写代码沿用仓库已有的模式,不要新立一套。

---

## 不引入自定义异常类

仓库 **没有** 项目级异常层级。功能任务里也别加。直接抛 stdlib 异常(`ValueError`、`RuntimeError`、`FileNotFoundError`、`ImportError`...),在失败有意义的边界处接住。

如果确实需要某个类型化信号做控制流(很少见),把它 **限制在抛出 + 处理的同一个模块内**。

---

## 三种实际在用的模式

### 1. 边界捕获 + 完整堆栈

顶层操作失败要可见。一定带 `exc_info=True`。

```python
# main.py — handle_activation
try:
    activation_service = await ActivationService.get_instance()
    init_result = await activation_service.initialize()
    ...
except Exception as e:
    logger.error(f"激活流程异常: {e}", exc_info=True)
    return False
```

```python
# src/ui/shared/models/settings_model.py
try:
    ...
except Exception as e:
    logger.error(f"保存唤醒词失败: {e}", exc_info=True)
```

适用: 生命周期入口、请求/事件 handler、丢失堆栈会让人无法调试的位置。

### 2. 软警告(降级路径)

可恢复的非关键路径。**不带** `exc_info`。

```python
# src/plugins/mcp.py
try:
    music_player.set_event_bus(ctx.event_bus)
    logger.info("MusicPlayer EventBus 已注入")
except Exception as e:
    logger.warning(f"设置 MusicPlayer EventBus 失败: {e}")
```

适用: 可选集成、第三方回调、shutdown 阶段不该掩盖原错的清理动作。

### 3. 静默吞(谨慎)

少量调用点静默吞异常,因为契约就是"尽力而为,不冒泡":

```python
# src/plugins/mcp.py — on_incoming_json
try:
    if message.get("type") == "mcp":
        ...
        await self._server.parse_message(payload)
except Exception:
    pass
```

```python
# main.py — SIGTRAP 信号安装
try:
    if hasattr(signal, "SIGTRAP"):
        signal.signal(signal.SIGTRAP, signal.SIG_IGN)
except Exception:
    pass
```

只在以下条件全满足时用:

- 调用方对错误不可能做出有意义反应。
- 每次重试都打日志会显著拖慢 UX。
- 有注释或结构性原因说明吞掉是安全的(信号 handler、插件隔离)。

拿不准时优先选 #2(warning),不选 #3。

---

## 插件 / 生命周期隔离

`PluginManager`(`src/plugins/manager.py`)会主动隔离插件失败: 一个插件 `setup_all` / `start_all` 失败 **不应** 中断其他插件。写插件时正常抛即可,manager 在边界已经接住。**不要** 在 `setup` 里再嵌一层 try/except 把自己的错误吞掉。

---

## 禁止

- `except: pass`(裸 except)—— 至少 `except Exception:`,不能吞 `KeyboardInterrupt` / `SystemExit`。仓库里所有 except 都用 `except Exception:`。
- `logger.exception(...)` —— 仓库里 **完全不用**。统一 `logger.error(..., exc_info=True)`。功能等价,但保持一致让 grep 可靠。
- 把原异常重新包装成新的 `Exception("something failed")` 丢失原始信息。要传播就 `raise`(re-raise),要重抛就 `raise NewError(...) from e`。

---

## Async 错误

`async def` 里的异常传播跟同步代码相同。`asyncio.gather(...)` 加 `return_exceptions=True` 仅在你 **明确想看每一个结果** 时使用;否则第一个异常会取消兄弟任务,这通常是生命周期 fail-fast 想要的语义。

`main.py` 里 qasync GUI loop 与 asyncio 接驳的代码,把 `RuntimeError("Event loop stopped before Future completed")` 当作 **正常退出** 处理 —— 见 `main.py` 里的 `RuntimeError` 分支。如果你新增类似桥,沿用同一过滤。
