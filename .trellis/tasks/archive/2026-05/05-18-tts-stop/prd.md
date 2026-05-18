# 自动对话模式 tts.stop 时清空播放缓冲区防回声

## Goal
自动对话模式下 tts.stop 切换到 LISTENING 前清空播放缓冲区，防止麦克风录到扬声器残留 TTS 音频导致自言自语。

## Requirements
- `_handle_tts_stop` 的 `keep_listening` 分支在切状态前调用 `clear_audio_queue`
- `clear_audio_queue` 同时清空 converter 内部 resampler 缓冲区
- 手动模式（非 keep_listening）不受影响，TTS 正常播完
