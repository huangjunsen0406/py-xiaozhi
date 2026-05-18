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


## Session 9: trellis-check 新增 PRD AC 验证步骤

**Date**: 2026-05-08
**Task**: trellis-check 新增 PRD AC 验证步骤
**Branch**: `feature/new_architecture`

### Summary

在 trellis-check skill 中新增 Step 5：回读 PRD Acceptance Criteria，区分可自动验证项（lint/文件存在/代码模式）与需手动测试项，通过则勾选 [x]，不可验证的保留 [ ] 并说明原因。同步更新 workflow.md Phase 2.2/3.1。用历史归档任务 05-07-refactor-activation 做 dry-run 验证分类正确。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `25f8832` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 10: 修复 MQTT/WSS 通信稳定性 + 提取协议基类重复代码

**Date**: 2026-05-08
**Task**: 修复 MQTT/WSS 通信稳定性 + 提取协议基类重复代码
**Branch**: `feature/new_architecture`

### Summary

修复 mqtt_protocol 的 loop_forever() 阻塞事件循环、UDP 显式绑定端口、print→logger；恢复 websocket_protocol 心跳检测；提取重复的监控/重连/清理逻辑到 protocol.py 基类，消除 273 行重复代码。reports/ 加入 .gitignore 仅本地查看。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `72b2ec8` | (see git log) |
| `30448ae` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 11: 修复 4 个高优先级问题 + 更新代码分析报告

**Date**: 2026-05-08
**Task**: 修复 4 个高优先级问题 + 更新代码分析报告
**Branch**: `feature/new_architecture`

### Summary

修复 #3 _on_network_error 硬编码依赖（移至 UIPlugin EventBus 订阅）、#5 删除 calendar/timer 空目录、#6 OpusCodec.close() 显式释放 C 资源、#7 WebSocket 移除冗余心跳。同步更新 reports/00-summary.md 和模块报告。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `22c6db2` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 12: ResourcePool 统一资源释放 + 退出稳定性修复

**Date**: 2026-05-08
**Task**: ResourcePool 统一资源释放 + 退出稳定性修复
**Branch**: `feature/new_architecture`

### Summary

引入 ResourcePool 统一资源释放机制（59行），逆序释放异常隔离；清理各插件 shutdown() 与 register_resources() 重复逻辑；修复 opus double free 崩溃、wake_word 退出阻塞、soxr nanobind 泄漏、coroutine never-awaited 警告等5个退出路径问题。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `9c4fabc` | (see git log) |
| `08dcd06` | (see git log) |
| `d4c12bc` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 13: 精简 logging 模块，修复日志系统问题

**Date**: 2026-05-08
**Task**: 精简 logging 模块，修复日志系统问题
**Branch**: `feature/new_architecture`

### Summary

logging 模块从 1959 行精简到 1339 行（-32%），删除未使用的 context.py 全文件、4 个未实例化的 filter/handler 类、ContextFilter；修复 except Exception: pass 裸吞异常、环境自适应覆盖 ConfigManager 级别、队列满静默丢弃 3 个 bug。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `1a2c1e3` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 14: 修复 camera 全链路阻塞 qasync 主线程

**Date**: 2026-05-08
**Task**: 修复 camera 全链路阻塞 qasync 主线程
**Branch**: `feature/new_architecture`

### Summary

修复3个阻塞问题: _load_cameras() cv2扫描移到后台线程, VLCamera OpenAI客户端加httpx.Timeout, capture_with_cv2()加ThreadPoolExecutor超时保护。更新MCP工具和PySide6规范。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `da7478f` | (see git log) |
| `4ece521` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 15: 清理 UI 模块死代码与 asyncio.create_task 保护

**Date**: 2026-05-08
**Task**: 清理 UI 模块死代码与 asyncio.create_task 保护
**Branch**: `feature/new_architecture`

### Summary

删除 EventBridge 4个零调用 emit_* 方法及未使用 Signal, 删除 _pending_events, 删除 shared/platform/ 空实现子模块, manager.py 3处 asyncio.create_task 迁移到 TaskManager.spawn()

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `807585f` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 16: 修复 UI 剩余 5 问题 — None 守卫、线程锁、monkey patch、弃用 API

