# py-xiaozhi 潜在隐患分析报告

**范围**: `main.py` + `src/`（编排、core、plugins、protocols、audio、mcp、ui 胶水）  
**日期**: 2026-07-19  
**性质**: 只读风险盘点；不包含修复实现  
**对照**: 仓库现有实现模式 + 本报告整改；不依赖已移除的 Trellis 脚手架

---

## 1. 执行摘要

> **修复状态（2026-07-19）**：Critical / High 与 P0–P3 均已落地；见 §6 与 §9。回归 `tests/test_resilience_fixes.py`；启动约 1.7s。不依赖 Trellis。  
> 规范沉淀：`.trellis/spec/backend/error-handling.md`、`asyncio-guidelines.md`。  
> 回归：`tests/test_resilience_fixes.py`。

项目在架构上为三层模型（`ServiceContainer` → core 服务 → plugins），PluginManager / EventBus / TaskManager 带隔离意图。

**原始问题（已修复）摘要**：

| 主题 | 修复前 | 修复后 |
|------|--------|--------|
| **(a) 异常可观测** | 大量 `except` 无 `exc_info` | 核心路径统一带堆栈；TaskManager 用 `exc_info=exc` |
| **(b) 模块隔离** | 依赖失败仍空转；Music/MCP 脏单例 | failed 标记 + 依赖 skip；容器 bind/unbind |
| **(c) 级联/僵死** | per-frame create_task；zombie wait | 有界音频队列；关键插件门闩 exit 1 |

---

## 2. 异常吞没与可观测性

### 2.1 模式统计（`src/` + `main.py`）

| 模式 | 约计数 | 说明 |
|------|--------|------|
| `except Exception` | **275** | 项目主模式；规范允许，但边界质量参差 |
| `except` + logger **无** `exc_info` | **~182** | 违反 error-handling 规范“关键路径要带堆栈” |
| `except ...: pass`（含 CancelledError/OSError 等） | **~29** | 多数为合理清理；少数静默 |
| `except Exception` 后 `pass` / 静默 `return` / `continue` | **~15** | 真正“吞掉且几乎无痕迹” |
| 裸 `except:` | **0** | 符合规范禁止项 |
| `asyncio.create_task`（含合法自管） | **~20** | 多处未走 TaskManager（见 §4） |

搜索关键词：`except Exception`、`except ...: pass`、`exc_info`、`asyncio.create_task`、`threading.Thread`、`get_instance`。

### 2.2 Critical / High：可观测性失效

#### H-1 EventBus 吞掉处理器异常且无堆栈  
- **位置**: `src/core/event_bus.py` `_safe_call` ~L166–178  
- **症状**: 任意订阅者抛错 → 只记一行 `处理器 X 执行异常: {e}`，**无 traceback**；`emit` 使用 `gather(..., return_exceptions=True)` 叠加后调用方完全无感。  
- **根因**: 隔离设计正确，但日志不符合规范 Pattern #1（边界应 `exc_info=True`）。  
- **影响半径**: UI、状态机、协议、音乐等所有经 EventBus 的路径；调试时只能看到“状态不更新”，看不到谁炸了。  
- **缓解方向**: `_safe_call` 改为 `logger.error(..., exc_info=True)`；可选对关键事件（如 `DEVICE_STATE_CHANGED`）做失败计数/metrics。

#### H-2 PluginManager 生命周期失败无堆栈  
- **位置**: `src/plugins/manager.py` `setup_all` / `start_all` / `notify_*` ~L150–203  
- **症状**: `logger.error(f"插件 {name} setup 失败: {e}")` 无 `exc_info`；失败插件仍留在列表中，后续 `start` / `notify` 继续调用。  
- **根因**: 隔离边界接住了异常，但未标记插件为 failed，也未保留堆栈。  
- **影响半径**: 半初始化插件在后续 hook 中再次失败或 NPE 式 AttributeError；日志噪声大、根因难追。  
- **缓解方向**: setup 失败则标记 `_failed=True` 并从 notify 列表剔除；日志统一 `exc_info=True`；对 `requires` 依赖失败的下游插件跳过 start。

#### H-3 TaskManager 任务异常日志可能丢 traceback  
- **位置**: `src/core/task_manager.py` `_on_done` ~L94–99  
```python
exc = t.exception()
if exc:
    logger.error(f"任务 {name} 异常结束: {exc}", exc_info=True)
```  
- **症状**: 在 done callback 里当前无 active exception context，`exc_info=True` **通常不会**附上 `exc` 的 traceback（应 `exc_info=(type(exc), exc, exc.__traceback__)` 或 `logger.error(..., exc_info=exc)`）。  
- **影响半径**: 所有经 `spawn` 的业务任务（UI start、调度命令等）“异常结束”日志残缺。  
- **缓解方向**: 使用 `exc_info=exc`（Py3.5+）或显式三元组。

