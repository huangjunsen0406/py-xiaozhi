# Workspace Index - junsen

> Journal tracking for AI development sessions.

---

## Current Status

<!-- @@@auto:current-status -->
- **Active File**: `journal-1.md`
- **Total Sessions**: 25
- **Last Active**: 2026-05-14
<!-- @@@/auto:current-status -->

---

## Active Documents

<!-- @@@auto:active-documents -->
| File | Lines | Status |
|------|-------|--------|
| `journal-1.md` | ~843 | Active |
<!-- @@@/auto:active-documents -->

---

## Session History

<!-- @@@auto:session-history -->
| # | Date | Title | Commits | Branch |
|---|------|-------|---------|--------|
| 25 | 2026-05-14 | 删除 bazi + 拆分 system 为 volume 和 app | `0a9809b` | `feature/new_architecture` |
| 24 | 2026-05-14 | 重写 MCP 开发指南文档 | `6aa6082` | `feature/new_architecture` |
| 23 | 2026-05-14 | 完善 Linux 音频依赖安装文档 | `0e61112` | `feature/new_architecture` |
| 22 | 2026-05-14 | 迁移 volume_controller 到 system 工具模块 | `39368ed` | `feature/new_architecture` |
| 21 | 2026-05-14 | 重构 MCP 模块：JSON 注入修复 + system 工具 psutil 重构 | `42f96bd`, `02c6899` | `feature/new_architecture` |
| 20 | 2026-05-14 | 修复 MCP 模块 JSON 注入、发现容错、相机代码优化 | `42f96bd` | `feature/new_architecture` |
| 19 | 2026-05-09 | 修复 plugins/constants 6个代码质量问题 | `9639f5e` | `feature/new_architecture` |
| 18 | 2026-05-08 | 修复 core/ 模块 5 个已知问题 | `99e6708` | `feature/new_architecture` |
| 17 | 2026-05-08 | 重构音频配置解耦——设备层/协议层分离 | `f933cb9` | `feature/new_architecture` |
| 16 | 2026-05-08 | 修复 UI 剩余 5 问题 — None 守卫、线程锁、monkey patch、弃用 API | `5825a2f` | `feature/new_architecture` |
| 15 | 2026-05-08 | 清理 UI 模块死代码与 asyncio.create_task 保护 | `807585f` | `feature/new_architecture` |
| 14 | 2026-05-08 | 修复 camera 全链路阻塞 qasync 主线程 | `da7478f`, `4ece521` | `feature/new_architecture` |
| 13 | 2026-05-08 | 精简 logging 模块，修复日志系统问题 | `1a2c1e3` | `feature/new_architecture` |
| 12 | 2026-05-08 | ResourcePool 统一资源释放 + 退出稳定性修复 | `9c4fabc`, `08dcd06`, `d4c12bc` | `feature/new_architecture` |
| 11 | 2026-05-08 | 修复 4 个高优先级问题 + 更新代码分析报告 | `22c6db2` | `feature/new_architecture` |
| 10 | 2026-05-08 | 修复 MQTT/WSS 通信稳定性 + 提取协议基类重复代码 | `72b2ec8`, `30448ae` | `feature/new_architecture` |
| 9 | 2026-05-08 | trellis-check 新增 PRD AC 验证步骤 | `25f8832` | `feature/new_architecture` |
| 8 | 2026-05-08 | 修复 Linux 唤醒词打断慢/失效问题 | `dc679d2`, `ada760e`, `a516799`, `adfcd9b`, `c39b6aa` | `feature/new_architecture` |
| 7 | 2026-05-07 | 修复唤醒词初始化流程：释放顺序 + 竞态条件 | `24eb5f7` | `feature/new_architecture` |
| 6 | 2026-05-07 | 消灭 except Exception: pass — 40+ 处静默吞异常修复 | `acd4202` | `feature/new_architecture` |
| 5 | 2026-05-07 | 补充遗留代码修复规范 | `bb706fd` | `feature/new_architecture` |
| 4 | 2026-05-07 | 激活流程重构：提取 BaseActivation + 补充 spec | `1743847`, `76e3913` | `feature/new_architecture` |
| 3 | 2026-05-07 | 解耦 CLI 与 GUI 依赖 | `745f80e` | `feature/new_architecture` |
| 2 | 2026-05-07 | 新增 Git 工作流与提交规范 spec | `931fb01` | `feature/new_architecture` |
| 1 | 2026-05-07 | 去除 AEC dead code + 接入 Trellis 工作流 + 项目 spec 体系 | `7360e4d`, `3fdb654` | `feature/new_architecture` |
<!-- @@@/auto:session-history -->

---

## Notes

- Sessions are appended to journal files
- New journal file created when current exceeds 2000 lines
- Use `add_session.py` to record sessions