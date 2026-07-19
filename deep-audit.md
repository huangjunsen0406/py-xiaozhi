# py-xiaozhi 深度审计报告（修复后复审）

**日期**: 2026-07-19  
**范围**: `main.py` + `src/`（可靠性 / 异常 / 隔离 / 级联）；对照本轮 P0–P3 修复  
**方法**: 静态扫描 + 关键路径源码核对 + 单元测试（`tests/test_resilience_fixes.py` **15 passed**）  
**性质**: 审计结论；不含新一轮大改（除文档本身）

---

## 0. 一句话结论

| 维度 | 评级 | 说明 |
|------|------|------|
| **架构级可靠性（原 C/H）** | **良好** | 协议热路径、插件健康门闩、EventBus/Task 堆栈、Music/MCP 绑定均已落地 |
| **全仓一致性** | **中等** | 外围模块仍有 ~149 处「打 `{e}` 无堆栈」、局部 fire-and-forget |
| **进程安全** | **中等偏上** | Python 异常大多被边界兜住；C 扩展与激活 GUI 异步桥仍有缺口 |
| **工程闭环** | **未完成** | 改动在工作区（`main` ahead 1 + 大量 unstaged），尚未形成完整可发布提交 |

**原风险报告的「会把整机拖死」类问题：当前代码层已基本消除。**  
**剩余是可观测性债务、局部任务泄漏、文档滞后、以及未提交的代码资产。**

---

## 1. 修复落地核查（门禁）

下列关键修复点在源码中 **全部存在**（静态标记核对 OK）：

| 修复 | 证据位置 |
|------|----------|
| 入站音频有界队列 + 单 consumer | `protocol_manager.py` `_audio_queue` / `_audio_consumer` |
| JSON 走 TaskManager.spawn | `ProtocolTransport._spawn` |
| TaskManager `exc_info=exc` | `task_manager.py` done callback |
| EventBus `exc_info=True` | `event_bus.py` `_safe_call` |
| 插件 `mark_failed` + 依赖 skip | `base.py` / `manager.py` |
| 关键插件 health → exit 1 | `container._check_critical_plugins` |
| 网络错误复位 IDLE | `container._on_network_error` |
| Music/MCP bind/unbind | `music_player.py` / `mcp_server.py` / `container._bind_shared_services` |
| constants 无 import-time Config | `constants.py` 头部无 `get_instance` |
| UI TaskManager 注入 | `UIPlugin` → GUI/CLI/GPIO |
| 启动优化 / 懒加载 Settings | `settings_model` / `ViewManager` |

---

## 2. 全仓扫描快照（当前）

| 模式 | 数量 | 解读 |
|------|------|------|
| `except Exception` | **293** | 仍高；边界 isolation 文化，问题在质量而非数量 |
| `logger.*{e}` **无** `exc_info` | **~149** | 较修复前 ~182 下降，但外围仍多 |
| `except ...: pass` | **~34** | 多为 CancelledError / QueueEmpty，多数合理 |
| 裸 `except:` | **0** | 合规 |
| `asyncio.create_task` | **11** | 10 合法自管 + **1 真问题**（歌词） |
| `ensure_future` | **1** | `gui/activation.py` |
| `get_event_loop` | **1** | 同上 |
| `get_instance` | **~33** | Config/Camera/Activation 等仍全局 |
| `threading.Thread` | **7** | 设置页音频/摄像头测试 + MQTT UDP + 激活播报 |

### 无堆栈日志 Top 文件

| 次数 | 文件 | 风险 |
|------|------|------|
| 15 | `mcp/tools/music/music_player.py` | 播放链路难排查 |
| 9 | `audio_codecs/audio_codec.py` | **实时回调线程**，刷屏 vs 可观测权衡 |
| 8 | `mcp/tools/screenshot/...` | 工具侧 |
| 7 | `ui/shared/models/settings_model.py` | 设置页 |
| 6 | `music_decoder` / `activation` / `protocol.py` | 中 |

---

## 3. 仍存在的问题（按严重度）

### 3.1 Medium — 建议排期

#### M-A 歌词任务 fire-and-forget — **已修**  
- `_lyrics_task` 可追踪；`stop` / `_start_playback` 统一 cancel；done callback 记堆栈  

#### M-B GUI 激活：`get_event_loop` + `ensure_future` — **已修**  
- 改为 `get_running_loop()` + `loop.create_task` 

#### M-C 音频回调路径日志无堆栈  
- **位置**: `audio_codec.py` 输入/输出 callback ~147–158、编码失败等  
- **症状**: 实时线程上只打 `str(e)`；真异常难定位  
- **影响**: 现场「没声音」类问题依赖猜  
- **注意**: 热路径加 `exc_info` 可能刷日志；建议 **error 带堆栈、warning 限流**  