#### H-4 协议/容器 JSON 热路径吞异常无堆栈  
- **位置**:  
  - `src/bootstrap/container.py` `_on_incoming_json` ~L362–377：`logger.error(f"处理 JSON 消息失败: {e}")`  
  - `src/core/protocol_manager.py` `connect` ~L124–126：连接异常无堆栈  
  - `src/core/resource_pool.py` ~L54–55：清理失败无堆栈  
- **症状**: TTS/状态机处理失败时只剩字符串消息。  
- **影响半径**: 语音会话状态错乱难复现。  
- **缓解方向**: 边界统一 `exc_info=True`。

### 2.3 Medium：静默 swallow（有意或近似静默）

#### M-1 音频清理双层 except 外层 `pass`  
- **位置**: `src/plugins/audio.py` `register_resources` ~L140–154  
- **症状**: 导入 music player 失败时外层 `except Exception: pass`，**无日志**。  
- **影响半径**: 关闭阶段音乐/解码器可能泄漏；难从日志发现。  
- **缓解方向**: 至少 `logger.debug(..., exc_info=True)`；符合规范“拿不准用 #2 warning”。

#### M-2 `_should_send_microphone_audio` 静默返回 False  
- **位置**: `src/plugins/audio.py` ~L188–193  
```python
except Exception:
    return False
```  
- **症状**: 状态查询异常时停止上行音频，无日志。  
- **影响半径**: 用户表现为“突然听不到我说话”，难关联到状态机 bug。  
- **缓解方向**: warning 一次 + 返回 False。

#### M-3 其它静默/降级返回（可接受但需知情）  
| 位置 | 行为 | 评估 |
|------|------|------|
| `main.py` L163–164 SIGTRAP | `pass` | 可接受（信号安装） |
| `src/constants/constants.py` L75–77 | frame duration 默认 20 | 可接受 |
| `src/activation/service.py` L466–467 | efuse 读失败 → 未激活 | 可接受，建议 debug 日志 |
| `src/protocols/websocket_protocol.py` L304–305 | `is_audio_channel_opened` 异常 → False | 可接受 |
| `src/plugins/manager.py` L54–55 | `get_plugin` 异常 → None | 过度防御，dict.get 几乎不抛 |
| MCP app launcher/scanner 多处 | 探测失败 continue/return | 工具侧可接受 |

### 2.4 规范符合度（error-handling.md）

| 规范项 | 现状 |
|--------|------|
| 禁止裸 `except:` | ✅ 未发现 |
| 关键路径 `exc_info=True` | ❌ 大量违反（EventBus、PluginManager、协议、UI bridge） |
| 禁止 `logger.exception` | ✅ 未见使用 |
| 插件失败由 manager 隔离、插件内勿再吞 | ⚠️ manager 隔离了，但 audio/mcp 内层仍大量 try（部分合理） |
| 静默吞仅用于真正无意义路径 | ⚠️ 少数清理路径过宽 |

---

## 3. 模块化与隔离完整性

### 3.1 架构意图 vs 实际

文档（`architecture-principles.md`）要求：

- plugins 只通过 `PluginContext` / `PluginCommands` 访问核心  
- core 不 import plugins/ui/protocols 具体实现  
- MCP tools 尽量无副作用，不 import core（`music_player` 例外）

**实测**:

| 检查项 | 结果 |
|--------|------|
| `src/core/*` import plugins/ui | ✅ 未发现（隔离较好） |
| plugins 经 Protocol 接口访问容器 | ✅ Adapter 模式存在 |
| MCP tools import core | ⚠️ `music_player.py` 直接 `from src.core.event_bus import Events` |
| 插件依赖拓扑 + 注入 | ✅ `requires` + Kahn 拓扑 |
| 失败插件阻断依赖者 | ❌ **未实现**（见 H-5） |

### 3.2 High：隔离空洞

#### H-5 依赖插件失败后下游仍启动（“半死”系统）  
- **位置**:  
  - `AudioPlugin.setup` ~L52–54：失败后 `self.codec = None` 继续  
  - `WakeWordPlugin.requires = ["audio"]`，`start` 发现无 codec 只 warning 返回（`wake_word.py` ~L57–59）  
  - `PluginManager.setup_all` 不根据 setup 结果剔除或失败传播  
