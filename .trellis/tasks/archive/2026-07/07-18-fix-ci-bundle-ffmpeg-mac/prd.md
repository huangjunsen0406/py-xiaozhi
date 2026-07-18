# fix CI mac bundle_ffmpeg eval Downloading

## Goal
修复 v2.0.7 CI macOS job：`bundle_ffmpeg.sh` 在首次下载 static-ffmpeg 时因 stdout 进度行被 `eval` 执行而失败。

## Root cause
`eval "$(py_script ... get_or_fetch ... print export ...)"`  
CI 无缓存时 static_ffmpeg 向 **stdout** 打印 `Downloading ...`，混入 eval 文本 → bash 报 `Downloading: command not found` (exit 127)。

本地已缓存二进制时无下载输出，故通过。

## Requirements
- mac 分支：只 eval/解析 `export _SF_*` 行，或把路径写文件再读，进度走 stderr
- 本地与 CI 均可首次冷下载成功
- 不破坏 win/linux BtbN 路径

## Acceptance
- [ ] mac cold path 不再因 Downloading 失败
- [ ] 合并后可重新触发 v2.0.7 或 2.0.8 构建成功（至少 mac bundle 步骤绿）

## Out of Scope
- 换 mac 二进制来源（除非修复不够）
