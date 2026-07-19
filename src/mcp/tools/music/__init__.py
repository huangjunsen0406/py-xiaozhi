"""音乐播放器工具包."""

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
