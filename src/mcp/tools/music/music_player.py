"""音乐播放器 (重构版).

使用 FFmpeg 解码 + AudioCodec 播放的架构。
"""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

import numpy as np
import requests

from src.audio_codecs.music_decoder import MusicDecoder
from src.constants.constants import AudioConfig
from src.logging import get_logger
from src.utils.resource_finder import get_user_cache_dir

if TYPE_CHECKING:
    from src.audio_codecs.audio_codec import AudioCodec

try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

logger = get_logger()


class MusicMetadata:
    """音乐元数据类"""

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
        """提取音乐文件元数据"""
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
        """从多个可能的标签名中获取值"""
        for tag_name in tag_names:
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, list) and value:
                    return str(value[0])
                elif value:
                    return str(value)
        return None

    def format_duration(self) -> str:
        """格式化播放时长"""
        if self.duration is None:
            return "未知"
        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"


class MusicPlayer:
    def __init__(
        self,
        audio_codec: "AudioCodec | None" = None,
    ):
        self._audio_codec = audio_codec
        self._event_bus = None
        self._plugin_ctx = None

        self.decoder: MusicDecoder | None = None
        self._music_queue = asyncio.Queue(maxsize=100)
        self._playback_task: asyncio.Task | None = None

        self.current_song = ""
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0
        self.is_playing = False
        self.paused = False
        self.current_position = 0
        self.start_play_time = 0
        self._pause_source: str | None = None
        self._current_file_path: Path | None = None

        self.lyrics: list[tuple[float, str]] = []
        self.current_lyric_index = -1

        user_cache_dir = get_user_cache_dir()
        self.cache_dir = user_cache_dir / "music"
        self.temp_cache_dir = self.cache_dir / "temp"
        self._init_cache_dirs()

        self.config = self._load_config()

        self._clean_temp_cache()

        self._local_playlist: list[MusicMetadata] | None = None
        self._last_scan_time = 0

        logger.info(
            f"音乐播放器初始化完成 (FFmpeg + AudioCodec 模式, "
            f"搜索: {self.config['SEARCH_URL']}, 直链: {self.config['URL_API']})"
        )
        logger.info(
            f"默认平台: {self.config['DEFAULT_SOURCE']}, "
            f"音质: {self.config['DEFAULT_BR']}"
        )

    @staticmethod
    def _load_config() -> dict:
        """从 ConfigManager 读取音乐配置，未配置时使用默认值."""
        from src.utils.config_manager import ConfigManager

        cm = ConfigManager.get_instance()

        return {
            "SEARCH_URL": cm.get_config(
                "MUSIC.SEARCH_URL", "http://search.kuwo.cn/r.s"
            ),
            "URL_API": cm.get_config(
                "MUSIC.URL_API", "https://lxmusicapi.onrender.com"
            ),
            "URL_API_KEY": cm.get_config("MUSIC.URL_API_KEY", "share-v3"),
            "LYRICS_URL": cm.get_config(
                "MUSIC.LYRICS_URL",
                "http://m.kuwo.cn/newh5/singles/songinfoandlrc",
            ),
            "DEFAULT_SOURCE": cm.get_config("MUSIC.DEFAULT_PLATFORM", "kw"),
            "DEFAULT_BR": cm.get_config("MUSIC.DEFAULT_QUALITY", "320k"),
            "SEARCH_LIMIT": 20,
            "HEADERS": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            },
        }

    def set_audio_codec(self, audio_codec: "AudioCodec | None") -> None:
        self._audio_codec = audio_codec
        if audio_codec:
            logger.info("AudioCodec 已设置到 MusicPlayer")

    def set_event_bus(self, event_bus, plugin_ctx=None) -> None:
        """设置事件总线并订阅控制事件.

        Args:
            event_bus: EventBus 实例
            plugin_ctx: PluginContextAdapter 实例（可选，用于检查设备状态）
        """
        from src.core.event_bus import Events

        self._event_bus = event_bus
        self._plugin_ctx = plugin_ctx
        if event_bus:
            event_bus.on(Events.MUSIC_PAUSE_REQUEST, self._on_pause_request)
            event_bus.on(Events.MUSIC_RESUME_REQUEST, self._on_resume_request)
            logger.info("MusicPlayer 已连接到 EventBus")

    def _get_audio_codec(self) -> "AudioCodec | None":
        if self._audio_codec is None:
            logger.warning("AudioCodec 未设置，音乐播放功能不可用")
        return self._audio_codec

    async def _clear_music_queue(self) -> int:
        count = 0
        while not self._music_queue.empty():
            try:
                self._music_queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        return count

    def _init_cache_dirs(self):
        """初始化缓存目录"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.temp_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"音乐缓存目录初始化完成: {self.cache_dir}")
        except Exception as e:
            logger.error(f"创建缓存目录失败: {e}")
            self.cache_dir = Path(tempfile.gettempdir()) / "xiaozhi_music_cache"
            self.temp_cache_dir = self.cache_dir / "temp"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.temp_cache_dir.mkdir(parents=True, exist_ok=True)

    def _clean_temp_cache(self):
        """清理临时缓存文件"""
        try:
            for file_path in self.temp_cache_dir.glob("*"):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                        logger.debug(f"已删除临时缓存文件: {file_path.name}")
                except Exception as e:
                    logger.warning(f"删除临时缓存文件失败: {file_path.name}, {e}")
            logger.info("临时音乐缓存清理完成")
        except Exception as e:
            logger.error(f"清理临时缓存目录失败: {e}")

    def _scan_local_music(self, force_refresh: bool = False) -> list[MusicMetadata]:
        """扫描本地音乐缓存"""
        current_time = time.time()

        if (
            not force_refresh
            and self._local_playlist is not None
            and (current_time - self._last_scan_time) < 300
        ):
            return self._local_playlist

        playlist = []
        if not self.cache_dir.exists():
            logger.warning(f"缓存目录不存在: {self.cache_dir}")
            return playlist

        music_files = []
        for pattern in ["*.mp3", "*.m4a", "*.flac", "*.wav", "*.ogg"]:
            music_files.extend(self.cache_dir.glob(pattern))

        logger.debug(f"找到 {len(music_files)} 个音乐文件")

        for file_path in music_files:
            try:
                metadata = MusicMetadata(file_path)
                if MUTAGEN_AVAILABLE:
                    metadata.extract_metadata()
                playlist.append(metadata)
            except Exception as e:
                logger.debug(f"处理音乐文件失败 {file_path.name}: {e}")

        playlist.sort(key=lambda x: (x.artist or "Unknown", x.title or x.filename))
        self._local_playlist = playlist
        self._last_scan_time = current_time

        logger.info(f"扫描完成，找到 {len(playlist)} 首本地音乐")
        return playlist

    # ==================== 公共 API ====================

    async def get_local_playlist(self, force_refresh: bool = False) -> dict:
        """获取本地音乐歌单"""
        try:
            playlist = self._scan_local_music(force_refresh)

            if not playlist:
                return {
                    "status": "info",
                    "message": "本地缓存中没有音乐文件",
                    "playlist": [],
                    "total_count": 0,
                }

            formatted_playlist = []
            for metadata in playlist:
                title = metadata.title or "未知标题"
                artist = metadata.artist or "未知艺术家"
                song_info = f"{title} - {artist}"
                formatted_playlist.append(song_info)

            return {
                "status": "success",
                "message": f"找到 {len(playlist)} 首本地音乐",
                "playlist": formatted_playlist,
                "total_count": len(playlist),
            }

        except Exception as e:
            logger.error(f"获取本地歌单失败: {e}")
            return {
                "status": "error",
                "message": f"获取本地歌单失败: {str(e)}",
                "playlist": [],
                "total_count": 0,
            }

    async def search_local_music(self, query: str) -> dict:
        """搜索本地音乐"""
        try:
            playlist = self._scan_local_music()

            if not playlist:
                return {
                    "status": "info",
                    "message": "本地缓存中没有音乐文件",
                    "results": [],
                    "found_count": 0,
                }

            query = query.lower()
            results = []

            for metadata in playlist:
                searchable_text = " ".join(
                    filter(
                        None,
                        [
                            metadata.title,
                            metadata.artist,
                            metadata.album,
                            metadata.filename,
                        ],
                    )
                ).lower()

                if query in searchable_text:
                    title = metadata.title or "未知标题"
                    artist = metadata.artist or "未知艺术家"
                    song_info = f"{title} - {artist}"
                    results.append(
                        {
                            "song_info": song_info,
                            "file_id": metadata.file_id,
                            "duration": metadata.format_duration(),
                        }
                    )

            return {
                "status": "success",
                "message": f"在本地音乐中找到 {len(results)} 首匹配的歌曲",
                "results": results,
                "found_count": len(results),
            }

        except Exception as e:
            logger.error(f"搜索本地音乐失败: {e}")
            return {
                "status": "error",
                "message": f"搜索失败: {str(e)}",
                "results": [],
                "found_count": 0,
            }

    async def play_local_song_by_id(self, file_id: str) -> dict:
        """根据文件ID播放本地歌曲"""
        try:
            file_path = self.cache_dir / f"{file_id}.mp3"

            if not file_path.exists():
                for ext in [".m4a", ".flac", ".wav", ".ogg"]:
                    alt_path = self.cache_dir / f"{file_id}{ext}"
                    if alt_path.exists():
                        file_path = alt_path
                        break
                else:
                    return {"status": "error", "message": f"本地文件不存在: {file_id}"}

            metadata = MusicMetadata(file_path)
            if MUTAGEN_AVAILABLE:
                metadata.extract_metadata()

            title = metadata.title or "未知标题"
            artist = metadata.artist or "未知艺术家"
            self.current_song = f"{title} - {artist}"
            self.song_id = file_id
            self.total_duration = metadata.duration or 0
            self.current_url = str(file_path)
            self.lyrics = []

            # 总是使用 ffprobe 获取准确的音频时长
            duration = await MusicDecoder.get_duration(file_path)
            if duration > 0:
                self.total_duration = duration
                logger.info(f"从音频文件获取准确时长: {duration:.2f}秒")
            elif self.total_duration == 0:
                logger.warning("无法获取音频时长")

            success = await self._start_playback(file_path)

            if success:
                duration_str = self._format_time(self.total_duration)
                return {
                    "status": "success",
                    "message": f"正在播放: {self.current_song}",
                    "song": self.current_song,
                    "duration": duration_str,
                    "total_seconds": self.total_duration,
                }
            else:
                return {"status": "error", "message": "播放失败"}

        except Exception as e:
            logger.error(f"播放本地音乐失败: {e}")
            return {"status": "error", "message": f"播放失败: {str(e)}"}

    async def search_and_play(self, song_name: str) -> dict:
        """搜索并播放歌曲"""
        try:
            song_id, url = await self._search_song(song_name)
            if not song_id or not url:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}

            success = await self._play_url(url)
            if success:
                duration_str = self._format_time(self.total_duration)
                return {
                    "status": "success",
                    "message": f"正在播放: {self.current_song}",
                    "song": self.current_song,
                    "duration": duration_str,
                    "total_seconds": self.total_duration,
                }
            else:
                return {"status": "error", "message": "播放失败"}

        except Exception as e:
            logger.error(f"搜索播放失败: {e}")
            return {"status": "error", "message": f"操作失败: {str(e)}"}

    async def stop(self) -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            current_song = self.current_song

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            if self._playback_task and not self._playback_task.done():
                self._playback_task.cancel()
                try:
                    await self._playback_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self._playback_task = None

            cleared = await self._clear_music_queue()
            logger.debug(f"停止时清空 {cleared} 帧音乐数据")

            self.is_playing = False
            self.paused = False
            self._pause_source = None
            self.current_position = 0

            await self._emit_state_change("stopped", current_song)
            logger.info(f"停止播放: {current_song}")
            return {"status": "success", "message": "已停止"}

        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return {"status": "error", "message": f"停止失败: {str(e)}"}

    async def pause(self, source: str = "manual") -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if self.paused:
                if self._pause_source != source:
                    old_source = self._pause_source
                    self._pause_source = source
                    logger.info(f"更新暂停来源: {old_source} → {source}")
                return {"status": "info", "message": "已经处于暂停状态"}

            self.paused = True
            self._pause_source = source

            if self.start_play_time > 0:
                self.current_position = time.time() - self.start_play_time

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            cleared = await self._clear_music_queue()

            logger.info(
                f"暂停播放: {self.current_song} at {self._format_time(self.current_position)}, "
                f"来源: {source}, 清空 {cleared} 帧音乐队列"
            )

            return {"status": "success", "message": "已暂停"}

        except Exception as e:
            logger.error(f"暂停播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"暂停失败: {str(e)}"}

    async def resume(self) -> dict:
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if not self.paused:
                return {"status": "info", "message": "当前未暂停"}

            if not self._current_file_path or not self._current_file_path.exists():
                return {"status": "error", "message": "无法找到音频文件"}

            logger.info(
                f"恢复播放: {self.current_song} from {self._format_time(self.current_position)}"
            )

            cleared = await self._clear_music_queue()
            if cleared > 0:
                logger.debug(f"恢复前清空 {cleared} 帧残留数据")

            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )

            success = await self.decoder.start_decode(
                self._current_file_path, self._music_queue, self.current_position
            )
            if not success:
                logger.error("重启解码器失败")
                return {"status": "error", "message": "恢复播放失败"}

            if self._playback_task and not self._playback_task.done():
                self._playback_task.cancel()
                try:
                    await self._playback_task
                except asyncio.CancelledError:
                    pass

            self._playback_task = asyncio.create_task(self._playback_loop())

            self.paused = False
            self._pause_source = None
            self.start_play_time = time.time() - self.current_position

            await self._emit_state_change("playing", self.current_song)
            return {"status": "success", "message": "已恢复播放"}

        except Exception as e:
            logger.error(f"恢复播放失败: {e}")
            return {"status": "error", "message": f"恢复失败: {str(e)}"}

    async def seek(self, position: float) -> dict:
        try:
            if not self.is_playing:
                return {"status": "error", "message": "没有正在播放的歌曲"}

            if not self._current_file_path or not self._current_file_path.exists():
                return {"status": "error", "message": "无法找到音频文件"}

            if position < 0:
                position = 0
            elif position >= self.total_duration:
                position = max(0, self.total_duration - 1)

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            await asyncio.sleep(0.05)

            cleared = await self._clear_music_queue()

            audio_codec = self._get_audio_codec()
            if audio_codec:
                await audio_codec.clear_audio_queue()

            logger.info(
                f"跳转到 {self._format_time(position)}，清空 {cleared} 帧音乐数据"
            )

            success = await self._start_playback(self._current_file_path, position)

            if success:
                return {
                    "status": "success",
                    "message": f"已跳转到 {self._format_time(position)}",
                }
            else:
                return {"status": "error", "message": "跳转失败"}

        except Exception as e:
            logger.error(f"跳转失败: {e}", exc_info=True)
            return {"status": "error", "message": f"跳转失败: {str(e)}"}

    async def get_lyrics(self) -> dict:
        """获取当前歌曲歌词"""
        if not self.lyrics:
            return {"status": "info", "message": "当前歌曲没有歌词", "lyrics": []}

        lyrics_text = []
        for time_sec, text in self.lyrics:
            time_str = self._format_time(time_sec)
            lyrics_text.append(f"[{time_str}] {text}")

        return {
            "status": "success",
            "message": f"获取到 {len(self.lyrics)} 行歌词",
            "lyrics": lyrics_text,
        }

    async def get_status(self) -> dict:
        """获取播放器状态"""
        position = await self.get_position()
        progress = await self.get_progress()

        if not self.is_playing:
            playing_state = "未播放"
        elif self.paused and self._pause_source == "manual":
            playing_state = "已暂停"
        elif self.is_playing:
            playing_state = "播放中"
        else:
            playing_state = "未知"

        duration_str = self._format_time(self.total_duration)
        position_str = self._format_time(position)

        return {
            "status": "success",
            "message": (
                f"当前歌曲: {self.current_song}\n"
                f"播放状态: {playing_state}\n"
                f"暂停来源: {self._pause_source or '无'} (tts=说话时临时暂停)\n"
                f"播放时长: {duration_str}\n"
                f"当前位置: {position_str}\n"
                f"播放进度: {progress}%\n"
                f"歌词可用: {'是' if len(self.lyrics) > 0 else '否'}"
            ),
        }

    async def get_position(self):
        """获取当前播放位置"""
        if not self.is_playing or self.paused:
            return self.current_position

        current_pos = min(self.total_duration, time.time() - self.start_play_time)

        if current_pos >= self.total_duration and self.total_duration > 0:
            await self._handle_playback_finished()

        return current_pos

    async def get_progress(self):
        """获取播放进度百分比"""
        if self.total_duration <= 0:
            return 0
        position = await self.get_position()
        return round(position * 100 / self.total_duration, 1)

    # ==================== 内部方法 ====================

    async def _search_song(
        self, song_name: str, source: str | None = None
    ) -> tuple[str, str]:
        """搜索歌曲获取 ID 和播放 URL.

        Args:
            song_name: 歌曲名称
            source: 音乐平台，默认使用配置中的平台

        Returns:
            (song_id, play_url) 元组
        """
        try:
            keyword_encoded = quote(song_name)
            limit = self.config["SEARCH_LIMIT"]

            search_url = (
                f"{self.config['SEARCH_URL']}"
                f"?client=kt&all={keyword_encoded}&pn=0&rn={limit}"
                f"&uid=794762570&ver=kwplayer_ar_9.2.2.1&vipver=1"
                f"&show_copyright_off=1&newver=1&ft=music&cluster=0"
                f"&strategy=2012&encoding=utf8&rformat=json&vermerge=1"
                f"&mobi=1&issubtitle=1"
            )

            logger.info(f"搜索歌曲: {song_name}")

            response = None
            for attempt in range(3):
                try:
                    response = await asyncio.to_thread(
                        requests.get,
                        search_url,
                        headers=self.config["HEADERS"],
                        timeout=10,
                    )
                    response.raise_for_status()
                    break
                except requests.exceptions.Timeout:
                    if attempt < 2:
                        logger.warning(f"搜索超时，重试 ({attempt + 1}/2)")
                        continue
                    logger.error(f"搜索歌曲超时，已重试 2 次: {song_name}")
                    return "", ""

            data = response.json()

            results = data.get("abslist", [])
            if not results:
                logger.warning(f"未找到歌曲: {song_name}")
                return "", ""

            first_result = results[0]
            music_rid = first_result.get("MUSICRID", "")
            song_id = music_rid.replace("MUSIC_", "") if music_rid else ""
            title = first_result.get("SONGNAME", song_name)
            artist = first_result.get("ARTIST", "")
            album = first_result.get("ALBUM", "")

            if not song_id:
                logger.error("搜索结果中没有歌曲ID")
                return "", ""

            display_name = title
            if artist:
                display_name = f"{title} - {artist}"
                if album:
                    display_name += f" ({album})"

            self.current_song = display_name
            self.song_id = song_id

            duration_str = first_result.get("DURATION", "")
            if duration_str:
                try:
                    self.total_duration = int(duration_str)
                except (ValueError, TypeError):
                    pass

            quality = self.config["DEFAULT_BR"]
            play_url = f"{self.config['URL_API']}/url/kw/{song_id}/{quality}"

            logger.info(f"找到歌曲: {display_name}, ID: {song_id}")

            await self._fetch_lyrics(song_id)

            return song_id, play_url

        except Exception as e:
            logger.error(f"搜索歌曲失败: {e}", exc_info=True)
            return "", ""

    async def _play_url(self, url: str) -> bool:
        """播放指定URL"""
        try:
            audio_codec = self._get_audio_codec()
            if not audio_codec:
                logger.error("无法获取 AudioCodec，播放失败")
                return False

            if self.is_playing:
                await self.stop()

            file_path = await self._get_or_download_file(url)
            if not file_path:
                return False

            # 总是使用 ffprobe 获取准确的音频时长（覆盖歌词推断的时长）
            duration = await MusicDecoder.get_duration(file_path)
            if duration > 0:
                self.total_duration = duration
                logger.info(f"从音频文件获取准确时长: {duration:.2f}秒")
            elif self.total_duration == 0:
                logger.warning("无法获取音频时长，将使用歌词时长或0")

            return await self._start_playback(file_path)

        except Exception as e:
            logger.error(f"播放失败: {e}")
            return False

    async def _start_playback(
        self, file_path: Path, start_position: float = 0.0
    ) -> bool:
        try:
            self._current_file_path = file_path

            cleared = await self._clear_music_queue()
            if cleared > 0:
                logger.debug(f"开始播放前清空 {cleared} 帧音乐数据")

            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                channels=AudioConfig.CHANNELS,
            )

            success = await self.decoder.start_decode(
                file_path, self._music_queue, start_position
            )
            if not success:
                logger.error("启动音频解码器失败")
                return False

            self._playback_task = asyncio.create_task(self._playback_loop())

            self.is_playing = True
            self.paused = False
            self.current_position = start_position
            self.start_play_time = time.time() - start_position
            self.current_lyric_index = -1

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(f"开始播放: {self.current_song}{position_info}")

            # 如果当前设备正在说话（TTS），立即暂停音乐等 TTS 结束
            if self._plugin_ctx and self._plugin_ctx.is_speaking():
                logger.info("检测到 TTS 正在播放，音乐自动暂停等待")
                await self.pause(source="tts")
            else:
                await self._emit_state_change(
                    "playing", self.current_song, start_position
                )

            asyncio.create_task(self._lyrics_update_task())

            return True

        except Exception as e:
            logger.error(f"启动播放失败: {e}")
            return False

    async def _playback_loop(self):
        """播放循环：从队列取PCM，写入AudioCodec"""
        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    audio_data = await asyncio.wait_for(
                        self._music_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("音乐队列读取超时")
                    continue

                if audio_data is None:
                    logger.info("音乐播放完成")
                    await self._handle_playback_finished()
                    break

                await self._write_to_audio_codec(audio_data)

        except asyncio.CancelledError:
            logger.debug("播放循环被取消")
        except Exception as e:
            logger.error(f"播放循环异常: {e}", exc_info=True)

    async def _write_to_audio_codec(self, pcm_data: np.ndarray):
        """将 PCM 数据写入 AudioCodec（全程 float32）"""
        try:
            audio_codec = self._get_audio_codec()
            if not audio_codec:
                logger.error("无法获取 AudioCodec")
                return

            # MusicDecoder 已输出 float32，直接使用
            # 如果是多声道，取平均转单声道
            if pcm_data.ndim > 1:
                pcm_data = pcm_data.mean(axis=1, dtype=np.float32)

            # 确保是 float32
            if pcm_data.dtype != np.float32:
                logger.warning(f"数据类型不匹配: {pcm_data.dtype}，转换为 float32")
                pcm_data = pcm_data.astype(np.float32)

            await audio_codec.write_pcm_direct(pcm_data)

        except Exception as e:
            logger.error(f"写入 AudioCodec 失败: {e}", exc_info=True)

    async def _get_or_download_file(self, url: str) -> Path | None:
        """获取或下载文件"""
        try:
            cache_filename = f"{self.song_id}.mp3"
            cache_path = self.cache_dir / cache_filename

            if cache_path.exists():
                logger.info(f"使用缓存: {cache_path}")
                return cache_path

            return await self._download_file(url, cache_filename)

        except Exception as e:
            logger.error(f"获取文件失败: {e}")
            return None

    async def _resolve_download_url(self, api_url: str) -> str | None:
        """请求直链 API 解析实际音频下载地址."""
        try:
            headers = {
                "X-Request-Key": self.config["URL_API_KEY"],
                "User-Agent": "lx-music-request",
            }

            response = await asyncio.to_thread(
                requests.get,
                api_url,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            real_url = None
            if isinstance(data, dict):
                real_url = data.get("url")
                if not real_url:
                    inner = data.get("data")
                    if isinstance(inner, dict):
                        real_url = inner.get("url")
                    elif isinstance(inner, str):
                        real_url = inner

            if not real_url:
                logger.error(f"未能从直链 API 提取播放 URL: {data}")
                return None

            logger.info(f"解析到播放地址: {real_url[:80]}...")
            return real_url

        except Exception as e:
            logger.error(f"解析播放 URL 失败: {e}")
            return None

    def _sync_download_file(
        self, download_url: str, headers: dict, temp_path: Path, cache_path: Path
    ) -> Path:
        """同步下载文件并移入缓存（在线程中执行，避免阻塞事件循环）"""
        response = requests.get(download_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        shutil.move(str(temp_path), str(cache_path))
        return cache_path

    async def _download_file(self, url: str, filename: str) -> Path | None:
        """下载文件到缓存目录"""
        temp_path = None
        try:
            download_url = await self._resolve_download_url(url)
            if not download_url:
                return None

            temp_path = self.temp_cache_dir / f"temp_{int(time.time())}_{filename}"
            cache_path = self.cache_dir / filename

            result = await asyncio.to_thread(
                self._sync_download_file,
                download_url,
                self.config["HEADERS"],
                temp_path,
                cache_path,
            )

            logger.info(f"音乐下载完成并缓存: {result}")
            return result

        except Exception as e:
            logger.error(f"下载失败: {e}")
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"已清理临时下载文件: {temp_path}")
                except Exception as e:
                    logger.debug(f"清理临时文件失败: {e}")
            return None

    async def _fetch_lyrics(self, song_id: str):
        """获取歌词.

        Args:
            song_id: 歌曲 ID (酷我数字 ID)
        """
        try:
            self.lyrics = []

            lyrics_url = self.config["LYRICS_URL"]
            params = {"musicId": song_id}

            logger.info(f"获取歌词: ID={song_id}")

            response = await asyncio.to_thread(
                requests.get,
                lyrics_url,
                params=params,
                headers=self.config["HEADERS"],
                timeout=10,
            )
            response.raise_for_status()

            data = response.json()

            if data.get("status") != 200:
                logger.info("该歌曲暂无歌词")
                return

            lrc_list = data.get("data", {}).get("lrclist", [])
            if not lrc_list:
                logger.warning("未获取到歌词数据")
                return

            filtered_count = 0
            _METADATA_PREFIXES = (
                "作词",
                "作曲",
                "编曲",
                "制作",
                "演唱",
                "原唱",
                "翻唱",
            )

            for item in lrc_list:
                time_str = item.get("time", "")
                text = item.get("lineLyric", "").strip()

                if not text or not time_str:
                    continue

                try:
                    time_sec = float(time_str)
                except (ValueError, TypeError):
                    continue

                if text.startswith(_METADATA_PREFIXES):
                    filtered_count += 1
                    continue

                self.lyrics.append((time_sec, text))

            if self.total_duration == 0 and self.lyrics:
                last_time, _ = self.lyrics[-1]
                self.total_duration = last_time + 5.0
                logger.info(f"从歌词提取歌曲时长: {self.total_duration}秒")

            logger.info(
                f"成功获取歌词，共 {len(self.lyrics)} 行"
                f"（过滤 {filtered_count} 行元数据）"
            )

        except Exception as e:
            logger.error(f"获取歌词失败: {e}", exc_info=True)

    async def _handle_playback_finished(self):
        """处理播放完成"""
        if self.is_playing:
            logger.info(f"歌曲播放完成: {self.current_song}")

            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            self.is_playing = False
            self.paused = False
            self.current_position = self.total_duration

            await self._emit_state_change("completed", self.current_song)

    async def _lyrics_update_task(self):
        """歌词更新任务"""
        logger.info(f"歌词更新任务启动，歌词数量: {len(self.lyrics)}")

        if not self.lyrics:
            logger.warning("没有歌词数据，歌词更新任务退出")
            return

        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.5)
                    continue

                current_time = time.time() - self.start_play_time

                # 只有当时长有效时才检查播放完成（避免时长为0时立即完成）
                if self.total_duration > 0 and current_time >= self.total_duration:
                    await self._handle_playback_finished()
                    break

                current_index = self._find_current_lyric_index(current_time)

                if current_index != self.current_lyric_index:
                    await self._display_current_lyric(current_index)

                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"歌词更新任务异常: {e}")

    def _find_current_lyric_index(self, current_time: float) -> int:
        """查找当前时间对应的歌词索引"""
        next_lyric_index = None
        for i, (time_sec, _) in enumerate(self.lyrics):
            if time_sec > current_time - 0.5:
                next_lyric_index = i
                break

        if next_lyric_index is not None and next_lyric_index > 0:
            return next_lyric_index - 1
        elif next_lyric_index is None and self.lyrics:
            return len(self.lyrics) - 1
        else:
            return 0

    async def _display_current_lyric(self, current_index: int):
        """显示当前歌词"""
        self.current_lyric_index = current_index

        if current_index < len(self.lyrics):
            time_sec, text = self.lyrics[current_index]

            position_str = self._format_time(time.time() - self.start_play_time)
            duration_str = self._format_time(self.total_duration)
            display_text = f"[{position_str}/{duration_str}] {text}"

            await self._emit_lyrics_update(display_text, time_sec)
            logger.debug(f"显示歌词: {text}")

    def _format_time(self, seconds: float) -> str:
        """将秒数格式化为 mm:ss 格式"""
        minutes = int(seconds) // 60
        seconds = int(seconds) % 60
        return f"{minutes:02d}:{seconds:02d}"

    async def _emit_state_change(
        self, state: str, song_name: str = None, position: float = None
    ):
        """发送播放状态变化事件.

        Args:
            state: 播放状态 ("playing", "paused", "stopped", "completed")
            song_name: 歌曲名称
            position: 播放位置（可选）
        """
        if not self._event_bus:
            return

        try:
            from src.core.event_bus import Events

            from .events import MusicStateData

            data = MusicStateData(
                state=state,
                song=song_name or self.current_song,
                position=position if position is not None else self.current_position,
                duration=self.total_duration,
                pause_source=self._pause_source if state == "paused" else None,
            )
            await self._event_bus.emit(Events.MUSIC_STATE_CHANGED, data)
            logger.debug(f"发送音乐状态变化事件: {state}")
        except Exception as e:
            logger.debug(f"发送状态事件失败: {e}")

    async def _emit_lyrics_update(self, lyrics_text: str, time_sec: float = 0):
        """发送歌词更新事件.

        Args:
            lyrics_text: 歌词文本
            time_sec: 时间戳
        """
        if not self._event_bus:
            return

        try:
            from src.core.event_bus import Events

            from .events import MusicLyricsData

            data = MusicLyricsData(
                text=lyrics_text, time_sec=time_sec, song_id=self.song_id
            )
            await self._event_bus.emit(Events.MUSIC_LYRICS_UPDATE, data)
        except Exception as e:
            logger.debug(f"发送歌词事件失败: {e}")

    async def _on_pause_request(self, data):
        """处理暂停请求事件.

        Args:
            data: MusicControlRequest 数据
        """
        try:
            from .events import MusicControlRequest

            if isinstance(data, MusicControlRequest):
                source = data.source
            elif isinstance(data, dict):
                source = data.get("source", "external")
            else:
                source = "external"

            if self.is_playing and not self.paused:
                logger.info(f"收到暂停请求，来源: {source}")
                await self.pause(source=source)
        except Exception as e:
            logger.error(f"处理暂停请求失败: {e}", exc_info=True)

    async def _on_resume_request(self, data):
        """处理恢复播放请求事件.

        Args:
            data: MusicControlRequest 数据
        """
        try:
            from .events import MusicControlRequest

            if isinstance(data, MusicControlRequest):
                source = data.source
            elif isinstance(data, dict):
                source = data.get("source", "external")
            else:
                source = None

            if self.is_playing and self.paused:
                # 只有当暂停来源匹配或未指定来源时才恢复
                if source is None or self._pause_source == source:
                    logger.info(f"收到恢复请求，来源: {source}")
                    await self.resume()
        except Exception as e:
            logger.error(f"处理恢复请求失败: {e}", exc_info=True)

    def __del__(self):
        """清理资源"""
        try:
            self._clean_temp_cache()
        except Exception as e:
            logger.debug(f"__del__ 清理临时缓存失败: {e}")


# 全局音乐播放器实例
_music_player_instance = None


def get_music_player_instance() -> MusicPlayer:
    """获取音乐播放器单例"""
    global _music_player_instance
    if _music_player_instance is None:
        _music_player_instance = MusicPlayer()
        logger.info("[MusicPlayer] 创建音乐播放器单例实例")
    return _music_player_instance