**Date**: 2026-05-08
**Task**: 修复 UI 剩余 5 问题 — None 守卫、线程锁、monkey patch、弃用 API
**Branch**: `feature/new_architecture`

### Summary

activation.py _service is None 守卫, gpio/input.py _callbacks 加 Lock, cli/display.py 移除 Logger.addHandler monkey patch, event_bridge.py get_event_loop→get_running_loop + ensure_future→TaskManager.spawn, UISendTextData 移除

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `5825a2f` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 17: 重构音频配置解耦——设备层/协议层分离

**Date**: 2026-05-08
**Task**: 重构音频配置解耦——设备层/协议层分离
**Branch**: `feature/new_architecture`

### Summary

AudioConfig 协议参数改为动态可重载类属性，新增 reload() 方法从 ConfigManager 刷新；OpusCodec 移除 AudioConfig 默认参数依赖，由 AudioCodec 显式注入；AudioCodec 提取 _configure_pipeline() 消除 initialize/reload_devices 重复映射代码。修复 Settings UI 修改 opus_output_sample_rate/frame_duration 后热重载不生效的问题。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `f933cb9` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 18: 修复 core/ 模块 5 个已知问题

**Date**: 2026-05-08
**Task**: 修复 core/ 模块 5 个已知问题
**Branch**: `feature/new_architecture`

### Summary

根据 reports/core.md 分析报告，修复 EventBus 死锁代码、emit 防御性拷贝、is_audio_channel_opened 异常日志、send_audio 静默失败日志。TaskManager.spawn 返回 None 为有意设计无需改动。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `99e6708` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 19: 修复 plugins/constants 6个代码质量问题

**Date**: 2026-05-09
**Task**: 修复 plugins/constants 6个代码质量问题
**Branch**: `feature/new_architecture`

### Summary

根据 reports/plugins.md、constants.md 分析报告，清理 AudioPlugin._audio_consumer_task 死代码、ShortcutsPlugin 虚假 async、pynput_backend 未使用字段、WakeWordPlugin 同步方法风格统一、枚举改为 str+Enum 混入、移除未使用的 DeviceState.CONNECTING。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `9639f5e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 20: 修复 MCP 模块 JSON 注入、发现容错、相机代码优化

**Date**: 2026-05-14
**Task**: 修复 MCP 模块 JSON 注入、发现容错、相机代码优化
**Branch**: `feature/new_architecture`

### Summary

修复 MCP 模块 3 类问题：(1) 所有 camera/screenshot 工具的 f-string JSON 改为 json.dumps 消除注入风险；(2) decorators.py 工具自动发现加 try-except 容错；(3) BaseCamera 增加 image_data 参数消除 ScreenshotCamera 线程安全问题，新增 set_explain_url/token 默认实现移除 hasattr 检查。附带修复 mcp_server.py 的 id 遮蔽、error code 缺失、typing 清理、日志脱敏。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `42f96bd` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 21: 重构 MCP 模块：JSON 注入修复 + system 工具 psutil 重构

**Date**: 2026-05-14
**Task**: 重构 MCP 模块：JSON 注入修复 + system 工具 psutil 重构
**Branch**: `feature/new_architecture`

### Summary

两个任务：(1) 修复 MCP 模块 JSON f-string 注入、工具发现容错、相机代码 image_data 参数优化消除线程安全问题、mcp_server.py 的 request_id/error code 修复；(2) 用 psutil 重构 system 工具模块，删除 3 个平台 killer（-939 行），新增 process_manager.py 统一进程管理，修复 mac/windows/linux launcher 的命令注入漏洞（消除全部 shell=True），添加智能进程过滤只返回用户可见应用。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `42f96bd` | (see git log) |
| `02c6899` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 22: 迁移 volume_controller 到 system 工具模块

**Date**: 2026-05-14
**Task**: 迁移 volume_controller 到 system 工具模块
**Branch**: `feature/new_architecture`

### Summary

将 volume_controller.py 从 src/utils/ 迁移到 src/mcp/tools/system/，简化 tools.py 为模块级单例模式，清理 typing imports，修复 print → logger.warning。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `39368ed` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 23: 完善 Linux 音频依赖安装文档

**Date**: 2026-05-14
**Task**: 完善 Linux 音频依赖安装文档
**Branch**: `feature/new_architecture`

### Summary

重写系统依赖安装文档的 Linux 部分：按 Ubuntu 版本（20.04/22.04/24.04+）区分安装命令，说明 libasound-dev 包名变更和 PipeWire 默认音频服务器，增加树莓派说明、音频验证命令和故障排除（设备找不到、PA/PW 冲突）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `0e61112` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 24: 重写 MCP 开发指南文档

**Date**: 2026-05-14
**Task**: 重写 MCP 开发指南文档
**Branch**: `feature/new_architecture`

### Summary

重写 MCP 开发指南：删除过时架构说明和不存在的 calendar 模块，以灯控工具为完整案例覆盖带参数/无参数场景，说明 @mcp_tool API、自动发现规则和开发规范。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `6aa6082` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 25: 删除 bazi + 拆分 system 为 volume 和 app

**Date**: 2026-05-14
**Task**: 删除 bazi + 拆分 system 为 volume 和 app
**Branch**: `feature/new_architecture`

### Summary

删除 bazi 模块（5461 行），拆分 system 为独立的 volume（3 个音量工具）和 app（4 个应用管理工具）包，消除 3 层嵌套改为扁平结构，平台文件改为同级命名。文件 43→29，代码 11430→5878 行（-49%）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `0a9809b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 26: opus_loader 优先内置库 + utils 清理

