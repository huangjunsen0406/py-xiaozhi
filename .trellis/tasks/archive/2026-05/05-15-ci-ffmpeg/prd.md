# CI 打包 FFmpeg 到应用内

## 背景

从启动台启动打包后的 .app 时，macOS 不继承终端 PATH，导致找不到 brew 安装的 ffmpeg。音乐播放功能依赖 FFmpeg 做音频解码，需要将 FFmpeg 二进制打包进应用。

## 目标

在 CI 构建时将平台对应的 FFmpeg 静态二进制注入到 `libs/ffmpeg/` 目录，PyInstaller 通过 `add_data: libs:libs` 自动打包进应用。代码侧优先从 bundled 路径查找 FFmpeg。

## 改动

### 1. CI workflow (`.github/workflows/build.yml`)

在 `Build package` 步骤前新增一步：将系统安装的 ffmpeg/ffprobe 二进制复制到 `libs/ffmpeg/<platform>/<arch>/`。

- **macOS arm64**: `cp $(which ffmpeg) libs/ffmpeg/mac/arm64/`
- **Windows x64**: 从 choco 安装路径复制 ffmpeg.exe/ffprobe.exe
- **Linux x64/arm64**: `cp $(which ffmpeg) libs/ffmpeg/linux/<arch>/`

### 2. resource_finder (`src/utils/resource_finder.py`)

新增 `get_ffmpeg_path()` 和 `get_ffprobe_path()` 函数：
- 打包后：从 `get_app_root() / "libs/ffmpeg/<platform>/<arch>/"` 查找
- 开发时：fallback 到系统 PATH（`shutil.which("ffmpeg")`）

参照已有的 `opus_loader.py` 模式。

### 3. music_decoder (`src/audio_codecs/music_decoder.py`)

将硬编码的 `"ffmpeg"` / `"ffprobe"` 替换为 `get_ffmpeg_path()` / `get_ffprobe_path()` 返回的路径。

### 4. .gitignore

添加 `libs/ffmpeg/` 避免二进制意外提交到 git。

## Acceptance Criteria

- [ ] CI 构建时 FFmpeg 被复制到 libs/ffmpeg/ 并打包进应用
- [ ] 打包后的 app 从启动台启动能找到 FFmpeg
- [ ] 开发时从源码运行仍然使用系统 PATH 的 FFmpeg
- [ ] libs/ffmpeg/ 在 .gitignore 中
- [ ] 音乐播放功能在打包后正常工作
