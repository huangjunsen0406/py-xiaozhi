"""通用媒体事件数据结构（供 MediaPlayer → UI / EventBus 使用）."""

from __future__ import annotations

from dataclasses import dataclass


def format_duration(seconds: float) -> str:
    """将秒数格式化为 mm:ss."""
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes:02d}:{secs:02d}"


@dataclass(frozen=True)
class MediaStateData:
    """媒体播放状态事件数据."""

    state: str  # "playing" | "paused" | "stopped" | "completed" | "error"
    title: str = ""
    position: float = 0.0
    duration: float = 0.0
    pause_source: str | None = None
    owner_id: str | None = None


@dataclass(frozen=True)
class MediaSubtitleData:
    """媒体副标题/歌词行展示事件数据."""

    text: str
    owner_id: str | None = None
