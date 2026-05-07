# 后端开发规范

> Python 后端开发约定(单仓库、Python 3.10+,代码全部在 `src/` 下)。

---

## 技术栈

- **语言**: Python ≥ 3.10,带类型注解。
- **异步运行时**: `asyncio`(CLI/GPIO 模式)和基于 PySide6 的 `qasync`(GUI 模式),入口见 `main.py`。
- **工具链**: ruff + black + isort + flake8(配置在 `pyproject.toml` 与 `.flake8`),便捷脚本: `./format_code.sh`。
- **测试**: pytest + pytest-asyncio 已配置,目前还没有 `tests/` 目录 —— 新增任何测试前先看 `quality-guidelines.md`。
- **持久化**: 没有数据库。配置以 JSON 形式由 `ConfigManager`(`src/utils/config_manager.py`) 管理,因此本目录下没有 DB 规范。

---

## 规范索引

| 文档 | 主题 |
|---|---|
| [架构原则](./architecture-principles.md) | 分层、依赖方向、Plugin 模式、何时抽象、反过度耦合 vs 反过度解耦 |
| [目录结构](./directory-structure.md) | `src/` 各域职责、新代码落点、单例 / import 约定 |
| [Python 风格](./python-style.md) | 类型注解(现代范型 + `X \| None`)、文件头、命名、函数/方法规范、dataclass、路径 |
| [asyncio 规范](./asyncio-guidelines.md) | `TaskManager.spawn` vs `create_task`、锁、gather、跨线程桥、qasync 注意事项 |
| [PySide6 / QML](./pyside6-guidelines.md) | ViewModel + `@Property`、`Signal`/`Slot`、`EventBridge`、QML 加载、线程边界 |
| [日志规范](./logging-guidelines.md) | `from src.logging import get_logger`、日志级别、`exc_info=True` 规则、敏感信息过滤 |
| [错误处理](./error-handling.md) | 三种实际使用的 try/except 模式;不引入自定义异常类 |
| [质量规范](./quality-guidelines.md) | ruff/black/isort、async、docstring、评审清单 |
| [Git 工作流](./git-workflow.md) | 分支模型、Conventional Commits、PR / merge 流程、SemVer tag |
| [MCP 工具](./mcp-tool-pattern.md) | `@mcp_tool` 装饰器 + auto-discovery 的目录骨架 |

---

## 真理来源约定

**Spec 描述的是标准,而不是"每个文件当前的样子"。** 仓库已经积累了一些漂移 —— `# -*- coding -*-` 头、被弃用的 `asyncio.get_event_loop()`、未追踪的 `asyncio.create_task()`、ViewModel 上的 `@property` 等等。规范把这些列为禁止项,并指向同仓库内的正确锚点。

两条规则:

1. **新代码遵循 spec。** 不允许"和当前文件保持一致"作为复刻反模式的理由。
2. **接触到的代码顺手迁移。** 改到一个仍带遗留模式(编码头、`Optional[X]` 与 builtin 范型混用、未追踪任务、`get_event_loop`)的文件时,在同一次改动里清理掉。不主动批量重构未接触的文件,但接触到的清干净。

如果某个 feature task 引入了新模式(比如第一次 DB 集成、第一次自定义异常、第一次写测试),在那次任务里同时新增 spec,后续 sub-agent 才能跟上。

---

## 语言

本目录下所有 Markdown 文档均用 **中文** 书写。代码块、文件路径、标识符、ruff/black 规则名、PySide6 类名等技术性英文保持原样。Python 源码里的 docstring 与日志字符串也是 **中文**(见 `logging-guidelines.md`)。
