# 架构原则

> 这份文档说明 py-xiaozhi 实际采用的架构思路、对应的取舍,以及哪些"好习惯"在本项目里反而是过度设计。先有原则,再看下面的具体子规范。

---

## 总体分层

整个应用是 **容器装服务、服务装插件** 的三层结构,依赖方向严格自上而下:

```
main.py
  └── ServiceContainer            (src/bootstrap/container.py)        — 应用入口、生命周期所有者
        ├── core 服务              (src/core/*)                        — 跨域基础设施
        │   ├── EventBus           (事件总线)
        │   ├── StateManager       (设备状态)
        │   ├── TaskManager        (异步任务追踪)
        │   └── ProtocolManager    (传输层)
        ├── PluginManager          (src/plugins/manager.py)
        │     └── 各 Plugin        (src/plugins/*.py)                  — 业务功能,通过 ctx/cmd 与核心交互
        ├── ProtocolAdapter        (src/protocols/*)                   — 实际传输实现
        └── ViewManager            (src/ui/*)                          — UI,只能在 GUI 模式下加载
```

**唯一允许的依赖方向:**

- `main.py` → `bootstrap` → `core` / `plugins` / `protocols` / `ui`
- `plugins/*` → `core` / `bootstrap.protocols`(只看 Protocol 接口,不看 ServiceContainer 实现)
- `core/*` → `logging` / `utils` / `constants`,**不 import** `plugins` / `ui` / `protocols` 的具体实现
- `ui/*` 可读 `core` / `utils`,但 UI 改变状态必须经 `EventBus.emit(...)`,不能直接调 plugin 内部方法
- `mcp/tools/*` → `mcp.decorators` 和 stdlib;**不 import** `core` / `plugins`(MCP 工具应该是无副作用的纯函数,例外见 `music_player.py` 通过 `set_event_bus` 注入)

跨方向的引用都视为架构破坏,必须在评审里拦下。

---

## 插件式架构 (本项目的解耦核心)

`PluginManager` (`src/plugins/manager.py`) + `Plugin` 基类 (`src/plugins/base.py`) 是项目主要的"按需可拔"机制。

### 何时该写成插件

满足以下任一条件就写插件,否则别写:

- 这个功能在不同运行模式下可能 **不需要**(快捷键插件在 GUI/CLI 都装,GPIO 模式不装)。
- 这个功能 **依赖** 其他功能但不能反过来(如 MCP 插件依赖 audio,但 audio 不依赖 MCP)。
- 这个功能有自己的 setup/start/stop/shutdown 完整生命周期。

### 怎么写插件

```python
class MyPlugin(Plugin):
    name = "my_plugin"          # 唯一标识,被 requires 引用
    priority = 50               # 1-100,越小越早 setup
    requires = ["audio"]        # 依赖的 plugin name 列表

    async def setup(self, ctx: PluginContext, cmd: PluginCommands) -> None:
        await super().setup(ctx, cmd)
        audio = self.deps["audio"]   # PluginManager 已自动注入

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def shutdown(self) -> None: ...

    # 事件钩子,看用得着哪个就 override
    async def on_protocol_connected(self, protocol): ...
    async def on_incoming_json(self, message): ...
    async def on_incoming_audio(self, data): ...
    async def on_device_state_changed(self, state): ...
```

`PluginManager.register(*plugins)` 之后会拓扑排序,保证 `requires` 先 setup。一个 plugin 抛异常 **不影响** 其他 plugin —— 这是 PluginManager 的隔离设计,你的插件 setup 体里不需要再裹一层 try/except 来"保护自己"。

### 不要做的事

- **不要** 在 `Plugin` 子类里直接持有别的 plugin 的具体类型引用 —— 用 `self.deps["name"]` 拿,类型用 `Plugin` 或者 `Protocol`。
- **不要** 把 plugin 用作通用容器塞十几个不相关的功能。一个 plugin = 一个职责。
- **不要** 在 plugin 里直接 `import ServiceContainer` 反向依赖容器。需要的能力通过 `ctx`/`cmd` 拿。

---

## Protocol 接口隔离 (typing.Protocol)

项目用 PEP 544 `typing.Protocol` 做结构化类型隔离 —— 见 `src/bootstrap/protocols.py`:

- `PluginContext` —— 插件可以读的状态(`get_device_state`、`is_listening` 等)
- `PluginCommands` —— 插件可以执行的命令(`start_listening`、`send_audio` 等)
- `WindowContext` —— UI 桥接相关

`ServiceContainer` 在 `container.py` 写了两个 Adapter 类(`PluginContextAdapter`、`PluginCommandsAdapter`),把容器内部 API 翻译成 Protocol 表面。Plugin 看到的只有 Protocol。

### 为什么用 Protocol 而不是抽象基类

