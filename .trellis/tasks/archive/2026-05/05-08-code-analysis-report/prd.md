# 分模块阅读 src 代码并生成项目分析报告

## Goal

分模块阅读 `src/` 下全部源码，由多个子代理并行分析，每个模块生成一份 markdown 分析报告，最后汇总为一份总报告。不修改任何代码，只读不写（报告存放于新建目录）。

## What I already know

* `src/` 共 14 个模块、~130 个 `.py` 文件 + 15 个 `.qml` 文件
* 模块清单及文件数：
  - `activation` (2) — 激活服务
  - `audio_codecs` (6) — 音频编解码、buffer、AEC
  - `audio_processing` (5) — 唤醒词检测、关键词转换
  - `bootstrap` (3) — 应用启动、容器、协议接口
  - `constants` (2) — 常量定义
  - `core` (5) — 事件总线、状态管理、任务管理、协议管理
  - `logging` (5) — 日志系统
  - `mcp` (~30) — MCP 工具集（bazi/相机/音乐/截图/系统/天气/日历/定时器）
  - `plugins` (10) — 插件系统（audio/wake_word/ui/mcp/shortcuts）
  - `protocols` (3) — MQTT/WebSocket 协议
  - `ui` (~30) — CLI/GPIO/GUI 三种模式 + shared 共享层
  - `utils` (8) — 工具函数（config/audio/resource/volume）
  - `iot` — 物联网（当前少或无代码）
  - `views` — 视图（当前少或无代码）

## Requirements

1. 每个模块生成一份独立的 `{module}.md` 分析报告
2. 生成一份 `00-summary.md` 汇总报告
3. 报告存放在新建的 `reports/` 目录下（项目根目录）
4. 只读代码，不修改任何源文件
5. 子代理并行分析不同模块，提高效率
6. 每个模块报告包含核心结构和关键设计要点

## Acceptance Criteria

* [ ] `reports/00-summary.md` 汇总报告存在，包含架构概览和各模块一句话摘要
* [ ] `reports/` 下每个模块都有对应的 `.md` 分析报告
* [ ] 每份报告包含：文件清单、核心类/函数、依赖关系、设计要点
* [ ] 未修改 `src/` 下任何文件
* [ ] 报告总数覆盖全部 14 个模块

## Definition of Done

* 所有模块报告生成完毕
* 汇总报告包含跨模块依赖图和架构总结
* `reports/` 目录完整，无缺失模块

## Technical Approach

## Decision (ADR-lite)

**Context**: 需要确定报告深度。
**Decision**: 源码级 — 每个文件、每个类/函数都详细列出签名、职责、关键逻辑。
**Consequences**: 报告较长（每模块 5-10 页），但信息完整，后续查阅无需再翻源码。

### 报告模板（源码级）

每份模块报告包含：
1. **文件清单** — 列出该模块所有源文件及行数
2. **逐文件分析** — 每个文件列出：
   - 所有类和函数签名
   - 每个类/函数的核心职责（一句话）
   - 关键实现细节（算法、状态机、线程模型）
3. **依赖关系** — 内部依赖（模块内文件间）和外部依赖（跨模块 import）
4. **设计模式与架构要点** — 使用的设计模式、异步模型、数据流
5. **潜在问题**（如有）— 代码异味、未使用的代码、安全关注点

### 执行策略

- 按模块复杂度分组，分为 3-4 批并行派遣 Explore 子代理
- 第一批（大模块各一个子代理）：`mcp`、`ui`、`plugins`
- 第二批（中模块合并）：`audio_codecs+audio_processing`、`core+bootstrap+protocols`、`logging+constants+utils+activation`
- 第三批：汇总 — 读取所有模块报告，生成 `00-summary.md`

### 输出目录

```
reports/
├── 00-summary.md
├── activation.md
├── audio_codecs.md
├── audio_processing.md
├── bootstrap.md
├── constants.md
├── core.md
├── logging.md
├── mcp.md
├── plugins.md
├── protocols.md
├── ui.md
├── utils.md
├── iot.md
└── views.md
```

## Out of Scope

* 修改任何源代码
* 运行测试或 lint
* 分析测试覆盖（`tests/` 目录不存在）
* 生成非 markdown 格式的报告（如 HTML/PDF）

## Technical Notes

* `src/iot/` 和 `src/views/` 目录下可能只有空壳，报告注明即可
* QML 文件集中在 `src/ui/gui/qml/` 下，15 个文件
* Explore 子代理只读模式，天然不会修改代码