- **症状**: 麦克风/PortAudio 初始化失败 → 进程仍进入 `wait_shutdown`，UI 可显示，但唤醒/对话核心能力全无；用户以为“程序在跑”。  
- **影响半径**: audio 是 priority=10 的根基；其失败应视为 **降级模式** 或 **致命错误**，目前两者皆非。  
- **缓解方向**:  
  - 定义插件 `health`: healthy / degraded / failed；  
  - `requires` 依赖 failed → 下游 auto-skip；  
  - 可选：关键插件（audio/ui）失败时 `request_shutdown` 或明确 degraded banner。

#### H-6 全局单例贯穿生命周期，容器无法真正 teardown/recreate  
- **位置**:  
  - `ConfigManager` — `src/utils/config_manager.py`，模块级使用  
  - `constants.py` L6：`config = ConfigManager.get_instance()` **import 时副作用**  
  - `McpServer.get_instance()` — `src/mcp/mcp_server.py`  
  - `get_music_player_instance()` — `src/mcp/tools/music/music_player.py` L1288–1297  
  - `ActivationService` / `LoggingConfigManager` 等同模式  
- **症状**: `ServiceContainer.shutdown` 释放了资源池，但单例状态（工具列表、music codec 指针、event_bus 注入）可能残留；测试或热重启时脏状态。  
- **影响半径**: 模块边界在文档上是 plugin，运行时是 **进程级共享堆**。  
- **缓解方向**: 单例改为容器持有并注入；至少提供 `reset_for_tests()`；`constants` 避免模块 import 时读配置。

#### H-7 Audio ↔ Music 双向耦合，绕过插件边界  
- **位置**:  
  - `AudioPlugin.setup` 调 `get_music_player_instance().set_audio_codec`  
  - `McpPlugin.setup` 又注入 EventBus 到同一 MusicPlayer  
  - 清理路径两边各自 stop music（`audio.py` resource cleanup + `mcp.py` resource cleanup）  
- **症状**: 关闭顺序依赖 resource_pool 注册顺序；一边失败另一边仍持有已 close 的 codec → 二次异常被吞。  
- **影响半径**: 关机卡顿、偶发 “codec is None” 播放失败。  
- **缓解方向**: Music 归属单一所有者插件；另一侧只发事件（`MUSIC_*`），不直接 set codec。

#### M-4 EventBus 字符串事件无类型约束  
- **位置**: `src/core/event_bus.py` `Events` 常量 + `emit(event: str, data: Any)`  
- **症状**: 拼写错误事件名静默无订阅者；data 形状靠约定。  
- **影响半径**: 跨模块重构易引入“事件发了没人收”。  
- **缓解方向**: 保持轻量即可；可加 debug 断言 `has_handlers` 或 typed payload dataclass（部分 UI/music 已用）。

#### M-5 UIPlugin 直连 ViewManager 内部实现  
- **位置**: `src/plugins/ui.py` 多处 `self.view_manager.main_model.set_*`、`_emotion_service`  
- **症状**: GUI/CLI 分支 if/else 膨胀；View 内部改名即破 plugin。  
- **影响半径**: UI 重构成本高，非运行时崩溃主因。  
- **缓解方向**: View 统一 facade（已有部分 set_status/set_tts_text）。

### 3.3 做得好的隔离（负向发现也写明）

- **PluginManager 主动隔离** setup/start/notify/stop：单插件异常默认不中断循环 — **符合设计**。  
- **EventBus `_safe_call`**：单 handler 失败不取消其它 handler — **符合设计**（缺堆栈是另一问题）。  
- **ResourcePool 逆序释放 + 单资源失败继续** — 关机 partial-success 合理。  
- **协议音频直连**（`set_audio_handler`）避开 EventBus 背压 — 有意识的架构优化。  
- **main.py 顶层** 捕获 `Exception` 并 `exc_info=True` — 进程级未处理异常有落点。

---

## 4. 单模块故障 → 全局崩溃 / 僵死

### 4.1 Critical / High

