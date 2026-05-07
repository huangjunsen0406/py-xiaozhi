# Git 工作流

> 单仓库、单 `main` 分支的 GitHub Flow。本规范描述 **标准**,而不是仓库当前的全部现状 —— 历史遗留的中文分支名、`bugfix/` 前缀、merge commit 等不追溯,从规范生效起按本文档执行,**接触即更新**。

---

## 分支模型

采用 **GitHub Flow**: `main` + 短生命周期 feature 分支,**不引入 `develop/`**,**不引入 release 分支**。

- `main` —— 永远可发布(deployable)。任何 commit 跑起来都不应崩。
- `feature/<name>` —— 新功能 / 改动。
- `fix/<name>` —— bug 修复(替代历史上混用的 `bugfix/`)。
- `hotfix/<name>` —— 紧急线上修复,从 `main` 拉,修完直接 PR 回 `main` 并打 PATCH tag。
- `chore/<name>` —— 工具、依赖、配置等非功能性改动。
- `docs/<name>` —— 仅文档/spec 改动。
- `refactor/<name>` —— 不改外部行为的重构。

### 分支命名

- **英文 kebab-case**: 全小写,单词之间用 `-` 连接。
- **不要中文**: 仓库 `feat/定制化` 这种分支名属于反例 —— 中文在 git hook、CI 工具、URL、cherry-pick 命令里都可能出问题。下次新建分支按规范走,旧分支不强行改名。
- **不要下划线**: 仓库 `feature/audio_select`、`bugfix/webrtc_apm` 这种属于历史遗留;新分支用 `feature/audio-select`、`fix/webrtc-apm`。
- **简短**: 不超过 4-5 个单词。能用 issue 编号就用: `fix/issue-123-mqtt-sample-rate`。
- **前缀必填**: `feature/` / `fix/` / `hotfix/` / `chore/` / `docs/` / `refactor/`,不允许直接 `myname/xxx` 这种个人命名空间。

### 历史与现状

仓库当前并存多种风格:

| 现状分支 | 评价 |
|---|---|
| `feature/new_architecture` | 下划线遗留,前缀正确;新分支应写 `feature/new-architecture` |
| `bugfix/webrtc_apm` | 前缀错(应为 `fix/`)+ 下划线;新分支写 `fix/webrtc-apm` |
| `feat/定制化` | 中文(禁止)+ 前缀写法不一致(应为 `feature/`);**反例** |
| `feature/aec` | 合规 |
| `refactor/audio_codec` | 前缀正确,下划线遗留;新分支用 `refactor/audio-codec` |

不主动批量改名既有分支,但合并/删除时按新规范命名后续分支。

---

## Commit message

使用 **Conventional Commits**,subject 中文。

### 格式

```
<type>(<scope>)?: <subject>

<body 可选,空行分隔,解释 why>

<footer 可选,空行分隔>
```

### type(限定列表)

| type | 含义 | 进 SemVer |
|---|---|---|
| `feat` | 新功能(用户可见) | MINOR |
| `fix` | bug 修复(用户可见) | PATCH |
| `perf` | 性能优化(用户可见) | PATCH |
| `refactor` | 重构,不改外部行为 | 不打 tag |
| `docs` | 文档 / spec 改动 | 不打 tag |
| `style` | 仅格式化(空格、换行、引号),无逻辑变化 | 不打 tag |
| `test` | 测试代码 | 不打 tag |
| `build` | 构建系统 / 依赖 (`pyproject.toml`、`requirements.txt`) | 不打 tag |
| `ci` | CI 配置 | 不打 tag |
| `chore` | 杂项(脚本、工具、归档),不属于上面任何一类 | 不打 tag |

不在表里的 type 一律不允许。

### scope(可选)

scope 用 **`src/` 下的顶层包名或子包名**,小写。多级用 `/` 连:

- `feat(audio_codec):` —— 改动落在 `src/audio_codec/` 下
- `fix(plugins/wake_word):` —— 改动落在 `src/plugins/wake_word/` 下
- `feat(mcp):` —— 改动落在 `src/mcp/` 下
- `docs(spec):` —— 改动落在 `.trellis/spec/` 下
- `chore(task):` —— Trellis 任务流相关(`.trellis/tasks/`)

scope 可省略 —— 跨多个域、或只是仓库级别配置时直接 `chore: 升级 ruff 到 0.5`。

### subject

