# brainstorm: 修复Linux唤醒词打断慢/失效问题

## Goal

修复在 Linux（尤其是 ARM/树莓派）上，对话过程中通过唤醒词打断（interrupt）响应慢或完全失效的问题。

## What I already know

* 用户反馈：Linux 上唤醒后对话过程中，通过唤醒词打断会比较慢或失效
* ARM 设备（树莓派）帧长为 60ms，x86 为 20ms（`get_frame_duration()`）
* 唤醒词检测流程：audio callback → `on_audio_data()` → asyncio.Queue → `_detection_loop()` → sherpa-onnx → 回调
* 检测到唤醒词后，如果是 speaking 状态 → `abort_speaking()` + `clear_audio_queue()`
* sherpa-onnx 使用 transducer 模型（encoder + decoder + joiner），需要连续音频上下

## Root Causes Identified

经过代码审查，发现以下 6 个问题，按影响程度排列：

### 1. 检测队列溢出导致音频帧丢失（主因）

**问题链路**：
- 音频以 60ms/帧（Pi）速率从 PortAudio 线程推入 asyncio.Queue (maxsize=100)
- sherpa-onnx 关键词检测在 Pi 上每帧推理需要 100-200ms
- 检测循环每 5ms 轮询一次，每次只处理一帧
- 当推理速度 < 音频到达速度时，队列逐渐填满
- 队列满后丢弃最旧帧 → 音频上下文断裂 → 唤醒词无法被 transducer 模型识别

**数据**：
- 100 帧队列 × 60ms = 6 秒窗口，当推理延迟 >60ms 时队列必然溢出
- 丢弃的帧包含了唤醒词的音素序列，transducer 模型需要连续上下文

### 2. 打断后未重置检测流状态

`_on_detected()` 中调用 `abort_speaking()` 后，检测循环继续运行，处理队列中残留的旧音频帧。sherpa-onnx stream 的内部状态混入 abort 前后的音频，可能导致误触发或状态混乱。

### 3. 长时间对话中 stream 状态无限增长

`accept_waveform()` 不断推入音频，但 `get_result()` 返回空时 `reset_stream()` 不被调用。在长时间对话中，stream 内部 buffer 越来越大。

### 4. 5ms 忙轮询浪费 CPU

`_detection_loop()` 使用 `asyncio.sleep(0.005)` 每秒循环 200 次。在 Pi 上与其他负载竞争 CPU，本身加剧了队列溢出问题。

### 5. 检测到唤醒词后无防重复机制

`_handle_detection()` 有 1.5s 冷却时间，但检测到后队列中仍有未处理的音频帧可能触发二次检测。

### 6. asyncio.Queue 跨线程操作

`on_audio_data()` 在 PortAudio 回调线程中调用 `asyncio.Queue.put_nowait()`，虽然是线程安全的，但队列满时的 `get_nowait()` + `put_nowait()` 组合不是原子操作。

## Requirements

### MVP (必须修复)

1. **解决队列溢出导致的帧丢失** — 检测循环需要能跟上传入音频的速率
2. **打断后重置检测流** — `abort_speaking()` 后重置 sherpa-onnx stream，丢弃旧音频
3. **减少空闲 CPU 消耗** — 将忙轮询改为事件驱动

### 扩展（建议修复）

4. 长时间对话中限制 stream 内部状态大小
5. 改善队列跨线程操作的健壮性

## Acceptance Criteria

* [ ] Pi 上对话中说出唤醒词，1 秒内完成打断
* [ ] Pi 上对话中唤醒词检测成功率 > 90%（10 次测试）
* [ ] 打断后不产生误触发
* [ ] x86/macOS 上唤醒词功能不受影响

## Technical Approach

### 修复方案：批量处理 + 事件驱动 + 打断重置

**核心改动在 `WakeWordDetector._detection_loop()` 和 `_process_audio()`**：

1. **批量处理音频帧**：每次循环从队列中取尽可能多的帧，连续送入 stream，替代每次只取一帧
2. **事件驱动替代轮询**：使用 `asyncio.Queue.get()` 阻塞等待替代 `sleep(0.005)` 忙轮询
3. **打断时重置**：在 `stop()` 或新增的 `reset_stream()` 方法中清理 sherpa-onnx stream
4. **限制 stream buffer**：定期或在 N 帧后强制 reset stream 防止状态无限增长
5. **打断后暂停短暂时间**：检测到唤醒词并打断后，短暂暂停检测让状态稳定

## Open Questions

* ~~批量处理时一次处理多少帧合适？~~ — 决定每次排空队列最多 20 帧

## Implementation Decisions (Final — 经过多轮迭代验证)

### 唤醒词修复 (wake_word_detect.py)

1. **保留原有轮询模式**: `get_nowait()` + `sleep(0.005)` — 事件驱动的 `queue.get()` 会饿死事件循环导致唤醒词推理无法调度，回退到轮询
2. **哨兵停止**: `stop()` 放入 `_STOP_SENTINEL` 唤醒检测循环，替代 `task.cancel()`，避免 Python 3.10 `Task was destroyed but it is pending!` 错误
3. **检测后暂停+排空**: 检测到唤醒词后暂停 300ms 并排空队列，避免旧音频触发重复检测
4. **改进错误日志**: `on_audio_data()` 异常日志显示异常类型名称

### TTS 尾部截断修复 (audio.py)

移除 tts stop 处理器中的 `clear_audio_queue()`，让 output_buffer 自然排空后再播放下一句。打断路径（wake_word、用户点击）有独立的队列清除。

### 已废弃的方案

- ~~事件驱动的 `queue.get()` 阻塞等待~~ → 饿死事件循环，唤醒词完全无法检测
- ~~批量送入音频帧~~ → transducer 模型需要 accept/decode 交替，不能 accept-all-then-decode-all

## Out of Scope

* 更换唤醒词模型（sherpa-onnx 替换方案）
* 音频采集流程改造
* GUI 相关修改

## Technical Notes

* 关键文件：
  - `src/audio_processing/wake_word_detect.py` — 主要修改目标
  - `src/plugins/wake_word.py` — 可能需要添加打断后重置调用
  - `src/plugins/audio.py` — 了解音频流与检测的交互
  - `src/audio_codecs/audio_codec.py` — 音频回调 → 监听器通知
* ARM 帧长 60ms，队列 100 帧 = 6s 缓冲
* sherpa-onnx KeywordSpotter API: `accept_waveform()` → `is_ready()` → `decode_stream()` → `get_result()` → `reset_stream()`
