# 解耦 CLI 与 GUI 依赖

## Goal

让用户跑 CLI / GPIO 模式时不需要安装 PySide6 / qasync 这套 GUI 依赖(200+MB),恢复 `src/ui/__init__.py` 注释里宣称的"按需导入,避免跨模式依赖问题"承诺。顺手把开发工具(pyinstaller / ruff / pytest)从顶层 deps 拆出,统一到 dev group。

## 背景与根因

### 用户反馈
> "启动 cli 还提示安装 gui 的依赖"

### 实测启动链路(grep 验证)
- `main.py` CLI 模式分支**不 import** qasync/PySide6(GUI 分支才触)
- `src/plugins/ui.py.setup()` 按 mode 延迟 import,**正确**
- `src/ui/cli/__init__.py` → `CLIActivation` + `CLIViewManager`,transitive 全干净
- `src/ui/gpio/__init__.py` 同理
- `src/ui/__init__.py` 注释明确说"不在顶层导入具体模块,避免跨模式依赖问题"

### 根因 1: pyproject.toml 把 `PySide6`/`qasync` 列顶层必装
```toml
"PySide6>=6.6.0",       # GUI,应进 [gui] extra
"qasync>=0.27.1",       # GUI,应进 [gui] extra
```
`pip install` / `uv sync` 强装 PySide6 wheel(100-300MB) —— 这就是用户感受到的"装 CLI 要 GUI 依赖"。

### 根因 2: 开发工具与运行依赖未分层
顶层 `[project] dependencies` 含:
```toml
"pyinstaller>=6.0.0",   # 打包工具,运行不需
"ruff>=0.4.0",          # 开发 lint,运行不需
"pytest>=8.0.0",        # 测试,运行不需
"pytest-asyncio>=0.23.0",
```
**同时** `[dependency-groups] dev` 也声明了一模一样的四项 —— 顶层让 dev group 形同虚设。

### 架构隐患(本任务不修,记录)
`src/ui/shared/models/` 与 `src/ui/shared/bridge/` 全部 `import PySide6`,目录名是 "shared" 但内容是 GUI 专用。当前因 `__init__.py` 不链式 import 而侥幸不出问题,但命名误导。**留给独立任务做架构调整**。

## Decision (ADR-lite)

**Context**: pyproject.toml 把 GUI 依赖与开发工具都列顶层必装,违反"按需安装"和"运行 vs 开发分层"。
**Decision**: 采用方案 B —— PySide6/qasync 进 `[project.optional-dependencies].gui`;pyinstaller/ruff/pytest 从顶层移除,只保留在 `[dependency-groups] dev`。`src/ui/shared/` 架构调整不在本任务。
**Consequences**:
- 新用户跑 CLI / GPIO 模式不再被强装 PySide6
- 开发者用 `uv sync` 默认装 dev group 行为不变
- 已装 PySide6 的旧用户无回归
- README 安装命令需要更新(GUI 模式额外步骤)

## Requirements

1. **`pyproject.toml` 改动**
   - 顶层 `[project] dependencies` **移除**: `PySide6`、`qasync`、`pyinstaller`、`ruff`、`pytest`、`pytest-asyncio`
   - `[project.optional-dependencies]` **新增**: `gui = ["PySide6>=6.6.0", "qasync>=0.27.1"]`
   - 注释更新: 标注"GUI 模式额外依赖,使用 `uv sync --extra gui` 或 `pip install '.[gui]'`"
   - `[dependency-groups] dev` 现状保留(已含 pyinstaller/ruff/pytest)
   - `sherpa-onnx-core` / `sherpa-onnx` 保留顶层(wake_word 必需)
   - 注: `[tool.black]`、`[tool.isort]` 等仍引用旧工具配置,**不动**(向后兼容)

2. **`main.py` GUI 入口友好提示**
   - 当前 `main.py` 已有 `try: import qasync; except ImportError as e: logger.error(f"GUI模式需要 qasync 和 PySide6 库: {e}"); sys.exit(1)` —— 升级为更清晰的中文提示,告诉用户具体的安装命令:
     ```
     GUI 模式需要 PySide6 + qasync。请安装 GUI 依赖:
       uv sync --extra gui          # 推荐
       pip install '.[gui]'         # 标准 pip
     若使用 CLI 或 GPIO 模式,请运行: python main.py --mode cli
     ```

3. **README 更新(README.md + README.en.md)**
   - 在"安装"段落区分基础安装 vs GUI 模式
   - 给出三个示例命令: 基础(只 CLI/GPIO)、GUI、完整开发

4. **新增一条 spec 防回归**
   - `.trellis/spec/backend/architecture-principles.md` 加一段"前端依赖隔离": GUI 专属代码 / 依赖不能进顶层 deps;非 `src/ui/gui/` 不允许 `import PySide6`
   - 或新建 `.trellis/spec/backend/dependency-management.md` 专门讲依赖分层(顶层 / extras / dev group 各自的边界)。看结构合适程度再定。

## Acceptance Criteria

