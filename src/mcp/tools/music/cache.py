"""本地音乐缓存目录管理."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from src.logging import get_logger
from src.utils.resource_finder import get_music_cache_dir

logger = get_logger()


class MusicCache:
    """管理 music 缓存目录和临时文件."""

    def __init__(self, root: Path | None = None) -> None:
        base = root or get_music_cache_dir()
        self.root = base
        self.temp_dir = base / "temp"
        self._ready = False
        self._temp_cleaned = False

    def ensure(self) -> None:
        """创建缓存目录（幂等）."""
        if self._ready:
            return
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self._ready = True
            logger.debug(f"音乐缓存目录就绪: {self.root}")
        except Exception as e:
            logger.error(f"创建缓存目录失败: {e}", exc_info=True)
            self.root = Path(tempfile.gettempdir()) / "xiaozhi_music_cache"
            self.temp_dir = self.root / "temp"
            self.root.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            self._ready = True

    def prepare(self) -> None:
        """首次用缓存前调用：建目录，并清理一次 temp."""
        self.ensure()
        if not self._temp_cleaned:
            self.clean_temp()
            self._temp_cleaned = True

    def path_for_song(self, song_id: str, ext: str = ".mp3") -> Path:
        """根据 song_id 生成缓存文件路径."""
        self.ensure()
        if not ext.startswith("."):
            ext = f".{ext}"
        return self.root / f"{song_id}{ext}"

    def find_song_file(self, song_id: str) -> Path | None:
        """按 song_id 找已缓存的文件（试常见后缀）."""
        self.ensure()
        for ext in (".mp3", ".m4a", ".flac", ".wav", ".ogg"):
            p = self.root / f"{song_id}{ext}"
            if p.exists():
                return p
        return None

    def has(self, song_id: str, ext: str = ".mp3") -> bool:
        return self.path_for_song(song_id, ext).exists()

    def temp_path(self, filename: str) -> Path:
        """下载过程中用的临时文件路径."""
        self.ensure()
        return self.temp_dir / f"temp_{int(time.time())}_{filename}"

    def list_music_files(self) -> list[Path]:
        """列出缓存里的音乐文件."""
        self.ensure()
        if not self.root.exists():
            return []
        files: list[Path] = []
        for pattern in ("*.mp3", "*.m4a", "*.flac", "*.wav", "*.ogg"):
            files.extend(self.root.glob(pattern))
        return files

    def clean_temp(self) -> None:
        """清空 temp 目录."""
        try:
            if not self.temp_dir.exists():
                return
            for file_path in self.temp_dir.glob("*"):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"已删除临时缓存文件: {file_path.name}")
                except Exception as e:
                    logger.warning(
                        f"删除临时缓存文件失败: {file_path.name}, {e}",
                        exc_info=True,
                    )
            logger.debug("临时音乐缓存清理完成")
        except Exception as e:
            logger.error(f"清理临时缓存目录失败: {e}", exc_info=True)
