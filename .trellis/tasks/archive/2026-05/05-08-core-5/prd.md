# 修复 core/ 模块 5 个已知问题

## 背景
`reports/core.md` 中列出了 6 个潜在问题，其中 #3 已修复，剩余 5 个需要在本次修复。

## 问题清单

### #1 EventBus._lock 死代码
- **文件**: `src/core/event_bus.py`
- **现状**: `self._lock = asyncio.Lock()` 定义后从未在 `on()`/`off()`/`clear()` 中使用
- **修复**: 移除未使用的 `_lock` 定义（asyncio 单线程模型下不需要锁）

### #2 ProtocolTransport.is_audio_channel_opened 静默吞异常
- **文件**: `src/core/protocol_manager.py`
- **现状**: `except Exception: return False` 吞掉所有异常
- **修复**: 记录异常日志后再返回 False

### #4 TaskManager.spawn 返回 None
- **文件**: `src/core/task_manager.py`
- **现状**: 关闭期间 spawn 返回 None
- **修复**: 此为有意设计（返回类型已标注 Optional），无需代码改动。如需感知失败，调用方应检查返回值。

### #5 ProtocolGateway.send_audio 静默失败
- **文件**: `src/core/protocol_manager.py`
- **现状**: 通道未打开时静默 return
- **修复**: 添加 debug 级别日志记录通道未打开的情况

### #6 emit 时 handler 列表无快照保护
- **文件**: `src/core/event_bus.py`
- **现状**: `emit()` 和 `emit_sequential()` 直接迭代 `self._handlers.get(event, [])`
- **修复**: asyncio 单线程模型 + `for` 循环无 await 点，实际无竞态风险。任务列表已在 await 前构建完成，当前实现安全。可在 `emit` 中做浅拷贝增加防御性。

## 修复范围
- `src/core/event_bus.py` — #1, #6
- `src/core/protocol_manager.py` — #2, #5
- `src/core/task_manager.py` — #4 无需改动
