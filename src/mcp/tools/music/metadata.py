"""本地音频文件元数据."""

from pathlib import Path

from src.logging import get_logger

logger = get_logger()

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False


class MusicMetadata:
    """一首缓存文件的标题/艺人等信息."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.filename = file_path.name
        self.file_id = file_path.stem
        self.file_size = file_path.stat().st_size

        self.title: str | None = None
        self.artist: str | None = None
        self.album: str | None = None
        self.duration: float | None = None

    def extract_metadata(self) -> bool:
        if not MUTAGEN_AVAILABLE:
            return False

        try:
            audio_file = MutagenFile(self.file_path)
            if audio_file is None:
                return False

            if hasattr(audio_file, "info"):
                self.duration = getattr(audio_file.info, "length", None)

            tags = audio_file.tags if audio_file.tags else {}
            self.title = self._get_tag_value(tags, ["TIT2", "TITLE", "\xa9nam"])
            self.artist = self._get_tag_value(tags, ["TPE1", "ARTIST", "\xa9ART"])
            self.album = self._get_tag_value(tags, ["TALB", "ALBUM", "\xa9alb"])
            return True

        except ID3NoHeaderError:
            return True
        except Exception as e:
            logger.debug(f"提取元数据失败 {self.filename}: {e}")
            return False

    def _get_tag_value(self, tags: dict, tag_names: list[str]) -> str | None:
        for tag_name in tag_names:
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, list) and value:
                    return str(value[0])
                if value:
                    return str(value)
        return None

    def format_duration(self) -> str:
        if self.duration is None:
            return "未知"
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def display_name(self) -> str:
        title = self.title or "未知标题"
        artist = self.artist or "未知艺术家"
        return f"{title} - {artist}"
