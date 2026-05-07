# 无音频设备时无法启动 + 静默吞异常

## Goal

修复部署在无音频设备（树莓派等）时应用启动异常，以及全局 `except Exception: pass` 导致的错误不可追溯问题。

## 根因分析

### 一、音频异常传播链（已确认：理论上被隔离）

```
audio_device.py:78  RuntimeError("无法找到可用的输入设备")
  ↓
audio_codec.py:107  catch → close → re-raise
  ↓
audio.py:53         catch → self.codec = None（不上抛）
  ↓
manager.py:153      PluginManager.setup_all() catch → log（不上抛）
  ↓
container.py:240    兜底 catch all → return 1
```

异常隔离机制存在，但 **crash 类型不明**——如果是 PortAudio C 层 segfault 或阻塞，Python try/except 无效。

### 二、全局 `except Exception: pass` 问题（主要问题）

扫描到 40+ 处，按严重程度分：

**高危（静默吞掉功能注册/请求处理异常）：**

| 文件 | 行号 | 影响 |
|------|------|------|
| `plugins/mcp.py` | 34-35 | `_send()` 失败——MCP 响应发不到客户端 |
| `plugins/mcp.py` | 40-41 | `add_common_tools()` 失败——**零 MCP 工具，零日志** |
| `plugins/mcp.py` | 64-65 | `parse_message()` 异常——不知道哪个工具出错 |
| `plugins/mcp.py` | 82-83 | shutdown 清理失败无日志 |
| `plugins/manager.py` | 46 | 依赖注入失败——插件拿不到依赖 |
| `plugins/manager.py` | 170,178,186,194 | 生命周期事件通知失败——下游不知状态变更 |
| `audio_utils.py` | 312 | `select_audio_device()` 失败返回 None——触发 RuntimeError |

**中危（静默吞掉运行时操作异常）：**

| 文件 | 行号 | 影响 |
|------|------|------|
| `plugins/audio.py` | 160,177,190 | 音频操作失败无日志 |
| `audio_codecs/music_decoder.py` | 175,241,257,269,285 | 音乐解码/清理失败无日志 |
| `mcp/tools/music/music_player.py` | 911,1252 | 音乐播放操作异常无日志 |

## 修复方案

### MVP：消灭 `except Exception: pass`

规则：**每个 `except Exception` 必须至少 `logger.error(..., exc_info=True)`**。
如果确实是可忽略的异常（如 shutdown 清理），至少 `logger.debug()`。

### 具体修改

1. **`plugins/mcp.py`**（最优先）：
   - `_send()` → `logger.error(f"MCP 发送失败: {e}")` 
   - `add_common_tools()` → `logger.error(f"MCP 工具注册失败: {e}", exc_info=True)`
   - `parse_message()` → `logger.error(f"MCP 消息处理失败: {e}", exc_info=True)`
   - shutdown → `logger.debug(f"MCP shutdown 清理: {e}")`

2. **`plugins/manager.py`**：生命周期 notify_* 方法加 `logger.error`

3. **`plugins/audio.py`**：运行时操作加 `logger.error`

4. **其他文件**：按同样规则修复

## Decision

**范围：全局 40+ 处全修。**

分级策略：
- **功能级异常**（setup/注册/请求处理）→ `logger.error(..., exc_info=True)` + 保留原有 pass 逻辑
- **清理级异常**（shutdown/close/stop）→ `logger.debug(..., exc_info=True)`
- **有注释说明的**（如 audio_codec.py:403 "锁可能已损坏"）→ `logger.warning()` 保留注释

## Implementation Plan

**PR1**: 高危文件修复
- `plugins/mcp.py` (4处)
- `plugins/manager.py` (5处)
- `plugins/audio.py` (3处)
- `utils/audio_utils.py` (1处)

**PR2**: 中危文件修复
- `audio_codecs/music_decoder.py` (5处)
- `mcp/tools/music/music_player.py` (2处)
- `utils/activation_announcer.py` (2处)
- `activation/service.py` (1处)

**PR3**: 其余文件修复
- `ui/cli/display.py` (3处)
- `ui/shared/models/settings_model.py` (1处)
- `plugins/shortcuts/` (4处)
- `mcp/tools/screenshot/` (1处)
- `mcp/tools/system/` (2处)
- `logging/log_handlers.py` (2处)
- `audio_codecs/audio_codec.py` (1处)

## Acceptance Criteria

* [x] 每个 `except Exception: pass` 替换为至少 `logger.debug()` 级别的日志
* [x] 功能级异常使用 `logger.error(..., exc_info=True)`
* [x] 不改变原有异常处理逻辑（不 re-raise，不改变控制流）
* [ ] Lint 通过

## Out of Scope

* 不在本次修改异常处理逻辑——只加日志，不改行为
* 不处理 PortAudio C 层 crash/hang——那是独立问题


## Technical Notes

* `add_common_tools()` 通过 `discover_tool_modules()` 递归 import 所有 MCP 工具子模块。如果任一模块 import 时抛异常，整个调用失败，当前被 `pass` 吞掉
* `mcp_server.py` 内部已有正确的 error logging（`_handle_tool_call` line 222 会 log 工具名+错误），但 plugin 层的 `pass` 让这些日志毫无意义——用户看不到
