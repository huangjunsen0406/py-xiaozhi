"""音乐播放器事件数据类型定义.

用于 EventBus 事件通信的数据结构。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MusicStateData:
    """音乐状态变化事件数据.

    Attributes:
        state: 播放状态 ("playing", "paused", "stopped", "completed")
        song: 歌曲名称
        position: 当前播放位置（秒）
        duration: 总时长（秒）
        pause_source: 暂停来源 ("tts", "manual", "external", None)
    """

    state: str
    song: str
    position: float
    duration: float
    pause_source: Optional[str] = None


@dataclass
class MusicLyricsData:
    """歌词更新事件数据.

    Attributes:
        text: 歌词文本
        time_sec: 时间戳（秒）
        song_id: 歌曲 ID（可选）
    """

    text: str
    time_sec: float
    song_id: Optional[str] = None


@dataclass
class MusicControlRequest:
    """音乐控制请求数据.

    Attributes:
        source: 请求来源 ("tts", "manual", "external", etc.)
    """

    source: str = "external"
