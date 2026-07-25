"""音乐相关工具.

- music_player: 播放会话（由容器创建并注入 MCP；对外唯一入口）
- playback / bus: PlaybackEngine / MusicEventBridge（内部组合，勿当公开 API）
- cache / download / lyrics: 缓存、直链、歌词
- online_search / local_library / metadata: 搜歌与本地库
- register_music_tools: 向 McpServer 注册工具（闭包持有 player）
"""

from .register import register_music_tools
from .music_player import MusicPlayer

__all__ = [
    "MusicPlayer",
    "register_music_tools",
]
