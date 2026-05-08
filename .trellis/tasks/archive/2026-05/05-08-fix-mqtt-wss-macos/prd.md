# 修复 macOS MQTT/WSS 通信不稳定的问题

## Goal

修复 macOS 上 MQTT 通信"偶尔可以、有时候没声音，特别是带耳机时"的问题。同时清理两个协议文件中的已知缺陷。

## What I already know

* 用户反馈：macOS 上 MQTT 偶尔正常、有时完全没声音，插耳机时更容易出现
* 已经审查完 `src/protocols/` 下 3 个文件（~3000 行）
* 已经审查完 `src/audio_codecs/audio_codec.py` 和 `src/utils/audio_device.py`

## Root Causes Identified

### 通信层（按影响程度排序）

**1. MQTT `loop_forever()` 阻塞事件循环（严重）**

`mqtt_protocol.py:676` 和 `:733`：
```python
self.mqtt_client.loop_forever()  # 阻塞调用！在 asyncio 线程上运行会冻结整个事件循环
```
paho-mqtt 的 `loop_forever()` 会进入无限阻塞循环。当 `_handle_goodbye()` 或 `__del__()` 中调用时，如果在 asyncio 线程上执行，整个 app 冻结。

**2. 自动重连默认关闭**

`mqtt_protocol.py:34-35`：
```python
self._max_reconnect_attempts = 0  # 默认不重连
self._auto_reconnect_enabled = False
```
MQTT 是长连接，但自动重连默认关闭。如果网络抖动断开，连接不会自动恢复，用户感知就是"突然没声音了"。WebSocket 同样问题。

**3. UDP socket 未绑定**

`mqtt_protocol.py:340`：
```python
self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# 没有 bind(('0.0.0.0', 0))
```
未绑定的 UDP socket 在某些 macOS 网络配置下（特别是插耳机后音频设备切换触发 CoreAudio 路由变化时）可能导致数据包被防火墙/路由丢弃。

**4. `print()` 调试遗留**

`mqtt_protocol.py:106`：`print(mqtt_config)` — 应改为 logger。

**5. 两个协议 80% 重复的重连/监控/清理逻辑**

`mqtt_protocol.py` 和 `websocket_protocol.py` 中 `_handle_connection_loss`、`_attempt_reconnect`、`_connection_monitor`、`_cleanup_connection` 几乎完全相同。

### macOS 音频层（辅助因素）

**6. 设备按名称保存，插拔耳机时名称可能不匹配**

`audio_device.py:103-108`：设备配置按名称保存。macOS 插拔耳机时audio device 列表变化，设备名称可能不完全一致（如 "External Headphones" vs "USB Audio Device"），导致 `find_device_by_name` 失败，自动 fallback 到默认设备，但如果默认设备选择逻辑有问题则可能出现无声音。

## Requirements

### MVP（必须修复）

1. 移除 MQTT `loop_forever()` 阻塞调用，用非阻塞替代
2. 启用 MQTT 和 WebSocket 自动重连（合理默认值：5 次，指数退避）
3. UDP socket 显式 `bind(('0.0.0.0', 0))`
4. 移除 `print()` 调试遗留
5. WSS `ssl._create_unverified_context()` 至少加注释说明原因

### 扩展

6. 抽取共同的重连逻辑到 `protocol.py` 基类中（本次一起做）

## Acceptance Criteria

* [ ] MQTT 断开后能自动重连（5 次，指数退避）
* [ ] WSS 断开后能自动重连（同上）
* [ ] MQTT `loop_forever()` 调用已移除
* [ ] UDP socket 显式 bind
* [ ] `print(mqtt_config)` 改为 logger
* [ ] macOS 上插拔耳机后音频回复正常（reload_devices）

## Definition of Done

* mqtt_protocol.py 和 websocket_protocol.py 修改完成
* lint 通过
* 本地 macOS 测试：MQTT 连接稳定，断开恢复

## Decision (ADR-lite)

**Context**: 两个协议文件有大量重复逻辑 + SSL 验证策略需决定。
**Decision**: 修 bug + 抽取公共重连/监控/清理逻辑到 `protocol.py` 基类中，用模板方法模式让子类提供连接检查方法。
**Consequences**: 代码重复消除，后续协议维护只需改一处。

## Out of Scope

* iOS/Android 平台测试
* 更换 MQTT 库（paho-mqtt → 其他）

## Technical Notes

* 关键文件：
  - `src/protocols/mqtt_protocol.py` — 主修目标
  - `src/protocols/websocket_protocol.py` — 次修目标
  - `src/protocols/protocol.py` — 基类（可能需要小改）
  - `src/audio_codecs/audio_codec.py` — 音频设备热重载
  - `src/utils/audio_device.py` — 设备发现
* `_heartbeat_loop` 在 WSS 中已经是死代码（被注释）
* `ssl._create_unverified_context()` 在模块顶部创建，有安全隐患但可能服务器证书不正规