**Date**: 2026-05-14
**Task**: opus_loader 优先内置库 + utils 清理
**Branch**: `feature/new_architecture`

### Summary

opus_loader 加载顺序改为内置优先、系统兜底，删除死代码（patched_find_library、restore_find_library），用模块级变量替代 sys._opus_loaded。附带清理 activation_announcer.py（编码头+typing）和 audio_utils.py（PEP 8 空行）。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `eaf7b1e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 27: 音乐播放器 API 替换与竞态修复

**Date**: 2026-05-15
**Task**: 音乐播放器 API 替换与竞态修复
**Branch**: `feature/new_architecture`

### Summary

替换已关停的 TuneFree API，改用酷我搜索+Huibq直链+酷我歌词三接口组合；新增独立音乐设置Tab；修复TTS与音乐竞态、FFmpeg seek科学计数法、退出时子进程残留等问题

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `6ed9d30` | (see git log) |
| `28bcaf4` | (see git log) |
| `771389c` | (see git log) |
| `fc2b877` | (see git log) |
| `3570f28` | (see git log) |
| `93b8f0b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 28: fix: 音乐下载阻塞 UI + macOS Metal shader 崩溃

**Date**: 2026-05-15
**Task**: fix: 音乐下载阻塞 UI + macOS Metal shader 崩溃
**Branch**: `feature/new_architecture`

### Summary

诊断并修复两个打包后问题：(1) _download_file 中 iter_content 阻塞事件循环导致 UI 卡顿，将下载+写入+move 整体移入 asyncio.to_thread；(2) macOS Sequoia adhoc 签名 app Metal shader 缓存写入被拒，设置 QSG_RHI_BACKEND=opengl 绕过。已提 PR #275 合入 main。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `362aece` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 29: feat(ci): 多平台自动打包 workflow + Windows 调试修复

**Date**: 2026-05-15
**Task**: feat(ci): 多平台自动打包 workflow + Windows 调试修复
**Branch**: `feature/new_architecture`

### Summary