- [ ] `cat pyproject.toml` 显示 `[project] dependencies` 不再含 PySide6/qasync/pyinstaller/ruff/pytest/pytest-asyncio
- [ ] `[project.optional-dependencies]` 新增 `gui` extra
- [ ] 在干净虚拟环境跑 `uv sync`(不带 --extra gui)→ 不安装 PySide6
- [ ] 该环境跑 `python main.py --mode cli` 启动成功(到达"启动 ServiceContainer"阶段)
- [ ] 该环境跑 `python main.py --mode gui` 给出**清晰中文错误**(含 `uv sync --extra gui` 命令),`exit 1`
- [ ] 跑 `uv sync --extra gui` 后,`python main.py --mode gui` 启动成功(macOS 实测)
- [ ] README.md 与 README.en.md 安装段更新
- [ ] spec 加防回归条目
- [ ] commit 走新规范: `chore(deps): 拆分 GUI 与开发依赖,默认安装不装 PySide6`

## Definition of Done

- `uv lock` 通过,生成的 lockfile 改动符合预期(deps 数量减少)
- `uv sync` 在干净环境跑通(不指定 extra 时不出 PySide6)
- 用本任务自己定义的 spec 评审清单跑过
- commit 按 git-workflow.md 规范

## Out of Scope

- 把 `src/ui/shared/models/` 与 `src/ui/shared/bridge/` 搬到 `src/ui/gui/` 下(架构调整,独立任务)
- 重构 `settings_model.py`(916 行 + threading 设备探测,本身有问题但与本任务无关)
- 把 `[tool.black]`、`[tool.isort]` 等遗留配置块清理(向后兼容,留给后续)
- CI/CD 上的 matrix 测试(确保 CLI 在没装 GUI 时跑通) —— 写下记录但不在本 PR 做

## Technical Notes

### pyproject.toml 改动详细

**移除(顶层 `[project] dependencies`)**:
```toml
"PySide6>=6.6.0",
"qasync>=0.27.1",
"pyinstaller>=6.0.0",
"ruff>=0.4.0",
"pytest>=8.0.0",
"pytest-asyncio>=0.23.0",
```

**新增(`[project.optional-dependencies]`)**:
```toml
gui = [
    "PySide6>=6.6.0",
    "qasync>=0.27.1",
]
```

**保留不动**:
- `sherpa-onnx-core` / `sherpa-onnx`(wake_word 运行依赖)
- 各平台 sys_platform 限定 deps(macos/windows/linux extras 维持现状)
- `[dependency-groups] dev`(已含 pyinstaller/ruff/pytest 四项,无需新加)

### main.py 改动详细

当前 `main.py:165-168`:
```python
try:
    import qasync
    from PySide6.QtWidgets import QApplication
except ImportError as e:
    logger.error(f"GUI模式需要 qasync 和 PySide6 库: {e}")
    sys.exit(1)
```

改为:
```python
try:
    import qasync
    from PySide6.QtWidgets import QApplication
except ImportError as e:
    logger.error(
        "GUI 模式需要 PySide6 + qasync,但未安装。请运行:\n"
        "  uv sync --extra gui          # 推荐 (uv 用户)\n"
        "  pip install '.[gui]'         # pip 用户\n"
        f"或改用 CLI/GPIO 模式: python main.py --mode cli  (原始错误: {e})"
    )
    sys.exit(1)
```

### README 改动建议

```markdown
## 安装

### 基础安装(CLI / GPIO 模式)
```bash
uv sync
python main.py --mode cli
```

### GUI 模式
```bash
uv sync --extra gui
python main.py --mode gui
```

### 完整开发环境
```bash
uv sync --extra gui --group dev
```
```

### 防回归 spec 草稿(放 architecture-principles.md 末尾)

```markdown
## 前端依赖隔离

`pyproject.toml` 顶层 `[project] dependencies` 只列 **运行任意一个 mode 都需要** 的依赖。GUI / 平台特定 / 开发工具走 extras 或 dev group:

| 类型 | 位置 | 例 |
|---|---|---|
| 全模式运行依赖 | `[project] dependencies` | aiohttp, sherpa-onnx, opuslib |
| GUI 模式 | `[project.optional-dependencies] gui` | PySide6, qasync |
| 平台限定 | sys_platform 标注 | pyobjc, pycaw, gpiozero |
| 开发工具 | `[dependency-groups] dev` | pyinstaller, ruff, pytest |

**禁止**: 顶层 deps 出现 GUI 专属库或开发工具。任何接触 `pyproject.toml` 的 PR 评审必须确认。
```

## Implementation Plan

单 PR 完成(改动小):

1. 改 `pyproject.toml`(deps 重组)
2. 改 `main.py`(GUI 入口提示)
3. 改 `README.md` + `README.en.md`(安装段)
4. 改 `.trellis/spec/backend/architecture-principles.md`(防回归条目)
5. `uv lock` 重生 lockfile(若 uv.lock 在仓库)
6. 验证: 干净 venv `uv sync` → 跑 `--mode cli`;`uv sync --extra gui` → 跑 `--mode gui`
7. 单个 commit: `chore(deps): 拆分 GUI 与开发依赖,默认安装不装 PySide6`

风险评估: 低。pyproject 改动是 metadata,不影响代码;main.py 仅改错误信息;README/spec 是文档。已装 PySide6 的旧用户无影响(extra 是扩展,不是替换)。
