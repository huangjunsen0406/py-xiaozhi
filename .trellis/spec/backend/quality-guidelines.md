# 质量规范

> Python 3.10+。工具链与必须模式锚定在 `pyproject.toml` 与 `format_code.sh`。

---

## 工具链

| 工具 | 真相来源 | 覆盖范围 |
|---|---|---|
| Ruff | `pyproject.toml` → `[tool.ruff]`、`[tool.ruff.lint]`、`[tool.ruff.format]` | Lint(`E`、`W`、`F`、`I`、`B`、`C4`、`UP`)和格式化。行宽 **88**,target **py310**,双引号。 |
| Black | `pyproject.toml` → `[tool.black]` | 兼容性保留(行宽 88、py310)。 |
| isort | `pyproject.toml` → `[tool.isort]` | profile `black`,`known_first_party = ["src"]`。 |
| flake8 | `.flake8` | 静态检查,忽略 Black 兼容的 E203 / W503 / E501。 |
| autoflake / docformatter | `format_code.sh` 里调用 | 清理未使用 import,规范化 docstring。 |
| pytest / pytest-asyncio | `pyproject.toml` → `[tool.pytest.ini_options]` | `asyncio_mode = "auto"`、`testpaths = ["tests"]`。仓库目前无 `tests/` 目录。 |

提交前跑:

```bash
./format_code.sh        # autoflake → docformatter → isort → black → flake8
```

或纯 ruff 路径:

```bash
ruff check --fix src/ scripts/ main.py
ruff format src/ scripts/ main.py
```

---

## 必须遵守的模式

详细规则在专项 spec 里,本节只做索引:

- **Python 语法 / 类型 / 命名 / 路径 / 函数与方法** → [`python-style.md`](./python-style.md)。现代范型(`list[X]`、`dict[K, V]`、`X | None`)、无 `# -*- coding -*-` 头、`Path` 替代 `os.path`、内置名不许遮蔽(`any`、`id`、`type`...)、函数与方法长度 / 关键字参数等。
- **架构思路** → [`architecture-principles.md`](./architecture-principles.md)。分层、Plugin 模式、Protocol 接口隔离、何时抽象、反过度耦合 vs 反过度解耦。
- **asyncio** → [`asyncio-guidelines.md`](./asyncio-guidelines.md)。`TaskManager.spawn(coro, name)` 创建追踪任务、`__init__` 里抓 `asyncio.get_running_loop()`、禁止 `asyncio.get_event_loop()` / `ensure_future`、锁 / 队列 / 事件的选型。
- **PySide6 / QML** → [`pyside6-guidelines.md`](./pyside6-guidelines.md)。ViewModel 用 `@Property(type, notify=signal)`(不用 `@property`)、`EventBridge` 是 Qt↔EventBus 唯一通道、构造时抓 loop。
- **日志** → [`logging-guidelines.md`](./logging-guidelines.md)。`from src.logging import get_logger; logger = get_logger()`、异常用 `logger.error(..., exc_info=True)`。
- **错误处理** → [`error-handling.md`](./error-handling.md)。三种实际模式;不引入自定义异常类。
- **MCP 工具** → [`mcp-tool-pattern.md`](./mcp-tool-pattern.md)。

### 导入(项目通用)

```python
from src.logging import get_logger
from src.utils.config_manager import ConfigManager
from src.constants.constants import DeviceState, ListeningMode
```

isort `profile=black`、`known_first_party=["src"]` 强制顺序: 标准库 → 第三方 → `src.*` → 同包相对。同包兄弟用 `.base` 这种相对路径(见 `src/plugins/manager.py`)是允许的。

### Async(摘要)

新写 I/O / 生命周期代码用 `async def`。`pytest-asyncio` 配置了 `asyncio_mode = "auto"`,测试协程不需要装饰器。**不要** 把阻塞 I/O 混进事件循环。详见 [`asyncio-guidelines.md`](./asyncio-guidelines.md)。

---

## 跨规范的禁止项

各专项 spec 里都有自己的禁止清单,以下是 **每个 PR 评审都要看** 的核心条目:

- `src/` 下 `print(...)` —— 用 `logger.*`。CLI 模式给最终用户的输出走 `CLIDisplay`,不是裸 print。
- 裸 `except:` —— 至少 `except Exception:`,让 `KeyboardInterrupt` / `SystemExit` 正常传播。
- `logger.exception(...)` —— 仓库不用。统一 `logger.error(f"...: {e}", exc_info=True)`。
- 自定义异常类用于通用控制流。
- 硬编码路径。统一走 `src/utils/resource_finder.py`(`get_log_dir`、`get_user_data_dir`、`get_user_cache_dir`、`get_config_dir`)。
- 在 `src/` 下新建顶层包而没有清晰的域。能扩展现有包就别新建。
- 直接 `logging.getLogger(...)`。永远经 `from src.logging import get_logger`。
- `# -*- coding: utf-8 -*-` 头(见 [`python-style.md`](./python-style.md))。
- `asyncio.get_event_loop()` / `asyncio.ensure_future()` / 未追踪的 `asyncio.create_task()`(见 [`asyncio-guidelines.md`](./asyncio-guidelines.md))。
- 暴露给 QML 的类用 `@property`(见 [`pyside6-guidelines.md`](./pyside6-guidelines.md))。
- 直接 push 到 `main`、`git push --force` 到共享分支、`git commit --no-verify` 跳过 hook(见 [`git-workflow.md`](./git-workflow.md))。
- 空洞 commit message(`WIP` / `update` / `修了下` / `Update foo.py`)或非 Conventional Commits 格式。
- 中文分支名 / `bugfix/` 前缀(应为 `fix/`)/ 无前缀的个人命名空间分支。