#### C-1 协议层 fire-and-forget `create_task`（规范明确反模式）  
- **位置**: `src/core/protocol_manager.py` L68–78  
```python
def _on_incoming_json(...):
    asyncio.create_task(self._event_bus.emit(Events.INCOMING_JSON, json_data))

def _on_incoming_audio(...):
    asyncio.create_task(self._incoming_audio_handler(data))  # 每帧音频
```  
- **症状**（规范 `asyncio-guidelines.md` 已点名）:  
  1. 任务不入 `TaskManager` → **shutdown 不取消**，可能 “Event loop stopped before Future completed” 或悬挂 IO；  
  2. 无 done_callback → 异常可能变成 “Task exception was never retrieved”；  
  3. **每帧音频** `create_task`：handler 稍慢即任务队列爆炸 → 内存上涨、调度延迟、最终 event loop 卡死（**进程未崩但全局不可用**）。  
- **影响半径**: 整个会话音频/JSON 通路；与 Protocol 同进程共存的 UI/插件全部饿死。  
- **缓解方向**:  
  - JSON：`TaskManager.spawn` 或合并到已有串行队列；  
  - 音频：优先 **直接 await 不可行（同步回调）** 时用有界队列 + 单一 consumer task，禁止 per-packet create_task。

#### H-8 MQTT 回调线程 → 裸 `create_task`  
- **位置**: `src/protocols/mqtt_protocol.py` ~L237–240、L257–260、L570 等  
```python
self.loop.call_soon_threadsafe(
    lambda: asyncio.create_task(self._attempt_reconnect(...))
)
```  
- **症状**: 与 C-1 相同的未追踪任务；另：`lambda` 闭包延迟绑定 `rc`/`error_msg` 在快速连续 disconnect 时可能错值；线程内 `asyncio.create_task` 若 loop 已关会抛，可能只打日志。  
- **影响半径**: 重连风暴、网络错误回调丢失 → 状态机停在 LISTENING/SPEAKING。  
- **缓解方向**: `asyncio.run_coroutine_threadsafe` + 保存 Future；或 `call_soon_threadsafe` 调 `TaskManager.schedule_nowait`；闭包用默认参数绑定。

#### H-9 关键插件失败后应用“空转”  
- **位置**: `ServiceContainer.run` ~L232–242：plugins setup/start 后无健康检查，直接 `await self.tasks.wait_shutdown()`  
- **症状**: UI setup 失败（被 manager 吞）→ 无窗口/无 CLI，但仍阻塞在 wait_shutdown，只能靠信号退出。Audio 失败类似。  
- **影响半径**: **全局僵死（zombie app）**，不是 Python traceback 崩溃。  
- **缓解方向**: setup 后检查关键插件；失败返回 exit code 1；或 CLI 打印明确 “degraded”。

#### H-10 网络错误处理过薄  
- **位置**: `container.py` `_on_network_error` ~L351–352  
```python
async def _on_network_error(...):
    self.state.set_keep_listening(False)
```  
- **症状**: 不改 device_state、不 abort、不保证 UI 之外的恢复路径完整（UI 另订 NETWORK_ERROR）。状态可能仍 SPEAKING/LISTENING。  
- **影响半径**: 断网后按键/唤醒行为异常，直到用户手动 abort。  
- **缓解方向**: 网络错误时统一 `set_device_state(IDLE)` + 清 keep_listening + 可选提示。

### 4.2 Medium：真崩溃与边界

#### M-6 顶层能兜住的 vs 兜不住的  
- **能兜住**: `main.py` L228–233 的 `except Exception`；`ServiceContainer.run` L245–247。  
- **兜不住（进程级）**:  
  - 音频回调线程中的 **C 扩展 segfault**（PortAudio / Opus / webrtc_apm / sherpa-onnx）；  
  - `threading.Thread` 内未捕获且非主线程的部分错误（取决于版本/配置）；  
  - Qt/qasync 原生断言。  
- **位置示例**: `audio_codec.py` `_input_callback` / `_output_callback` 有 Python try，但 numpy/opus 原生错误可能直接 abort 进程。  
- **缓解方向**: 保持回调尽量薄；原生库初始化失败 fail-fast；崩溃时依赖 OS 级日志。

#### M-7 UI 事件处理器未自包 try  
- **位置**: `src/plugins/ui.py` `_press` / `_send_text` / `_abort` 等  
- **症状**: 异常依赖 EventBus `_safe_call` 兜底（见 H-1）；若将来有人直接 await 这些方法则冒泡。  
- **影响半径**: 当前被 EventBus 挡住，不会全局崩；但与 H-1 叠加导致“按钮失灵无堆栈”。

