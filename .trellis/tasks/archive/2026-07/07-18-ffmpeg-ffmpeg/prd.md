# 修复 FFmpeg 打包不可移植导致无系统 FFmpeg 环境异常

## Goal

让安装包在**未安装系统 FFmpeg** 的干净机器上，音乐解码可用；激活语音播报**不依赖 FFmpeg**（预置 WAV）。CI 注入真正可分发的 ffmpeg/ffprobe。支持 mac 本机打临时测试包。

## What I already know

* 用户反馈：最新安装包在未装 ffmpeg 的电脑上异常/闪退。
* `get_ffmpeg_path()` 优先 `libs/ffmpeg/<plat>/<arch>/`，再 fallback 系统 PATH。
* 调用点：`music_decoder.py`（音乐，需 ffmpeg）；`activation_announcer.py`（激活，当前用 ffmpeg 解 ogg）。
* CI 用 brew/apt/choco `cp $(which ffmpeg)` — mac/linux 动态链接，用户机不可跑。
* `libs/ffmpeg/` gitignore，仅 CI/本地注入。
* 激活资源：`assets/sounds/<locale>/{0-9,activation}.ogg`（Opus/Ogg，极小）。
* 本地打包：`unifypy . --config build.json`。

## Decision (ADR-lite)

**Context**: 动态链接 ffmpeg 不可分发；激活播报不必依赖完整解码器。  
**Decision**:
1. CI/本地注入**可移植** ffmpeg+ffprobe（优先官方/社区 static 或等价可分发构建），构建后隔离 PATH 冒烟。
2. 激活音：**仓库内直接换成 WAV**（24kHz mono 与现播放参数对齐），`ActivationAnnouncer` 用标准库 `wave` + numpy，零 ffmpeg。
3. 音乐仍走内置 ffmpeg；失败日志明确，避免用户误装系统 ffmpeg。
4. 文档补充：安装包用户不必装 ffmpeg；mac 本地临时打包步骤。

**Consequences**: 安装包体积略增（ffmpeg 静态 + wav）；激活路径更稳；音乐依赖 CI 注入质量。

## Requirements

* CI 各平台注入可移植 ffmpeg + ffprobe → `libs/ffmpeg/<plat>/<arch>/`
* 构建后冒烟：隔离 PATH 执行 `-version`，失败则红
* 激活播报：WAV + sounddevice，不启动 ffmpeg
* 仓库 `assets/sounds/**` 改为（或并列后替换）wav；announcer 只读 wav
* 提供脚本：`scripts/bundle_ffmpeg.sh`（或等价）供 CI 与 mac 本地复用
* 文档：系统依赖说明 + 本地打包注入步骤

## Acceptance Criteria

* [ ] CI 不再仅 `cp $(which ffmpeg)` 动态链接副本
* [ ] 干净机无系统 ffmpeg：音乐解码可用
* [ ] 干净机无系统 ffmpeg：激活播报可用，进程树无 ffmpeg
* [ ] CI 冒烟失败则构建失败
* [ ] 开发态激活不依赖系统 ffmpeg
* [ ] mac 本地可按文档打临时 app/dmg

## Definition of Done

* build.yml + bundle 脚本 + announcer + 资源 + 文档
* 本地/CI 验证说明
* Lint 不回归

## Out of Scope

* 重写音乐架构
* 嵌套 ffmpeg 签名/公证
* 无关启动闪退（除非同源）

## Research References

* [`research/portable-ffmpeg-sources.md`](research/portable-ffmpeg-sources.md) — 推荐：BtbN lgpl win/linux；mac arm64 用 redistributable/static 或 imageio/static-ffmpeg 提取，禁止 brew cp
* [`research/pyinstaller-ffmpeg-bundling.md`](research/pyinstaller-ffmpeg-bundling.md) — datas 含 libs；+x；Windows DLL 同目录；mac xattr；打包后隔离 PATH 冒烟

## Technical Notes

* 文件：`.github/workflows/build.yml`、`src/utils/resource_finder.py`、`src/audio_codecs/music_decoder.py`、`src/utils/activation_announcer.py`、`assets/sounds/**`、`build.json`、打包文档
* 历史：`05-15-ci-ffmpeg`、`0fdada1`、`bea1aae`、`841c5f1`
* 激活播放现用 24000 Hz mono float32；WAV 建议 s16le 24kHz mono
