# 示例媒体播放外挂插件 (`demo_media_plugin`)

演示如何编写一个与宿主音频层彻底解耦的外挂 MCP 插件：

- 通过 `host.get("media_player")` 获取受控的 `MediaPlayerFacade`，直接享有宿主 AEC 回声消除、TTS 闪避/自动暂停与音频设备热切换；
- 通过 `host.get("data_dir")` 获取插件专属隔离数据目录（保存播放历史、缓存、登录态等，不污染代码目录）；
- `manifest.json` 中的 `runtime` 可在 `"python-subprocess"` 与 `"python-inprocess"` 之间自由切换，插件代码无需修改。

## 使用方法

1. 将本目录打包为 ZIP（或直接选择本文件夹）；
2. 打开 `py-xiaozhi` → **参数设置 → MCP 工具** → 点击「导入 ZIP」或「导入文件夹」；
3. 开启「**允许外挂使用应用内播放**」开关并保存，即可通过对话调用 `demo_media.play_url` 播放音频，并使用宿主的 `media.pause` / `media.stop` / `media.seek` 控制播放。