#### M-8 `constants.py` import 副作用  
- **位置**: L6 `config = ConfigManager.get_instance()`  
- **症状**: 任何 import constants 即初始化配置目录/读盘；测试或工具脚本意外触发 IO；配置损坏时 import 链失败 → **启动早期全局失败**。  
- **缓解方向**: 懒加载 `get_frame_duration` 内取 config（函数内已有路径，模块级应删）。

#### M-9 资源清理失败无堆栈 + 继续  
- **位置**: `resource_pool.py` L49–55  
- **症状**: 某一 cleanup 抛错被吞（无堆栈），后续资源仍释放 — 正确的 partial shutdown，但难排查泄漏。  
- **缓解方向**: `exc_info=True`。

### 4.3 不会因 A 模块异常直接全局崩的路径（负向）

经搜索与阅读，以下路径 **默认不会** 因单插件异常杀掉进程：

- Plugin setup/start/notify（manager 边界）  
- EventBus handler（`_safe_call`）  
- TaskManager.spawn 的任务（done callback 记日志，不 re-raise 到 loop 默认 handler——取决于是否还有其它引用）  
- MCP tool call（`mcp_server._handle_tool_call` 捕获并 `_reply_error`）

**例外**: 未追踪 `create_task` 的异常依赖 asyncio 默认 “Task exception was never retrieved” 日志，**不保证**业务恢复。

---

## 5. 严重度汇总表

| ID | 严重度 | 主题 | 一句话 | 位置 |
|----|--------|------|--------|------|
| C-1 | **Critical** | 级联/僵死 | 协议 JSON/音频 per-message `create_task` 可堆积拖死 loop | `protocol_manager.py:68-78` |
| H-1 | **High** | 异常吞没 | EventBus 吞异常且无堆栈 | `event_bus.py:166-178` |
| H-2 | **High** | 异常吞没+隔离 | Plugin 失败无堆栈、无 failed 标记 | `manager.py:150-203` |
| H-3 | **High** | 异常吞没 | Task 异常 `exc_info=True` 可能丢 traceback | `task_manager.py:94-99` |
| H-4 | **High** | 异常吞没 | 容器/协议关键路径无堆栈 | `container.py:362-377` 等 |
| H-5 | **High** | 隔离 | audio 失败仍空转运行 | `audio.py:52-54` + container run |
| H-6 | **High** | 隔离 | 全局单例破坏容器生命周期 | config/mcp/music get_instance |
| H-7 | **High** | 隔离 | Audio↔Music 双向耦合 | `audio.py` + `mcp.py` + music_player |
| H-8 | **High** | 级联 | MQTT 线程裸 create_task / 闭包 | `mqtt_protocol.py:237+` |
| H-9 | **High** | 级联 | 关键插件失败后 zombie wait_shutdown | `container.py:232-242` |
| H-10 | **High** | 级联 | 网络错误不复位设备状态 | `container.py:351-352` |
| M-1..M-9 | **Medium** | 混合 | 静默 pass、UI 耦合、C 崩溃面等 | 见上文 |
| — | Low | — | CancelledError pass、QueueEmpty pass、SIGTRAP pass 等 | 多处，可接受 |

---

## 6. 建议优先级（仅方向，非 redesign）

### P0（尽快）
1. **消灭热路径 fire-and-forget**: `protocol_manager` 音频改有界队列；JSON 走 `TaskManager.spawn`。  
2. **关键路径统一 `exc_info`**: EventBus、PluginManager、ResourcePool、container JSON handler、TaskManager done callback。  
3. **关键插件健康门闩**: audio/ui setup 失败 → 明确 exit 或 degraded 横幅，禁止 silent zombie。

### P1
4. 插件 `_failed` 标记 + 依赖 skip。  
5. MQTT/GPIO/CLI 跨线程任务全部纳入 TaskManager 或 `run_coroutine_threadsafe` 可追踪 Future。  
6. 网络错误统一拉回 IDLE。

### P2（已落地）
7. MusicPlayer/McpServer 容器 bind/unbind + 插件注入  
8. `constants.py` 懒加载 ConfigManager  
9. UI facade 收口  
10. CLI/GPIO 事件调度可追踪  

### P3 / 收尾（已落地）
11. CLI/GPIO/GUI 注入容器 `TaskManager`；`_safe_emit` 优先 `schedule_nowait`  
12. WebSocket/MQTT 热路径 `logger.error` 补 `exc_info`  
13. `ConfigManager.reset_instance()` 测试钩子  
14. 启动优化：Settings/OpenCV 延后扫描；SettingsModel 懒加载  
15. 歌词任务可追踪取消；GUIActivation 使用 `get_running_loop` + `create_task`  