- **中文 ≤ 25 字**(英文 ≤ 50 字符),祈使句。
- **不以句号结尾**。
- 不重复 type / scope 已经表达过的信息: `feat(audio_codec): 新增` 是错的(没说做了啥);`feat(audio_codec): 新增 AEC processor 实现` 才对。
- 不写"Update X.py"、"修了下"、"WIP" 这种空洞 message。

### body(可选)

- 与 subject 之间用 **空行** 分隔。
- 解释 **为什么** 做这件事、**取舍**、**注意事项**,而不是 **做了什么**(diff 已经说明)。
- 每行 ≤ 72 字符(中文不强制,但段落不要太长)。

### footer(可选)

footer 与 body 之间用 **空行** 分隔。常见 trailer:

- `BREAKING CHANGE: <说明>` —— 触发 MAJOR bump,**必须** 显式写。
- `Fixes: #123` / `Closes: #123` —— 关联 issue。
- `Co-Authored-By: <name> <email>` —— 协作者(见下文 AI 协作)。

### 例子

合规范例(取自仓库历史):

```
chore: 移除未使用的 AEC processor 实现与 demo

旧 AEC 实现已被 webrtc_apm 路径替代,保留死代码会让新人误以为还
有第二条链路。一并删除其 demo 与配套文档。
```

```
fix(plugins/wake_word): 修复唤醒词检测器停止流程的线程竞争

sherpa-onnx 对象在停止时可能被多个线程同时访问,导致段错误。
加线程锁保护对象的读写边界。

Fixes: #142
```

```
feat(mcp): 新增天气查询 MCP 工具

实现 @mcp_tool 装饰器形式的注册示例,验证 auto-discovery 路径
对 third-party HTTP 调用的兼容性。
```

反例:

```
update                                  # type 缺失,subject 空洞
feat: 修改                              # subject 没有信息
Feat(MCP): Add weather tool.            # 大写 type,英文不统一,以句号结尾
chore: WIP                              # WIP 不允许
fix:修复了一个bug                       # 冒号后无空格,subject 空洞
```

---

## Commit 拆分

合并策略是 **rebase + fast-forward**(见下节)。这意味着 `main` 上每一个 commit 都会被 `git bisect` 单独 checkout 出来跑。

### 硬规则

- **每个 commit 必须能独立编译/运行**: lint 过、import 不报错、`python main.py --mode cli` 至少能启动。否则 bisect 会断在中间。
- **一 commit 一事**: 重构与新功能 **不混**。把一段代码挪位置 + 改逻辑要拆成两个 commit: 先纯挪动(`refactor:`),再改逻辑(`feat:` / `fix:`)。
- **不要 "保存进度" 提交**: 本地可以,push 之前用 `git rebase -i` 整理(注: `git rebase -i` 是交互式工作,本规范允许人在终端手动操作,不要在 AI 自动化里跑)。

### 软规则

- 单个 commit **改动文件 ≤ 5、涉及域 ≤ 2** 是健康值。同时改 `core/` + `plugins/` + `ui/` + `mcp/` 的 commit 几乎肯定该拆。
- 纯格式化(`style:`)单独成 commit,**绝不** 和逻辑改动混合 —— 否则 review 噪声大到失去意义。
- 大 PR 拆成"基础设施 → 接入 → 清理旧路径"三段是常见且健康的拆法。

---

## PR 流程

### 开发期

1. `git fetch origin && git checkout main && git pull --ff-only` —— 保 main 最新。
2. `git checkout -b feature/<name>` —— 拉新分支。
3. 写代码,本地按 commit 拆分原则提交。
4. 期间定期 `git fetch origin && git rebase origin/main` 跟主分支同步。**不要** 用 `git merge main` 进 feature 分支,会产生 merge commit,破坏线性。
5. push: `git push -u origin feature/<name>`(首次)或 `git push --force-with-lease`(rebase 后必要)。
   - `--force-with-lease` 比 `--force` 安全,会拒绝覆盖他人的 push。
   - 对 **共享分支** 仍然 **禁止** force push。

### 提交 PR

PR 描述至少包含三段:

```markdown
## 动机
<为什么做这件事,链接 issue / PRD / spec>

## 方案
<怎么做的,关键决策点>

## 验证
- [ ] 跑过 `./format_code.sh`
- [ ] `python main.py --mode cli` 启动成功
- [ ] <feature 特定的手动验证步骤>
```

### Review 与合并

