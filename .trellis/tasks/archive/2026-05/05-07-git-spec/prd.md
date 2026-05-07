# PRD: 新增 Git 工作流与提交规范 spec

## 背景

项目目前事实上采用以下工作流,但 **没有规范文件** 描述:

- **分支模型**: `main` + `feature/*`,无 `develop/`(GitHub Flow,不是经典 GitFlow)。
- **commit 风格**: Conventional Commits(`feat:`、`fix:`、`chore:`、`chore(task):`),中文 subject。
- **分支命名混乱**: 仓库实际存在 `feature/aec`、`feat/custome_emoji`、`feat/定制化`、`bugfix/webrtc_apm` 等多种风格,需要收敛。
- **无 tag / 无 release**: `pyproject.toml` 写 `1.0.0` 但未在 git 中打 tag,版本与代码不挂钩。
- **AI 协作**: 已使用 `Co-Authored-By: Claude` 的 trailer,需要约定。

## 决策(已与用户确认)

1. **分支模型**: GitHub Flow(`main` + `feature/*`,**不引入 `develop/`**)。
2. **合并策略**: PR 上做 **rebase + fast-forward**,不产生 merge commit。这要求每个 commit 自身可独立运行(否则二分查找会断)。
3. **版本号**: 手动 SemVer tag(`vMAJOR.MINOR.PATCH`),`fix` 进 PATCH,`feat` 进 MINOR,breaking change 进 MAJOR。`pyproject.toml` 的 version 与 tag 同步更新。

## 目标

写一份 `.trellis/spec/backend/git-workflow.md`,描述:

- 分支模型与命名规范
- Conventional Commits 完整规则(type / scope / subject / body / footer)
- commit 拆分原则(rebase + ff 要求每个 commit 独立可运行)
- PR / merge 流程
- SemVer + 手动 tag
- AI 协作的 `Co-Authored-By` 约定
- 反模式与禁止项

并在 `.trellis/spec/backend/index.md` 注册新条目,在 `quality-guidelines.md` 评审清单中加一段"git/commit"条目。

## 范围

### 新增

| 文件 | 内容 |
|---|---|
| `.trellis/spec/backend/git-workflow.md` | 完整规范 |

### 修改

| 文件 | 内容 |
|---|---|
| `.trellis/spec/backend/index.md` | 索引表新增一行 [Git 工作流](./git-workflow.md) |
| `.trellis/spec/backend/quality-guidelines.md` | "Forbidden patterns (cross-cutting)" 与 "Review checklist" 加 git/commit 项 |

### 不动

- 现有 git 历史(`3635e94` 这种 merge commit 不追溯,从规范生效起执行)
- 现有分支(`feature/new_architecture` 等)的命名,等下次创建新分支时按新规范走
- `pyproject.toml` 的 `1.0.0` 版本号(等首次打 tag 时同步)
- 主分支保护、CI/CD 等仓库管理员配置(超出 spec 范围)

## 内容要点

`git-workflow.md` 至少覆盖以下条目,每条带具体例子:

### 分支模型
- `main` 永远可发布
- 新工作建 `feature/<kebab-case>` (英文,小写,短横连接)
- bug 修复建 `fix/<kebab-case>`(替代当前混用的 `bugfix/`)
- 紧急线上修复建 `hotfix/<kebab-case>`,从 `main` 拉,修完直接 PR 回 `main` + 打 PATCH tag
- 禁止中文分支名(影响跨平台 / CI 工具)

### Commit message
- 格式: `<type>(<scope>)?: <subject>`(中文 subject 可)
- type 限定: `feat` / `fix` / `chore` / `docs` / `style` / `refactor` / `perf` / `test` / `build` / `ci`
- scope 可选,使用 `src/` 下顶层包名(`audio_codec`、`mcp`、`plugins/wake_word` 等)
- subject 短(≤ 50 字符,中文不超过 25 字),不以句号结尾,祈使句
- body 可选,空行分隔,解释 **为什么** 而不是 **是什么**
- footer 可选: `Co-Authored-By: <name> <email>`,`BREAKING CHANGE: ...`,`Fixes: #123`

### Commit 拆分
- 因为合并走 rebase + ff,**每个 commit 必须能独立编译/运行**
- 一个 commit 一件事(重构与功能不混)
- 禁止 "WIP"、"修了下"、"Update X.py" 这种空洞 message

### PR 流程
- 基于最新 `main` 拉分支,定期 `git fetch && git rebase origin/main` 保持线性
- PR 描述包含: 动机 / 方案 / 验证步骤(对应 PRD 的"验证")
- review 通过后 squash 内部草稿 commit(若有),最终 push,maintainer 用 `git merge --ff-only` 合并
- 合并后 **删除分支**

### SemVer tag
- 格式: `v<MAJOR>.<MINOR>.<PATCH>`
- 合并到 main 后立即打 tag(若该 PR 包含 user-visible 变更)
- 同步更新 `pyproject.toml` 的 version
- 内部重构 / spec / docs 类不打 tag(没有 user 变更)

### AI 协作 trailer
- AI 参与的 commit 加 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`
- 仅在 AI 真正参与代码修改时加,纯人写不加
- 不是免责声明,是事实标记

### 反模式
- 主分支直接 push
- `git commit --no-verify` 跳过 hook(除非用户明确要求)
- `git commit --amend` 修改已 push 的 commit
- `git push --force` 到共享分支
- 一个 commit 同时改超过 5 个文件且涉及 ≥ 2 个域

## 验证

1. **新文件结构正确**: `git-workflow.md` 含上述全部章节,每节有具体例子
2. **索引同步**: `index.md` 表格里能找到新条目
3. **quality-guidelines.md 串通**: review checklist 里能找到 "git/commit" 段
4. **本任务自身遵守新规范**: 实施完毕的 commit message 严格按新规范写(`docs(spec):` 或 `chore(spec):` 前缀,subject ≤ 25 中文字符,有 body 解释 why,有 Co-Authored-By trailer)

## 实施顺序

1. 写 `.trellis/spec/backend/git-workflow.md`
2. 更新 `.trellis/spec/backend/index.md` 添加索引条目
3. 更新 `.trellis/spec/backend/quality-guidelines.md` 加 review 项
4. 自检: 本任务的 commit message 是否符合新规范
5. commit (单个 commit,前缀 `docs(spec):`)

## 风险

极低 — 纯文档,无代码改动,无运行时影响。唯一风险是规范与团队后续实践偏离,但规范是"接触即更新"的(spec 里已有约定),后续 PR 发现不符自然会修。