### 刻意保留 / 非代码可彻底消除
- **ConfigManager 进程单例**：全局配置权威源；仅提供 reset 给测试  
- **原生 C 扩展 segfault**（PortAudio/Opus/ONNX）：Python 边界无法兜底  
- **MCP tools 经 get_instance 取 MusicPlayer**：兼容路径，运行时绑定到容器实例  

---

## 9. 修复对照表（C/H）

| ID | 状态 | 实现要点 |
|----|------|----------|
| C-1 | ✅ | 音频有界队列 + JSON TaskManager.spawn |
| H-1 | ✅ | EventBus `exc_info=True` |
| H-2 | ✅ | mark_failed + 依赖 skip + 堆栈 |
| H-3 | ✅ | `exc_info=exc` |
| H-4 | ✅ | container/resource_pool/协议堆栈 |
| H-5 | ✅ | audio mark_failed + 门闩 |
| H-6 | ✅ | Music/MCP bind；Config 保留单例+reset |
| H-7 | ✅ | 注入 + detach 生命周期 |
| H-8 | ✅ | MQTT `_schedule_coro` |
| H-9 | ✅ | 关键插件 health 检查 exit 1 |
| H-10 | ✅ | 网络错误 → IDLE |

---


## 7. 三大主题对照（修复后复审）

### (a) 异常被吞、无法抛出 / 无法诊断
- **已修**: 核心路径（EventBus / PluginManager / TaskManager / ResourcePool / 协议热路径）统一 `exc_info`；audio 静默路径补日志。  
- **不存在**: 裸 `except:`（全仓 0）。  
- **残留**: 外围模块（settings / activation / 部分 MCP tools）仍有无堆栈的 `logger.error(f"...{e}")`，属可观测性债务，非架构洞。  
- **设计性吞没**: 插件/事件隔离仍是有意行为；现已 mark_failed + 带堆栈。

### (b) 模块化无法完整隔离
- **已改善**: Plugin failed + 依赖 skip；Music/MCP 容器 bind/unbind；UI facade；TaskManager 注入 UI。  
- **仍保留（合理）**: ConfigManager 进程单例；MCP tools 经 `get_*_instance` 兼容入口（运行时为容器实例）。  
- **EventBus**: 仍为字符串事件名 + Any data（低优先级）。

### (c) A 模块异常导致全局崩溃
- **已修**: 协议音频有界队列；关键插件门闩 exit 1；网络错误回 IDLE；MQTT 可追踪调度。  
- **启动体验**: Settings/OpenCV 延后扫描，冷启动 ~55s → ~2s（见实测日志）。  
- **仍可能**: 原生 C 扩展 segfault；歌词/播放任务现已可追踪取消。  
- **结论**: 架构级「进程活着产品已死」主路径已关闭；剩余为 polish 与工程闭环。

---

## 8. 附录：检索与抽样证据（初审快照，修复前）

### 8.1 命令/模式（2026-07-19 初扫）
```
except Exception          → ~275
except + logger 无 exc_info → ~182
except ...: pass          → ~29
asyncio.create_task       → ~20（含合法自管）
get_instance(             → ~32 调用点
threading.Thread          → ~7
```

### 8.2 抽样源码核对（初审）

| 文件 | 行号 | 模式 |
|------|------|------|
| `src/core/event_bus.py` | 172–178 | 已修：exc_info |
| `src/core/task_manager.py` | 94–99 | 已修：exc_info=exc |
| `src/plugins/manager.py` | 150–162 | 已修：failed + 堆栈 |
| `src/core/protocol_manager.py` | 68–78 | 未追踪 create_task |
| `src/plugins/audio.py` | 52–54, 153–154 | soft fail + pass |
| `src/bootstrap/container.py` | 245–249, 351–352, 362–377 | run 兜底；网络/JSON 处理 |
| `src/protocols/mqtt_protocol.py` | 237–240 | 线程 + create_task |
| `src/constants/constants.py` | 6 | import-time singleton |
| `src/core/resource_pool.py` | 49–55 | cleanup catch 无 stack |
| `main.py` | 163–164, 231–233 | 有意 pass + 顶层兜底 |

### 8.3 备注
- 项目已移除 Trellis 脚手架；本报告与 `deep-audit.md` 为独立审计/整改记录，不绑定 `.trellis/`。

---

*本报告为静态代码分析 + 整改记录。动态行为以实测日志与 `tests/test_resilience_fixes.py` 为准。*
