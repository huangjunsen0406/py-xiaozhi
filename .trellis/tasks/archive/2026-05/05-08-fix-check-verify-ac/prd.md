# 让 trellis-check 对标 PRD 验收标准逐项勾选

## Goal

`trellis-check` 子代理在实现完成后，必须回读 PRD 的 Acceptance Criteria，逐项验证并勾选 `[x]`，然后提交更新后的 PRD。解决当前归档任务中大量 AC 未勾选、无法判断是否真正完成的问题。

## What I already know

* `trellis-check` skill 位于 `.claude/skills/trellis-check/SKILL.md`，当前有 6 个步骤：识别变更 → 读 spec → lint/type-check/tests → checklist → cross-layer → report
* `workflow.md` Phase 2.2 和 Phase 3.1 都会调用 trellis-check
* Phase 2.2：实现完成后检查（可重复）
* Phase 3.1：最终质量验证（可重复）
* 当前 check 不包含 PRD AC 验证步骤
* 归档任务中 6/8 有未勾选的 AC 项
* PRD 中的 AC 使用 markdown checkbox 格式：`- [ ] <描述>`

## Requirements

1. `trellis-check` 新增 Step：读取任务 PRD 的 Acceptance Criteria，逐项验证
2. 对于可验证的 AC（lint pass、功能行为等），验证后勾选 `[x]`
3. 对于无法自动验证的 AC（如手动测试项），标记为待用户确认并保持 `[ ]`
4. 提交更新后的 PRD（勾选后的版本）到仓库，作为 check 输出的一部分
5. 不影响现有 check 流程，作为追加步骤

## Acceptance Criteria

* [x] 修改后的 `trellis-check` skill 包含 PRD AC 验证步骤
* [x] `workflow.md` Phase 2.2 / 3.1 描述更新，体现 AC 验证
* [x] 拿一个历史归档任务验证：check 能正确识别可验证/不可验证的 AC 项
* [x] 验证后不可验证的 AC 保留 `[ ]`，可验证且通过的改为 `[x]`

## Definition of Done

* trellis-check skill 更新完成
* workflow.md 相关段落更新
* 用至少一个历史任务 PRD 做 dry-run 验证

## Technical Approach

修改 `.claude/skills/trellis-check/SKILL.md`，在 Step 4 之后新增 Step：

### 新增 Step: PRD Acceptance Criteria Verification

1. 读取 `{TASK_DIR}/prd.md` 中的 `## Acceptance Criteria` 段
2. 解析所有 `- [ ]` 复选框项
3. 对每项判断：
   - **可自动验证**：lint pass、type-check pass、文件存在、代码模式匹配 → 执行验证，通过则勾选 `[x]`
   - **不可自动验证**：需要手动测试、需要特定硬件/环境 → 标记保留 `[ ]`，并说明原因
4. 用 Edit 工具将通过的项从 `[ ]` 改为 `[x]`
5. 在 check 输出中报告验证结果

### workflow.md 更新

在 Phase 2.2 和 Phase 3.1 的 check 描述中，明确提到 PRD AC 验证。

## Decision (ADR-lite)

**Context**: trellis-check 子代理当前不验证 PRD AC，导致归档任务 AC 大量未勾选。
**Decision**: 在 trellis-check 中新增 PRD AC 验证步骤，Auto-verifiable 的勾选，manual-only 的保留 `[ ]` 并说明原因。Phase 2.2 和 3.1 都跑此步骤。
**Consequences**: 归档时 PRD 的 AC 勾选状态能真实反映完成情况，手动测试项仍需用户确认。

## Out of Scope

* 修改 `task.py archive` 的逻辑
* 回填历史归档任务的 AC 勾选
* 自动化手动测试项（不在本次范围）

## Technical Notes

* 关键文件：
  - `.claude/skills/trellis-check/SKILL.md` — 主要修改目标
  - `.trellis/workflow.md` — 同步更新 Phase 2.2 / 3.1 描述
* trellis-check 子代理有 Edit 工具权限，可以直接修改 PRD
* 任务目录路径需要从 check.jsonl 上下文或当前 task 指针获取
