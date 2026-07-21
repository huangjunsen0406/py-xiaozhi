"""音乐相关工具.

- music_player: 播放会话
- cache / download / lyrics: 缓存、直链、歌词
- online_search / local_library / metadata: 搜歌与本地库
"""

from .music_player import (
    bind_music_player,
    get_music_player_instance,
    is_music_player_bound,
    reset_music_player_instance,
    unbind_music_player,
)

__all__ = [
    "bind_music_player",
    "get_music_player_instance",
    "is_music_player_bound",
    "reset_music_player_instance",
    "unbind_music_player",
]
