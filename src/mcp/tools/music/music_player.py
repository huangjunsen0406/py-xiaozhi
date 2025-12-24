"""音乐播放器 (重构版).

使用 FFmpeg 解码 + AudioCodec 播放的架构。
"""

import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

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

        self.title = None
        self.artist = None
        self.album = None
        self.duration = None

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

    def _get_tag_value(self, tags: dict, tag_names: List[str]) -> Optional[str]:
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
        audio_codec: Optional["AudioCodec"] = None,
        ui_display: Optional[Any] = None,
    ):
        self._audio_codec = audio_codec
        self._ui_display = ui_display

        self.decoder: Optional[MusicDecoder] = None
        self._music_queue = asyncio.Queue(maxsize=100)
        self._playback_task: Optional[asyncio.Task] = None

        self.current_song = ""
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0
        self.is_playing = False
        self.paused = False
        self.current_position = 0
        self.start_play_time = 0
        self._pause_source: Optional[str] = None
        self._current_file_path: Optional[Path] = None

        self.lyrics = []
        self.current_lyric_index = -1

        user_cache_dir = get_user_cache_dir()
        self.cache_dir = user_cache_dir / "music"
        self.temp_cache_dir = self.cache_dir / "temp"
        self._init_cache_dirs()

        self.config = {
            "SEARCH_URL": "http://search.kuwo.cn/r.s",
            "PLAY_URL": "http://api.xiaodaokg.com/kuwo.php",
            "LYRIC_URL": "https://api.xiaodaokg.com/kw/kwlyric.php",
            "HEADERS": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Connection": "keep-alive",
            },
        }

        self._clean_temp_cache()

        self._local_playlist = None
        self._last_scan_time = 0

        logger.info("音乐播放器初始化完成 (FFmpeg + AudioCodec 模式)")

    def set_audio_codec(self, audio_codec: Optional["AudioCodec"]) -> None:
        self._audio_codec = audio_codec
        if audio_codec:
            logger.info("AudioCodec 已设置到 MusicPlayer")

    def set_ui_display(self, ui_display: Optional[Any]) -> None:
        self._ui_display = ui_display
        if ui_display:
            logger.debug("UI Display 已设置到 MusicPlayer")

    def _get_audio_codec(self) -> Optional["AudioCodec"]:
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

    def _scan_local_music(self, force_refresh: bool = False) -> List[MusicMetadata]:
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

            await self._safe_update_ui(f"已停止: {current_song}")
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

            await asyncio.sleep(0.05)

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

            await self._safe_update_ui(f"继续播放: {self.current_song}")
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

    async def _search_song(self, song_name: str) -> Tuple[str, str]:
        """搜索歌曲获取ID和URL"""
        try:
            params = {
                "all": song_name,
                "ft": "music",
                "newsearch": "1",
                "alflac": "1",
                "itemset": "web_2013",
                "client": "kt",
                "cluster": "0",
                "pn": "0",
                "rn": "1",
                "vermerge": "1",
                "rformat": "json",
                "encoding": "utf8",
                "show_copyright_off": "1",
                "pcmp4": "1",
                "ver": "mbox",
                "vipver": "MUSIC_8.7.6.0.BCS31",
                "plat": "pc",
                "devid": "0",
            }

            response = await asyncio.to_thread(
                requests.get,
                self.config["SEARCH_URL"],
                params=params,
                headers=self.config["HEADERS"],
                timeout=10,
            )
            response.raise_for_status()

            text = response.text.replace("'", '"')

            song_id = self._extract_value(text, '"DC_TARGETID":"', '"')
            if not song_id:
                return "", ""

            title = self._extract_value(text, '"NAME":"', '"') or song_name
            artist = self._extract_value(text, '"ARTIST":"', '"')
            album = self._extract_value(text, '"ALBUM":"', '"')
            duration_str = self._extract_value(text, '"DURATION":"', '"')

            if duration_str:
                try:
                    self.total_duration = int(duration_str)
                except ValueError:
                    self.total_duration = 0

            display_name = title
            if artist:
                display_name = f"{title} - {artist}"
                if album:
                    display_name += f" ({album})"
            self.current_song = display_name
            self.song_id = song_id

            play_url = f"{self.config['PLAY_URL']}?ID={song_id}"
            url_response = await asyncio.to_thread(
                requests.get, play_url, headers=self.config["HEADERS"], timeout=10
            )
            url_response.raise_for_status()

            play_url_text = url_response.text.strip()
            if play_url_text and play_url_text.startswith("http"):
                await self._fetch_lyrics(song_id)
                return song_id, play_url_text

            return song_id, ""

        except Exception as e:
            logger.error(f"搜索歌曲失败: {e}")
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

            await self._safe_update_ui(f"正在播放: {self.current_song}")
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

    async def _get_or_download_file(self, url: str) -> Optional[Path]:
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

    async def _download_file(self, url: str, filename: str) -> Optional[Path]:
        """下载文件到缓存目录"""
        temp_path = None
        try:
            temp_path = self.temp_cache_dir / f"temp_{int(time.time())}_{filename}"

            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=self.config["HEADERS"],
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            cache_path = self.cache_dir / filename
            shutil.move(str(temp_path), str(cache_path))

            logger.info(f"音乐下载完成并缓存: {cache_path}")
            return cache_path

        except Exception as e:
            logger.error(f"下载失败: {e}")
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"已清理临时下载文件: {temp_path}")
                except Exception:
                    pass
            return None

    async def _fetch_lyrics(self, song_id: str):
        """获取歌词"""
        try:
            self.lyrics = []

            lyric_url = self.config.get("LYRIC_URL")
            lyric_api_url = f"{lyric_url}?id={song_id}"
            logger.info(f"获取歌词URL: {lyric_api_url}")

            response = await asyncio.to_thread(
                requests.get, lyric_api_url, headers=self.config["HEADERS"], timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if (
                data.get("code") == 200
                and data.get("data")
                and data["data"].get("content")
            ):
                lrc_content = data["data"]["content"]

                import re

                lines = lrc_content.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    time_match = re.match(r"\[(\d{2}):(\d{2})\.(\d{2})\](.+)", line)
                    if time_match:
                        minutes = int(time_match.group(1))
                        seconds = int(time_match.group(2))
                        centiseconds = int(time_match.group(3))
                        text = time_match.group(4).strip()

                        time_sec = minutes * 60 + seconds + centiseconds / 100.0

                        if (
                            text
                            and not text.startswith("作词")
                            and not text.startswith("作曲")
                            and not text.startswith("编曲")
                            and not text.startswith("ti:")
                            and not text.startswith("ar:")
                            and not text.startswith("al:")
                            and not text.startswith("by:")
                            and not text.startswith("offset:")
                        ):
                            self.lyrics.append((time_sec, text))

                logger.info(f"成功获取歌词，共 {len(self.lyrics)} 行")
            else:
                logger.warning(f"未获取到歌词或歌词格式错误: {data.get('msg', '')}")

        except Exception as e:
            logger.error(f"获取歌词失败: {e}")

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

            dur_str = self._format_time(self.total_duration)
            await self._safe_update_ui(f"播放完成: {self.current_song} [{dur_str}]")

    async def _lyrics_update_task(self):
        """歌词更新任务"""
        if not self.lyrics:
            return

        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.5)
                    continue

                current_time = time.time() - self.start_play_time

                if current_time >= self.total_duration:
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

            await self._safe_update_ui(display_text)
            logger.debug(f"显示歌词: {text}")

    def _extract_value(self, text: str, start_marker: str, end_marker: str) -> str:
        """从文本中提取值"""
        start_pos = text.find(start_marker)
        if start_pos == -1:
            return ""

        start_pos += len(start_marker)
        end_pos = text.find(end_marker, start_pos)

        if end_pos == -1:
            return ""

        return text[start_pos:end_pos]

    def _format_time(self, seconds: float) -> str:
        """将秒数格式化为 mm:ss 格式"""
        minutes = int(seconds) // 60
        seconds = int(seconds) % 60
        return f"{minutes:02d}:{seconds:02d}"

    async def _safe_update_ui(self, message: str):
        try:
            if self._ui_display and hasattr(self._ui_display, "update_text"):
                await self._ui_display.update_text(message)
            else:
                logger.debug(f"MusicPlayer UI (无显示): {message}")
        except Exception as e:
            logger.debug(f"更新UI失败: {e}, 消息: {message}")

    def __del__(self):
        """清理资源"""
        try:
            self._clean_temp_cache()
        except Exception:
            pass


# 全局音乐播放器实例
_music_player_instance = None


def get_music_player_instance() -> MusicPlayer:
    """获取音乐播放器单例"""
    global _music_player_instance
    if _music_player_instance is None:
        _music_player_instance = MusicPlayer()
        logger.info("[MusicPlayer] 创建音乐播放器单例实例")
    return _music_player_instance
