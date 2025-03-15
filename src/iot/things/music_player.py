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
from typing import Optional
from tqdm import tqdm
import logging

logger = logging.getLogger("MusicPlayer")

class MusicPlayer(Thing):
    def __init__(self):
        super().__init__("MusicPlayer", "在线音乐播放器，优先播放本地音乐如果没有再播放在线音乐")
        self.current_song = ""  # 当前歌曲名称
        self.playing = False    # 播放状态
        self.audio_decode_queue = queue.Queue(maxsize=100)  # 音频解码队列
        self.play_thread = None  # 播放线程
        self.stop_event = threading.Event()  # 停止事件
        
        logger.info("音乐播放器初始化完成")

        # 定义属性
        self.add_property("current_song", "当前播放的歌曲", lambda: self.current_song)
        self.add_property("playing", "是否正在播放", lambda: self.playing)

        # 定义方法
        self.add_method(
            "Play", 
            "播放指定歌曲",
            [
                Parameter("song_name", "歌曲名称", ValueType.STRING, True)
            ],
            lambda params: self._play(params["song_name"].get_value())
        )

        self.add_method("Pause", "暂停播放", [],
                        lambda params: self._pause())

    def _play(self, song_name):
        # 如果已经在播放，先停止当前播放
        if self.playing:
            self._pause()
        
        self.current_song = song_name
        self.playing = True
        
        # 通过API搜索获取歌曲ID
        try:
            # 设置请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity',  # 不使用任何压缩
                'Connection': 'keep-alive',
                'Referer': 'https://music.163.com/',
                'Cookie': ''  # 添加空Cookie头
            }
            
            # 1. 先搜索歌曲获取ID
            search_url = f"http://localhost:3000/search?keywords={song_name}"
            logger.info(f"搜索歌曲URL: {search_url}")
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # 获取第一首歌曲的ID
            if data.get('result') and data['result'].get('songs') and len(data['result']['songs']) > 0:
                song_id = data['result']['songs'][0]['id']
                logger.info(f"获取到歌曲ID: {song_id}")
                
                # 2. 通过ID获取实际播放链接
                url_api = f"http://localhost:3000/song/url?id={song_id}"
                logger.info(f"获取歌曲URL的API: {url_api}")
                
                # 尝试直接使用浏览器中可以工作的URL
                try:
                    # 使用GET请求获取歌曲URL
                    url_response = requests.get(url_api, headers=headers, timeout=10)
                    logger.info(f"URL API响应状态码: {url_response.status_code}")
                    logger.info(f"URL API响应内容: {url_response.text[:200]}...")  # 记录响应内容的前200个字符
                    
                    url_response.raise_for_status()
                    url_data = url_response.json()
                    
                    if url_data.get('code') == 200 and url_data.get('data') and len(url_data['data']) > 0 and url_data['data'][0].get('url'):
                        url = url_data['data'][0]['url']
                        logger.info(f"获取到歌曲URL: {url}")
                    else:
                        # 如果API返回了结果但没有URL，使用直接构建的URL
                        url = f"http://music.163.com/song/media/outer/url?id={song_id}.mp3"
                        logger.warning(f"API未返回URL，使用直接构建的URL: {url}")
                except Exception as e:
                    # 如果API请求失败，使用直接构建的URL
                    url = f"http://music.163.com/song/media/outer/url?id={song_id}.mp3"
                    logger.warning(f"获取URL失败: {str(e)}，使用直接构建的URL: {url}")
            else:
                # 如果没有找到歌曲，使用默认ID
                url = f"http://music.163.com/song/media/outer/url?id=2670088128.mp3"
                logger.warning(f"未找到歌曲 '{song_name}'，使用默认URL")
                return {"status": "error", "message": f"未找到歌曲 '{song_name}'"}
        except Exception as e:
            # 搜索失败时使用默认ID
            url = f"http://music.163.com/song/media/outer/url?id=2670088128.mp3"
            logger.error(f"搜索歌曲失败: {str(e)}，使用默认URL")
            return {"status": "error", "message": f"搜索歌曲失败: {str(e)}"}
        
        logger.info(f"正在播放: {song_name}, URL: {url}")
        
        # 创建并启动播放线程
        self.stop_event.clear()
        self.play_thread = threading.Thread(
            target=self._process_audio,
            args=(url,),
            daemon=True
        )
        self.play_thread.start()
        
        return {"status": "success", "message": f"正在播放: {song_name}"}

    def _pause(self):
        if not self.current_song:
            return {"status": "error", "message": "没有正在播放的歌曲"}
        
        if self.playing:
            self.playing = False
            self.stop_event.set()  # 设置停止事件
            
            # 清空队列
            while not self.audio_decode_queue.empty():
                try:
                    self.audio_decode_queue.get_nowait()
                except queue.Empty:
                    break
            
            # 等待播放线程结束
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=2.0)
            
            logger.info(f"已暂停播放: {self.current_song}")
            return {"status": "success", "message": f"已暂停播放: {self.current_song}"}
        else:
            return {"status": "info", "message": f"歌曲 {self.current_song} 已经是暂停状态"}

    def _download_stream(self, url, chunk_queue):
        """流式下载音频文件"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Referer': 'https://music.163.com/'
            }
            session = requests.Session()
            session.trust_env = False

            # 添加重试机制
            for attempt in range(3):
                try:
                    response = session.get(url, stream=True, headers=headers, timeout=30)
                    response.raise_for_status()

                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=32768):  # 增加chunk大小
                        if self.stop_event.is_set():
                            logger.info("下载被中止")
                            break
                        if chunk:
                            chunk_queue.put(chunk)
                            downloaded += len(chunk)
                            # 每下载10%更新一次日志
                            if total_size > 0 and downloaded % (total_size // 10) < 32768:
                                logger.info(f"下载进度: {downloaded * 100 // total_size}%")
                    break  # 下载成功，跳出重试循环
                except requests.exceptions.RequestException as e:
                    if attempt == 2:  # 最后一次尝试
                        logger.error(f"下载失败 (尝试 {attempt + 1}/3): {str(e)}")
                        return
                    logger.warning(f"下载失败，正在重试 ({attempt + 1}/3)...")
                    time.sleep(1)  # 等待1秒后重试
                    continue
        except Exception as e:
            logger.error(f"下载失败: {str(e)}")
        finally:
            chunk_queue.put(None)

    def _decode_audio_stream(self, process):
        """解码音频流并将数据块放入队列"""
        try:
            while not self.stop_event.is_set():
                # 读取固定大小的数据块
                chunk = process.stdout.read(8192)  # 增加读取缓冲区大小
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
        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=24000,
                output=True,
                frames_per_buffer=4096
            )

            logger.info("开始播放音频流...")
            total_chunks = 0

            while not self.stop_event.is_set():
                try:
                    chunk = self.audio_decode_queue.get(timeout=1)
                    if chunk is None:
                        break
                    stream.write(chunk)
                    total_chunks += 1
                    if total_chunks % 100 == 0:  # 每100个数据块更新一次进度
                        logger.debug(f"已播放 {total_chunks} 个数据块")
                    self.audio_decode_queue.task_done()
                except queue.Empty:
                    continue

            logger.info("播放完成!")

        except Exception as e:
            logger.error(f"播放过程中出错: {str(e)}")
        finally:
            if 'stream' in locals():
                stream.stop_stream()
                stream.close()
            if 'p' in locals():
                p.terminate()
            self.playing = False

    def _process_audio(self, url):
        """处理音频URL，实现并行的流式下载、转换和播放"""
        try:
            # 创建下载队列
            download_queue = queue.Queue(maxsize=100)

            # 创建下载线程
            download_thread = threading.Thread(target=self._download_stream, args=(url, download_queue))
            download_thread.daemon = True
            download_thread.start()

            # 创建转换进程
            cmd = [
                'ffmpeg',
                '-f', 'mp3',  # 指定输入格式
                '-i', 'pipe:0',  # 从标准输入读取
                '-f', 's16le',  # 输出格式
                '-ar', '24000',
                '-ac', '1',
                'pipe:1'  # 输出到标准输出
            ]
            convert_process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # 创建解码线程
            decode_thread = threading.Thread(target=self._decode_audio_stream, args=(convert_process,))
            decode_thread.daemon = True
            decode_thread.start()

            # 创建播放线程
            play_thread = threading.Thread(target=self._play_audio_stream)
            play_thread.daemon = True
            play_thread.start()

            # 从下载队列读取数据并写入转换进程
            while not self.stop_event.is_set():
                try:
                    chunk = download_queue.get(timeout=1)
                    if chunk is None:
                        break
                    convert_process.stdin.write(chunk)
                    download_queue.task_done()
                except queue.Empty:
                    continue
                except BrokenPipeError:
                    logger.error("管道已断开")
                    break
            
            # 关闭转换进程的输入
            try:
                convert_process.stdin.close()
            except:
                pass

            # 如果没有被中止，等待所有线程完成
            if not self.stop_event.is_set():
                download_thread.join()
                decode_thread.join()
                play_thread.join()

        except Exception as e:
            logger.error(f"音频处理过程中出错: {str(e)}")
        finally:
            if 'convert_process' in locals():
                try:
                    convert_process.terminate()
                except:
                    pass
            # 如果播放被中止，设置playing为False
            if self.stop_event.is_set():
                self.playing = False
