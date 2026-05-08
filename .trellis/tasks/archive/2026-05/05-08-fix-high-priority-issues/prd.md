# fix-high-priority-issues

## Goal

修复 reports/00-summary.md 中的 4 个高优先级问题（排除天气 mock，该模块为手写案例代码）。

## What I already know

从报告复检结果和源码阅读中确认：

1. **#3 `_on_network_error` 硬编码依赖** — `container.py:326-335` 的 `_on_network_error` 方法从 `src.ui.shared.events` 直接导入 `UIStatusUpdate` 并 emit `Events.UI_UPDATE_STATUS`，造成 bootstrap → UI 的硬依赖。UIPlugin 当前未订阅 `NETWORK_ERROR`。

2. **#5 calendar/timer 空目录** — `mcp/tools/calendar/` 和 `mcp/tools/timer/` 仅有 `__pycache__/` 残留。

3. **#6 OpusCodec.close() C 资源泄漏** — `opus_codec.py:117-121` 仅将 encoder/decoder 设为 None，依赖 Python GC 通过 `__del__` 释放。opuslib 的 Encoder/Decoder 在 `__del__` 中调用 `opuslib.api.*.destroy()`，但 GC 时机不确定。

4. **#7 WebSocket 心跳冗余** — `websocket_protocol.py` 自定义 `_heartbeat_loop` + websockets 库内置 `ping_interval=20` 形成双重保活，代码冗余。

## Requirements

### #3: 解耦 `_on_network_error` 硬编码依赖
- 从 `container.py` 的 `_on_network_error` 移除 UI 导入和 emit
- 在 `UIPlugin` 中订阅 `NETWORK_ERROR` 事件，更新 UI 状态

### #5: 清理 calendar/timer 空目录
- 删除 `src/mcp/tools/calendar/` 及残留 `__pycache__/`
- 删除 `src/mcp/tools/timer/` 及残留 `__pycache__/`

### #6: 修复 OpusCodec.close() C 资源释放
- 在 `close()` 中显式调用 `opuslib.api.encoder.destroy()` 和 `opuslib.api.decoder.destroy()`

### #7: 移除 WebSocket 冗余心跳
- 移除 `_heartbeat_loop`、`_start_heartbeat`、心跳相关字段
- 移除 `_do_cleanup` 中心跳任务清理
- 移除 `get_connection_info` 中心跳时间戳
- websockets 库内置 ping/pong 保留

## Out of Scope

- 天气 mock 模块（用户手写案例）
- SSL 证书验证（部分修复，剩余 activation/WebSocket 本次不处理）
- efuse.json 加密（严重问题，本次只处理高优先级）

## Technical Notes

- opuslib 未在开发机安装（libopus 缺失），需在代码层面通过 `opuslib.api.encoder.destroy(encoder_state)` 调用
- `import time` 在 websocket_protocol.py 中仅被 `_heartbeat_loop` 使用（`time.time()`），移除心跳后可一并移除
- `UIPlugin` 已有完整的 EventBus 订阅模式，添加 NETWORK_ERROR 订阅风格一致
