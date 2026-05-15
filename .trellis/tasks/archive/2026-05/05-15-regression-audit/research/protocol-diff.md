# Research: Protocol Layer Diff (6cad765 vs HEAD)

- **Query**: Compare protocol layer between commit 6cad765 (pre-merge main) and current HEAD; identify root cause of Windows first-connection timeout regression
- **Scope**: internal
- **Date**: 2026-05-15

## Findings

### Files Changed

| File Path | Old (6cad765) | New (HEAD) | Key Changes |
|---|---|---|---|
| `src/protocols/protocol.py` | Pure abstract base — no connection state, no reconnect, no monitor | Concrete base with `_handle_connection_loss`, `_attempt_reconnect`, `_connection_monitor`, `_do_cleanup` template methods; owns `_is_closing`, `_reconnect_attempts`, `_max_reconnect_attempts`, `_auto_reconnect_enabled`, `_connection_monitor_task` | Massive responsibility shift from subclass to base |
| `src/protocols/websocket_protocol.py` | Self-contained: owns all connection state, heartbeat, monitor, reconnect, cleanup | Thin subclass: implements `_is_connected`, `_do_cleanup`, `_monitor_interval`; delegates loss-handling and reconnect to base class | Removed ~200 lines; heartbeat loop removed entirely |
| `requirements.txt` | `websockets==11.0.3` | `websockets>=11.0.3` (installed: **15.0.1**) | Major version jump with breaking behavioral changes |

### Commits Between the Two Points (protocol files only)

```
8ed8b7a fix(audio+protocol): 修复多声道下混失败 + 禁用自动重连
22828de fix: 修复 4 个高优先级问题 — 解耦网络错误依赖、清理空目录、释放 Opus C 资源、移除 WebSocket 冗余心跳
6502550 fix: 修复 MQTT/WSS 通信稳定性并提取协议基类重复代码
22af5da chore: 格式化代码
5cca52f chore: 重构日志模块
```

---

## Critical Difference 1: `websockets` Library Version (11.0.3 -> 15.0.1)

### `open_timeout` is NOT set — defaults to 10 seconds

Neither the old nor the new code passes `open_timeout` to `websockets.connect()`. However:

- **websockets 11.x**: `open_timeout` default was **10 seconds** (same as 15.x), but the connect handshake was simpler.
- **websockets 15.0.1**: `open_timeout` default is **10 seconds**, AND it introduces a **`proxy` parameter that defaults to `True`**.

When `proxy=True`, websockets 15.x **auto-detects system proxy settings** (`HTTP_PROXY`, `HTTPS_PROXY`, `ALL_PROXY` environment variables, and on Windows also reads **IE/system proxy settings via registry**). If a proxy is configured at the OS level but is unreachable or slow, the connection attempt will hang during the proxy negotiation phase until `open_timeout` (10s) expires.

**On Windows specifically**, corporate/enterprise machines often have proxy settings configured in the registry that were never intended for WebSocket traffic. websockets 15.x will attempt to use these proxies, causing the initial handshake to stall.

### Timeline of the breakage

The `requirements.txt` was changed from `websockets==11.0.3` (pinned) to `websockets>=11.0.3` (unpinned floor) during the dependency reorganization. On any fresh install or `pip install --upgrade`, this resolves to websockets 15.0.1, which has the proxy auto-detection behavior.

---

## Critical Difference 2: `_on_network_error` Callback — Sync/Async Mismatch

### Old code (6cad765 — `websocket_protocol.py` owned everything)

All calls to `self._on_network_error(...)` were **synchronous** (no `await`):
```python
# Old websocket_protocol.py lines 143-144, 150-151, 265, 270, 272, 309-310, 316-317, 496-497
self._on_network_error("等待响应超时")
self._on_network_error(f"无法连接服务: {str(e)}")
self._on_network_error(f"连接丢失: {reason}")
```

### New code (HEAD — split between base class and subclass)

The **base class** `protocol.py` now calls `_on_network_error` with **`await`**:
```python
# protocol.py lines 357, 359, 396, 403
await self._on_network_error(f"连接丢失且重连失败: {reason}")
await self._on_network_error(f"连接丢失: {reason}")
await self._on_network_error(f"重连异常: {str(e)}")
```

But the **subclass** `websocket_protocol.py` still calls it **without** `await`:
```python
# websocket_protocol.py lines 128, 135, 338
self._on_network_error("等待响应超时")
self._on_network_error(f"无法连接服务: {str(e)}")
self._on_network_error(f"处理服务器响应失败: {str(e)}")
```

The actual callback registered is `ProtocolTransport._on_network_error` (in `src/core/protocol_manager.py:63`), which is a **sync** function:
```python
def _on_network_error(self, error_message: str = None) -> None:
    if error_message:
        logger.error(f"网络错误: {error_message}")
    asyncio.create_task(self._event_bus.emit(Events.NETWORK_ERROR, error_message))
```

- The subclass calls (sync, no await) work correctly with this sync callback.
- The base class calls (`await self._on_network_error(...)`) will `await None` (the return value of the sync function), which in Python **does not raise** — `await None` is valid. So this is technically not a crash bug, but it IS inconsistent and fragile.

---

## Critical Difference 3: Default Reconnect Behavior Changed

