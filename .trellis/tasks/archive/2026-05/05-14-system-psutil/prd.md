# 重构 system 工具模块：psutil 替代自定义进程管理 + 消除命令注入

## Goal

用 `psutil`（已在依赖中）替代 18 个文件中的自定义 subprocess 进程管理代码，消除所有命令注入漏洞，将文件数从 18 压缩到 ~10，保持 7 个 MCP 工具的外部接口不变。

## What I already know

- system 模块是完全自包含的，唯一消费者是 MCP JSON-RPC（通过 `@mcp_tool` 装饰器）
- 无外部 Python 调用者，无测试
- `psutil>=5.9.0` 已在 requirements.txt 但 app_management 完全未使用
- 5 处命令注入漏洞（`shell=True` + 用户输入拼接）
- 音量控制已使用正确的库（pycaw/applescript/CLI），不需要改动
- 应用启动和已安装应用扫描没有跨平台库，需要保留分平台逻辑

## Requirements

### 保持不变的 MCP 接口

| 工具名 | 参数 | 返回类型 |
|--------|------|----------|
| `self.audio_speaker.set_volume` | `volume: int(0-100)` | `bool` |
| `self.audio_speaker.get_volume` | 无 | `int` |
| `self.audio_speaker.get_volume_status` | 无 | JSON str |
| `self.application.launch` | `app_name: str` | `bool` |
| `self.application.scan_installed` | `force_refresh: bool` | JSON str |
| `self.application.kill` | `app_name: str, force: bool` | `bool` |
| `self.application.list_running` | `filter_name: str` | JSON str |

### 进程管理（kill + list_running）→ psutil 重写

- 用 `psutil.process_iter()` 替代所有 `ps aux`/`tasklist`/`wmic`/JXA 进程列表
- 用 `psutil.Process(pid).terminate()/kill()` 替代所有 `kill -9`/`taskkill`/PowerShell kill
- 删除 `mac/killer.py`、`windows/killer.py`、`linux/killer.py`
- 统一的 `killer.py` 用 psutil 实现，无平台分支

### 应用启动 → 保留分平台但消除 shell=True

- macOS: `subprocess.run(["open", "-a", app_name])` 替代 osascript 注入
- Windows: 使用参数列表形式，不用 `shell=True`
- Linux: 保持 `subprocess.Popen([app_name])` + `xdg-open` 方式

### 已安装应用扫描 → 简化但保留分平台

- 保留 macOS glob `/Applications`、Windows 注册表、Linux `.desktop` 逻辑
- 合并重复的 hardcoded 系统应用去重逻辑
- 修复 import 放在文件末尾的问题

### 音量控制 → 不改动

- `tools.py` + `src/utils/volume_controller.py` 保持现状

## Acceptance Criteria

- [ ] 7 个 MCP 工具名称、参数、返回格式不变
- [ ] 零 `shell=True` 调用
- [ ] 零 f-string 拼接 shell 命令
- [ ] 进程列表和杀进程全部使用 psutil API
- [ ] 所有文件 `py_compile` 通过
- [ ] ruff check 无新增错误

## Definition of Done

- Lint 通过
- py_compile 通过
- 无 shell=True
- 无命令注入向量

## Technical Approach

### 新文件结构

```
src/mcp/tools/system/
├── __init__.py              # 不变
├── _tools.py                # 不变（MCP 工具注册）
├── tools.py                 # 不变（音量控制）
└── app_management/
    ├── __init__.py           # 简化导出
    ├── _utils.py             # 保留 clean_app_name
    ├── utils.py              # 保留 AppMatcher + 缓存
    ├── process_manager.py    # 新文件：psutil 统一进程管理（kill + list）
    ├── launcher.py           # 统一入口，分发到平台
    ├── scanner.py            # 统一入口，分发到平台
    ├── mac/
    │   ├── launcher.py       # 修复 osascript 注入
    │   └── scanner.py        # 保留
    ├── windows/
    │   ├── launcher.py       # 消除 shell=True
    │   └── scanner.py        # 保留
    └── linux/
        ├── launcher.py       # 保留（已安全）
        └── scanner.py        # 保留
```

删除文件：`mac/killer.py`、`windows/killer.py`、`linux/killer.py`、`mac/__init__.py`、`windows/__init__.py`、`linux/__init__.py`（如果只导出 killer）

### 核心变更：process_manager.py

```python
import psutil

def list_running_applications(filter_name: str = "") -> list[dict]:
    """用 psutil 列出运行中的应用."""
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
        ...

def kill_application(app_name: str, force: bool = False) -> bool:
    """用 psutil 终止匹配的进程."""
    p = psutil.Process(pid)
    p.terminate() if not force else p.kill()
```

## Out of Scope

- 音量控制重构
- 新增测试（当前无测试基础设施）
- AppMatcher 匹配算法优化
- 应用扫描性能优化

## Research References

- [system-management-libs.md](../research/system-management-libs.md) — psutil 可替代所有自定义进程管理代码

## Technical Notes

- `_tools.py` 中 `tool_list_running` 有 killer→scanner 的 fallback 逻辑，重构后不再需要
- `utils.py` 内部调用了 `scanner.list_running_applications`，需改为调用新的 `process_manager`
- 所有平台 killer `__init__.py` 如果只导出 killer 相关函数，可以删除
