# CI/CD 多平台自动打包 Workflow

## 背景

项目目前只有 release-drafter（生成 changelog）和 VitePress 文档部署，没有自动打包。每次发版都要手动在各平台打包，效率低。需要一个 GitHub Actions workflow，在 push tag 时自动构建多平台安装包并上传到 Release。

## 目标

创建 `.github/workflows/build.yml`，在 tag push (`v*.*.*`) 时自动：
1. 在 5 个平台/架构组合上并行构建
2. 使用 `uv` 管理依赖 + `unifypy` 打包
3. 将产物上传到对应的 GitHub Release

## 构建矩阵

| 平台 | Runner | 架构 | 产物格式 |
|------|--------|------|----------|
| macOS arm64 | `macos-latest` | arm64 | `.dmg` |
| macOS x86_64 | `macos-13` | x64 | `.dmg` |
| Windows x64 | `windows-latest` | x64 | `.exe` (Inno Setup) |
| Linux x64 | `ubuntu-24.04` | x64 | `.deb` |
| Linux arm64 | `ubuntu-24.04-arm` | arm64 | `.deb` |

## 每个 job 的步骤

1. Checkout 代码
2. 安装 uv
3. `uv sync --extra gui --dev` 安装依赖（含 PySide6 + PyInstaller）
4. 安装系统依赖（brew/apt/choco）
5. 安装 unifypy（`uv pip install unifypy`）
6. 运行 `uv run unifypy . --config build.json --verbose`
7. 上传产物到 GitHub Release

## 系统依赖

- **macOS**: `brew install portaudio opus ffmpeg`
- **Linux**: `sudo apt install portaudio19-dev libportaudio2 ffmpeg libopus0 libopus-dev libasound-dev libxcb-xinerama0 libxkbcommon-x11-0 libegl1 build-essential`
- **Windows**: `choco install ffmpeg innosetup` 或用 scoop

## 约束

- 触发条件: push tag `v*.*.*`
- 环境工具: uv（不用 pip/conda）
- 与现有 `release.yml` 协同：release.yml 创建 Release，build.yml 上传产物
- macOS 签名: adhoc（暂无 Developer ID）
- Linux arm64 的 PySide6 需要 glibc 2.39（Ubuntu 24.04+）

## Acceptance Criteria

- [x] workflow 文件语法正确（可通过 actionlint 检查）
- [x] 5 个平台矩阵定义完整
- [x] 使用 uv 安装所有依赖
- [x] 各平台系统依赖正确安装
- [x] unifypy 打包命令正确
- [x] 产物上传到 GitHub Release
- [x] 与现有 release.yml 不冲突
