# 重构音频配置：设备层/协议层分离

## 问题

`AudioConfig` 类属性在模块 import 时一次性求值，导致 Settings UI 中
`opus_output_sample_rate` 和 `frame_duration` 的修改在运行时无法生效。

同时管线拓扑（设备↔协议映射）硬编码在 AudioCodec 的两个方法中，
`initialize()` 和 `reload_devices()` 各写了一遍。

## 目标

1. `AudioConfig` 中的协议采样率/帧时长改为动态读取，支持运行时重载
2. OpusCodec 由 AudioCodec 显式注入采样率参数，不依赖类默认值
3. 提取 `AudioPipelineConfig`，消除 initialize/reload 的重复映射代码
4. Settings UI 改 opus_output_sample_rate / frame_duration 后触发热重载时生效

## 不改的

- 设备层的采样率/声道逻辑（DeviceConfig 每次重建已正确）
- stream_manager 的 sounddevice 流创建逻辑
- AudioBuffer、MusicDecoder 等其他组件

## 文件清单

| 文件 | 改动 |
|------|------|
| `src/constants/constants.py` | AudioConfig 改动态属性 |
| `src/audio_codecs/audio_codec.py` | 提取 pipeline config，消除重复 |
| `src/audio_codecs/opus_codec.py` | 移除 AudioConfig 默认参数依赖 |
