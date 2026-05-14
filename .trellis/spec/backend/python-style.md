# Python 风格

> Python ≥ 3.10。`pyproject.toml` 里 `target-version = "py310"`。代码库里已经在向新语法收敛的地方,新代码也走新语法;别复刻遗留写法。

本规范是 **标准**,而不是"现状描述"。下面列出的反模式都在仓库里有对应位置,在你接触到那些文件时一并修干净。

---

## 类型注解 —— 用现代写法

Python ≥ 3.9 起 builtin 范型 (`list[X]`、`dict[K, V]`) 可用,≥ 3.10 起 `X | Y` 联合类型可用。仓库里较新的代码 (`src/core/event_bus.py`、`src/core/task_manager.py`、`src/plugins/manager.py`、`src/plugins/base.py`) 已经在用。

| 用 | 别用 |
|---|---|
| `list[str]` | `List[str]` |
| `dict[str, Any]` | `Dict[str, Any]` |
| `tuple[int, str]` | `Tuple[int, str]` |
| `set[asyncio.Task]` | `Set[asyncio.Task]` |
| `str \| None` | `Optional[str]`(仅遗留代码继续用) |
| `int \| str` | `Union[int, str]` |

仍然从 `typing` 导入的两类例外:

- `typing.Any` —— "任意类型"。**注意 lowercase `any` 是内置函数,绝不能出现在类型注解里**。已知 bug: `src/ui/shared/bridge/event_bridge.py:46` 写成 `list[tuple[str, any]]`,下次接触此文件时改成 `list[tuple[str, Any]]`。
- `typing.Callable`、`typing.Awaitable`、`typing.TYPE_CHECKING`、`typing.Protocol` —— 没有 builtin 替代,继续 `from typing import ...`。

`Optional[X]` 在已经统一使用它的旧文件里可以保留,但 **不要在同一个文件里混用** `Optional[X]` 和 `X | None`。要么整文件迁,要么和文件保持一致。

### `from __future__ import annotations`

仓库里目前没有任何文件使用。**别引入** —— 项目用字符串前向引用(`"Plugin"`)和 `TYPE_CHECKING` 块来解决循环,见 `src/plugins/base.py`、`src/plugins/manager.py`。

---

## 文件头

每个 Python 模块以模块 docstring(中文)开头。**不要** 写编码声明,**不要** 写 shebang(库模块),**不要** 写 license header。

```python
"""任务管理器.

统一管理异步任务的创建、追踪和清理。
"""

import asyncio
...
```

### 禁止的头部行

- `# -*- coding: utf-8 -*-` —— Python 3 源码默认 UTF-8。仓库里 `src/ui/shared/`、`src/ui/cli/`、`src/ui/gui/activation.py` 还有大量遗留,接触即删。
- `#!/usr/bin/env python3` —— 只允许出现在真正的脚本入口,不允许出现在库模块。
- license header —— 本项目不用。别加。

---

## 导入

isort (`profile=black`,`known_first_party=["src"]`) 会强制以下顺序:

```python
# 1. 标准库
import asyncio
from pathlib import Path
from typing import Any, Optional

# 2. 第三方
from PySide6.QtCore import QObject, Signal

# 3. 项目内 (src.*)
from src.core.event_bus import EventBus
from src.logging import get_logger

# 4. 同包相对
from .base import Plugin
```

- 跨包一律用 `from src.*` 绝对路径。
- 相对 import (`.base`、`..foo`) 只在同一个包内的兄弟模块间用,见 `src/plugins/manager.py`。
- 函数内的延迟 import 仅用于:(a) 打破循环依赖、(b) 可选/重型依赖(PySide6、qasync、sherpa-onnx)。例如 `main.py` 延迟 import `ServiceContainer`、`ConfigManager`、UI 模块。

---

## 命名

### 大写小写

- 模块/包: `snake_case`(`event_bus.py`、`mcp_tool_pattern.md` 这类下划线分词)。
- 类: `PascalCase`(`EventBus`、`PluginManager`)。
- 函数 / 方法 / 变量: `snake_case`。私有以 `_` 开头(`_handlers`、`_loop`)。
- 常量 / 枚举值: `UPPER_SNAKE`(`Events.DEVICE_STATE_CHANGED`、`SystemConstants.APP_DISPLAY_NAME`)。
- 异步函数: 仍然 `snake_case`,**不要** 加 `async_` / `_async` 后缀。`async def` 已经说明了。
- PySide6 信号: **camelCase**(`statusChanged`、`showSettingsWindow`)—— QML 当 JavaScript 标识符读,只能这样。这是项目里唯一允许 camelCase 的地方,详见 `pyside6-guidelines.md`。

