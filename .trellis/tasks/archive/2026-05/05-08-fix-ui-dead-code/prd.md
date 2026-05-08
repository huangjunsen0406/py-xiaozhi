# 清理 UI 模块死代码与 asyncio.create_task 保护

## Goal

删除 UI 模块中的死代码，修复 `asyncio.create_task` 未持有引用问题。

## Requirements

**R1: 删除 EventBridge 死代码**
- 文件：`src/ui/shared/bridge/event_bridge.py`
- 删除 4 个零调用方法：`emit_status()`, `emit_emotion()`, `emit_text()`, `emit_mode()`（line 159-173）
- 删除 4 个未被发射的 Signal：`statusChanged`, `emotionChanged`, `textChanged`, `modeChanged`
- 删除未使用的 `_pending_events` 列表（line 46）

**R2: 删除 shared/platform/ 死代码**
- `src/ui/shared/platform/macos.py` — 空实现 pass，`apply_window_effects` 无调用方
- `src/ui/shared/platform/__init__.py` — 移除死导出
- 如整个 `platform/` 子模块变为空，可考虑删除目录

**R3: `asyncio.create_task` → `TaskManager.spawn()`**
- `src/ui/gui/manager.py:66` — `_on_config_saved` 中无引用 task
- `src/ui/gui/manager.py:172` — 同样问题
- `src/ui/gui/manager.py:209` — 同样问题
- 改用 `TaskManager.spawn()` 确保 task 被引用且异常可追踪

## Acceptance Criteria

- [ ] `emit_status/emotion/text/mode` 方法已删除
- [ ] 未使用的 Signal 已删除
- [ ] `_pending_events` 已删除
- [ ] `shared/platform/` 死代码已清理
- [ ] `asyncio.create_task` 三处已改为 `TaskManager.spawn()`
- [ ] lint / typecheck 通过

## Out of Scope

- SettingsModel 拆分
- MVVM 数据流重构
- `get_event_loop()` 迁移

## Technical Notes

- 验证：所有删除项已通过 grep 确认零外部调用
- `TaskManager.spawn()` 来自 `src.core.task_manager`
