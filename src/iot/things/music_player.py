from src.application import Application
from src.constants.constants import DeviceState
from src.iot.thing import Thing, Parameter, ValueType
import os
import sys
import tempfile
import requests
from urllib.parse import urlparse
from pathlib import Path
import subprocess
import pyaudio
import queue
import threading
import time
from typing import Optional, Dict, Any, Tuple, List
from tqdm import tqdm
import logging
import json

logger = logging.getLogger("MusicPlayer")

class MusicPlayer(Thing):
    """
    音乐播放器组件
    
    提供在线音乐搜索、播放、暂停等功能，支持歌词显示和播放进度跟踪。
    优先播放本地音乐，如果没有再播放在线音乐。
    """
    
    def __init__(self):
        """初始化音乐播放器"""
        super().__init__("MusicPlayer", "在线音乐播放器，优先播放本地音乐如果没有再播放在线音乐")
        
        # 播放状态相关属性
        self.current_song = ""  # 当前歌曲名称
        self.playing = False    # 播放状态
        self.total_duration = 0  # 歌曲总时长（秒）
        self.current_position = 0  # 当前播放位置（秒）
        self.position_update_time = 0  # 上次更新播放位置的时间
        
        # 播放控制相关
        self.audio_decode_queue = queue.Queue(maxsize=100)  # 音频解码队列
        self.play_thread = None  # 播放线程
        self.stop_event = threading.Event()  # 停止事件
        
        # 歌词相关
        self.lyrics = []  # 歌词列表，格式为 [(时间, 文本), ...]
        self.current_lyric_index = 0  # 当前歌词索引
        
        # 获取应用程序实例
        self.app = Application.get_instance()
        
        # 加载配置文件
        self.config = self._load_config()
        
        logger.info("音乐播放器初始化完成")
        
        # 注册属性和方法
        self._register_properties()
        self._register_methods()
    
    def _register_properties(self):
        """注册播放器属性"""
        self.add_property("current_song", "当前播放的歌曲", lambda: self.current_song)
        self.add_property("playing", "是否正在播放", lambda: self.playing)
        self.add_property("total_duration", "歌曲总时长（秒）", lambda: self.total_duration)
        self.add_property("current_position", "当前播放位置（秒）", lambda: self._get_current_position())
        self.add_property("progress", "播放进度（百分比）", lambda: self._get_progress())
    
    def _register_methods(self):
        """注册播放器方法"""
        self.add_method(
            "Play", 
            "播放指定歌曲",
            [Parameter("song_name", "歌曲名称", ValueType.STRING, True)],
            lambda params: self._play(params["song_name"].get_value())
        )
        
        self.add_method(
            "Pause", 
            "暂停播放", 
            [],
            lambda params: self._pause()
        )
        
        self.add_method(
            "GetDuration", 
            "获取当前歌曲时长", 
            [],
            lambda params: {
                "duration": self.total_duration, 
                "position": self._get_current_position(), 
                "progress": self._get_progress()
            }
        )

    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置文件
        
        返回:
            Dict[str, Any]: 音乐播放器配置
        """
        try:
            config_path = os.path.join("config", "config.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config.get("MUSIC_PLAYER", {})
        except Exception as e:
            logger.error(f"加载配置文件失败: {str(e)}")
            # 返回默认配置
            return {
                "API": {
                    "BASE_URL": "http://localhost:3200",
                    "SEARCH_ENDPOINT": "/getSearchByKey",
                    "PLAY_ENDPOINT": "/getMusicPlay",
                    "LYRIC_ENDPOINT": "/getLyric"
                },
                "HEADERS": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "*/*",
                    "Accept-Encoding": "identity",
                    "Connection": "keep-alive",
                    "Referer": "https://y.qq.com/",
                    "Cookie": ""
                }
            }

    def _get_current_position(self) -> float:
        """
        获取当前播放位置，考虑播放状态
        
        返回:
            float: 当前播放位置（秒）
        """
        if not self.playing:
            return self.current_position
        
        # 如果正在播放，计算当前时间与上次更新时间的差值
        elapsed = 0
        if self.position_update_time > 0:
            elapsed = time.time() - self.position_update_time
        
        return min(self.total_duration, self.current_position + elapsed)
    
    def _get_progress(self) -> float:
        """
        获取播放进度百分比
        
        返回:
            float: 播放进度（0-100）
        """
        if self.total_duration <= 0:
            return 0
        return round(self._get_current_position() * 100 / self.total_duration, 1)

    def _play(self, song_name: str) -> Dict[str, Any]:
        """
        播放指定歌曲
        
        参数:
            song_name: 歌曲名称
            
        返回:
            Dict[str, Any]: 播放结果
        """
        # 如果已经在播放，先停止当前播放
        if self.playing:
            self._pause()
            # 添加短暂延迟确保之前的播放线程完全停止
            time.sleep(0.5)
        
        # 清空之前的歌词显示
        if self.app:
            self.app.schedule(lambda: self.app.set_chat_message("assistant", f"正在播放: {song_name}"))
        
        # 检查应用程序状态，如果正在说话，不等待而是直接播放
        if self.app and self.app.device_state == DeviceState.SPEAKING:
            logger.info(f"应用程序正在说话，但将继续播放歌曲: {song_name}")
        
        # 重置播放状态
        self.current_song = song_name
        self.playing = True
        self.current_position = 0
        self.position_update_time = time.time()
        self.lyrics = []  # 清空歌词
        self.current_lyric_index = -1  # 重置歌词索引为-1，确保第一句歌词能显示
        
        # 确保停止事件被清除
        self.stop_event.clear()
        
        # 通过API搜索获取歌曲信息
        try:
            # 获取歌曲ID和播放URL
            song_mid, url = self._get_song_info(song_name)
            if not song_mid or not url:
                return {"status": "error", "message": f"未找到歌曲 '{song_name}' 或无法获取播放链接"}
            
            logger.info(f"正在播放: {song_name}, URL: {url}")
            
            # 创建并启动播放线程
            self.play_thread = threading.Thread(
                target=self._process_audio,
                args=(url,),
                daemon=True
            )
            self.play_thread.start()
            
            # 不等待播放线程开始，直接返回成功
            return {"status": "success", "message": f"正在播放: {song_name}", "duration": self.total_duration}
            
        except Exception as e:
            logger.error(f"播放歌曲失败: {str(e)}")
            self.playing = False
            return {"status": "error", "message": f"播放歌曲失败: {str(e)}"}

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
        base_url = self.config.get("API", {}).get("BASE_URL", "http://localhost:3200")
        search_endpoint = self.config.get("API", {}).get("SEARCH_ENDPOINT", "/getSearchByKey")
        play_endpoint = self.config.get("API", {}).get("PLAY_ENDPOINT", "/getMusicPlay")
        
        # 1. 先搜索歌曲获取ID
        search_url = f"{base_url}{search_endpoint}?key={song_name}"
        logger.info(f"搜索歌曲URL: {search_url}")
        
        response = requests.get(search_url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 获取第一首歌曲的ID
        if (data.get('response') and data['response'].get('data') and 
            data['response']['data'].get('song') and 
            data['response']['data']['song'].get('list') and 
            len(data['response']['data']['song']['list']) > 0):
            
            song_info = data['response']['data']['song']['list'][0]
            song_mid = song_info['songmid']
            logger.info(f"获取到歌曲ID: {song_mid}")
            
            # 获取歌曲时长（秒）
            if 'interval' in song_info:
                self.total_duration = song_info['interval']
                logger.info(f"歌曲时长: {self.total_duration}秒")
            else:
                self.total_duration = 0
                logger.warning("无法获取歌曲时长")
            
            # 获取歌词
            self._fetch_lyrics(song_mid)
            
            # 2. 通过ID获取实际播放链接
            url_api = f"{base_url}{play_endpoint}?songmid={song_mid}"
            logger.info(f"获取歌曲URL的API: {url_api}")
            
            url_response = requests.get(url_api, headers=headers, timeout=10)
            url_response.raise_for_status()
            url_data = url_response.json()
            
            if (url_data.get('data') and url_data['data'].get('playUrl') and 
                url_data['data']['playUrl'].get(song_mid) and 
                url_data['data']['playUrl'][song_mid].get('url')):
                
                url = url_data['data']['playUrl'][song_mid]['url']
                logger.info(f"获取到歌曲URL: {url}")
                return song_mid, url
            else:
                logger.warning(f"API未返回有效的URL")
                return song_mid, ""
        else:
            logger.warning(f"未找到歌曲 '{song_name}'")
            return "", ""

    def _pause(self) -> Dict[str, Any]:
        """
        暂停当前播放
        
        返回:
            Dict[str, Any]: 暂停结果
        """
        if not self.current_song:
            return {"status": "error", "message": "没有正在播放的歌曲"}
        
        if self.playing:
            # 更新当前播放位置
            if self.position_update_time > 0:
                elapsed = time.time() - self.position_update_time
                self.current_position += elapsed
                self.current_position = min(self.total_duration, self.current_position)
            
            self.playing = False
            self.stop_event.set()  # 设置停止事件
            
            # 清空队列
            self._clear_audio_queue()
            
            # 等待播放线程结束
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=2.0)
            
            # 更新Application显示
            if self.app and self.app.display:
                position_str = self._format_time(self.current_position)
                duration_str = self._format_time(self.total_duration)
                pause_message = f"已暂停: {position_str}/{duration_str}"
                print(pause_message)
            
            logger.info(f"已暂停播放: {self.current_song}, 位置: {self.current_position}秒")
            return {"status": "success", "message": f"已暂停播放: {self.current_song}", "position": self.current_position}
        else:
            return {"status": "info", "message": f"歌曲 {self.current_song} 已经是暂停状态"}
    
    def _clear_audio_queue(self):
        """清空音频解码队列"""
        while not self.audio_decode_queue.empty():
            try:
                self.audio_decode_queue.get_nowait()
            except queue.Empty:
                break

    def _download_stream(self, url: str, chunk_queue: queue.Queue):
        """
        流式下载音频文件
        
        参数:
            url: 音频文件URL
            chunk_queue: 数据块队列
        """
        try:
            # 使用配置中的请求头
            headers = self.config.get("HEADERS", {}).copy()
            # 修改Accept-Encoding以支持流式下载
            headers.update({
                'Accept-Encoding': 'gzip, deflate, br',
                'Referer': 'https://music.163.com/'
            })
            
            session = requests.Session()
            session.trust_env = False

            # 添加重试机制
            for attempt in range(3):
                try:
                    response = session.get(url, stream=True, headers=headers, timeout=30)
                    response.raise_for_status()

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    # 使用更大的chunk大小提高下载效率
                    for chunk in response.iter_content(chunk_size=32768):
                        if self.stop_event.is_set():
                            logger.info("下载被中止")
                            break
                        if chunk:
                            chunk_queue.put(chunk)
                            downloaded += len(chunk)
                            # 每下载10%更新一次日志
                            if total_size > 0 and downloaded % (total_size // 10) < 32768:
                                logger.info(f"下载进度: {downloaded * 100 // total_size}%")
                    
                    # 下载成功，跳出重试循环
                    break
                    
                except requests.exceptions.RequestException as e:
                    if attempt == 2:  # 最后一次尝试
                        logger.error(f"下载失败 (尝试 {attempt + 1}/3): {str(e)}")
                        return
                    logger.warning(f"下载失败，正在重试 ({attempt + 1}/3)...")
                    time.sleep(1)  # 等待1秒后重试
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
        finally:
            # 标记下载结束
            chunk_queue.put(None)

    def _decode_audio_stream(self, process: subprocess.Popen):
        """
        解码音频流并将数据块放入队列
        
        参数:
            process: FFmpeg进程
        """
        try:
            buffer_size = 8192  # 增加读取缓冲区大小提高效率
            
            while not self.stop_event.is_set():
                # 读取固定大小的数据块
                chunk = process.stdout.read(buffer_size)
                if not chunk:
                    break
                # 将数据块放入队列
                self.audio_decode_queue.put(chunk)
        except Exception as e:
            logger.error(f"解码过程中出错: {str(e)}")
        finally:
            # 标记流结束
            self.audio_decode_queue.put(None)

    def _play_audio_stream(self):
        """
        播放解码后的音频流
        
        处理音频播放、暂停、恢复等逻辑，同时更新播放进度和歌词显示
        """
        try:
            # 初始化PyAudio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=4096
            )

            logger.info("开始播放音频流...")
            
            # 播放状态跟踪变量
            total_chunks = 0
            start_time = time.time()
            playback_started = False  # 标记是否已经开始播放
            
            # TTS优先级处理相关变量
            paused_for_tts = False  # 标记是否因为TTS而暂停
            tts_check_time = 0  # 上次检查TTS状态的时间
            pause_start_time = 0  # 暂停开始时间
            total_pause_time = 0  # 总暂停时间

            while not self.stop_event.is_set():
                # TTS优先级处理：每200ms检查一次应用程序是否正在说话
                current_time = time.time()
                if current_time - tts_check_time >= 0.2:
                    tts_check_time = current_time
                    paused_for_tts, pause_start_time, total_pause_time = self._handle_tts_priority(
                        stream, current_time, paused_for_tts, pause_start_time, total_pause_time
                    )

                # 如果因为TTS暂停了，就不处理音频数据
                if paused_for_tts:
                    time.sleep(0.1)
                    continue

                try:
                    # 从队列获取音频数据
                    chunk = self.audio_decode_queue.get(timeout=1)
                    
                    # 处理流结束标记
                    if chunk is None:
                        if self._check_stream_end(stream, total_chunks):
                            break
                        continue

                    # 播放音频数据
                    stream.write(chunk)
                    total_chunks += 1

                    # 标记播放已经开始（确保有足够的数据已经播放）
                    if not playback_started and total_chunks > 5:
                        playback_started = True
                        logger.info("音频播放已开始")

                    # 更新播放位置，考虑暂停时间
                    self.current_position = (time.time() - start_time - total_pause_time)
                    self.position_update_time = time.time()

                    # 显示歌词
                    self._update_lyrics()

                    # 更新播放进度显示（约每秒更新一次）
                    if total_chunks % 50 == 0:
                        self._update_progress_display()
                        
                    self.audio_decode_queue.task_done()
                    
                except queue.Empty:
                    # 如果队列为空但播放已经开始，可能是因为下载速度慢
                    if playback_started and total_chunks > 0:
                        logger.debug("音频队列暂时为空，等待更多数据...")
                    continue

            # 播放完成时更新位置
            if not self.stop_event.is_set() and playback_started and total_chunks > 100:
                logger.info(f"歌曲 '{self.current_song}' 播放完成")
                self.playing = False

        except Exception as e:
            logger.error(f"播放过程中出错: {str(e)}")
        finally:
            # 清理资源
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            if 'p' in locals():
                p.terminate()
            self.playing = False
            logger.info("音频播放结束，资源已释放")
    
    def _handle_tts_priority(self, stream, current_time, paused_for_tts, pause_start_time, total_pause_time):
        """
        处理TTS优先级逻辑
        
        在应用程序说话时暂停音乐播放，说话结束后恢复播放
        
        参数:
            stream: 音频流
            current_time: 当前时间
            paused_for_tts: 是否因为TTS而暂停
            pause_start_time: 暂停开始时间
            total_pause_time: 总暂停时间
        """
        # 检查应用程序是否正在说话
        if self.app and self.app.device_state == DeviceState.SPEAKING:
            if not paused_for_tts and stream.is_active():
                logger.info("应用程序正在说话，暂停音乐播放")
                paused_for_tts = True
                pause_start_time = current_time
                stream.stop_stream()
        elif paused_for_tts:
            # 如果之前因为TTS而暂停，现在恢复播放
            logger.info("应用程序说话结束，恢复音乐播放")
            paused_for_tts = False
            # 计算暂停时间
            total_pause_time += (current_time - pause_start_time)
            if not stream.is_active():
                stream.start_stream()
        
        return paused_for_tts, pause_start_time, total_pause_time

    def _check_stream_end(self, stream, total_chunks):
        """
        检查音频流是否结束
        
        参数:
            stream: 音频流
            total_chunks: 已播放的数据块数量
            
        返回:
            bool: 是否结束
        """
        # 确认是否真的播放结束，而不是因为缓冲区暂时为空
        if total_chunks > 0:
            # 再等待一小段时间，确认没有更多数据
            try:
                next_chunk = self.audio_decode_queue.get(timeout=2)
                if next_chunk is not None:
                    stream.write(next_chunk)
                    return False
            except queue.Empty:
                # 确认没有更多数据，可以结束播放
                logger.info("音频流结束")
                return True
        # 如果还没有播放任何数据，继续等待
        return False
    
    def _update_progress_display(self):
        """更新播放进度显示"""
        progress = self._get_progress()
        position_str = self._format_time(self.current_position)
        duration_str = self._format_time(self.total_duration)
        status_text = f"播放中: {position_str}/{duration_str} ({progress}%)"

        # 更新Application显示
        if self.app and self.app.display:
            # 更新状态栏显示播放进度
            self.app.display.update_status(status_text)
            logger.debug(f"更新播放进度: {status_text}")

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

    def _process_audio(self, url: str):
        """
        处理音频URL，实现并行的流式下载、转换和播放
        
        参数:
            url: 音频URL
        """
        try:
            # 创建下载队列
            download_queue = queue.Queue(maxsize=100)

            # 创建下载线程
            download_thread = threading.Thread(target=self._download_stream, args=(url, download_queue))
            download_thread.daemon = True
            download_thread.start()

            # 创建FFmpeg转换进程
            cmd = [
                'ffmpeg',
                '-f', 'mp3',  # 指定输入格式
                '-i', 'pipe:0',  # 从标准输入读取
                '-f', 's16le',  # 输出格式
                '-ar', '24000',  # 采样率
                '-ac', '1',      # 单声道
                'pipe:1'  # 输出到标准输出
            ]
            convert_process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE
            )

            # 创建解码线程
            decode_thread = threading.Thread(target=self._decode_audio_stream, args=(convert_process,))
            decode_thread.daemon = True
            decode_thread.start()

            # 创建播放线程
            play_thread = threading.Thread(target=self._play_audio_stream)
            play_thread.daemon = True
            play_thread.start()

            # 从下载队列读取数据并写入转换进程
            self._feed_download_to_converter(download_queue, convert_process)

            # 如果没有被中止，等待所有线程完成
            if not self.stop_event.is_set():
                download_thread.join()
                decode_thread.join()
                play_thread.join()

        except Exception as e:
            logger.error(f"音频处理过程中出错: {str(e)}")
        finally:
            # 清理资源
            if 'convert_process' in locals():
                try:
                    convert_process.terminate()
                except:
                    pass
            # 如果播放被中止，设置playing为False
            if self.stop_event.is_set():
                self.playing = False
    
    def _feed_download_to_converter(self, download_queue: queue.Queue, convert_process: subprocess.Popen):
        """
        将下载的数据喂给转换进程
        
        参数:
            download_queue: 下载队列
            convert_process: 转换进程
        """
        try:
            while not self.stop_event.is_set():
                try:
                    chunk = download_queue.get(timeout=1)
                    if chunk is None:
                        logger.info("下载完成，关闭转换进程输入")
                        break
                    convert_process.stdin.write(chunk)
                    download_queue.task_done()
                except queue.Empty:
                    continue
                except BrokenPipeError:
                    logger.error("管道已断开")
                    break
        finally:
            # 关闭转换进程的输入
            try:
                convert_process.stdin.close()
                logger.debug("已关闭转换进程输入")
            except:
                pass

    def _fetch_lyrics(self, song_mid: str):
        """
        获取歌词
        
        参数:
            song_mid: 歌曲ID
        """
        try:
            # 从配置中获取请求头和API URL
            headers = self.config.get("HEADERS", {})
            base_url = self.config.get("API", {}).get("BASE_URL", "http://localhost:3200")
            lyric_endpoint = self.config.get("API", {}).get("LYRIC_ENDPOINT", "/getLyric")

            lyric_url = f"{base_url}{lyric_endpoint}?songmid={song_mid}"
            logger.info(f"获取歌词URL: {lyric_url}")

            response = requests.get(lyric_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get('response') and data['response'].get('lyric'):
                raw_lyric = data['response']['lyric']
                self._parse_lyrics(raw_lyric)
                logger.info(f"成功获取歌词，共 {len(self.lyrics)} 行")
            else:
                logger.warning("未获取到歌词")
        except Exception as e:
            logger.error(f"获取歌词失败: {str(e)}")

    def _parse_lyrics(self, raw_lyric: str):
        """
        解析歌词文本，提取时间标签和歌词内容
        
        参数:
            raw_lyric: 原始歌词文本
        """
        self.lyrics = []
        lines = raw_lyric.split('\n')

        for line in lines:
            # 匹配时间标签 [mm:ss.xx]
            if line.startswith('[') and ']' in line:
                time_end = line.find(']')
                time_str = line[1:time_end]

                # 跳过非时间标签（元数据标签）
                if not (time_str.startswith('ti:') or time_str.startswith('ar:') or 
                        time_str.startswith('al:') or time_str.startswith('by:') or 
                        time_str.startswith('offset:')):
                    try:
                        # 解析时间
                        minutes, seconds = time_str.split(':')
                        time_seconds = float(minutes) * 60 + float(seconds)

                        # 提取歌词文本
                        lyric_text = line[time_end + 1:].strip()
                        
                        # 只添加非空歌词
                        if lyric_text:
                            self.lyrics.append((time_seconds, lyric_text))
                    except Exception as e:
                        logger.warning(f"解析歌词行失败: {line}, 错误: {str(e)}")

        # 按时间排序
        self.lyrics.sort(key=lambda x: x[0])
        logger.debug(f"解析完成，共 {len(self.lyrics)} 行有效歌词")

    def _update_lyrics(self):
        """
        根据当前播放位置更新歌词显示
        
        在适当的时间点显示对应的歌词，考虑TTS优先级
        """
        # 如果没有歌词或应用程序正在说话，不更新歌词
        if not self.lyrics or (self.app and self.app.device_state == DeviceState.SPEAKING):
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
            if self.app and self.app.device_state != DeviceState.SPEAKING:
                # 创建歌词文本副本，避免引用可能变化的变量
                lyric_text = text
                
                # 可选：在歌词前添加时间和进度信息
                # position_str = self._format_time(self.current_position)
                # duration_str = self._format_time(self.total_duration)
                # progress = self._get_progress()
                # display_text = f"[{position_str}/{duration_str}] {lyric_text}"
                
                # 使用schedule方法安全地更新UI
                self.app.schedule(lambda: self.app.set_chat_message("assistant", lyric_text))
                logger.debug(f"显示歌词: {lyric_text}")