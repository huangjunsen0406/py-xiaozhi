# 排查 feature/new_architecture 合并前后的回归问题

## Goal

定位并修复 feature/new_architecture 合并后引入的 Windows 平台回归：
音频多声道下混失败、WebSocket 连接阻塞、打包版崩溃。

## Research References

* [`research/protocol-diff.md`](research/protocol-diff.md) — websockets 15.x proxy=True 导致 Windows 连接卡 10 秒
* [`research/wake-word-diff.md`](research/wake-word-diff.md) — 唤醒词代码无回归，问题在外部音频管线
* [`research/activation-diff.md`](research/activation-diff.md) — 激活系统重写，打包版 sherpa-onnx DLL 加载冲突

## Requirements

* [x] 修复 `indata.flatten()` 破坏多声道结构导致下混失败
* [x] 禁用 websockets 15.x 默认 proxy 自动检测
* [x] 设置 `open_timeout=5` 缩短握手超时
* [x] 默认禁用自动重连
* [x] 移除 CI mt.exe manifest 步骤
* [x] tokens.txt 非 ASCII 路径兜底
* [x] 激活错误日志补充异常类型 + traceback
* [x] 唤醒词模型延迟到 start() 加载，避免 PyInstaller DLL 冲突

## Acceptance Criteria

* [x] Windows 2ch 设备 20ms 帧长度下麦克风正常录音
* [x] WebSocket 首次连接不阻塞 UI 10+ 秒
* [x] 打包版 (.exe) 启用唤醒词时不崩溃
* [x] 错误日志有完整异常类型

## Out of Scope

* pycaw 音量控制 `Activate` 属性缺失（独立 bug）
* FFmpeg cmd 黑窗 + buffer size 错误（独立 bug）
* 音频帧长度 20ms/60ms 性能优化