---

## 测试

仓库目前没有 `tests/` 目录,pytest 已配置但未投入使用。**不要** 声明测试覆盖率而实际没写。如果功能任务确实需要测试,放在 `tests/<package>/test_<thing>.py`,`asyncio_mode = "auto"` 已生效(无需 `@pytest.mark.asyncio`)。

在第一个测试模式建立之前,主要验收方式仍是 **手动跑各 `--mode`**(`gui`、`cli`、`gpio` 适用时)。

---

## 评审清单(最低)

通用:

- [ ] `ruff check src/ scripts/ main.py` 干净(或 `format_code.sh` 通过)。
- [ ] `src/` 下没有新增 `print(...)`;日志遵循 [`logging-guidelines.md`](./logging-guidelines.md)。
- [ ] 异常在边界处带 `exc_info=True` 记录;可恢复路径用 `warning`;**绝不** 裸 `except:`。
- [ ] 新常量在 `src/constants/`,不是行内字面量。
- [ ] 新单例走 `ClassName.get_instance()`。
- [ ] import 按 isort/black 分组,跨包用绝对 `from src.*`。
- [ ] 公开 API 都有类型注解;docstring 中文,首行一句话。

Python 风格(见 [`python-style.md`](./python-style.md)):

- [ ] 接触到的文件没有 `# -*- coding: utf-8 -*-` 头;有就删。
- [ ] 类型注解用 `list[X]`、`dict[K, V]`、`X | None`(或文件本身就是遗留风格,保持 `Optional[X]` 一致即可)。
- [ ] 注解里没出现小写 `any`,统一 `typing.Any`。
- [ ] 没有可变默认参数;没遮蔽内置名。
- [ ] 函数 / 方法单一职责,超过一屏(≈ 60 行)考虑拆。
- [ ] 公开 API 参数 ≥ 3 个时用 keyword-only(`*` 隔)。

asyncio(见 [`asyncio-guidelines.md`](./asyncio-guidelines.md)):

- [ ] 长生命周期 / 顺手丢的任务走 `TaskManager.spawn(coro, name)`;裸 `asyncio.create_task` 仅在调用方持 `self._xxx_task` 时允许。
- [ ] 构造时抓 loop(`self._loop = asyncio.get_running_loop()`)。无 `asyncio.get_event_loop()` / `asyncio.ensure_future(...)`。
- [ ] 失败需要隔离时 `gather(*tasks, return_exceptions=True)`。
- [ ] `CancelledError` re-raise,**绝不** 静默吞。

PySide6 / QML(见 [`pyside6-guidelines.md`](./pyside6-guidelines.md)):

- [ ] ViewModel 暴露给 QML 的属性用 `@Property(type, notify=signal)`,不是 `@property`。
- [ ] Setter "先比较再 emit"(`if self._x != value: self._x = value; self.xChanged.emit()`)。
- [ ] `src/core`、`src/plugins`、`src/protocols`、`src/audio_*`、`src/mcp` 下不出现 `PySide6.*` import。
- [ ] Qt slot 同步,跨 loop 工作走 `EventBridge` / `loop.call_soon_threadsafe` / `run_coroutine_threadsafe`。

接触 MCP 工具时(见 [`mcp-tool-pattern.md`](./mcp-tool-pattern.md)):

- [ ] 工具用 `@mcp_tool` 注册,放在 `src/mcp/tools/<name>/`,`__init__.py` 中 import 工具模块。

架构(见 [`architecture-principles.md`](./architecture-principles.md)):

- [ ] 依赖方向遵循 bootstrap → core / plugins / protocols / ui;无 core import plugins、UI import protocols 等反向。
- [ ] 是否新增了仅有 1 个调用点的间接层 / Protocol / 单例?能否删掉。
- [ ] 是否给同模块内的方法之间用 EventBus 通信?直接调函数。

Git / Commit(见 [`git-workflow.md`](./git-workflow.md)):

- [ ] 分支名英文 kebab-case,前缀正确(`feature/` / `fix/` / `hotfix/` / `chore/` / `docs/` / `refactor/`),无中文。
- [ ] commit message 走 Conventional Commits: `<type>(<scope>)?: <subject>`,type 在限定列表内,subject 中文 ≤ 25 字、不以句号结尾。
- [ ] 每个 commit 自身可独立编译/运行(rebase + ff 要求);重构与功能改动不混。
- [ ] PR 描述含 **动机 / 方案 / 验证步骤** 三段;feature 分支基于最新 `main` rebase,无 merge commit。
- [ ] AI 实质参与代码改动时,footer 含 `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`;user-visible 改动同步打 SemVer tag 并对齐 `pyproject.toml` 的 `version`。
