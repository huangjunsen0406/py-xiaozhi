# fix-medium-priority-issues

## Goal

修复 reports/00-summary.md 中的 7 个中级问题。

## What I already know

经过代码探索，7 个问题详情如下：

| # | 问题 | 文件 | 复杂度 |
|---|------|------|--------|
| 8 | camera.py 死代码 — `__init__.py` 不导入它，无调用方 | `mcp/tools/camera/camera.py` | 简单 |
| 9 | `_clean_app_name` 三平台完全相同的函数 | `system/.../{mac,linux,windows}/scanner.py` | 简单 |
| 10 | WakeWordDetector `get_nowait()` 非阻塞轮询 | `audio_processing/wake_word_detect.py` | 中等 |
| 11 | `_save_config()` 无原子写入保护 | `utils/config_manager.py` | 简单 |
| 12 | `_patch_find_library` 全局替换 `ctypes.util.find_library` | `utils/opus_loader.py` | 中等 |
| 13 | StateManager 属性与 getter 方法并存（3 组重复） | `core/state_manager.py` | 中等 |
| 14 | `refreshDevices` 使用 `sd._terminate()/_initialize()` 私有 API | `ui/shared/models/settings_model.py` | 中等 |

## Recommended approach for each

- **#8**: 直接删除 `camera.py`（死代码，无导入方）
- **#9**: 在 `app_management/` 下创建 `_utils.py`，提取 `_clean_app_name`，三个 scanner 导入使用
- **#10**: 需确认调用方模式后决定是改用 `await queue.get()` 还是保持现状
- **#11**: `_save_config` 先写 `.tmp` 临时文件，再 `os.replace()` 原子移动
- **#12**: 将 `_patch_find_library` 改为 context manager，`setup_opus()` 中使用 `with patch_opus(lib_path):`
- **#13**: 删除 `get_device_state()`、`get_listening_mode()`、`is_keep_listening()` 三个冗余方法，更新所有调用方
- **#14**: 研究 sounddevice 公共 API 替代方案，若无可替代则保留并加注释说明版本兼容

## Open Questions

* 全部 7 项都修复？还是有想跳过的？
