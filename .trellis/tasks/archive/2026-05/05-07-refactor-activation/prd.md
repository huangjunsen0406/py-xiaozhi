# 简化激活流程，提取核心逻辑复用

## Goal

消除 GUI/CLI/GPIO 三种激活模式中的重复代码，将激活核心逻辑提取为共享层，各模式仅负责差异化的 UI 展示。

## Decision (ADR-lite)

**Context**：CLIActivation、GUIActivation、GPIOActivation 核心流程完全一致（获取数据 → 展示 → 调用 activate → 展示结果），仅 UI 层不同。CLI 路径存在 `initialize()` 重复调用 bug。

**Decision**：方案 B — 提取 `BaseActivation` 抽象基类，子类覆盖纯展示方法。删除 GPIOActivation，GPIO 模式直接复用 CLIActivation。

**Consequences**：核心逻辑一处维护；加新模式只需实现 3 个展示方法；消除 `initialize()` 重复调用。GUI 的 QFuture 桥接保留在子类中（Qt 事件循环耦合无法消除）。

## Requirements

* 新建 `BaseActivation` 抽象基类，定义模板方法 `run()`
* CLI/GUI 子类仅覆盖 `show_code`、`show_result`、`show_error` 三个展示方法
* `handle_activation()` 的 `init_result` 直接传递给激活类，不再重复 `initialize()`
* GPIO 模式直接复用 CLIActivation（删除 GPIOActivation 文件）
* main.py 三个 `_run_*_activation()` 函数合并为一个工厂函数
* 修复死代码：`cancelActivation` 双重 `_complete(False)`、`_do_activate` 死 return
* 删除 `CLIActivation.get_activation_result()` 未被调用的方法

## Acceptance Criteria

* [ ] CLI 模式激活正常（`python main.py --mode cli --skip-activation` 跳过，或真实激活流）
* [ ] GUI 模式激活正常（窗口弹出、激活码显示、激活流程可用）
* [ ] GPIO 模式激活正常（委托 CLI 不变）
* [x] `initialize()` 每种模式只调用一次
* [ ] `uv run python main.py --mode cli` 启动正常
* [ ] `uv run python main.py --mode gui` 启动正常
* [x] 激活相关代码行数减少 30%+
* [x] 通过 `ast.parse` 语法检查

## Definition of Done

* lint / typecheck 绿色
* CLI + GUI 模式手工启动验证通过
* 激活路径无 regression

## Technical Approach

### 文件变更清单

| 文件 | 操作 |
|------|------|
| `src/ui/shared/activation.py` | **新建** — `BaseActivation` 抽象基类 |
| `src/ui/__init__.py` | 修改 — 导出 BaseActivation |
| `src/ui/cli/activation.py` | 修改 — 继承 BaseActivation，仅保留展示方法 |
| `src/ui/gui/activation.py` | 修改 — 继承 BaseActivation，仅保留 QML/展示方法 |
| `src/ui/gpio/activation.py` | **删除** — GPIO 直接用 CLIActivation |
| `main.py` | 修改 — 合并三个 `_run_*_activation()` 为一个，传递 `init_result` |
| `src/activation/service.py` | 修改 — 删除死代码 (line 831-832) |

### BaseActivation 设计

```python
class BaseActivation(ABC):
    def __init__(self, activation_service, init_result):
        self._service = activation_service
        self._init_result = init_result  # 由 main.py 传入，不再自己调 initialize()

    async def run(self) -> bool:
        # 模板方法：核心流程
        if not self._init_result.get("need_activation_ui", False):
            return True  # 无需激活

        self._show_device_info()

        data = self._service.get_activation_data()
        if not data:
            self._show_error("未获取到激活数据")
            return False

        self._show_code(data)

        success = await self._service.activate(data)
        self._show_result(success)
        return success

    # ---- 子类覆盖 ----
    @abstractmethod
    def _show_device_info(self): ...
    @abstractmethod
    def _show_code(self, data): ...
    @abstractmethod
    def _show_result(self, success): ...
    def _show_error(self, msg): ...
```

### main.py 简化

```python
# 之前：3 个函数 + if/elif 分支
async def handle_activation(mode, service):
    init_result = await service.initialize()  # 只调一次
    if not init_result["need_activation_ui"]:
        return True
    return await _create_activation(mode, service, init_result).run()

def _create_activation(mode, service, init_result):
    if mode == "gui":
        return GUIActivation(service, init_result)
    else:  # cli / gpio 同走 CLI
        return CLIActivation(service, init_result)
```

## Out of Scope (explicit)

* 不修改 ActivationService 内部逻辑（仅删除 dead return）
* 不修改激活 UI/QML 界面
* 不改动 `ActivationService._show_activation_info()` 的 stdout 输出（虽然 GUI 模式下多余，但属 service 层行为，不在本次范围）

## Technical Notes

* 分析记录见 [`research/activation-analysis.md`](research/activation-analysis.md)
* 关键文件：`main.py`、`src/ui/cli/activation.py`、`src/ui/gui/activation.py`、`src/ui/gpio/activation.py`、`src/activation/service.py`