### 语义

- 用 **行为** 命名方法,不用类型: `start_listening()`、`emit(event)`,而不是 `do_listening()`、`process(event)`。
- 用 **意图** 命名变量,不用值: `idle_timeout`、`shutdown_event`,而不是 `t`、`e`。
- bool 变量/方法以 `is_` / `has_` / `should_` / `can_` 开头: `is_running`、`has_handlers`、`should_capture_audio`。
- 私有助手以 `_` 开头,纯内部不暴露的以 `__` 双下划线(罕见,会触发 Python 名字 mangling)。

### 缩写

避免缩写,除非该缩写在仓库里 **已经一致**(`ctx`、`cmd`、`cfg`、`mgr` 是已有约定;不要新造)。

---

## 内置名遮蔽

类型注解和 `ruff/B` (`flake8-bugbear`) 都会因为遮蔽内置名而出问题:

- 不要把 `any`、`all`、`id`、`type`、`list`、`dict`、`set`、`tuple`、`str`、`int`、`bytes`、`input`、`format` 当作变量名 / 参数名 / 属性名。

确实需要这个语义时加后缀: `tool_type`、`event_type`、`node_id`。

---

## 函数 / 方法规范

### 长度

经验值: **超过一屏(≈ 60 行)就考虑拆**。拆分的边界看意图,而不是行数 —— 可以拆出"输入校验 / 主流程 / 善后清理"三段时是好时机。

`src/ui/shared/models/settings_model.py` 已经超过 800 行了,这是技术债务,不是参照对象。新写代码别让它继续膨胀。

### 单一职责

一个方法做一件事。"做一件事"的判断: 给方法写 docstring 时,如果非要写"先...然后...再..."就该拆。

### 公开 vs 私有

- 公开方法在 `__init__.py` 里 `__all__` 显式声明的才算公开。
- 类的公开方法(无 `_` 前缀)就是它的契约,改签名要看所有调用方。
- `_` 前缀方法是内部细节,可以随意改。同类的子类不要 override `_` 方法 —— 那等于把内部细节升级成契约。
- `__` 双下划线极少用。除非真要 Python 名字 mangling(基本不需要)。

### 默认参数

- 不要用可变对象做默认值: `def f(items: list[str] = []):` 错。统一改成 `= None`,函数内部判空赋值。
- 默认参数表达调用方 90% 的常见用法。如果 80% 的调用都要覆盖默认值,默认值就是错的。

### 关键字参数

- 公开 API 超过 2 个参数时,后续参数用 `*` 强制 keyword-only:

  ```python
  def spawn(self, coro: Awaitable[Any], *, name: str) -> Optional[asyncio.Task]: ...
  ```

  调用方写 `spawn(coro, name="task")` 比 `spawn(coro, "task")` 显然。

  注: `TaskManager.spawn` 现在还是位置参数,可以维持现状,但新增公开 API 走 keyword-only。

### `staticmethod` / `classmethod`

- `@classmethod` —— 单例 `get_instance()` 这类替代构造器,以及"操作类本身"的工厂。
- `@staticmethod` —— 极少用。如果方法和实例无关、和类也无关,直接做模块函数。
- 不要为了"挂在类下面看起来归属感强"而强行 `@staticmethod`。

### 类型注解的完整性

公开方法的所有参数 + 返回值都要有注解。私有助手可以省略返回值注解,但参数注解仍然要有。

`async def` 的返回值是 **被 await 后的值**,不是 `Awaitable[X]`:

```python
async def emit(self, event: str, data: Any = None) -> None: ...
# 调用方:  await bus.emit("x")  # → None,不是 Awaitable[None]
```

`Awaitable[X]` 只用在 **参数 / 字段** 上,见 `TaskManager.spawn(coro: Awaitable[Any], ...)`。

---

## Dataclass

适用场景: 跨模块传递 + 字段稳定 + 字段数 ≥ 3 的 **纯数据载体**。

```python
from dataclasses import dataclass, field

@dataclass
class LoggingConfig:
    level: str = "INFO"
    format_type: str = "colored"
    third_party_levels: dict[str, str] = field(default_factory=lambda: {...})
```

