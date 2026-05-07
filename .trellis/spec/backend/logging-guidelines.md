# 日志规范

> 使用 `src/logging` 模块(基于 stdlib `logging` 二次封装)。应用在 `main.py` 里调用 `setup_logging(...)` 完成一次性初始化,其它模块只需要 `get_logger()`。

---

## 拿 logger(只有一种写法)

模块顶部 import 之后:

```python
from src.logging import get_logger

logger = get_logger()
```

无参数的 `get_logger()` 会自动解析调用者的 `__name__`。**不要** 自己起名字 —— 没意义。

```python
# 不要这样写
logger = logging.getLogger(__name__)         # 绕过项目封装,丢了 context filter
logger = get_logger("my.custom.thing")       # 自定义名字会破坏第三方库分级
```

---

## 日志级别(什么时候用哪个)

| 级别 | 用途 | 仓库示例 |
|---|---|---|
| `debug` | 调试用的详细状态,生产环境也可以保留 | `logger.debug(f"日志文件: {log_file}")`(`src/logging/__init__.py`)、`logger.debug("MCP shutdown: 已停止音乐播放器")`(`src/plugins/mcp.py`) |
| `info` | 生命周期 / 状态切换;开发者在普通日志里希望看到 | `logger.info("日志系统已初始化")`、`logger.info("开始设备激活流程检查...")`(`main.py`) |
| `warning` | 出错但已被恢复 / 走了降级路径 | `logger.warning(f"设置 MusicPlayer EventBus 失败: {e}")`(`src/plugins/mcp.py`) |
| `error` | 操作失败,要保留完整上下文(有异常时一定带 `exc_info=True`) | `logger.error(f"激活流程异常: {e}", exc_info=True)`(`main.py`) |
| `critical` | 全局不可恢复错误。极少用。 | — |

---

## 记录异常

**统一用 `logger.error(f"...: {e}", exc_info=True)`**。整个仓库都不用 `logger.exception(...)`,保持一致。

```python
try:
    await activation_service.initialize()
except Exception as e:
    logger.error(f"激活流程异常: {e}", exc_info=True)
    return False
```

如果只是想标记一次 **非关键** 失败、不需要完整堆栈,用 `logger.warning(f"...: {e}")`(不要 `exc_info`)。

---

## 格式

`main.py` 中 `parse_args` 之后只调一次:

```python
from src.logging import setup_logging
setup_logging(enable_console=(_args.mode != "cli"))   # CLI 模式禁用控制台,因为 CLIDisplay 接管终端
```

控制台 handler 用 `ColoredFormatter`;文件 handler 用带 trace-id 的 `SimpleFormatter`;生产环境会通过 `LoggingConfigManager` 启用 JSON 文件 handler。**业务代码不要去配置 handler**,只调 `get_logger()`。

---

## 该记什么

- 服务 / 插件生命周期: setup、start、stop、shutdown。
- 状态切换: 设备状态、监听模式、协议 connect/disconnect。
- 外部 I/O: 协议消息(debug 级)、配置读写、设备激活步骤。
- 工具调用: MCP 工具进入时记录工具名 + 参数(`logger.info(f"[WeatherTool] 获取 {city} ...")` —— 见 `src/mcp/tools/weather/weather_tools.py`)。

## 不该记什么

`SensitiveDataFilter`(配置在 `src/logging/log_config.py`)会自动过滤已知敏感字段,默认覆盖: `password`、`passwd`、`secret`、`token`、`api_key`、`apikey`、`access_token`、`refresh_token`、`authorization`、`credential`、`private_key`。

即便有过滤器:

- 不要打印完整请求/响应体(可能含用户音频或转录文本)。
- 不要 dump 整个配置;只 log 你改动的 key。
- `src/` 里 **不允许** `print(...)` —— 它会绕过过滤器和轮转。

---

## Trace 上下文(可选)

需要跨 async 任务 / 跨线程关联日志时,用 `src.logging.with_trace` / `set_trace_id`(见 `src/logging/context.py`)。普通流程不需要 —— 默认空 trace-id 就行。

---

## 语言

仓库里所有 `logger.*` 消息都是 **中文**,经常带 `[Component]` 或 `Component:` 前缀方便 grep:

```python
logger.warning(f"EventBridge: 事件循环未运行,跳过事件 {event}")
logger.info(f"[WeatherTool] 获取 {city} 的当前天气")
```

写新代码时跟周围文件的前缀风格保持一致。
