"""音量后端协议与工厂."""

from __future__ import annotations

from typing import Protocol


class VolumeBackend(Protocol):
    """平台音量实现."""

    def get_volume(self) -> int:
        """当前音量 0-100."""
        ...

    def set_volume(self, volume: int) -> None:
        """设置音量 0-100（调用方已 clamp）."""
        ...
