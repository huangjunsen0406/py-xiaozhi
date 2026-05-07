# Journal - junsen (Part 1)

> AI development session journal
> Started: 2026-05-07

---



## Session 1: 去除 AEC dead code + 接入 Trellis 工作流 + 项目 spec 体系

**Date**: 2026-05-07
**Task**: 去除 AEC dead code + 接入 Trellis 工作流 + 项目 spec 体系
**Branch**: `feature/new_architecture`

### Summary

1) 删除 src/audio_codecs/aec_processor.py (461 行) + scripts/webrtc_aec_demo.py (656 行): 经全仓库 grep 验证为孤岛代码,从未接入主链路 (AudioListener 协议要求 on_audio_data 但该类只暴露 process_audio,签名不兼容)。AEC_OPTIONS / ListeningMode.REALTIME / libs/webrtc_apm/ / 设置 UI 全部保留,作为后续音频路径重构的接入点。2) 建立 .trellis/spec/backend/ 下 10 份中文规范 (架构原则 / Python 风格 / asyncio / PySide6 / 日志 / 错误处理 / 目录结构 / 质量 / MCP 工具 / 索引),全部基于真实代码模式,标注现存反模式的具体 file:line。3) 接入 Trellis + Claude Code 工作流基础设施 (.trellis/ + .claude/ + AGENTS.md),配置 .gitignore 忽略 settings.local.json 和草稿。4) 完成 src/ 架构深度分析与启动性能瓶颈定位 (实测 3.5s,主要瓶颈: SettingsModel 的 OpenCV camera 探测 1140ms / WakeWord sherpa-onnx 加载 577ms / MCP discover_tool_modules 257ms)。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `7360e4d` | (see git log) |
| `3fdb654` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 新增 Git 工作流与提交规范 spec

**Date**: 2026-05-07
**Task**: 新增 Git 工作流与提交规范 spec
**Branch**: `feature/new_architecture`

### Summary

新增 .trellis/spec/backend/git-workflow.md (301 行) 沉淀项目事实上的工作流: GitHub Flow (main + feature/*, 不引入 develop)、Conventional Commits 完整规则 (type/scope/subject 中文 ≤ 25 字 / body 解释 why / footer)、commit 拆分要求 (rebase + ff 必须每 commit 独立可运行)、PR 流程 (rebase 保线性 / maintainer 用 --ff-only 合并 / 合后删分支)、SemVer 手动 tag、AI Co-Authored-By trailer 固定格式、11 条反模式清单。同步更新 index.md 注册新条目, quality-guidelines.md 在跨规范禁止项加 git/commit 条目并新增评审清单 'Git/Commit' 段。本任务自身严格按新规范实施 (commit 走 docs(spec) + 中文 subject 11 字 + body 解释 why + Co-Authored-By),作为规范自检。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `931fb01` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: 解耦 CLI 与 GUI 依赖

**Date**: 2026-05-07
**Task**: 解耦 CLI 与 GUI 依赖
**Branch**: `feature/new_architecture`

### Summary

将 PySide6 + qasync 从核心依赖拆分为可选 extra [gui]，CLI 模式不再需要 GUI 库。添加 import 守卫，缺失时给出清晰安装提示。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `745f80e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: 激活流程重构：提取 BaseActivation + 补充 spec

**Date**: 2026-05-07
**Task**: 激活流程重构：提取 BaseActivation + 补充 spec
**Branch**: `feature/new_architecture`

### Summary

消除 GUI/CLI/GPIO 激活代码重复：提取 BaseActivation 模板方法基类，GUIActivation 通过多重继承（QObject+BaseActivation）复用核心流程。补充 pyside6-guidelines.md（多重继承规则，来源 Shiboken 官方文档）和 architecture-principles.md（Template Method+工厂正例）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `1743847` | (see git log) |
| `76e3913` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: 补充遗留代码修复规范

**Date**: 2026-05-07
**Task**: 补充遗留代码修复规范
**Branch**: `feature/new_architecture`

### Summary

在 architecture-principles.md 新增「遗留代码处理」章节：接触即修、不复刻旧写法、范围限当前 diff。补充了 pyside6-guidelines.md 中已有提及的通用化表述。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `bb706fd` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: 消灭 except Exception: pass — 40+ 处静默吞异常修复

**Date**: 2026-05-07
**Task**: 消灭 except Exception: pass — 40+ 处静默吞异常修复
**Branch**: `feature/new_architecture`

### Summary

扫描到 16 个文件中 40+ 处 except Exception: pass，全部替换为分级日志。高危修复 mcp.py（4处）和 manager.py（5处）的静默吞异常，mcp.py 的 add_common_tools() 失败现在有 exc_info=True。全局规则：功能级异常 → logger.error，清理级 → logger.debug。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `acd4202` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: 修复唤醒词初始化流程：释放顺序 + 竞态条件

**Date**: 2026-05-07
**Task**: 修复唤醒词初始化流程：释放顺序 + 竞态条件
**Branch**: `feature/new_architecture`

### Summary

从日志'模型资源已释放'出现在'sherpa_onnx未安装'之前的反常顺序发现 initialize() 流程问题。三个修复：_release_model() 加 _model_loaded 守卫、_load_model() 用 _onnx_lock 保护赋值、initialize() 重排为配置检查→参数→路径→释放→加载。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `24eb5f7` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: 修复 Linux 唤醒词打断慢/失效问题

**Date**: 2026-05-08
**Task**: 修复 Linux 唤醒词打断慢/失效问题
**Branch**: `feature/new_architecture`

### Summary

经过多轮迭代修复唤醒词打断问题：保留原有轮询模式（事件驱动 queue.get() 会饿死事件循环），添加哨兵停止避免 Python 3.10 task pending 错误，检测到唤醒词后暂停并排空队列防重复触发，移除 TTS stop 中的 clear_audio_queue 修复尾部截断。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `dc679d2` | (see git log) |
| `ada760e` | (see git log) |
| `a516799` | (see git log) |
| `adfcd9b` | (see git log) |
| `c39b6aa` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
