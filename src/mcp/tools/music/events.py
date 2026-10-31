"""音乐播放器事件数据类型定义.

用于 EventBus 事件通信的数据结构。
"""

from dataclasses import dataclass


@dataclass
class MusicStateData:
    """音乐状态变化事件数据.

    Attributes:
        state: 播放状态 ("playing", "paused", "stopped", "completed", "error")
        song: 歌曲名称
        position: 当前播放位置（秒）
        duration: 总时长（秒）
        pause_source: 暂停来源 ("tts", "manual", "external", None)
    """

    state: str
    song: str
    position: float
    duration: float
    pause_source: str | None = None


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
    song_id: str | None = None


@dataclass
class MusicControlRequest:
    """音乐控制请求数据.

    Attributes:
        source: 请求来源 ("tts", "manual", "external", etc.)
    """

    source: str = "external"


class MusicEventPublisher:
    """Publish complete event payloads without owning a player or engine."""

    def __init__(self):
        self.event_bus = None

    async def emit_state(self, data: MusicStateData) -> None:
        from src.core.event_bus import Events

        await self._emit(Events.MUSIC_STATE_CHANGED, data)

    async def emit_lyrics(self, data: MusicLyricsData) -> None:
        from src.core.event_bus import Events

        await self._emit(Events.MUSIC_LYRICS_UPDATE, data)

    async def _emit(self, event: str, data) -> None:
        if self.event_bus is None:
            return
        try:
            await self.event_bus.emit(event, data)
        except Exception as error:
            from src.logging import get_logger

            get_logger().debug("发送音乐事件失败: %s", error)