- Protocol 是 **结构化类型**: 实现方不需要 `class X(PluginContext)` 显式继承,只要方法签名对上就算实现。Adapter 不需要继承,降低耦合。
- 同一个对象可以同时满足多个 Protocol,组合更灵活。
- 类型检查器会 enforce,运行时 0 开销。

### 何时引入新 Protocol

只在以下情况增加新 Protocol:

- 已经有 **2 个以上** 的实现方且接口预期长期稳定。
- 调用方和实现方在不同包下,直接 import 会造成循环依赖或跨域污染。

**不要** 因为"以后可能换实现"就先抽 Protocol。一个实现就别抽。

---

## EventBus vs 直接调用

`EventBus` (`src/core/event_bus.py`) 是项目里 **跨域** 异步通信的标准方式。但它不是万能的,误用会让代码难追。

### 用 EventBus

- **跨域、不关心谁处理**: UI 层发 `UI_BUTTON_PRESS`,不关心音频插件还是快捷键插件接收。
- **一对多**: `DEVICE_STATE_CHANGED` 多个订阅者(UI、插件、托盘)。
- **生命周期解耦**: 发送方不关心接收方是否还存活。

### 不用 EventBus(直接调)

- **同一个对象内部** 的方法链。一个类内不要给自己发事件。
- **明确的请求/响应**: 你明确知道 A 必须调 B 拿结果,直接 `await b.do(...)`。
- **强时序约束**: 必须在 X 完成后立刻执行 Y。事件总线是 fire-and-forget,顺序不保证。
- **同包内的紧密协作**: 同包模块直接 import + 调用,清晰过事件。

判定方法: 写之前自问"如果我是事件订阅者,grep 这个事件名能猜出谁会处理吗?",不能就直接调。

---

## 何时抽象、何时不抽

> "三次法则": 同样的 pattern 重复出现 **3 次以上** 才考虑抽象。两次允许复制。

### 抽出来的标准

1. 三处以上的代码在做相同的事,且未来可能继续增加。
2. 重复的不只是结构,还有意图(都在解决同一类问题)。
3. 抽象后命名能写清楚 —— 写不清说明意图还没收敛。

### 不要抽的反例

- **单调用点的"工厂方法"**: 一个 `create_xxx()` 全项目就被一个地方调用 —— 直接写在调用点。
- **"以后可能扩展"**: 没有具体场景的扩展点是债务,不是设计。
- **"为了好看"的间接层**: A → B → C,B 没有任何转换或选择逻辑 —— 删 B,直接 A → C。
- **抽出来再 if/elif 各种类型**: 如果抽象内部要靠类型判断分支,说明抽象错了 —— 多半是两个不同的概念被强塞一起。

### 正例：激活流程的 Template Method + 工厂

GUI/CLI/GPIO 三种激活原本是三个独立类，核心流程完全一致，仅在展示层不同。重构后：

```
BaseActivation (模板方法 _core_activate)
├── CLIActivation (覆盖 _show_code / _show_result)    —— cli / gpio 模式
└── GUIActivation (QObject + BaseActivation 多重继承) —— gui 模式

main.py:
  handle_activation() → _create_activation(mode, svc, result).run()
```

满足了"三次法则"的三个标准：

1. **三处重复**：CLI/GUI/GPIO 的 `get_data → show_code → activate → show_result` 完全相同。
2. **相同意图**：都在执行"获取激活数据、展示验证码、等待激活、展示结果"这一件事。
3. **命名清晰**：`BaseActivation._core_activate()` 无需打开实现就能理解。

工厂 `_create_activation(mode, ...)` 虽只被一处调用，但它隔离了"选哪个实现"的决策，让 `handle_activation()` 保持简洁。

### 引入新 Plugin / Protocol / 单例 / 接口前的检查清单

- [ ] 已经有具体场景在用,不是预期。
- [ ] 用了之后调用方代码确实更短或更清楚。
- [ ] 命名能在不打开实现的情况下就让人知道用途。
- [ ] 删掉这层抽象,直接复制代码 —— 我反而觉得难受 —— 才说明值得抽。

---

## 单例 (`get_instance()`) 的代价

`ConfigManager`、`McpServer`、`LoggingConfigManager`、`ActivationService` 都是单例 (`ClassName.get_instance()`)。这是项目既定模式,但要清楚代价:

- 单例 **隐藏依赖**: 任何模块都能 `Foo.get_instance()`,看不出谁依赖谁。
- 单例 **难以替换**: 测试或多实例场景需要全局状态重置。

### 添加新单例的判定

只在以下两种情况下加新单例:

1. 整个进程内确实只能有一份(配置文件、日志系统、串口设备)。
2. 替代方案(经构造器注入或参数传递)会让 5+ 调用方代码显著变长。