规则:

- 可变默认值 **必须** 用 `field(default_factory=...)`。绝不允许 `[]`/`{}` 直接做默认值。
- 不可变实例加 `frozen=True`。
- **不要** 引入 Pydantic。项目不用 Pydantic,JSON 配置校验在 `ConfigManager` 里手写。

不要为只有 1-2 个字段、调用点 ≤ 2 个的临时数据上 dataclass —— 直接用 tuple/dict 更轻。

---

## 路径

用 `pathlib.Path`,**不要用** `os.path` 字符串拼接。仓库里基本统一(`Path(__file__).parent / "qml"`、`Path.cwd() / "logs"`)。

用户/缓存/配置/日志目录走 `src/utils/resource_finder.py`(`get_log_dir`、`get_user_data_dir`、`get_user_cache_dir`、`get_config_dir`)。它处理过 PyInstaller 打包后的可写路径,`Path.cwd()` 不行。

---

## 字符串与引号

- 双引号 —— ruff format 强制(`quote-style = "double"`)。
- 字符串拼接用 f-string: `f"已加载 QML: {main_qml}"`。
- **新代码不用** `%` 格式化或 `str.format(...)`。
- 唯一允许的例外: `logger.warning("Tool %s already registered, overriding.", name)` 这类 logging 模块的 lazy 格式化(见 `src/mcp/decorators.py:88`)—— 延迟到 handler 才格式化,可以接受。

---

## 比较与真值

- 与 `None` 比较用 `is` / `is not`,**不允许** `== None`。
- 与 bool 比较用隐式真值: `if connected:`、`if not running:`,**不允许** `== True`。
- 容器空判断用真值: `if not handlers: return`。

---

## 异常

详见 `error-handling.md`。摘要:

- `except Exception:` —— 永远不允许裸 `except:`。
- `logger.error(f"...: {e}", exc_info=True)` —— 永远不用 `logger.exception(...)`。
- 项目层不定义自定义异常体系。

---

## Docstring

中文,三引号,首行一句话总结,空行后写参数 / 返回 / 备注。`docformatter` 强制 88 列换行。

```python
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取配置好的日志记录器.

    Args:
        name: 日志记录器名称。如果不传,自动使用调用者的模块名。

    Returns:
        配置好的日志记录器
    """
```

- 公开函数/类必须有 docstring。私有助手可省略,但语义不显然时仍建议写一行。
- **别写"做了什么"** —— 命名已经告诉读者了。docstring 写"为什么 / 注意什么 / 不变量"。
- `Args:` / `Returns:` / `Raises:` 用 Google 风格(项目已统一)。

---

## 注释

默认 **不写** 注释。命名表达不出来的隐藏约束才写。

不允许的注释类型:

- 复述代码: `# 创建实例` `obj = X()` —— 删。
- "用于 X 流程" / "为了修 #123" —— 写在 PR 描述,不写在代码。
- "TODO 以后改" 没有 issue 号或日期 —— 删。

允许的注释:

- 隐藏约束: `# pynput 在 macOS 必须在主线程注册`。
- 与直觉相反的特例: `# 这里要 await,否则 qasync 会丢失 cancel`。
- 模块/段落分隔的视觉标题 —— 仓库里用 `# ========== xxx ==========`,可以保留但别滥用。

---

## 禁止

- `# -*- coding: utf-8 -*-` 头。
- 类型注解里小写 `any`(用 `typing.Any`)。
- 自行加 `from __future__ import annotations`(项目不用)。
- `src/` 里的 `print(...)`(用 logger)。
- `os.path.join`(用 `Path / "x"`)。
- `eval`、`exec`、`__import__` 做动态加载(用 `importlib.import_module(...)`,见 `src/mcp/decorators.py`)。
- 可变默认参数。
- 同文件里混用 `Optional[X]` 和 `X | None`。
- 内置名作为参数/属性名(`any`、`id`、`type`...)。

---

## 现代风格的参照文件

- `src/core/event_bus.py` —— 现代范型、双引号、f-string。
- `src/core/task_manager.py` —— 现代范型 + 必要时保留 `Optional[asyncio.AbstractEventLoop]`。
- `src/plugins/manager.py` —— 小型管理类的注解。
- `src/logging/__init__.py` —— 公开 API 的类型注解。
