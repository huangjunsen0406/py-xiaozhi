"""音乐工具包.

拆分（SRP / 方案 A）：
- cache: 本地缓存路径
- download: 直链下载
- lyrics: 歌词解析 + lyric_at 纯函数（无独立轮询 task）
- music_player: 编排门面 + 单一播放主循环
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
