"""Immutable inputs and observations of a music playback session."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlaybackRequest:
    song: str
    song_id: str
    source: str | Path
    duration: float = 0.0
    lyrics: tuple[tuple[float, str], ...] = ()
    resolve_url: bool = False


@dataclass(frozen=True)
class PlaybackState:
    song: str
    song_id: str
    source: str
    duration: float
    is_playing: bool
    paused: bool
    pause_source: str | None
    position: float
    error: str | None
    lyrics: tuple[tuple[float, str], ...]
