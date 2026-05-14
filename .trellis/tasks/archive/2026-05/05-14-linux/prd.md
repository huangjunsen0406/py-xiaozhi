# 完善 Linux 音频依赖安装文档

## Goal

重写 `documents/docs/guide/系统依赖安装.md` 的 Linux 部分，按 Ubuntu 版本区分音频依赖安装命令，增加树莓派说明，避免用户因驱动安装错误无法使用音频。

## Requirements

- 按 Ubuntu 版本（20.04/22.04/24.04-25.04）区分安装命令
- 说明各版本默认音频服务器（PulseAudio vs PipeWire）
- 警告不要在 PipeWire 系统上安装 pulseaudio 守护进程
- 增加树莓派/ARM 专门说明
- Ubuntu 20.04 需说明 Python 3.10+ 需要 deadsnakes PPA
- 增加音频验证命令
- 增加常见问题排查

## Research References

- [linux-audio-deps.md](../research/linux-audio-deps.md)

## Acceptance Criteria

- [ ] Linux 部分按版本区分
- [ ] 树莓派有独立说明
- [ ] 音频验证命令完整
- [ ] 无错误包名