创建 .github/workflows/build.yml 实现 tag push 时 5 平台并行打包（macOS arm64/x64、Windows x64、Linux x64/arm64）。使用 uv + unifypy。迭代修复 Windows CI 问题：ISCC.exe 退出码、uv run --no-sync 防卸载、PYTHONIOENCODING=utf-8 修复 rich 编码崩溃。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `bf5faee` | (see git log) |
| `cce58eb` | (see git log) |
| `38b45fb` | (see git log) |
| `6b8383a` | (see git log) |
| `fc72780` | (see git log) |
| `01f2a9a` | (see git log) |
| `f491d54` | (see git log) |
| `d6d830a` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 30: feat: CI 打包 FFmpeg + 日志修复 + CI 迭代完善

**Date**: 2026-05-15
**Task**: feat: CI 打包 FFmpeg + 日志修复 + CI 迭代完善
**Branch**: `feature/new_architecture`

### Summary

1. CI 打包 FFmpeg 到应用内，解决启动台找不到 ffmpeg 的问题；2. 修复 DuplicateFilter 共享实例导致文件日志丢失的 bug；3. CI workflow 多轮迭代修复（Windows Inno Setup PATH、uv run --no-sync、PYTHONIOENCODING、产物路径、Linux 编译依赖）；4. build.json name 改为 ASCII 避免路径编码问题。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `0fdada1` | (see git log) |
| `c0a26b5` | (see git log) |
| `cb0643e` | (see git log) |
| `ad4905c` | (see git log) |
| `9a1d623` | (see git log) |
| `03f7e26` | (see git log) |
| `d6d830a` | (see git log) |
| `f491d54` | (see git log) |
| `01f2a9a` | (see git log) |
| `fc72780` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 31: GUI 切换自动对话按钮文案不同步修复

**Date**: 2026-05-17
**Task**: GUI 切换自动对话按钮文案不同步修复
**Branch**: `feature/new_architecture`

### Summary

MainModel.set_auto_mode 切换模式时同步刷新 _button_text 并 emit buttonTextChanged，修复 QML manualBtn/autoBtn 共享 buttonText 在切换自动模式后仍显示"按住后说话"的问题；统一默认值为"按住后说话"。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `8d97ffa` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 32: fix: Opus 帧时长自动检测 + 输出回调循环取 chunk

**Date**: 2026-05-18
**Task**: fix: Opus 帧时长自动检测 + 输出回调循环取 chunk
**Branch**: `feature/new_architecture`

### Summary

解析 Opus TOC 字节自动检测服务端帧时长，解决 buffer too small 和非整除采样率卡顿；output_callback 改为循环取 chunk + drain 剩余数据避免整帧静音

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `c48ea3c` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 33: feat: system.py 唯一真相源 + release.py 自动发版 + 配置文档更新

**Date**: 2026-05-18
**Task**: feat: system.py 唯一真相源 + release.py 自动发版 + 配置文档更新
**Branch**: `feature/new_architecture`

### Summary

system.py 为版本/名称唯一真相源，新建 release.py 替代 release.js 实现交互式发版；build.json 从 system.py 动态生成；APP_DISPLAY_NAME 改为小智；更新配置说明文档指向用户数据目录

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `b1bb5c8` | (see git log) |
| `e8dffb3` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 34: docs: 升级项目定位 + README 专业化 + PyInstaller spec

**Date**: 2026-05-18
**Task**: docs: 升级项目定位 + README 专业化 + PyInstaller spec
**Branch**: `feature/new_architecture`

### Summary

项目定位从语音客户端升级为跨平台多模态 AI 交互主控框架；英文 README 重写突出 embodied AI / edge computing；VitePress tagline 同步；添加 py-xiaozhi.spec

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `492320e` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 35: fix: 自动对话模式 tts.stop 清缓冲区防回声 + v2.0.5 发布

**Date**: 2026-05-18
**Task**: fix: 自动对话模式 tts.stop 清缓冲区防回声 + v2.0.5 发布
**Branch**: `feature/new_architecture`

### Summary

自动对话模式 tts.stop 切 LISTENING 前清空 output_buffer 和 resampler 缓冲区，防止麦克风录到残留 TTS 音频；手动模式不受影响；已合并 main 并发布 v2.0.5

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `555f114` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
