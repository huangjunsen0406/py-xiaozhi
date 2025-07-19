# WebRTC Audio Processing Module for Python

工业级的实时音频处理Python包，基于Google WebRTC项目的AudioProcessing模块。

> 📚 **完整使用指南**: 请参考项目根目录的 [`WebRTC_APM_Complete_Guide.md`](../../WebRTC_APM_Complete_Guide.md)，包含完整的API文档、版本对比、最佳实践和故障排除。

## 功能特性

- 🎯 **回声消除 (AEC3/AECM)**: 消除扬声器播放音频在麦克风中的回音
- 🔇 **噪声抑制 (NS)**: 4级可调的噪声抑制强度
- 📢 **自动增益控制 (AGC1/AGC2)**: 自动调整音频音量到合适水平
- 🎛️ **高通滤波器**: 消除低频噪声和直流分量
- ⚡ **实时处理**: 支持10ms低延迟音频处理
- 🔧 **跨平台**: 支持Windows、macOS、Linux (x64/ARM64)

## 快速开始

### 基本使用

```python

from libs import webrtc_apm
import numpy as np

# 创建音频处理器
processor = webrtc_apm.AudioProcessor(sample_rate=16000, channels=1)

# 处理音频数据（10ms帧，160个样本@16kHz）
audio_data = np.random.randn(160).astype(np.float32)
processed = processor.process(audio_data)

print(f"处理完成: {processed.shape}")
```

### 便捷函数

```python

from libs import webrtc_apm

# 使用便捷函数创建
processor = webrtc_apm.create_audio_processor(
    sample_rate=16000,
    channels=1,
    echo_canceller=True,
    noise_suppression=True,
    gain_control=True
)

processed = processor.process(audio_data)
```

### 自定义配置

```python

from libs import webrtc_apm

# 创建自定义配置
config = webrtc_apm.Config()
config.echo_canceller = True
config.noise_suppression = True
config.noise_level = 'high'  # 'low', 'moderate', 'high', 'very_high'
config.gain_control = True
config.high_pass_filter = True

# 使用自定义配置
processor = webrtc_apm.AudioProcessor(16000, 1, config)
```

### 回声消除（双向处理）

```python

from libs import webrtc_apm

processor = webrtc_apm.AudioProcessor(16000, 1)

# 设置回声路径延迟（根据实际硬件调整）
processor.set_delay(50)  # 50ms延迟

# 处理流程：先播放音频，再采集音频
processor.process_playback(playback_audio)  # 播放音频（参考信号）
clean_audio = processor.process(capture_audio)  # 采集音频（应用回声消除）
```

### 上下文管理器

```python

from libs import webrtc_apm

with webrtc_apm.AudioProcessor(16000, 1) as processor:
    processed = processor.process(audio_data)
    # 自动资源清理
```

## 配置选项

### 预设配置

```python
# 默认配置
config = webrtc_apm.Config.default()

# 增强配置（推荐）
config = webrtc_apm.Config.enhanced()

# 最小配置（仅回声消除）
config = webrtc_apm.Config.minimal()
```

### 详细配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `echo_canceller` | bool | True | 启用回声消除 |
| `noise_suppression` | bool | True | 启用噪声抑制 |
| `noise_level` | str | 'high' | 噪声抑制级别 |
| `gain_control` | bool | True | 启用自动增益控制 |
| `high_pass_filter` | bool | True | 启用高通滤波器 |

### 噪声抑制级别

- `'low'`: 轻微抑制，保持音质
- `'moderate'`: 中等抑制，平衡音质和效果
- `'high'`: 强抑制，适合嘈杂环境（推荐）
- `'very_high'`: 极强抑制，可能影响音质

## 性能建议

### 音频帧大小

推荐使用10ms音频帧以获得最佳性能：

```python
# 不同采样率的10ms帧大小
frame_sizes = {
    8000: 80,    # 8kHz
    16000: 160,  # 16kHz (推荐)
    32000: 320,  # 32kHz
    48000: 480,  # 48kHz
}

sample_rate = 16000
frame_size = frame_sizes[sample_rate]
```

### 实时音频处理

```python
import sounddevice as sd
from libs import webrtc_apm

processor = webrtc_apm.AudioProcessor(16000, 1)


def audio_callback(indata, outdata, frames, time, status):
    # 处理音频
    processed = processor.process(indata[:, 0])
    outdata[:, 0] = processed.astype(np.float32) / 32767.0


# 启动音频流
with sd.Stream(
        samplerate=16000,
        channels=1,
        callback=audio_callback,
        blocksize=160,  # 10ms
        dtype=np.float32
):
    input("按Enter停止...")
```

## 故障排除

### 常见问题

1. **动态库加载失败**
   ```
   WebRTCAudioProcessingError: 加载动态库失败
   ```
   解决：确保对应平台的动态库文件存在且有执行权限

2. **音频格式错误**
   ```
   ValueError: 音频数据格式不正确
   ```
   解决：确保输入音频为numpy数组，支持float32或int16格式

3. **帧大小不匹配**
   ```
   警告: 帧大小不匹配 320 != 160
   ```
   解决：使用推荐的10ms帧大小

### 调试模式

```python

from libs import webrtc_apm
import numpy as np

# 创建处理器
processor = webrtc_apm.AudioProcessor(16000, 1)

# 调试信息
print(f"采样率: {processor.sample_rate}")
print(f"通道数: {processor.channels}")

# 测试处理
test_audio = np.random.randn(160).astype(np.float32)
print(f"输入音频: shape={test_audio.shape}, dtype={test_audio.dtype}")

processed = processor.process(test_audio)
print(f"输出音频: shape={processed.shape}, dtype={processed.dtype}")
```

## 系统要求

- Python 3.7+
- NumPy
- 支持的操作系统：
  - macOS (Intel x64 / Apple Silicon ARM64)
  - Linux (x64 / ARM64)
  - Windows (x64 / x86)

## 许可证

基于WebRTC项目的BSD许可证。

## 演示和测试

运行项目根目录的综合演示：
```bash
python webrtc_apm_demo.py
```

该演示包含：
- 自动检测可用版本
- 完整功能测试
- 性能基准测试
- 实时处理模拟
- 版本对比分析

## 文档和资源

- 📚 **完整指南**: [`WebRTC_APM_Complete_Guide.md`](../../WebRTC_APM_Complete_Guide.md)
- 🧪 **综合演示**: [`webrtc_apm_demo.py`](../../webrtc_apm_demo.py)
- 🌐 **WebRTC项目**: https://webrtc.org/
- 🔧 **pip版本**: `pip install git+https://github.com/huangjunsen0406/webrtc-audio-processing.git`

## 许可证

基于WebRTC项目的BSD许可证。