#### M-D 设置页工作线程无统一异常出口  
- **位置**: `settings_model.py` 4× `threading.Thread`（录音/播放/摄像头）  
- **症状**: 工作线程异常依赖线程内 try；与 Qt Signal 回传失败时 UI 可能一直转圈  
- **缓解**: 线程入口统一 try/except + Signal 错误态  

#### M-E 外围 `exc_info` 债务  
- 约 149 处；非核心路径，但 settings / activation / music 影响用户感知  
- 可按文件批量扫，不必一次全改  

### 3.2 Low — 技术债 / 一致性

| 项 | 说明 |
|----|------|
| EventBus 字符串事件 | 拼写错误静默无 handler |
| Config/Camera/Activation 单例 | 进程级合理；热重启/测试需 reset |
| MCP tools `get_music_player_instance` | 兼容层，运行时已是容器实例 |
| `risk-analysis.md` §7 | 仍写旧「失败点」措辞，与 §1/§9 矛盾 |
| 无 e2e / GUI 冒烟 | 单元测覆盖核心修复，未覆盖真机音频会话 |
| **改动未完整入库** | 源码 diff + untracked tests/risk docs |

### 3.3 Critical / High — 当前未再发现新的「整机必挂」设计洞

对照原 C-1、H-1…H-10：

- 协议 per-frame 任务堆积 → **已修**  
- EventBus/Plugin 无堆栈 / 无 failed → **已修**  
- zombie wait_shutdown → **已修**  
- MQTT 裸 create_task → **已修**  
- 网络错误不回 IDLE → **已修**  

**新扫未发现同等级架构洞。**

---

## 4. 架构健康度（隔离）

```
main → ServiceContainer
         ├─ TaskManager  ← UI / Protocol 注入
         ├─ EventBus
         ├─ ProtocolManager（有界音频 + spawn）
         ├─ PluginManager（failed + 依赖 skip）
         ├─ bind(McpServer, MusicPlayer)
         └─ ResourcePool（逆序；最后 unbind 共享服务）
```

| 检查 | 结果 |
|------|------|
| core 不 import plugins/ui | ✅ |
| 插件经 ctx/cmd | ✅ |
| 关键插件失败 exit | ✅ |
| 共享服务生命周期 | ✅ bind/unbind（非完全 DI，但是可控） |
| 跨线程进 loop | ✅ 主路径 TaskManager / run_coroutine_threadsafe |

**残余耦合**: Audio 仍 set codec 到 Music；MCP 仍 set EventBus —— 职责分界清晰但双向触点仍在（已用 detach 收敛）。

---

## 5. 级联失败场景（修复后推演）

| 场景 | 预期行为 | 置信度 |
|------|----------|--------|
| PortAudio 初始化失败 | audio failed → 门闩 exit 1 | 高（单测+代码路径） |
| UI QML 加载失败 | ui failed → exit 1 | 高 |
| 单插件 setup 抛错 | 标记 failed，其它继续 | 高（单测） |
| EventBus handler 抛错 | 隔离 + 堆栈；其它 handler 继续 | 高（单测） |
| 入站音频风暴 | 队列有界丢旧帧，单 consumer | 高（单测） |
| MQTT 断线 | `_schedule_coro` 可追踪 | 中（未 e2e） |
| 网络错误 | keep_listening=False + IDLE | 中 |
| 音乐歌词任务泄漏 | **仍可能** 残留 task | 中（代码审查） |
| 原生库 segfault | 进程直接死 | 已知不可防 |
| 激活 GUI ensure_future | 边缘环境可能异常 | 中 |

---

## 6. 测试与仓库状态

| 项 | 状态 |
|----|------|
| `tests/test_resilience_fixes.py` | **15 passed**（0.2s） |
| 真机 GUI/CLI 会话 | **未跑** |
| Git | 整改改动需单独 commit（不含 Trellis） |

---

## 7. 建议优先级（若继续投入）

### P0（小改、高收益）
1. 歌词任务改 `self._lyrics_task` + stop 时 cancel  
2. `gui/activation.py`：`get_running_loop` + `create_task`（去掉 ensure_future）  
3. **提交本轮全部修复**（含 tests + 报告），避免工作区丢失  

### P1
4. `audio_codec` 回调 error 路径 `exc_info`（warning 限流）  
5. `music_player` / `settings_model` 批量补堆栈  
6. 同步 `risk-analysis.md` §7 措辞  

### P2
7. 设置页 Thread 统一错误 Signal  
8. 可选：degraded 模式（audio 失败不 exit，UI 横幅）  
9. e2e 冒烟脚本（cli + mock protocol）  

---

## 8. 审计方法附录

```
扫描: except / create_task / ensure_future / get_event_loop /
      get_instance / Thread / logger*{e} 无 exc_info
门禁: 10 个关键修复标记存在性
测试: pytest tests/test_resilience_fixes.py
```

---

*本报告为修复后深度复审。架构级 C/H 已关闭；剩余 Medium 与工程闭环（提交、e2e、日志扫尾）。*
