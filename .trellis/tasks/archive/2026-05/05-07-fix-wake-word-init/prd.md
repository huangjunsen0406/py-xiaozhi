# 修复唤醒词初始化流程问题

## Goal

修复 `WakeWordDetector.initialize()` 中的代码顺序问题，以及潜在竞态条件。

## 根因分析

### 问题一：`_release_model()` 无条件调用（日志顺序错乱的根因）

`initialize()` line 57:
```python
# Release old model
self._release_model()      # ← 无条件执行，即使从未加载过模型
```

导致日志 "模型资源已释放" 出现在初始化最前面，而此时 `_stream` 和 `_keyword_spotter` 都是 `None`。

**应该改为**：只在 `_model_loaded=True` 时才释放。

### 问题二：`_load_model()` 不加锁设置 `_keyword_spotter`

`_release_model()` 用 `self._onnx_lock` 保护，但 `_load_model()` line 140 直接赋值：
```python
self._keyword_spotter = sherpa_onnx.KeywordSpotter(...)
```
没有锁保护。如果 `reload()` 并发调用，可能与 `_process_audio()` 中的读操作竞态。

### 问题三：`_load_config()` 在模型加载前打印调试日志

Line 114 `logger.debug(f"KWS配置: ...")` 在 sherpa_onnx 不可用时仍然输出，产生误导。

## 修复方案

1. **`_release_model()` 加条件判断**：只在 `_model_loaded` 时释放
2. **`_load_model()` 加锁保护赋值**：与 `_release_model()` 保持一致
3. **调整 `initialize()` 执行顺序**：config check → config load → release old (if loaded) → load new

## Acceptance Criteria

* [ ] `_release_model()` 不在模型未加载时打印 "模型资源已释放"
* [ ] 日志顺序合理：配置检查 → 配置加载 → 旧模型释放(如有) → 新模型加载
* [ ] `_load_model()` 中 `_keyword_spotter` 赋值受 `_onnx_lock` 保护
* [ ] 代码 lint 通过

## Technical Notes

* `wake_word_detect.py:50-95` — `initialize()` 主入口
* `wake_word_detect.py:116-164` — `_load_model()`
* `wake_word_detect.py:166-185` — `_release_model()`
* `wake_word.py:32-57` — `WakeWordPlugin.setup()` 调用方