### Old code (6cad765)
```python
# websocket_protocol.py __init__
self._max_reconnect_attempts = 0   # 默认不重连
self._auto_reconnect_enabled = False  # 默认关闭自动重连
```

### New code (HEAD)
```python
# protocol.py __init__
self._max_reconnect_attempts = 5   # 默认重连5次
self._auto_reconnect_enabled = False  # 默认禁用自动重连
```

`_auto_reconnect_enabled` is still `False` by default, and `enable_auto_reconnect()` is never called anywhere in the codebase. So reconnect is effectively disabled. However, `_max_reconnect_attempts` was bumped from 0 to 5, meaning if someone ever sets `_auto_reconnect_enabled = True` without calling `enable_auto_reconnect()`, the behavior silently changed.

---

## Critical Difference 4: Connection Flow Timing

### Old flow (6cad765)

1. `websockets.connect()` — uses websockets 11.0.3; **no proxy detection**; `open_timeout=10s` (default)
2. Start `_message_handler` task
3. Start custom `_heartbeat_loop` (30s interval, 10s ping timeout) — **was already commented out at 6cad765**
4. Start `_connection_monitor` (5s interval, checks `close_code`)
5. Send hello message
6. `asyncio.wait_for(hello_received.wait(), timeout=10.0)`
7. Total worst-case blocking: ~20s (10s open_timeout + 10s hello timeout)

### New flow (HEAD)

1. `websockets.connect()` — uses websockets 15.0.1; **proxy=True (auto-detect)**; `open_timeout=10s` (default)
2. Start `_message_handler` task
3. ~~heartbeat~~ removed
4. Start `_connection_monitor` via base class (5s interval, calls `_is_connected()`)
5. Send hello message
6. `asyncio.wait_for(hello_received.wait(), timeout=10.0)`
7. Total worst-case blocking: ~20s (10s open_timeout + 10s hello timeout)

The connect flow logic itself is nearly identical. The critical difference is in step 1: websockets 15.x proxy auto-detection.

### Caller wraps with another timeout

`ProtocolTransport.connect()` in `src/core/protocol_manager.py:97-126` wraps the entire `open_audio_channel()` call with `asyncio.wait_for(..., timeout=12.0)`. This means:

- If `websockets.connect()` hangs for 10s due to proxy, the hello wait only gets ~2s before the outer 12s timeout kills it
- Or if the proxy hang is slow but not 10s, the remaining time may not be enough for the hello handshake

---

## Critical Difference 5: Heartbeat / Custom Ping Removed

The old code had a custom heartbeat loop (`_heartbeat_loop`) with 30s ping interval and 10s pong timeout. However, at commit 6cad765 it was **already commented out** in `connect()`:
```python
# 注释掉自定义心跳，使用websockets内置的心跳机制
# self._start_heartbeat()
```

The new code simply deleted this dead code. Both versions rely on `websockets.connect(ping_interval=20, ping_timeout=20)` for keepalive. **No behavioral change here.**

---

## Critical Difference 6: Cleanup Method Rename and Responsibility Split

| Aspect | Old | New |
|---|---|---|
| Cleanup method | `_cleanup_connection()` in subclass — clears everything | `_do_cleanup()` in subclass — only protocol-specific resources |
| Connection state reset | `_cleanup_connection()` sets `self.connected = False` | Base `_handle_connection_loss()` sets `self.connected = False` |
| Monitor task cancel | `_cleanup_connection()` cancels monitor task | Base `_handle_connection_loss()` calls `_cancel_monitor_task()` before `_do_cleanup()` |
| `close_audio_channel()` | Calls `_cleanup_connection()` | Manually sets `connected=False`, calls `_cancel_monitor_task()`, then `_do_cleanup()` |

The new `close_audio_channel()` in the subclass does NOT go through `_handle_connection_loss()`, so it manually replicates some of the base class cleanup. This is correct but fragile.

---

## Root Cause Assessment for Windows First-Connection Timeout

**Primary suspect**: `websockets>=11.0.3` resolving to **15.0.1**, which introduces `proxy=True` default. On Windows machines with system proxy settings (common in corporate/enterprise environments), the proxy negotiation hangs until `open_timeout` (10s) expires, causing the "timed out during opening handshake" error.

**Evidence**:
- The `websockets.connect()` call in both old and new code does NOT pass `open_timeout` or `proxy`
- websockets 15.x defaults: `proxy=True`, `open_timeout=10`
- websockets 11.x had no proxy parameter at all
- The error message "timed out during opening handshake" maps exactly to the `open_timeout` expiration in websockets
- The issue is Windows-specific, consistent with Windows system proxy auto-detection

**Fix**: Either pass `proxy=None` to `websockets.connect()` to disable proxy auto-detection, or pin `websockets==11.0.3` in requirements, or set an explicit `open_timeout` with longer duration.

---

## Caveats / Not Found

- Could not directly inspect websockets 15.x source code for proxy implementation details (permission denied for dynamic inspection). The `proxy=True` default and its behavior is confirmed from the function signature.
- The `_on_network_error` sync/await mismatch does not cause a crash but should be harmonized for correctness.
- No MQTT protocol file was analyzed (out of scope for this query).
- The exact commit that changed `websockets==11.0.3` to `websockets>=11.0.3` was not isolated to a single hash; it happened during the dependency reorganization commits.
