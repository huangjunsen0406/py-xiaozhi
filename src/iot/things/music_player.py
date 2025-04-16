from src.application import Application
from src.constants.constants import DeviceState, AudioConfig
from src.iot.thing import Thing, Parameter, ValueType
import os
import requests
import pygame
import time
import threading
from typing import Dict, Any, Tuple, List, Optional
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class MusicPlayer(Thing):
    """
    音乐播放器组件

    提供在线音乐搜索、播放、暂停等功能，支持歌词显示和播放进度跟踪。
    使用pygame播放引擎实现音频播放功能。
    """

    def __init__(self):
        """初始化音乐播放器组件"""
        super().__init__(
            "MusicPlayer",
            "在线音乐播放器，支持音乐搜索、播放控制和歌词显示"
        )

        # 初始化pygame mixer
        pygame.mixer.init(frequency=AudioConfig.OUTPUT_SAMPLE_RATE,
                          channels=AudioConfig.CHANNELS)

        # 搜索结果相关属性
        self.current_song = ""  # 当前歌曲名称
        self.current_url = ""   # 当前歌曲播放链接
        self.song_id = ""       # 当前歌曲ID
        self.total_duration = 0  # 歌曲总时长（秒）

        # 播放控制相关属性
        self.is_playing = False      # 是否正在播放
        self.paused = False          # 是否暂停
        self.current_position = 0    # 当前播放位置（秒）
        self.start_play_time = 0     # 开始播放的时间点

        # 歌词相关
        self.lyrics = []  # 歌词列表，格式为 [(时间, 文本), ...]
        self.current_lyric_index = -1  # 当前歌词索引

        # 线程控制
        self.progress_thread = None   # 进度更新线程
        self.stop_progress = threading.Event()  # 用于停止进度更新线程

        # 缓存相关
        cache_root = os.path.dirname(os.path.dirname(os.path.dirname(
                     os.path.dirname(__file__))))
        self.cache_dir = os.path.join(cache_root, "cache", "music")
        self._ensure_cache_dir()

        # 当前正在使用的临时文件
        self.current_temp_file = None

        # 获取应用程序实例
        self.app = Application.get_instance()

        # 加载配置文件
        self.config = self._load_config()

        # 清空临时缓存
        self._clear_temp_cache()

        # 清理遗留的临时文件
        self._cleanup_temp_files()

        logger.info("音乐播放器初始化完成")

        # 注册属性和方法
        self._register_properties()
        self._register_methods()

    def _register_properties(self):
        """注册播放器属性"""
        self.add_property("current_song", "当前歌曲", lambda: self.current_song)
        self.add_property("is_playing", "是否正在播放", lambda: self.is_playing)
        self.add_property("paused", "是否暂停", lambda: self.paused)
        self.add_property("total_duration", "歌曲总时长（秒）",
                          lambda: self.total_duration)
        self.add_property("current_position", "当前播放位置（秒）",
                          lambda: self._get_current_position())
        self.add_property("progress", "播放进度（百分比）",
                          lambda: self._get_progress())

    def _register_methods(self):
        """注册播放器方法"""
        self.add_method(
            "SearchPlay",
            "搜索并播放指定歌曲",
            [Parameter("song_name", "输入歌曲名称", ValueType.STRING, True)],
            lambda params: self.search_play(params["song_name"].get_value())
        )

        self.add_method(
            "SearchSong",
            "仅搜索歌曲不播放",
            [Parameter("song_name", "输入歌曲名称", ValueType.STRING, True)],
            lambda params: self._search_song(params["song_name"].get_value())
        )

        self.add_method(
            "PlayPause",
            "播放/暂停切换",
            [],
            lambda params: self.play_pause()
        )

        self.add_method(
            "Stop",
            "停止播放",
            [],
            lambda params: self.stop()
        )

        self.add_method(
            "Seek",
            "跳转到指定位置",
            [Parameter("position_seconds", "跳转位置（秒）", ValueType.NUMBER, True)],
            lambda params: self.seek(params["position_seconds"].get_value())
        )

        self.add_method(
            "GetLyrics",
            "获取当前歌曲歌词",
            [],
            lambda params: self._get_lyrics_text()
        )

    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件

        返回:
            Dict[str, Any]: 音乐播放器配置
        """
        return {
            "API": {
                "SEARCH_URL": "http://search.kuwo.cn/r.s",
                "PLAY_URL": "http://api.xiaodaokg.com/kuwo.php",
                "LYRIC_URL": "http://m.kuwo.cn/newh5/singles/songinfoandlrc"
            },
            "HEADERS": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                             "AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
                "Referer": "https://y.kuwo.cn/",
                "Cookie": ""
            }
        }

    def _search_song(self, song_name: str) -> Dict[str, Any]:
        """
        搜索指定歌曲

        参数:
            song_name: 歌曲名称

        返回:
            Dict[str, Any]: 搜索结果
        """
        # 重置搜索状态
        self.current_song = song_name
        self.current_url = ""
        self.song_id = ""
        self.total_duration = 0
        self.lyrics = []

        # 通过API搜索获取歌曲信息
        try:
            # 获取歌曲ID和播放URL
            song_id, url = self._get_song_info(song_name)
            if not song_id or not url:
                return {
                    "status": "error",
                    "message": f"未找到歌曲 '{song_name}' 或无法获取播放链接"
                }

            # 保存歌曲信息
            self.current_url = url
            self.song_id = song_id

            logger.info(f"搜索成功: {song_name}, URL: {url}")

            # 返回搜索结果
            return {
                "status": "success",
                "message": f"已找到歌曲: {self.current_song}",
                "song_id": song_id,
                "url": url,
                "duration": self.total_duration,
                "lyrics_count": len(self.lyrics)
            }

        except Exception as e:
            logger.error(f"搜索歌曲失败: {str(e)}")
            return {"status": "error", "message": f"搜索歌曲失败: {str(e)}"}

    def _get_song_info(self, song_name: str) -> Tuple[str, str]:
        """
        获取歌曲信息（ID和播放URL）

        参数:
            song_name: 歌曲名称

        返回:
            Tuple[str, str]: (歌曲ID, 播放URL)
        """
        # 从配置中获取请求头和API URL
        headers = self.config.get("HEADERS", {})
        search_url = self.config.get("API", {}).get(
            "SEARCH_URL", "http://search.kuwo.cn/r.s")
        play_url = self.config.get("API", {}).get(
            "PLAY_URL", "http://api.xiaodaokg.com/kuwo.php")

        # 1. 搜索歌曲获取ID
        search_params = {
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
            "devid": "0"
        }

        logger.info(f"搜索歌曲: {song_name}")

        try:
            response = requests.get(
                search_url, params=search_params, headers=headers, timeout=10)
            response.raise_for_status()

            # 记录响应内容到日志（调试用）
            logger.debug(f"搜索API响应内容: {response.text[:200]}...")

            # 处理响应文本
            response_text = response.text.replace("'", '"')  # 替换单引号为双引号

            # 提取歌曲ID
            song_id = ""
            dc_targetid_pos = response_text.find('"DC_TARGETID":"')
            if dc_targetid_pos != -1:
                start_pos = dc_targetid_pos + len('"DC_TARGETID":"')
                end_pos = response_text.find('"', start_pos)
                if end_pos != -1:
                    song_id = response_text[start_pos:end_pos]
                    logger.info(f"提取到歌曲ID: {song_id}")

            # 如果没有找到歌曲ID，返回失败
            if not song_id:
                logger.warning(f"未找到歌曲 '{song_name}' 的ID")
                return "", ""

            # 提取歌曲时长
            duration = 0
            duration_pos = response_text.find('"DURATION":"')
            if duration_pos != -1:
                start_pos = duration_pos + len('"DURATION":"')
                end_pos = response_text.find('"', start_pos)
                if end_pos != -1:
                    try:
                        duration = int(response_text[start_pos:end_pos])
                        self.total_duration = duration
                        logger.info(f"提取到歌曲时长: {duration}秒")
                    except ValueError:
                        logger.warning(
                            f"歌曲时长解析失败: {response_text[start_pos:end_pos]}")

            # 提取艺术家
            artist = ""
            artist_pos = response_text.find('"ARTIST":"')
            if artist_pos != -1:
                start_pos = artist_pos + len('"ARTIST":"')
                end_pos = response_text.find('"', start_pos)
                if end_pos != -1:
                    artist = response_text[start_pos:end_pos]

            # 提取歌曲名
            title = song_name
            name_pos = response_text.find('"NAME":"')
            if name_pos != -1:
                start_pos = name_pos + len('"NAME":"')
                end_pos = response_text.find('"', start_pos)
                if end_pos != -1:
                    title = response_text[start_pos:end_pos]

            # 提取专辑名
            album = ""
            album_pos = response_text.find('"ALBUM":"')
            if album_pos != -1:
                start_pos = album_pos + len('"ALBUM":"')
                end_pos = response_text.find('"', start_pos)
                if end_pos != -1:
                    album = response_text[start_pos:end_pos]

            # 更新当前歌曲信息
            display_name = title
            if artist:
                display_name = f"{title} - {artist}"
                if album:
                    display_name += f" ({album})"
            self.current_song = display_name

            logger.info(
                f"获取到歌曲: {self.current_song}, ID: {song_id}, 时长: {duration}秒")

            # 2. 获取歌曲播放链接
            play_api_url = f"{play_url}?ID={song_id}"
            logger.info(f"获取歌曲播放链接: {play_api_url}")

            for attempt in range(3):
                try:
                    url_response = requests.get(
                        play_api_url, headers=headers, timeout=10)
                    url_response.raise_for_status()

                    # 获取播放链接（直接返回的文本）
                    play_url_text = url_response.text.strip()

                    # 检查URL是否有效
                    if play_url_text and play_url_text.startswith("http"):
                        logger.info(f"获取到有效的歌曲URL: {play_url_text[:60]}...")

                        # 3. 获取歌词
                        self._fetch_lyrics(song_id)

                        return song_id, play_url_text
                    else:
                        logger.warning(
                            f"返回的播放链接格式不正确: {play_url_text[:100]}")
                        if attempt < 2:
                            logger.info(f"尝试重新获取播放链接 ({attempt+1}/3)")
                            time.sleep(1)
                        else:
                            return song_id, ""
                except Exception as e:
                    logger.error(f"获取播放链接时出错: {str(e)}")
                    if attempt < 2:
                        logger.info(f"尝试重新获取播放链接 ({attempt+1}/3)")
                        time.sleep(1)
                    else:
                        return song_id, ""

            return song_id, ""
        except Exception as e:
            logger.error(f"获取歌曲信息失败: {str(e)}")
            return "", ""

    def _fetch_lyrics(self, song_id: str):
        """
        获取歌词

        参数:
            song_id: 歌曲ID
        """
        try:
            # 从配置中获取请求头和API URL
            headers = self.config.get("HEADERS", {})
            lyric_url = self.config.get("API", {}).get(
                "LYRIC_URL", "http://m.kuwo.cn/newh5/singles/songinfoandlrc")

            # 构建歌词API请求
            lyric_api_url = f"{lyric_url}?musicId={song_id}"
            logger.info(f"获取歌词URL: {lyric_api_url}")

            response = requests.get(lyric_api_url, headers=headers, timeout=10)
            response.raise_for_status()

            # 添加错误处理
            try:
                # 尝试解析JSON
                data = response.json()

                # 解析歌词
                if (data.get("status") == 200 and data.get("data") and
                        data["data"].get("lrclist")):
                    lrc_list = data["data"]["lrclist"]
                    self.lyrics = []

                    for lrc in lrc_list:
                        time_sec = float(lrc.get("time", "0"))
                        text = lrc.get("lineLyric", "").strip()

                        # 跳过空歌词和元信息歌词
                        if (text and not text.startswith("作词") and
                                not text.startswith("作曲") and
                                not text.startswith("编曲")):
                            self.lyrics.append((time_sec, text))

                    logger.info(f"成功获取歌词，共 {len(self.lyrics)} 行")
                else:
                    logger.warning(
                        f"未获取到歌词或歌词格式错误: {data.get('msg', '')}")
            except ValueError as e:
                logger.warning(f"歌词API返回非JSON格式数据: {str(e)}")
                # 记录部分响应内容
                if hasattr(response, 'text') and response.text:
                    sample = (response.text[:100] + "..."
                             if len(response.text) > 100 else response.text)
                    logger.warning(f"歌词API响应内容: {sample}")
        except Exception as e:
            logger.error(f"获取歌词失败: {str(e)}")

    def _update_lyrics(self):
        """
        根据当前播放位置更新歌词显示
        """
        # 如果没有歌词或应用程序正在说话，不更新歌词
        if not self.lyrics or (self.app and self.app.is_tts_playing):
            return

        current_time = self.current_position

        # 查找当前时间对应的歌词
        current_index = self._find_current_lyric_index(current_time)

        # 如果歌词索引变化了，更新显示
        if current_index != self.current_lyric_index:
            self._display_current_lyric(current_index)

    def _find_current_lyric_index(self, current_time: float) -> int:
        """
        查找当前时间对应的歌词索引

        参数:
            current_time: 当前播放时间（秒）

        返回:
            int: 当前歌词索引
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

    def _display_current_lyric(self, current_index: int):
        """
        显示当前歌词

        参数:
            current_index: 当前歌词索引
        """
        self.current_lyric_index = current_index

        if current_index < len(self.lyrics):
            time_sec, text = self.lyrics[current_index]

            # 只在应用程序不在说话时更新UI
            # 创建歌词文本副本，避免引用可能变化的变量
            lyric_text = text

            # 在歌词前添加时间和进度信息
            position_str = self._format_time(self.current_position)
            duration_str = self._format_time(self.total_duration)
            display_text = f"[{position_str}/{duration_str}] {lyric_text}"

            # 使用schedule方法安全地更新UI
            if self.app:
                self.app.schedule(lambda: self.app.set_chat_message(
                    "assistant", display_text))
            logger.debug(f"显示歌词: {lyric_text}")

    def _get_lyrics_text(self) -> Dict[str, Any]:
        """
        获取当前歌曲歌词文本

        返回:
            Dict[str, Any]: 歌词信息
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
            "lyrics": lyrics_text
        }

    def _download_file(self, url: str, file_path: str) -> bool:
        """
        下载音乐文件到指定路径（同步方法）

        参数:
            url: 音乐URL
            file_path: 保存路径

        返回:
            bool: 是否下载成功
        """
        try:
            # 使用配置中的请求头
            headers = self.config.get("HEADERS", {}).copy()
            headers.update({
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://music.163.com/'
            })

            # 创建唯一的临时文件路径，避免冲突
            temp_path = f"{file_path}.{int(time.time())}.tmp"

            # 下载文件
            with requests.get(url, stream=True, headers=headers,
                              timeout=30) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 每下载25%更新一次日志
                            if (total_size > 0 and
                                    downloaded % (total_size // 4) < 32768):
                                progress = downloaded * 100 // total_size
                                logger.info(f"下载进度: {progress}%")

                # 下载完成后，将临时文件重命名为正式文件
                if downloaded == total_size:
                    # 如果目标文件已存在，先尝试删除
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"删除已存在的文件失败: {str(e)}")
                            # 如果无法删除，使用新名称
                            file_path = f"{file_path}.new"

                    try:
                        os.replace(temp_path, file_path)
                        logger.info(f"音乐文件下载完成: {file_path}")
                        return True
                    except Exception as e:
                        logger.error(f"重命名临时文件失败: {str(e)}")
                        return False
                else:
                    # 如果下载不完整，删除临时文件
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass
                    logger.warning("音乐文件下载不完整")
                    return False

        except Exception as e:
            logger.error(f"下载音乐文件失败: {str(e)}")
            # 清理临时文件
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
            return False

    def _download_mp3(self, url: str, cache_path: str):
        """
        下载完整的MP3文件到缓存目录

        参数:
            url: 音频URL
            cache_path: 缓存文件路径
        """
        try:
            # 使用配置中的请求头
            headers = self.config.get("HEADERS", {}).copy()
            headers.update({
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://music.163.com/'
            })

            # 创建唯一的临时文件路径，避免冲突
            temp_path = f"{cache_path}.{int(time.time())}.temp"

            with requests.get(url, stream=True, headers=headers, timeout=30) as response:
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        if not self.is_playing:
                            logger.info("缓存下载被中止")
                            break
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # 每下载10%更新一次日志
                            if total_size > 0 and downloaded % (total_size // 10) < 32768:
                                progress = downloaded * 100 // total_size
                                logger.info(f"缓存下载进度: {progress}%")

                # 下载完成后，将临时文件重命名为正式文件
                if downloaded == total_size and self.is_playing:
                    # 如果目标文件已存在且正在使用，不覆盖
                    if os.path.exists(cache_path):
                        try:
                            # 尝试删除已存在的文件
                            os.remove(cache_path)
                            os.replace(temp_path, cache_path)
                            logger.info("MP3文件已缓存到本地")
                        except Exception as e:
                            logger.warning(f"替换缓存文件失败，可能正在使用中: {str(e)}")
                            # 保留临时文件，不删除
                            logger.info(f"保留临时缓存文件: {temp_path}")
                    else:
                        try:
                            os.replace(temp_path, cache_path)
                            logger.info("MP3文件已缓存到本地")
                        except Exception as e:
                            logger.error(f"缓存MP3文件失败: {str(e)}")
                            if os.path.exists(temp_path):
                                try:
                                    os.remove(temp_path)
                                except Exception:
                                    pass
                else:
                    # 如果下载不完整或播放已停止，删除临时文件
                    if os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                            logger.info("已清理临时文件")
                        except Exception as e:
                            logger.error(f"清理临时文件失败: {str(e)}")

        except Exception as e:
            logger.error(f"下载MP3文件失败: {str(e)}")
            # 清理临时文件
            try:
                if 'temp_path' in locals() and os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info("已清理临时文件")
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}")

    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
                logger.info(f"创建音乐缓存目录: {self.cache_dir}")
        except Exception as e:
            logger.error(f"创建缓存目录失败: {str(e)}")

    def _get_cache_path(self, song_id: str) -> str:
        """获取歌曲缓存文件路径"""
        return os.path.join(self.cache_dir, f"{song_id}.mp3")

    def _is_song_cached(self, song_id: str) -> bool:
        """检查歌曲是否已缓存"""
        cache_path = self._get_cache_path(song_id)
        return os.path.exists(cache_path)

    def _get_current_position(self) -> float:
        """
        获取当前播放位置

        返回:
            float: 当前播放位置（秒）
        """
        if not self.is_playing:
            return self.current_position

        if self.paused:
            return self.current_position

        # 如果正在播放，计算当前位置
        current_pos = time.time() - self.start_play_time
        return min(self.total_duration, current_pos)

    def _get_progress(self) -> float:
        """
        获取播放进度百分比

        返回:
            float: 播放进度（0-100）
        """
        if self.total_duration <= 0:
            return 0
        return round(self._get_current_position() * 100 / self.total_duration, 1)

    def search_play(self, song_name: str) -> Dict[str, Any]:
        """
        搜索并播放指定歌曲

        参数:
            song_name: 歌曲名称

        返回:
            Dict[str, Any]: 播放结果
        """
        # 先搜索歌曲
        result = self._search_song(song_name)

        # 如果搜索成功且有URL，则播放
        if result.get("status") == "success" and self.current_url:
            self._play_url(self.current_url)
            return {
                "status": "success",
                "message": f"正在播放: {self.current_song}",
                "duration": self.total_duration
            }

        # 搜索失败直接返回搜索结果
        return result

    def _cleanup_temp_files(self, max_keep=1):
        """
        清理临时文件夹中的旧文件，只保留最新的几个

        参数:
            max_keep: 保留的最新文件数量
        """
        try:
            temp_dir = os.path.join(self.cache_dir, "temp")
            if not os.path.exists(temp_dir):
                return

            # 获取所有临时文件
            files = []
            for f in os.listdir(temp_dir):
                if f.startswith("playing_") and f.endswith(".mp3"):
                    file_path = os.path.join(temp_dir, f)
                    files.append((file_path, os.path.getmtime(file_path)))

            # 按修改时间排序
            files.sort(key=lambda x: x[1], reverse=True)

            # 保留最新的几个，删除其余的
            for file_path, _ in files[max_keep:]:
                try:
                    if file_path != self.current_temp_file:
                        os.remove(file_path)
                        logger.info(f"已清理旧的临时文件: {file_path}")
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")

        except Exception as e:
            logger.warning(f"清理临时文件操作失败: {str(e)}")

    def _clear_temp_cache(self):
        """
        清空临时缓存目录
        """
        try:
            temp_dir = os.path.join(self.cache_dir, "temp")
            if not os.path.exists(temp_dir):
                return

            cleared = 0
            for f in os.listdir(temp_dir):
                if f.endswith(".mp3") or f.endswith(".tmp") or f.endswith(".temp"):
                    try:
                        os.remove(os.path.join(temp_dir, f))
                        cleared += 1
                    except Exception as e:
                        logger.warning(f"删除临时文件失败: {str(e)}")

            if cleared > 0:
                logger.info(f"启动时清理了 {cleared} 个临时缓存文件")

        except Exception as e:
            logger.warning(f"清理临时缓存失败: {str(e)}")

    def _play_url(self, url: str) -> bool:
        """
        播放指定URL的音乐

        参数:
            url: 音乐URL

        返回:
            bool: 是否成功开始播放
        """
        # 如果当前有歌曲在播放，先停止
        if self.is_playing:
            self.stop()

        try:
            # 创建临时文件路径
            temp_dir = os.path.join(self.cache_dir, "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            temp_file = os.path.join(temp_dir, "current_playing.mp3")

            # 检查是否有缓存
            cache_path = None
            use_cache = False

            if self.song_id:
                cache_path = self._get_cache_path(self.song_id)
                # 检查缓存是否存在且可用
                if os.path.exists(cache_path):
                    try:
                        # 尝试直接使用缓存文件播放
                        pygame.mixer.music.load(cache_path)
                        use_cache = True
                        logger.info(f"使用缓存播放: {cache_path}")
                    except Exception as e:
                        # 如果加载缓存失败，回退到下载
                        logger.warning(f"加载缓存文件失败: {str(e)}，将重新下载")
                        use_cache = False

            if not use_cache:
                # 需要下载文件
                if os.path.exists(temp_file):
                    try:
                        # 尝试清理已存在的临时文件
                        os.remove(temp_file)
                        logger.info("已清理临时播放文件")
                    except Exception as e:
                        logger.warning(f"清理临时播放文件失败: {str(e)}")
                        # 使用唯一文件名代替
                        temp_file = os.path.join(temp_dir, f"playing_{int(time.time())}.mp3")

                # 记录当前使用的临时文件
                self.current_temp_file = temp_file

                # 清理过多的旧临时文件
                self._cleanup_temp_files(max_keep=3)

                # 如果有缓存路径但缓存不存在，直接下载到缓存位置并创建符号链接或副本到临时位置
                if cache_path and not os.path.exists(cache_path):
                    logger.info(f"下载音乐到缓存: {cache_path}")
                    if self._download_file(url, cache_path):
                        try:
                            # 创建从缓存到临时文件的副本
                            import shutil
                            shutil.copy2(cache_path, temp_file)
                            logger.info(f"从缓存创建临时播放文件: {temp_file}")
                            pygame.mixer.music.load(temp_file)
                        except Exception as e:
                            logger.error(f"创建临时播放文件失败: {str(e)}，尝试直接使用缓存")
                            try:
                                pygame.mixer.music.load(cache_path)
                            except Exception as e2:
                                logger.error(f"加载缓存文件失败: {str(e2)}")
                                return False
                    else:
                        logger.error("下载到缓存失败")
                        return False
                else:
                    # 没有缓存路径或无法使用缓存，直接下载到临时文件
                    logger.info(f"下载音乐到临时文件: {temp_file}")
                    if not self._download_file(url, temp_file):
                        logger.error("下载音乐文件失败")
                        return False

                    pygame.mixer.music.load(temp_file)

                    # 如果有缓存路径但缓存不存在，异步创建缓存（非必须，仅作为备份）
                    if cache_path and not os.path.exists(cache_path) and os.path.exists(temp_file):
                        def copy_to_cache():
                            try:
                                import shutil
                                shutil.copy2(temp_file, cache_path)
                                logger.info(f"临时文件已复制到缓存: {cache_path}")
                            except Exception as e:
                                logger.warning(f"复制到缓存失败: {str(e)}")

                        threading.Thread(
                            target=copy_to_cache,
                            daemon=True
                        ).start()

            # 开始播放
            pygame.mixer.music.play()
            self.is_playing = True
            self.paused = False
            self.current_position = 0
            self.start_play_time = time.time()

            # 更新UI显示
            if self.app:
                self.app.schedule(lambda: self.app.set_chat_message(
                    "assistant", f"正在播放: {self.current_song}"))

            # 启动进度更新线程
            self._start_progress_thread()

            return True

        except Exception as e:
            logger.error(f"播放歌曲失败: {str(e)}")
            self.is_playing = False
            return False

    def play_pause(self) -> Dict[str, Any]:
        """
        播放/暂停切换

        返回:
            Dict[str, Any]: 操作结果
        """
        if not self.is_playing:
            # 如果没有正在播放的歌曲但有URL，尝试播放
            if self.current_url:
                if self._play_url(self.current_url):
                    return {
                        "status": "success",
                        "message": f"开始播放: {self.current_song}"
                    }
                else:
                    return {
                        "status": "error",
                        "message": "播放失败"
                    }
            else:
                return {
                    "status": "error",
                    "message": "没有可播放的歌曲"
                }
        elif self.paused:
            # 恢复播放
            pygame.mixer.music.unpause()
            self.paused = False
            # 更新开始时间，考虑已经暂停的时间
            self.start_play_time = time.time() - self.current_position

            if self.app:
                self.app.schedule(lambda: self.app.set_chat_message(
                    "assistant", f"继续播放: {self.current_song}"))

            return {
                "status": "success",
                "message": f"继续播放: {self.current_song}"
            }
        else:
            # 暂停播放
            pygame.mixer.music.pause()
            self.paused = True
            self.current_position = time.time() - self.start_play_time

            if self.app:
                pos_str = self._format_time(self.current_position)
                dur_str = self._format_time(self.total_duration)
                self.app.schedule(lambda: self.app.set_chat_message(
                    "assistant", f"已暂停: {self.current_song} [{pos_str}/{dur_str}]"))

            return {
                "status": "success",
                "message": f"已暂停: {self.current_song}",
                "position": self.current_position
            }

    def stop(self) -> Dict[str, Any]:
        """
        停止播放

        返回:
            Dict[str, Any]: 操作结果
        """
        if not self.is_playing:
            return {
                "status": "info",
                "message": "没有正在播放的歌曲"
            }

        # 停止进度更新线程
        self.stop_progress.set()
        if self.progress_thread and self.progress_thread.is_alive():
            self.progress_thread.join(timeout=1.0)
        self.stop_progress.clear()

        # 停止音乐播放
        pygame.mixer.music.stop()

        # 更改播放状态
        current_song = self.current_song
        self.is_playing = False
        self.paused = False

        # 清理临时文件
        temp_dir = os.path.join(self.cache_dir, "temp")
        if os.path.exists(temp_dir):
            try:
                temp_file = os.path.join(temp_dir, "current_playing.mp3")
                if os.path.exists(temp_file):
                    try:
                        # 尝试删除临时播放文件
                        os.remove(temp_file)
                        logger.info("已清理临时播放文件")
                    except Exception as e:
                        logger.warning(f"清理临时播放文件失败: {str(e)}")
            except Exception as e:
                logger.warning(f"清理临时文件时出错: {str(e)}")

        # 清理旧的临时文件
        self._cleanup_temp_files(max_keep=1)

        # 重置当前临时文件
        self.current_temp_file = None

        # 返回结果
        msg = f"已停止播放: {current_song}"
        if self.app:
            self.app.schedule(lambda: self.app.set_chat_message("assistant", msg))

        return {
            "status": "success",
            "message": msg
        }

    def seek(self, position: float) -> Dict[str, Any]:
        """
        跳转到指定位置

        参数:
            position: 目标位置（秒）

        返回:
            Dict[str, Any]: 操作结果
        """
        if not self.is_playing:
            return {
                "status": "error",
                "message": "没有正在播放的歌曲"
            }

        # 确保位置在有效范围内
        position = max(0, min(position, self.total_duration))

        # 记录当前位置
        self.current_position = position

        # 更新开始时间
        self.start_play_time = time.time() - position

        # 使用pygame跳转
        pygame.mixer.music.rewind()
        pygame.mixer.music.set_pos(position)

        # 如果处于暂停状态，保持暂停
        if self.paused:
            pygame.mixer.music.pause()

        # 更新UI
        pos_str = self._format_time(position)
        dur_str = self._format_time(self.total_duration)
        msg = f"已跳转到: {pos_str}/{dur_str}"

        if self.app:
            self.app.schedule(lambda: self.app.set_chat_message("assistant", msg))

        return {
            "status": "success",
            "message": msg,
            "position": position
        }

    def _start_progress_thread(self):
        """启动进度更新线程"""
        # 确保之前的线程已经停止
        if self.progress_thread and self.progress_thread.is_alive():
            self.stop_progress.set()
            self.progress_thread.join(timeout=1.0)
            self.stop_progress.clear()

        # 创建新线程
        self.progress_thread = threading.Thread(
            target=self._update_progress_thread,
            daemon=True
        )
        self.progress_thread.start()

    def _update_progress_thread(self):
        """进度更新线程"""
        last_lyric_update = 0

        while not self.stop_progress.is_set() and self.is_playing:
            # 如果暂停了，等待恢复
            if self.paused:
                time.sleep(0.2)
                continue

            # 计算当前位置
            self.current_position = time.time() - self.start_play_time

            # 检查是否到达歌曲末尾
            if self.current_position >= self.total_duration:
                # 已播放完成
                self.current_position = self.total_duration
                logger.info(f"歌曲 '{self.current_song}' 播放完成")

                # 停止播放并重置状态
                pygame.mixer.music.stop()
                self.is_playing = False

                # 更新UI显示完成状态
                if self.app:
                    dur_str = self._format_time(self.total_duration)
                    self.app.schedule(lambda: self.app.set_chat_message(
                        "assistant", f"播放完成: {self.current_song} [{dur_str}]"))

                # 根据自动模式设置应用状态
                if self.app:
                    self.app.set_device_state(DeviceState.IDLE)
                break

            # 更新歌词显示（每0.5秒检查一次）
            if time.time() - last_lyric_update > 0.5:
                self._update_lyrics()
                last_lyric_update = time.time()

            # 短暂休眠再继续
            time.sleep(0.1)

        logger.debug("进度更新线程已退出")

    def _format_time(self, seconds: float) -> str:
        """
        将秒数格式化为 mm:ss 格式

        参数:
            seconds: 秒数

        返回:
            str: 格式化后的时间字符串
        """
        minutes = int(seconds) // 60
        seconds = int(seconds) % 60
        return f"{minutes:02d}:{seconds:02d}"