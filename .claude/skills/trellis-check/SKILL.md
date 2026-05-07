---
name: trellis-check
description: "Comprehensive quality verification: spec compliance, lint, type-check, tests, cross-layer data flow, code reuse, and consistency checks. Use when code is written and needs quality verification, before committing changes, or to catch context drift during long sessions."
---

# Code Quality Check

Comprehensive quality verification for recently written code. Combines spec compliance, cross-layer safety, and pre-commit checks.

---

## Step 1: Identify What Changed

```bash
git diff --name-only HEAD
git status
```

## Step 2: Read Applicable Specs

```bash
python3 ./.trellis/scripts/get_context.py --mode packages
```

For each changed package/layer, read the spec index and follow its **Quality Check** section:

```bash
cat .trellis/spec/<package>/<layer>/index.md
```

Read the specific guideline files referenced — the index is a pointer, not the goal.

## Step 3: Run Project Checks

Run the project's lint, type-check, and test commands. Fix any failures before proceeding.

## Step 4: Review Against Checklist

### Code Quality

- [ ] Linter passes?
- [ ] Type checker passes (if applicable)?
- [ ] Tests pass?
- [ ] No debug logging left in?
- [ ] No suppressed warnings or type-safety bypasses?

### Test Coverage

- [ ] New function → unit test added?
- [ ] Bug fix → regression test added?
- [ ] Changed behavior → existing tests updated?

### Spec Sync

- [ ] Does `.trellis/spec/` need updates? (new patterns, conventions, lessons learned)

> "If I fixed a bug or discovered something non-obvious, should I document it so future me won't hit the same issue?" → If YES, update the relevant spec doc.

## Step 5: PRD Acceptance Criteria Verification

### 5A. Locate the PRD

Find the current task's `prd.md`. Use one of these methods in order:

1. Run `python3 ./.trellis/scripts/task.py current --source` to get the active task directory
2. If no active task, check for a task directory matching the current git branch name under `.trellis/tasks/`
3. If neither works, skip this step and note that the PRD could not be located

### 5B. Parse Acceptance Criteria

Read the `## Acceptance Criteria` section from the PRD. Parse all checkbox items:

- `- [ ] <description>` — unchecked, needs verification
- `- [x] <description>` — already checked, skip

### 5C. Classify Each Unchecked Item

For each `- [ ]` item, determine whether it can be auto-verified by this agent:

**Auto-verifiable** (this agent can confirm directly):
- Lint passes, type-check passes, tests pass
- A specific file exists at a known path
- A specific code pattern is present (grep for function signature, import, class name, etc.)
- A specific configuration value is set
- A command produces expected output

**Manual-only** (requires the user, specific hardware, or subjective judgment):
- Requires a specific hardware device (e.g., "Pi 上测试唤醒词检测成功率 > 90%")
- Requires manual UI interaction (e.g., "手动测试按钮点击效果")
- Requires subjective human judgment (e.g., "代码可读性良好")
- Requires an environment this agent cannot access (e.g., "在 Windows 上验证")
- Contains vague or qualitative criteria that cannot be checked programmatically

### 5D. Verify and Check Off

For each auto-verifiable item that passes: use the Edit tool to change `- [ ]` to `- [x]` in the PRD.

For each auto-verifiable item that **fails**: leave as `- [ ]` and note the failure in the report.

For each manual-only item: leave as `- [ ]` and note in the report why it cannot be auto-verified.

### 5E. Report

Report a summary in the check output:

```
## PRD Acceptance Criteria Verification

### Verified and checked off
- [x] Linter passes
- [x] Type checker passes

### Failed (auto-verifiable, needs fixing)
- [ ] Tests pass → 3 test failures in test_auth.py

### Skipped (manual verification required)
- [ ] Pi 上测试唤醒词检测成功率 > 90% → 需要 Pi 硬件
- [ ] 手动测试 UI 交互 → 需要手动操作
```

> Do NOT check off items you cannot verify. A false `[x]` is worse than a missing `[x]`.

## Step 6: Cross-Layer Dimensions (if applicable)

Skip this step if your change is confined to a single layer.

### A. Data Flow (changes touch 3+ layers)

- [ ] Read flow traces correctly: Storage → Service → API → UI
- [ ] Write flow traces correctly: UI → API → Service → Storage
- [ ] Types/schemas correctly passed between layers?
- [ ] Errors properly propagated to caller?

### B. Code Reuse (modifying constants, creating utilities)

- [ ] Searched for existing similar code before creating new?
  ```bash
  grep -r "pattern" src/
  ```
- [ ] If 2+ places define same value → extracted to shared constant?
- [ ] After batch modification, all occurrences updated?

### C. Import/Dependency (creating new files)

- [ ] Correct import paths (relative vs absolute)?
- [ ] No circular dependencies?

### D. Same-Layer Consistency

- [ ] Other places using the same concept are consistent?

---

## Step 7: Report and Fix

Report violations found and fix them directly. Re-run project checks after fixes.
