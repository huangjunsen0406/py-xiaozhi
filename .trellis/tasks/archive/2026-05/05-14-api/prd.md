# 音乐播放器 API 地址可配置化

## 目标

将 MusicPlayer 中硬编码的 TuneFree API 配置改为从 ConfigManager 读取，支持用户在 config.json 中自定义音乐 API 地址（如落雪音乐 API 公共实例），无需改代码即可切换音源。

## 背景

当前 `music_player.py` 中 API 地址（`https://music-dl.sayqz.com/api/`）、默认平台（`kuwo`）、默认音质（`320k`）全部硬编码。用户想使用其他兼容 API（如落雪音乐 lx-music-api-server 的公共实例）需要改源码。

TuneFree API 和落雪 API 使用几乎相同的查询参数格式（`?type=search/url/lrc/info&source=X&id=Y`），主要差异是 `type=url` 的返回方式：TuneFree 直接返回音频流，落雪部分实例返回 JSON `{"data":{"url":"..."}}`。

## 需求

### 必须实现

1. MusicPlayer 初始化时从 ConfigManager 读取以下配置项（带默认值回退）：
   - `MUSIC.API_URL` — API 地址，默认 `https://music-dl.sayqz.com/api/`
   - `MUSIC.DEFAULT_PLATFORM` — 默认音乐平台，默认 `kuwo`
   - `MUSIC.DEFAULT_QUALITY` — 默认音质，默认 `320k`
   - `MUSIC.URL_RESPONSE_TYPE` — URL 接口返回类型：`stream`（直接返回音频流）或 `json`（返回 JSON 需提取 URL），默认 `stream`

2. `_download_file` 方法支持两种模式：
   - `stream` 模式：当前行为，直接下载响应体
   - `json` 模式：先解析 JSON 提取 `data.url`，再下载该 URL

3. 设置界面（SystemOptionsTab.qml）添加音乐 API 配置项

### 不需要实现

- 不做音源抽象类/多实现拆分
- 不改 MCP 工具注册
- 不改播放/解码逻辑
- 不做 JS 脚本解析

## 改动文件

1. `src/mcp/tools/music/music_player.py` — 从 ConfigManager 读配置，`_download_file` 支持 json 模式
2. `src/ui/gui/qml/windows/settings/SystemOptionsTab.qml` — 添加音乐 API 配置 UI
3. `src/ui/shared/models/settings_model.py` — 添加音乐配置项的读写

## 配置示例

```json
{
  "MUSIC": {
    "API_URL": "http://someone-shared-lx-api.com:9763",
    "DEFAULT_PLATFORM": "kuwo",
    "DEFAULT_QUALITY": "320k",
    "URL_RESPONSE_TYPE": "json"
  }
}
```
