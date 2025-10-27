import asyncio
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

import pygame
import requests

from src.constants.constants import AudioConfig
from src.iot.thing import Parameter, Thing, ValueType
from src.utils.logging_config import get_logger
from src.utils.resource_finder import get_project_root

logger = get_logger(__name__)


class MusicPlayer(Thing):
    """音乐播放器 - 专为IoT设备设计

    只保留核心功能：搜索、播放、暂停、停止、跳转
    """

    def __init__(self):
        super().__init__("MusicPlayer", "音乐播放器，支持在线音乐播放控制")

        # 初始化pygame mixer
        pygame.mixer.init(
            frequency=AudioConfig.OUTPUT_SAMPLE_RATE, channels=AudioConfig.CHANNELS
        )

        # 核心播放状态
        self.current_song = ""
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0
        self.is_playing = False
        self.paused = False
        self.current_position = 0
        self.start_play_time = 0

        # 歌词相关
        self.lyrics = []  # 歌词列表，格式为 [(时间, 文本), ...]
        self.current_lyric_index = -1  # 当前歌词索引

        # 缓存目录设置
        self.cache_dir = Path(get_project_root()) / "cache" / "music"
        self.temp_cache_dir = self.cache_dir / "temp"
        self._init_cache_dirs()

        # API配置
        self.config = {
            "SEARCH_URL": "http://search.kuwo.cn/r.s",
            "PLAY_URL": "http://api.xiaodaokg.com/kuwo.php",
            "LYRIC_URL": "http://m.kuwo.cn/newh5/singles/songinfoandlrc",
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

        # 获取应用程序实例
        self.app = None
        self._initialize_app_reference()

        logger.info("简化版音乐播放器初始化完成")
        self._register_properties_and_methods()

    def _initialize_app_reference(self):
        """
        初始化应用程序引用.
        """
        try:
            from src.application import Application

            self.app = Application.get_instance()
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

    def _register_properties_and_methods(self):
        """
        注册属性和方法.
        """
        # 属性
        self.add_property("current_song", "当前歌曲", self.get_current_song)
        self.add_property("is_playing", "是否播放", self.get_is_playing)
        self.add_property("paused", "是否暂停", self.get_paused)
        self.add_property("duration", "总时长", self.get_duration)
        self.add_property("position", "当前位置", self.get_position)
        self.add_property("progress", "播放进度（百分比）", self.get_progress)

        # 方法
        self.add_method(
            "SearchAndPlay",
            "搜索并播放歌曲",
            [Parameter("song_name", "歌曲名称", ValueType.STRING, True)],
            self.search_and_play,
        )

        self.add_method("PlayPause", "播放/暂停切换", [], self.play_pause)

        self.add_method("Stop", "停止播放", [], self.stop)

        self.add_method(
            "Seek",
            "跳转到指定位置",
            [Parameter("position", "位置(秒)", ValueType.NUMBER, True)],
            self.seek,
        )

        self.add_method("GetLyrics", "获取当前歌曲歌词", [], self.get_lyrics)

    # 属性getter方法
    async def get_current_song(self):
        return self.current_song

    async def get_is_playing(self):
        return self.is_playing

    async def get_paused(self):
        return self.paused

    async def get_duration(self):
        return self.total_duration

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
            pygame.mixer.music.stop()
            self.is_playing = False
            self.paused = False
            self.current_position = self.total_duration

            # 更新UI显示完成状态
            if self.app and hasattr(self.app, "set_chat_message"):
                dur_str = self._format_time(self.total_duration)
                await self._safe_update_ui(f"播放完成: {self.current_song} [{dur_str}]")

    # 核心方法
    async def search_and_play(self, params):
        """
        搜索并播放歌曲.
        """
        song_name = params["song_name"].get_value()

        try:
            # 搜索歌曲
            song_id, url = await self._search_song(song_name)
            if not song_id or not url:
                return {"status": "error", "message": f"未找到歌曲: {song_name}"}

            # 播放歌曲
            success = await self._play_url(url)
            if success:
                return {
                    "status": "success",
                    "message": f"正在播放: {self.current_song}",
                }
            else:
                return {"status": "error", "message": "播放失败"}

        except Exception as e:
            logger.error(f"搜索播放失败: {e}")
            return {"status": "error", "message": f"操作失败: {str(e)}"}

    async def play_pause(self, params):
        """
        播放/暂停切换.
        """
        try:
            if not self.is_playing and self.current_url:
                # 重新播放
                success = await self._play_url(self.current_url)
                return {
                    "status": "success" if success else "error",
                    "message": (
                        f"开始播放: {self.current_song}" if success else "播放失败"
                    ),
                }

            elif self.is_playing and self.paused:
                # 恢复播放
                pygame.mixer.music.unpause()
                self.paused = False
                self.start_play_time = time.time() - self.current_position

                # 更新UI
                if self.app and hasattr(self.app, "set_chat_message"):
                    await self._safe_update_ui(f"继续播放: {self.current_song}")

                return {
                    "status": "success",
                    "message": f"继续播放: {self.current_song}",
                }

            elif self.is_playing and not self.paused:
                # 暂停播放
                pygame.mixer.music.pause()
                self.paused = True
                self.current_position = time.time() - self.start_play_time

                # 更新UI
                if self.app and hasattr(self.app, "set_chat_message"):
                    pos_str = self._format_time(self.current_position)
                    dur_str = self._format_time(self.total_duration)
                    await self._safe_update_ui(
                        f"已暂停: {self.current_song} [{pos_str}/{dur_str}]"
                    )

                return {"status": "success", "message": f"已暂停: {self.current_song}"}

            else:
                return {"status": "error", "message": "没有可播放的歌曲"}

        except Exception as e:
            logger.error(f"播放暂停操作失败: {e}")
            return {"status": "error", "message": f"操作失败: {str(e)}"}

    async def stop(self, params):
        """
        停止播放.
        """
        try:
            if not self.is_playing:
                return {"status": "info", "message": "没有正在播放的歌曲"}

            pygame.mixer.music.stop()
            current_song = self.current_song
            self.is_playing = False
            self.paused = False
            self.current_position = 0

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"已停止: {current_song}")

            return {"status": "success", "message": f"已停止: {current_song}"}

        except Exception as e:
            logger.error(f"停止播放失败: {e}")
            return {"status": "error", "message": f"停止失败: {str(e)}"}

    async def seek(self, params):
        """
        跳转到指定位置.
        """
        try:
            position = params["position"].get_value()

            if not self.is_playing:
                return {"status": "error", "message": "没有正在播放的歌曲"}

            position = max(0, min(position, self.total_duration))
            self.current_position = position
            self.start_play_time = time.time() - position

            pygame.mixer.music.rewind()
            pygame.mixer.music.set_pos(position)

            if self.paused:
                pygame.mixer.music.pause()

            # 更新UI
            pos_str = self._format_time(position)
            dur_str = self._format_time(self.total_duration)
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"已跳转到: {pos_str}/{dur_str}")

            return {"status": "success", "message": f"已跳转到: {position:.1f}秒"}

        except Exception as e:
            logger.error(f"跳转失败: {e}")
            return {"status": "error", "message": f"跳转失败: {str(e)}"}

    async def get_lyrics(self, params):
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
        播放指定URL.
        """
        try:
            # 停止当前播放
            if self.is_playing:
                pygame.mixer.music.stop()

            # 检查缓存或下载
            file_path = await self._get_or_download_file(url)
            if not file_path:
                return False

            # 加载并播放
            pygame.mixer.music.load(str(file_path))
            pygame.mixer.music.play()

            self.current_url = url
            self.is_playing = True
            self.paused = False
            self.current_position = 0
            self.start_play_time = time.time()
            self.current_lyric_index = -1  # 重置歌词索引

            logger.info(f"开始播放: {self.current_song}")

            # 更新UI
            if self.app and hasattr(self.app, "set_chat_message"):
                await self._safe_update_ui(f"正在播放: {self.current_song}")

            # 启动歌词更新任务
            asyncio.create_task(self._lyrics_update_task())

            return True

        except Exception as e:
            logger.error(f"播放失败: {e}")
            return False

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
            lyric_api_url = f"{lyric_url}?musicId={song_id}"
            logger.info(f"获取歌词URL: {lyric_api_url}")

            response = await asyncio.to_thread(
                requests.get, lyric_api_url, headers=self.config["HEADERS"], timeout=10
            )
            response.raise_for_status()

            # 解析JSON
            data = response.json()

            # 解析歌词
            if (
                data.get("status") == 200
                and data.get("data")
                and data["data"].get("lrclist")
            ):
                lrc_list = data["data"]["lrclist"]

                for lrc in lrc_list:
                    time_sec = float(lrc.get("time", "0"))
                    text = lrc.get("lineLyric", "").strip()

                    # 跳过空歌词和元信息歌词
                    if (
                        text
                        and not text.startswith("作词")
                        and not text.startswith("作曲")
                        and not text.startswith("编曲")
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
