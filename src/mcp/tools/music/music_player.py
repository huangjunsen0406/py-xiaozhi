import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import requests

from src.audio_codecs.music_decoder import MusicDecoder
from src.constants.constants import AudioConfig
from src.utils.logging_config import get_logger
from src.utils.resource_finder import get_user_cache_dir

# 尝试导入音乐元数据库
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3NoHeaderError

    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

logger = get_logger(__name__)


class MusicMetadata:
    """
    音乐元数据类.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.filename = file_path.name
        self.file_id = file_path.stem  # 文件名去掉扩展名，即歌曲ID
        self.file_size = file_path.stat().st_size

        # 从文件提取的元数据
        self.title = None
        self.artist = None
        self.album = None
        self.duration = None  # 秒数

    def extract_metadata(self) -> bool:
        """
        提取音乐文件元数据.
        """
        if not MUTAGEN_AVAILABLE:
            return False

        try:
            audio_file = MutagenFile(self.file_path)
            if audio_file is None:
                return False

            # 基本信息
            if hasattr(audio_file, "info"):
                self.duration = getattr(audio_file.info, "length", None)

            # ID3标签信息
            tags = audio_file.tags if audio_file.tags else {}

            # 标题
            self.title = self._get_tag_value(tags, ["TIT2", "TITLE", "\xa9nam"])

            # 艺术家
            self.artist = self._get_tag_value(tags, ["TPE1", "ARTIST", "\xa9ART"])

            # 专辑
            self.album = self._get_tag_value(tags, ["TALB", "ALBUM", "\xa9alb"])

            return True

        except ID3NoHeaderError:
            # 没有ID3标签，不是错误
            return True
        except Exception as e:
            logger.debug(f"提取元数据失败 {self.filename}: {e}")
            return False

    def _get_tag_value(self, tags: dict, tag_names: List[str]) -> Optional[str]:
        """
        从多个可能的标签名中获取值.
        """
        for tag_name in tag_names:
            if tag_name in tags:
                value = tags[tag_name]
                if isinstance(value, list) and value:
                    return str(value[0])
                elif value:
                    return str(value)
        return None

    def format_duration(self) -> str:
        """
        格式化播放时长.
        """
        if self.duration is None:
            return "未知"

        minutes = int(self.duration) // 60
        seconds = int(self.duration) % 60
        return f"{minutes:02d}:{seconds:02d}"


class MusicPlayer:
    def __init__(self):
        # FFmpeg 解码器和播放队列
        self.decoder: Optional[MusicDecoder] = None
        self._music_queue: Optional[asyncio.Queue] = None
        self._playback_task: Optional[asyncio.Task] = None

        # 核心播放状态
        self.current_song = ""
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0
        self.is_playing = False
        self.paused = False
        self.current_position = 0
        self.start_play_time = 0
        self._pause_source: Optional[str] = None  # "tts" | "manual" | None

        # 当前播放文件路径（用于暂停/恢复）
        self._current_file_path: Optional[Path] = None

        # 延迟启动：等待TTS结束后启动
        self._deferred_start_path: Optional[Path] = None
        self._deferred_start_position: float = 0.0

        # 歌词相关
        self.lyrics = []  # 歌词列表，格式为 [(时间, 文本), ...]
        self.current_lyric_index = -1  # 当前歌词索引

        # 缓存目录设置 - 使用用户缓存目录确保可写
        user_cache_dir = get_user_cache_dir()
        self.cache_dir = user_cache_dir / "music"
        self.temp_cache_dir = self.cache_dir / "temp"
        self._init_cache_dirs()

        # API配置
        self.config = {
            "SEARCH_URL": "http://search.kuwo.cn/r.s",
            "PLAY_URL": "http://api.xiaodaokg.com/kuwo.php",
            "LYRIC_URL": "https://api.xiaodaokg.com/kw/kwlyric.php",
            "HEADERS": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) " "AppleWebKit/537.36"
                ),
                "Accept": "*/*",
                "Connection": "keep-alive",
            },
        }

        # 清理临时缓存
        self._clean_temp_cache()

        # 获取应用程序实例和 AudioCodec
        self.app = None
        self.audio_codec = None
        self._initialize_app_reference()

        # 本地歌单缓存
        self._local_playlist = None
        self._last_scan_time = 0

        logger.info("音乐播放器单例初始化完成 (FFmpeg + AudioCodec 模式)")

    def _initialize_app_reference(self):
        """
        初始化应用程序引用和 AudioCodec.
        """
        try:
            from src.application import Application

            self.app = Application.get_instance()
            self.audio_codec = getattr(self.app, "audio_codec", None)

            if not self.audio_codec:
                logger.warning("AudioCodec 未初始化，音乐播放可能不可用")

        except Exception as e:
            logger.warning(f"获取Application实例失败: {e}")
            self.app = None

    def _init_cache_dirs(self):
        """
        初始化缓存目录.
        """
        try:
            # 创建主缓存目录
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # 创建临时缓存目录
            self.temp_cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"音乐缓存目录初始化完成: {self.cache_dir}")
        except Exception as e:
            logger.error(f"创建缓存目录失败: {e}")
            # 回退到系统临时目录
            self.cache_dir = Path(tempfile.gettempdir()) / "xiaozhi_music_cache"
            self.temp_cache_dir = self.cache_dir / "temp"
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.temp_cache_dir.mkdir(parents=True, exist_ok=True)

    def _clean_temp_cache(self):
        """
        清理临时缓存文件.
        """
        try:
            # 清空临时缓存目录中的所有文件
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
        """
        扫描本地音乐缓存，返回歌单.
        """
        current_time = time.time()

        # 如果不强制刷新且缓存未过期（5分钟），直接返回缓存
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

        # 查找所有音乐文件
        music_files = []
        for pattern in ["*.mp3", "*.m4a", "*.flac", "*.wav", "*.ogg"]:
            music_files.extend(self.cache_dir.glob(pattern))

        logger.debug(f"找到 {len(music_files)} 个音乐文件")

        # 扫描每个文件
        for file_path in music_files:
            try:
                metadata = MusicMetadata(file_path)

                # 尝试提取元数据
                if MUTAGEN_AVAILABLE:
                    metadata.extract_metadata()

                playlist.append(metadata)

            except Exception as e:
                logger.debug(f"处理音乐文件失败 {file_path.name}: {e}")

        # 按艺术家和标题排序
        playlist.sort(key=lambda x: (x.artist or "Unknown", x.title or x.filename))

        # 更新缓存
        self._local_playlist = playlist
        self._last_scan_time = current_time

        logger.info(f"扫描完成，找到 {len(playlist)} 首本地音乐")
        return playlist

    async def get_local_playlist(self, force_refresh: bool = False) -> dict:
        """
        获取本地音乐歌单.
        """
        try:
            playlist = self._scan_local_music(force_refresh)

            if not playlist:
                return {
                    "status": "info",
                    "message": "本地缓存中没有音乐文件",
                    "playlist": [],
                    "total_count": 0,
                }

            # 格式化歌单，简洁格式方便 AI 读取
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
        """
        搜索本地音乐.
        """
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
                # 在标题、艺术家、文件名中搜索
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
        """
        根据文件ID播放本地歌曲.
        """
        try:
            # 构建文件路径
            file_path = self.cache_dir / f"{file_id}.mp3"

            if not file_path.exists():
                # 尝试其他格式
                for ext in [".m4a", ".flac", ".wav", ".ogg"]:
                    alt_path = self.cache_dir / f"{file_id}{ext}"
                    if alt_path.exists():
                        file_path = alt_path
                        break
                else:
                    return {"status": "error", "message": f"本地文件不存在: {file_id}"}

            # 获取歌曲信息
            metadata = MusicMetadata(file_path)
            if MUTAGEN_AVAILABLE:
                metadata.extract_metadata()

            # 更新歌曲信息
            title = metadata.title or "未知标题"
            artist = metadata.artist or "未知艺术家"
            self.current_song = f"{title} - {artist}"
            self.song_id = file_id
            self.total_duration = metadata.duration or 0
            self.current_url = str(file_path)  # 本地文件路径
            self.lyrics = []  # 本地文件暂不支持歌词

            # 直接开始播放
            success = await self._start_playback(file_path)

            if success:
                # 返回歌曲信息（包含时长等详细信息）
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

    # 内部方法：位置和进度计算
    async def get_position(self):
        if not self.is_playing or self.paused:
            return self.current_position

        current_pos = min(self.total_duration, time.time() - self.start_play_time)

        # 检查是否播放完成
        if current_pos >= self.total_duration and self.total_duration > 0:
            await self._handle_playback_finished()

        return current_pos

    async def get_progress(self):
        """
        获取播放进度百分比.
        """
        if self.total_duration <= 0:
            return 0
        position = await self.get_position()
        return round(position * 100 / self.total_duration, 1)

    async def _handle_playback_finished(self):
        """
        处理播放完成.
        """
        if self.is_playing:
            logger.info(f"歌曲播放完成: {self.current_song}")
            # 停止解码器
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            self.is_playing = False
            self.paused = False
            self.current_position = self.total_duration

            # 更新UI显示完成状态
            if self.app and hasattr(self.app, "set_chat_message"):
                dur_str = self._format_time(self.total_duration)
                await self._safe_update_ui(f"播放完成: {self.current_song} [{dur_str}]")

    # 核心方法
    async def search_and_play(self, song_name: str) -> dict:
        """
        搜索并播放歌曲.
        """
        try:
            # 搜索歌曲
            song_id, url = await self._search_song(song_name)
            if not song_id or not url:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}

            # 播放歌曲
            success = await self._play_url(url)
            if success:
                # 返回歌曲信息（包含时长等详细信息）
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
        """
        停止播放.
        """
        try:
            if not self.is_playing and not self._pending_play:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            current_song = self.current_song

            # 停止解码器
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            # 取消播放任务
            if self._playback_task and not self._playback_task.done():
                self._playback_task.cancel()
                try:
                    await self._playback_task
                except asyncio.CancelledError:
                    pass

            # 清空队列
            if self._music_queue:
                while not self._music_queue.empty():
                    try:
                        self._music_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

            # 重置状态
            self.is_playing = False
            self.paused = False
            self._pause_source = None  # 清除暂停来源标记
            self._pending_play = False
            self._pending_file_path = None
            self.current_position = 0

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"已停止: {current_song}")

            logger.info(f"停止播放: {current_song}")
            return {"status": "success", "message": "已停止"}

        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return {"status": "error", "message": f"停止失败: {str(e)}"}

    async def pause(self, source: str = "manual") -> dict:
        """暂停播放（只停止解码器，不清空队列）.

        Args:
            source: 暂停来源，"manual"=用户主动暂停, "tts"=TTS触发的暂停
        """
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if self.paused:
                # 如果已经暂停，但来源不同，更新来源（用户意图优先）
                if self._pause_source != source:
                    old_source = self._pause_source
                    self._pause_source = source
                    logger.info(f"更新暂停来源: {old_source} → {source}")
                return {"status": "info", "message": "已经处于暂停状态"}

            # ✅ 立即设置暂停标志，防止重复调用
            self.paused = True
            self._pause_source = source

            # 记录暂停时的播放位置
            if self.start_play_time > 0:
                self.current_position = time.time() - self.start_play_time

            # 停止解码器（停止生成新数据）
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            # 等待解码器完全停止
            await asyncio.sleep(0.05)

            # 清空音乐内部队列（但不清空 AudioCodec 共享队列）
            cleared_count = 0
            if self._music_queue:
                while not self._music_queue.empty():
                    try:
                        self._music_queue.get_nowait()
                        cleared_count += 1
                    except asyncio.QueueEmpty:
                        break

            logger.info(
                f"暂停播放: {self.current_song} at {self._format_time(self.current_position)}, "
                f"来源: {source}, 清空 {cleared_count} 帧音乐内部队列"
            )

            return {"status": "success", "message": "已暂停"}

        except Exception as e:
            logger.error(f"暂停播放失败: {e}", exc_info=True)
            return {"status": "error", "message": f"暂停失败: {str(e)}"}

    async def resume(self) -> dict:
        """
        恢复播放（从暂停位置重启解码）.
        """
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            if not self.paused:
                return {"status": "info", "message": "当前未暂停"}

            if not self._current_file_path or not self._current_file_path.exists():
                return {"status": "error", "message": "无法找到音频文件"}

            # ✅ 从暂停位置重新启动解码和播放
            logger.info(
                f"恢复播放: {self.current_song} from {self._format_time(self.current_position)}"
            )

            # 重新创建音乐队列
            self._music_queue = asyncio.Queue(maxsize=100)

            # 重新启动 FFmpeg 解码器（从暂停位置开始）
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

            # 取消旧的播放任务（如果存在）
            if self._playback_task and not self._playback_task.done():
                self._playback_task.cancel()
                try:
                    await self._playback_task
                except asyncio.CancelledError:
                    pass

            # 启动新的播放任务
            self._playback_task = asyncio.create_task(self._playback_loop())

            # 恢复状态
            self.paused = False
            self._pause_source = None  # 清除暂停来源标记
            self.start_play_time = time.time() - self.current_position  # 调整时间基准

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"继续播放: {self.current_song}")

            return {"status": "success", "message": "已恢复播放"}

        except Exception as e:
            logger.error(f"恢复播放失败: {e}")
            return {"status": "error", "message": f"恢复失败: {str(e)}"}

    async def seek(self, position: float) -> dict:
        """
        跳转到指定位置（通过重新解码实现）.
        """
        try:
            if not self.is_playing:
                return {"status": "error", "message": "没有正在播放的歌曲"}

            if not self._current_file_path or not self._current_file_path.exists():
                return {"status": "error", "message": "无法找到音频文件"}

            # 限制跳转范围
            if position < 0:
                position = 0
            elif position >= self.total_duration:
                position = max(0, self.total_duration - 1)

            # ✅ 关键：立即停止当前播放（类似切歌）
            # 停止解码器
            if self.decoder:
                await self.decoder.stop()
                self.decoder = None

            # 等待解码器完全停止
            await asyncio.sleep(0.05)

            # 清空音乐队列
            cleared_count = 0
            if self._music_queue:
                while not self._music_queue.empty():
                    try:
                        self._music_queue.get_nowait()
                        cleared_count += 1
                    except asyncio.QueueEmpty:
                        break

            # 清空 AudioCodec 播放队列（立即停止播放）
            if self.audio_codec:
                await self.audio_codec.clear_audio_queue()

            logger.info(
                f"跳转到 {self._format_time(position)}，清空 {cleared_count} 帧音乐数据"
            )

            # 从新位置重新开始播放
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
        """
        获取当前歌曲歌词.
        """
        if not self.lyrics:
            return {"status": "info", "message": "当前歌曲没有歌词", "lyrics": []}

        # 提取歌词文本，转换为列表
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
        """获取播放器状态.

        注意：只返回用户可见的状态，不返回内部暂停标志。 TTS 临时暂停不应该让 AI 认为音乐"已暂停"。
        """
        position = await self.get_position()
        progress = await self.get_progress()

        # 判断实际播放状态（排除 TTS 临时暂停）
        if not self.is_playing:
            playing_state = "未播放"
        elif self.paused and self._pause_source == "manual":
            # 只有用户主动暂停才报告"已暂停"
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
                f"暂停来源状态: {self._pause_source} tts是说话时临时暂停\n"
                f"播放时长: {duration_str}\n"
                f"当前位置: {position_str}\n"
                f"播放进度: {progress}%\n"
                f"歌词可用: {'是' if len(self.lyrics) > 0 else '否'}"
            ),
        }

    # 内部方法
    async def _search_song(self, song_name: str) -> Tuple[str, str]:
        """
        搜索歌曲获取ID和URL.
        """
        try:
            # 构建搜索参数
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

            # 搜索歌曲
            response = await asyncio.to_thread(
                requests.get,
                self.config["SEARCH_URL"],
                params=params,
                headers=self.config["HEADERS"],
                timeout=10,
            )
            response.raise_for_status()

            # 解析响应
            text = response.text.replace("'", '"')

            # 提取歌曲ID
            song_id = self._extract_value(text, '"DC_TARGETID":"', '"')
            if not song_id:
                return "", ""

            # 提取歌曲信息
            title = self._extract_value(text, '"NAME":"', '"') or song_name
            artist = self._extract_value(text, '"ARTIST":"', '"')
            album = self._extract_value(text, '"ALBUM":"', '"')
            duration_str = self._extract_value(text, '"DURATION":"', '"')

            if duration_str:
                try:
                    self.total_duration = int(duration_str)
                except ValueError:
                    self.total_duration = 0

            # 设置显示名称
            display_name = title
            if artist:
                display_name = f"{title} - {artist}"
                if album:
                    display_name += f" ({album})"
            self.current_song = display_name
            self.song_id = song_id

            # 获取播放URL
            play_url = f"{self.config['PLAY_URL']}?ID={song_id}"
            url_response = await asyncio.to_thread(
                requests.get, play_url, headers=self.config["HEADERS"], timeout=10
            )
            url_response.raise_for_status()

            play_url_text = url_response.text.strip()
            if play_url_text and play_url_text.startswith("http"):
                # 获取歌词
                await self._fetch_lyrics(song_id)
                return song_id, play_url_text

            return song_id, ""

        except Exception as e:
            logger.error(f"搜索歌曲失败: {e}")
            return "", ""

    async def _play_url(self, url: str) -> bool:
        """
        播放指定URL（新实现：使用 FFmpeg + AudioCodec）
        """
        try:
            # 检查 AudioCodec 是否可用
            if not self.audio_codec:
                logger.error("AudioCodec 未初始化，无法播放音乐")
                return False

            # 停止当前播放
            if self.is_playing:
                await self.stop()

            # 检查缓存或下载
            file_path = await self._get_or_download_file(url)
            if not file_path:
                return False

            # 直接开始播放
            return await self._start_playback(file_path)

        except Exception as e:
            logger.error(f"播放失败: {e}")
            return False

    async def _start_playback(
        self, file_path: Path, start_position: float = 0.0
    ) -> bool:
        """开始播放音乐（内部方法）

        Args:
            file_path: 音频文件路径
            start_position: 开始位置（秒），默认从头开始
        """
        try:
            # ✅ 检查 TTS 状态：如果TTS正在播放，延迟启动
            if self.app and self.app.is_speaking():
                logger.info("TTS 播放中，音乐延迟启动")
                self._deferred_start_path = file_path
                self._deferred_start_position = start_position
                # 标记为"准备播放"状态（AudioPlugin恢复时会检查）
                self.is_playing = True
                self.paused = True
                return True

            # 清除延迟启动标志
            self._deferred_start_path = None
            self._deferred_start_position = 0.0

            # 保存当前文件路径（用于暂停/恢复）
            self._current_file_path = file_path

            # 创建音乐队列
            self._music_queue = asyncio.Queue(maxsize=100)

            # 启动 FFmpeg 解码器（支持从指定位置开始）
            self.decoder = MusicDecoder(
                sample_rate=AudioConfig.OUTPUT_SAMPLE_RATE,  # 24000Hz
                channels=AudioConfig.CHANNELS,  # 1 channel
            )

            success = await self.decoder.start_decode(
                file_path, self._music_queue, start_position
            )
            if not success:
                logger.error("启动音频解码器失败")
                return False

            # 启动播放任务
            self._playback_task = asyncio.create_task(self._playback_loop())

            # 更新播放状态
            self.is_playing = True
            self.paused = False
            self._pending_play = False
            self.current_position = start_position  # 从指定位置开始
            self.start_play_time = time.time() - start_position  # 调整时间基准
            self.current_lyric_index = -1

            position_info = f" from {start_position:.1f}s" if start_position > 0 else ""
            logger.info(f"开始播放: {self.current_song}{position_info}")

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"正在播放: {self.current_song}")

            # 启动歌词更新任务
            asyncio.create_task(self._lyrics_update_task())

            return True

        except Exception as e:
            logger.error(f"启动播放失败: {e}")
            return False

    async def _playback_loop(self):
        """
        播放循环：从队列取PCM，写入AudioCodec.
        """
        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.1)
                    continue

                # 从音乐队列取数据
                try:
                    audio_data = await asyncio.wait_for(
                        self._music_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("音乐队列读取超时")
                    continue

                if audio_data is None:
                    # EOF，播放结束
                    logger.info("音乐播放完成")
                    await self._handle_playback_finished()
                    break

                # ✅ 关键：写入 AudioCodec 播放队列
                await self._write_to_audio_codec(audio_data)

        except asyncio.CancelledError:
            logger.debug("播放循环被取消")
        except Exception as e:
            logger.error(f"播放循环异常: {e}")

    async def _write_to_audio_codec(self, pcm_data: np.ndarray):
        """
        将 PCM 数据写入 AudioCodec 播放队列.
        """
        try:
            if not self.audio_codec:
                return

            # 确保是单声道数据
            if pcm_data.ndim > 1:
                # 立体声转单声道（取平均）
                pcm_data = pcm_data.mean(axis=1).astype(np.int16)

            # 调用 AudioCodec 的 write_pcm_direct 方法
            await self.audio_codec.write_pcm_direct(pcm_data)

        except Exception as e:
            logger.warning(f"写入 AudioCodec 失败: {e}")

    async def _get_or_download_file(self, url: str) -> Optional[Path]:
        """获取或下载文件.

        先检查缓存，如果缓存中没有则下载
        """
        try:
            # 使用歌曲ID作为缓存文件名
            cache_filename = f"{self.song_id}.mp3"
            cache_path = self.cache_dir / cache_filename

            # 检查缓存是否存在
            if cache_path.exists():
                logger.info(f"使用缓存: {cache_path}")
                return cache_path

            # 缓存不存在，需要下载
            return await self._download_file(url, cache_filename)

        except Exception as e:
            logger.error(f"获取文件失败: {e}")
            return None

    async def _download_file(self, url: str, filename: str) -> Optional[Path]:
        """下载文件到缓存目录.

        先下载到临时目录，下载完成后移动到正式缓存目录
        """
        temp_path = None
        try:
            # 创建临时文件路径
            temp_path = self.temp_cache_dir / f"temp_{int(time.time())}_{filename}"

            # 异步下载
            response = await asyncio.to_thread(
                requests.get,
                url,
                headers=self.config["HEADERS"],
                stream=True,
                timeout=30,
            )
            response.raise_for_status()

            # 写入临时文件
            with open(temp_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            # 下载完成，移动到正式缓存目录
            cache_path = self.cache_dir / filename
            shutil.move(str(temp_path), str(cache_path))

            logger.info(f"音乐下载完成并缓存: {cache_path}")
            return cache_path

        except Exception as e:
            logger.error(f"下载失败: {e}")
            # 清理临时文件
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                    logger.debug(f"已清理临时下载文件: {temp_path}")
                except Exception:
                    pass
            return None

    async def _fetch_lyrics(self, song_id: str):
        """
        获取歌词.
        """
        try:
            # 重置歌词
            self.lyrics = []

            # 构建歌词API请求
            lyric_url = self.config.get("LYRIC_URL")
            lyric_api_url = f"{lyric_url}?id={song_id}"
            logger.info(f"获取歌词URL: {lyric_api_url}")

            response = await asyncio.to_thread(
                requests.get, lyric_api_url, headers=self.config["HEADERS"], timeout=10
            )
            response.raise_for_status()

            # 解析JSON
            data = response.json()

            # 解析歌词
            if (
                data.get("code") == 200
                and data.get("data")
                and data["data"].get("content")
            ):
                lrc_content = data["data"]["content"]

                # 解析LRC格式歌词
                lines = lrc_content.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    # 匹配时间标签格式 [mm:ss.xx]
                    import re

                    time_match = re.match(r"\[(\d{2}):(\d{2})\.(\d{2})\](.+)", line)
                    if time_match:
                        minutes = int(time_match.group(1))
                        seconds = int(time_match.group(2))
                        centiseconds = int(time_match.group(3))
                        text = time_match.group(4).strip()

                        # 转换为总秒数
                        time_sec = minutes * 60 + seconds + centiseconds / 100.0

                        # 跳过空歌词和元信息歌词
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

    async def _lyrics_update_task(self):
        """
        歌词更新任务.
        """
        if not self.lyrics:
            return

        try:
            while self.is_playing:
                if self.paused:
                    await asyncio.sleep(0.5)
                    continue

                current_time = time.time() - self.start_play_time

                # 检查是否播放完成
                if current_time >= self.total_duration:
                    await self._handle_playback_finished()
                    break

                # 查找当前时间对应的歌词
                current_index = self._find_current_lyric_index(current_time)

                # 如果歌词索引变化了，更新显示
                if current_index != self.current_lyric_index:
                    await self._display_current_lyric(current_index)

                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"歌词更新任务异常: {e}")

    def _find_current_lyric_index(self, current_time: float) -> int:
        """
        查找当前时间对应的歌词索引.
        """
        # 查找下一句歌词
        next_lyric_index = None
        for i, (time_sec, _) in enumerate(self.lyrics):
            # 添加一个小的偏移量(0.5秒)，使歌词显示更准确
            if time_sec > current_time - 0.5:
                next_lyric_index = i
                break

        # 确定当前歌词索引
        if next_lyric_index is not None and next_lyric_index > 0:
            # 如果找到下一句歌词，当前歌词就是它的前一句
            return next_lyric_index - 1
        elif next_lyric_index is None and self.lyrics:
            # 如果没找到下一句，说明已经到最后一句
            return len(self.lyrics) - 1
        else:
            # 其他情况（如播放刚开始）
            return 0

    async def _display_current_lyric(self, current_index: int):
        """
        显示当前歌词.
        """
        self.current_lyric_index = current_index

        if current_index < len(self.lyrics):
            time_sec, text = self.lyrics[current_index]

            # 在歌词前添加时间和进度信息
            position_str = self._format_time(time.time() - self.start_play_time)
            duration_str = self._format_time(self.total_duration)
            display_text = f"[{position_str}/{duration_str}] {text}"

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(display_text)
                logger.debug(f"显示歌词: {text}")

    def _extract_value(self, text: str, start_marker: str, end_marker: str) -> str:
        """
        从文本中提取值.
        """
        start_pos = text.find(start_marker)
        if start_pos == -1:
            return ""

        start_pos += len(start_marker)
        end_pos = text.find(end_marker, start_pos)

        if end_pos == -1:
            return ""

        return text[start_pos:end_pos]

    def _format_time(self, seconds: float) -> str:
        """
        将秒数格式化为 mm:ss 格式.
        """
        minutes = int(seconds) // 60
        seconds = int(seconds) % 60
        return f"{minutes:02d}:{seconds:02d}"

    async def _safe_update_ui(self, message: str):
        """
        安全地更新UI.
        """
        if not self.app or not hasattr(self.app, "set_chat_message"):
            return

        try:
            self.app.set_chat_message("assistant", message)
        except Exception as e:
            logger.error(f"更新UI失败: {e}")

    def __del__(self):
        """
        清理资源.
        """
        try:
            # 如果程序正常退出，额外清理一次临时缓存
            self._clean_temp_cache()
        except Exception:
            # 忽略错误，因为在对象销毁阶段可能会有各种异常
            pass


# 全局音乐播放器实例
_music_player_instance = None


def get_music_player_instance() -> MusicPlayer:
    """
    获取音乐播放器单例.
    """
    global _music_player_instance
    if _music_player_instance is None:
        _music_player_instance = MusicPlayer()
        logger.info("[MusicPlayer] 创建音乐播放器单例实例")
    return _music_player_instance