否则一律走 **构造器注入** —— 像 `EventBus` / `TaskManager` 一样从 `ServiceContainer` 透传下去。

---

## 反过度耦合的具体规则

不要发生:

- `src/core/*.py` import `src/plugins/*` —— 核心服务不知道插件存在,只暴露接口。
- `src/plugins/*.py` 互相 import 具体类 —— 走 `self.deps["name"]` 拿,类型当 `Plugin` / Protocol。
- `src/ui/*.py` import `src/protocols/*` —— UI 不接触传输层,经 EventBus + 插件中转。
- `src/mcp/tools/*` import `src/core` / `src/plugins` —— 工具应该是 stateless 的纯计算/IO。需要事件能力的特例(如 `music_player`)用 `set_event_bus(...)` 由插件注入,而不是反向 import。

---

## 反过度解耦的具体规则

也不要发生:

- 同一文件、同一模块内的方法之间互相 emit 事件。直接调函数。
- 给只有一个调用方的内部方法定义 Protocol。直接用具体类。
- 把 3 行的工具函数封装成类、装饰器、抽象基类。函数就够了。
- `src/utils/` 里出现"通用 framework" —— `utils` 是项目专用胶水,不是要发布的库。
- 给每个数据 dict 配一个 dataclass 包装。只在跨模块传递 + 字段稳定 + 字段 ≥ 3 时才上 dataclass。

---

## 何时打破规则

规则是默认值,不是律法。打破规则的合法理由:

1. **物理约束**: 第三方库要求特定调用方式(如 sherpa-onnx 必须 thread-local lock)。
2. **性能**: 测过、有数据,EventBus 一跳的延迟实际会影响用户体验。
3. **临时绕路**: 需要快速修一个线上问题,且在同一个 PR 里留下 TODO + spec 更新计划。

每次打破规则都在 PR 描述里写一行原因。spec 不是用来背的,是用来对齐共识的。

---

## 遗留代码处理

接触遗留代码时，**不允许在新代码里复刻旧写法**，也不允许因为"文件本来就这样"而跳过。

### 规则

- **接触即修**: 修改一个文件时，顺手把该文件中明显违反现行 spec 的写法修复。例：`pyside6-guidelines.md` 列了 `# -*- coding: utf-8 -*-`、`@property` 替代 `@Property`、`asyncio.ensure_future()` 等禁止项 —— 见到就删/改。
- **范围限定**: 只修你在本次 diff 中已经接触到的代码区域，不扩大到整个文件的无关注代码。
- **不复刻**: 在同一文件中新增代码时，必须按现行 spec 写，不能因为"和周边代码风格一致"而复制旧写法。

### 不要做的事

- **不要** 以"统一风格"为由把修复扩散到本次 PR 未触及的文件 —— 那是独立 PR 的事。
- **不要** 在修复遗留代码的同一个 commit 里夹带功能变更 —— 修复 commit 只做修复，功能 commit 只做功能。

---

## 前端依赖隔离

`pyproject.toml` 顶层 `[project] dependencies` 只列 **运行任意一个 mode 都需要** 的依赖。GUI / 平台特定 / 开发工具走 extras 或 dev group:

| 类型 | 位置 | 例 |
|---|---|---|
| 全模式运行依赖 | `[project] dependencies` | aiohttp、sherpa-onnx、opuslib、numpy |
| GUI 模式 | `[project.optional-dependencies] gui` | PySide6、qasync |
| 平台限定 | sys_platform 标注 | pyobjc(macOS)、pycaw(Windows)、gpiozero(Linux GPIO) |
| 开发工具 | `[dependency-groups] dev` | pyinstaller、ruff、pytest、pytest-asyncio |

**禁止**:

- 顶层 deps 出现 GUI 专属库(`PySide6`、`qasync`、`PyQt*`)
- 顶层 deps 出现纯开发工具(`pyinstaller`、`ruff`、`pytest`)
- `src/ui/gui/` 之外的代码 `import PySide6.*`(已经在 `pyside6-guidelines.md` 列禁,这里复述强调)

**评审动作**: 任何接触 `pyproject.toml` 的 PR,reviewer 必须确认顶层 deps 只增不减地保持"全模式必需"语义。

---

## 参考文件

- `src/bootstrap/container.py` —— 容器、Adapter、依赖注入入口。
- `src/bootstrap/protocols.py` —— `PluginContext` / `PluginCommands` / `WindowContext`。
- `src/plugins/base.py` / `manager.py` —— 插件基类与拓扑排序。
- `src/core/event_bus.py` —— EventBus 实现与 `Events` 常量集合。
- `src/ui/shared/activation.py` —— 激活基类，模板方法模式的标准范本。
- `src/plugins/mcp.py` —— 一个紧凑插件的完整范本(setup 注入、事件钩子、shutdown 清理)。
