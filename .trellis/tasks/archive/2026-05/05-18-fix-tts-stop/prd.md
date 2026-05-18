# fix: tts_stop 清缓冲区只清输出路径 + 异常保护

## 问题

v2.0.5 中 `_handle_tts_stop` 新增 `clear_audio_queue()` 防止 TTS 尾音被麦克风收录（回声），但实现有两个缺陷导致"一轮游"（只有第一次对话正常，之后卡住）：

1. `converter.clear_buffers()` 同时清了 `_input_buffer`（麦克风重采样缓冲区），破坏了输入管线的 resampler 状态
2. `clear_audio_queue()` 没有异常保护，一旦抛异常会阻断 `set_device_state(LISTENING)` 和 `send_start_listening`，设备永远卡在 SPEAKING

## 修改范围

### 1. `src/audio_codecs/audio_converter.py`
- 新增 `clear_output_buffer()` 方法，只清 `_output_buffer`，不动 `_input_buffer`

### 2. `src/audio_codecs/audio_codec.py`
- `clear_audio_queue()` 调用 `converter.clear_output_buffer()` 替代 `converter.clear_buffers()`

### 3. `src/bootstrap/container.py`
- `_handle_tts_stop` 中的 `clear_audio_queue()` 调用包裹 try/except，确保状态切换一定执行

## 不改的

- `clear_buffers()` 原方法保留（给 `reload_devices` 等场景用）
- `_output_callback` while 循环逻辑不动
- `write_audio` Opus TOC 检测不动