1. Reviewer 关注 commit 拆分、commit message、是否符合 spec。
2. 作者按 review 整理 commit(`git rebase -i` 合并 fixup commit、改 message),然后 `git push --force-with-lease`。
3. CI / 本地验证全过后,**maintainer** 用:

   ```bash
   git checkout main
   git pull --ff-only
   git merge --ff-only feature/<name>
   git push origin main
   ```

   或者通过 GitHub UI 选择 **"Rebase and merge"**(产出线性历史)。**不要** 选 "Create a merge commit",**不要** 选 "Squash and merge"(后者会丢失精心拆分的 commit 历史)。

4. 合并完成后 **删除分支**:

   ```bash
   git branch -d feature/<name>
   git push origin --delete feature/<name>
   ```

### 历史 merge commit

仓库里的 `3635e94 Merge branch 'main' into feature/new_architecture` 这种 merge commit 是规范生效前的产物,不追溯。新工作必须线性。

---

## SemVer tag

### 格式

`v<MAJOR>.<MINOR>.<PATCH>`,例: `v1.2.3`、`v2.0.0-rc.1`。

### bump 规则

| 改动 | bump |
|---|---|
| 不兼容的 API / 行为变化(footer 写 `BREAKING CHANGE:`) | MAJOR |
| 新功能(`feat:` / `perf:`,用户可见) | MINOR |
| bug 修复(`fix:`,用户可见) | PATCH |
| 内部重构 / spec / docs / test / ci / build / chore | **不打 tag** |

### 操作

合并 PR 到 `main` 后,如果该 PR 含 user-visible 变更:

1. 同步更新 `pyproject.toml` 的 `version = "x.y.z"`(单独的 `chore: bump version to x.y.z` commit,或并入 PR 最后一个 commit)。
2. 打 tag:

   ```bash
   git tag -a v1.2.3 -m "v1.2.3"
   git push origin v1.2.3
   ```

3. tag 是 **annotated**(`-a`),不用 lightweight tag。

仓库 `pyproject.toml` 当前写 `1.0.0` 但 git 里没有 `v1.0.0` tag —— 首次按本规范打 tag 时同步对齐。

---

## AI 协作 trailer

AI(Claude / Codex / GitHub Copilot Chat 等)真正参与代码修改时,在 commit footer 加 `Co-Authored-By:`:

```
docs(spec): 新增 Git 工作流与提交规范

现有分支命名混用、缺少版本 tag、Conventional Commits 规则未沉
淀,把当前事实上的工作流写成 spec,后续 sub-agent 与人类贡献
者有共同基线。

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

规则:

- **格式固定**: `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`(模型名 + 邮箱占位符,GitHub 会识别为协作者)。
- **仅在 AI 真正改了代码 / 文档时加**。AI 只参与 review 讨论、不直接产出 diff 时不加。
- **trailer 是事实标记,不是免责声明**。加了 trailer 仍然由提交者对内容负全责。
- 多个协作者各占一行,trailer 块整体放在 footer 最后。

---

## 反模式

下面这些行为在新规范下 **明确禁止**:

- **直接 push 到 `main`**。所有改动经 PR + ff-merge。
- **`git push --force` 到共享分支**。个人 feature 分支可以 `--force-with-lease`,共享分支(`main`、长期 feature)不可以。
- **`git commit --no-verify` 跳过 hook**,除非用户明确要求并知道后果。
- **`git commit --amend` 已经 push 的 commit**,会让其他基于它工作的人丢东西。新建一个修复 commit。
- **空洞 commit message**: `WIP`、`update`、`fix typo`(没说哪里)、`修了下`、`Update foo.py`。
- **一个 commit 同时改 ≥ 5 文件且涉及 ≥ 2 个域**(audio + UI + mcp),几乎肯定该拆。
- **混合格式化与逻辑改动**。`style:` commit 单独走。
- **中文分支名**(见上文)。
- **`Squash and merge`** —— 会摧毁精心拆分的 commit 历史,本仓库不用。
- **`git merge main` 进 feature 分支** —— 用 `git rebase origin/main` 替代。
- **不带 trailer 的伪 AI 协作**: AI 写了大段代码却不挂 `Co-Authored-By`,违反事实标记原则。

---

## 参考

- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/zh-hans/v1.0.0/)
- [Semantic Versioning 2.0.0](https://semver.org/lang/zh-CN/)
- [GitHub Flow](https://docs.github.com/zh/get-started/quickstart/github-flow)
- 仓库内合规 commit 范例: `7360e4d`、`00cf6c3`、`ebcc85e`
- 仓库内待迁移分支: `bugfix/webrtc_apm`、`feat/定制化`、`feature/audio_select`(命名层面)
