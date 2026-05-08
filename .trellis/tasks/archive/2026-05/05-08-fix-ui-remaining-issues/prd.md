# 修复 UI 剩余问题

## Goal

修复 UI 模块中的 5 个代码质量问题：None 检查缺失、线程安全、monkey patch、弃用 API、依赖方向。

## Requirements

**R1: `_core_activate()` 未检查 `_service` 为 None**
- 文件：`src/ui/shared/activation.py`
- `BaseActivation._core_activate()` 直接调 `self._service.get_activation_data()` 未检查 None
- 加 `if self._service is None` 守卫，提前返回或抛明确错误

**R2: `gpio/input.py` `_callbacks` 字典无线程保护**
- 文件：`src/ui/gpio/input.py`
- `_callbacks` 在 gpiozero 回调线程中读写，无锁
- 加 `threading.Lock` 保护

**R3: `cli/display.py` monkey patch `logging.Logger.addHandler`**
- 文件：`src/ui/cli/display.py`
- `_remove_stream_handlers()` 全局替换 `Logger.addHandler`，副作用大
- 改用 Filter 或直接操作 root logger handlers 列表

**R4: `EventBridge._emit_event` 使用弃用 `get_event_loop()`**
- 文件：`src/ui/shared/bridge/event_bridge.py`
- 改用 `asyncio.get_running_loop()`

**R5: EventBridge 反向依赖 `UISendTextData`**
- 文件：`src/ui/shared/bridge/event_bridge.py`
- 从 models 层导入数据类违反依赖方向
- 将 `UISendTextData` 移到 `src/ui/shared/events.py`（或就近合适位置）

## Acceptance Criteria

- [ ] `_core_activate()` 有 `_service is None` 守卫
- [ ] `gpio/input.py` `_callbacks` 有锁保护
- [ ] `cli/display.py` 不再 monkey patch `Logger.addHandler`
- [ ] `event_bridge.py` 使用 `get_running_loop()` 而非 `get_event_loop()`
- [ ] `UISendTextData` 移出 event_bridge 的 model 依赖
- [ ] lint / typecheck 通过

## Out of Scope

- SettingsModel 拆分
- QML 命名统一
- 音频测试 sounddevice 线程问题
