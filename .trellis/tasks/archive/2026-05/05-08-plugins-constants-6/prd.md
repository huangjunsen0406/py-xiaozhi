# 修复 plugins/constants 6 个代码质量问题

## 背景
基于 `reports/plugins.md`、`reports/constants.md` 的分析，清理死代码和统一编码风格。

## 修复清单

### 1. `_audio_consumer_task` 死代码
- **文件**: `src/plugins/audio.py`
- **修复**: 移除 `__init__` 中的声明和 `shutdown` 中的取消逻辑

### 2. `reload_from_config` 虚假 async
- **文件**: `src/plugins/shortcuts/__init__.py`
- **修复**: 去掉 `async`，改为普通方法

### 3. `_activity_timeout` 未使用
- **文件**: `src/plugins/shortcuts/pynput_backend.py`
- **修复**: 删除 `_activity_timeout` 定义

### 4. `_on_error` 同步方法风格不统一
- **文件**: `src/plugins/wake_word.py`
- **修复**: 改为 `async def _on_error` 以与其他方法风格统一

### 5. 枚举风格不统一
- **文件**: `src/constants/constants.py`
- **修复**: 将 ListeningMode、DeviceState、AbortReason 从字符串类改为 `enum.Enum`

### 6. CONNECTING 状态未被使用
- **文件**: `src/constants/constants.py`
- **修复**: 移除 `DeviceState.CONNECTING`（仅在定义处）

## 注意事项
- 枚举重构需同步所有引用处（`is` 比较改为 `==` 比较，Enum 值从 `.value` 获取）
- 字符串枚举改 Enum 会影响约 10+ 个文件中的引用
