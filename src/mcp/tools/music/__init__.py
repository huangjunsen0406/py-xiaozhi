"""音乐播放器工具包.

提供完整的音乐播放功能，包括搜索、播放、暂停、停止、跳转等操作。
"""

from .manager import MusicToolsManager, get_music_tools_manager
from .music_player import get_music_player_instance

__all__ = [
    "MusicToolsManager",
    "get_music_tools_manager",
    "get_music_player_instance",
]
