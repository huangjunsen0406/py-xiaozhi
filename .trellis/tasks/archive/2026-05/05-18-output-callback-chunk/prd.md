# 修复 output_callback 单次取 chunk 导致卡顿

## Goal

修复 `_output_callback` 每次只从 `output_buffer` 取一个 chunk 的问题。当 Opus 解码后的数据经过重采样不足以填满设备 blocksize 时（采样率非整除、服务器帧时长不匹配等场景），导致播放卡顿。

## What I already know

- 问题文件：`src/audio_codecs/audio_codec.py:_output_callback`（L159-195）
- 当前逻辑：每次回调只调用一次 `output_buffer.get_nowait()`，取一个 chunk
- `AudioConverter.convert_output()` 内部有 `_output_buffer`（deque）做流式重采样累积
- 当累积不够 `target_frames` 时返回 `None`，回调填静音
- 两台 Win PC 均为 44100Hz / 2ch，同一第三方服务器，同样 16kHz + 60ms 配置
- 用户 A 正常，用户 B 卡顿 → 根因是 soxr 流式重采样 2646.375 非整除 + 单次取 chunk 零容错
- `output_buffer` 是 `asyncio.Queue`，`get_nowait()` 从 sounddevice 线程调用

## Requirements

- `_output_callback` 应循环从 `output_buffer` 取 chunk 并喂给 `convert_output`，直到 resampler 内部缓冲区凑够 `frames` 或队列为空
- 队列为空仍不够时，输出已有数据 + 尾部填静音（而非全部静音）
- 不改变现有接口和其他组件的行为

## Acceptance Criteria

- [ ] 44100Hz 设备 + 16kHz/60ms 协议不再卡顿
- [ ] 服务器发 20ms 帧、客户端配 60ms 时能正常播放
- [ ] 48000Hz 设备（整除场景）行为不退化
- [ ] output_buffer 为空时仍输出静音（无异常）

## Definition of Done

- Lint / typecheck / CI green
- 不引入新依赖

## Out of Scope

- asyncio.Queue 线程安全问题（已有，不在本次修）
- 24kHz 第三方服务器兼容性（服务端问题）
- 音频输入链路

## Technical Approach

**改动 1：`audio_codec.py:_output_callback`**

将单次 `get_nowait()` 改为 while 循环：

```python
def _output_callback(self, outdata, frames, time_info, status):
    try:
        audio_converted = None
        while audio_converted is None:
            audio_data = self.output_buffer.get_nowait()
            if audio_data is None:
                break  # 队列空
            audio_converted = self.converter.convert_output(audio_data, frames)

        if audio_converted is None or len(audio_converted) < frames:
            outdata.fill(0.0)
            if audio_converted is not None and len(audio_converted) > 0:
                outdata[:len(audio_converted)] = audio_converted
        else:
            outdata[:] = audio_converted[:frames]
    except Exception as e:
        logger.error(f"输出回调错误: {e}")
        outdata.fill(0.0)
```

循环逻辑：每次从队列取一个 chunk 喂给 `convert_output`，`convert_output` 内部 `_output_buffer` 累积重采样数据，直到够 `frames` 返回非 None，或队列耗尽 break。

**无需改 `AudioConverter.convert_output`**：其现有接口已支持"喂入数据 → 累积 → 够了就返回"的语义。
