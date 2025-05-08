"""
通用工具函数集合模块
包含文本转语音、浏览器操作、剪贴板等通用工具函数
"""
import logging
import shutil
import webbrowser
from typing import Optional
import asyncio
import traceback

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

def open_url(url: str) -> bool:
    """
    打开指定URL的网页
    
    Args:
        url: 要打开的URL
        
    Returns:
        bool: 是否成功打开
    """
    try:
        success = webbrowser.open(url)
        if success:
            logger.info(f"已成功打开网页: {url}")
        else:
            logger.warning(f"无法打开网页: {url}")
        return success
    except Exception as e:
        logger.error(f"打开网页时出错: {e}")
        return False

def copy_to_clipboard(text: str) -> bool:
    """
    复制文本到剪贴板
    
    Args:
        text: 要复制的文本
        
    Returns:
        bool: 是否成功复制
    """
    try:
        import pyperclip
        pyperclip.copy(text)
        logger.info(f"文本 \"{text}\" 已复制到剪贴板")
        return True
    except ImportError:
        logger.warning("未安装pyperclip模块，无法复制到剪贴板")
        return False
    except Exception as e:
        logger.error(f"复制到剪贴板时出错: {e}")
        return False

async def text_to_opus_audio(text: str) -> Optional[list]:
    """
    将文本转换为Opus编码的音频数据

    Args:
        text: 要转换的文本

    Returns:
        Optional[list]: Opus编码的音频帧列表，失败时返回None
    """
    try:
        from src.utils.tts_utility import TtsUtility
        from src.constants.constants import AudioConfig

        tts_utility = TtsUtility(AudioConfig)

        # 生成 Opus 音频数据包
        opus_frames = await tts_utility.text_to_opus_audio(text)

        if opus_frames:
            logger.info(f"已成功将文本转换为{len(opus_frames)}个Opus音频帧")
            return opus_frames
        else:
            logger.error("生成音频失败")
            return None

    except Exception as e:
        logger.error(f"文本转音频时出错: {e}")
        logger.error(traceback.format_exc())
        return None

def play_audio_nonblocking(text: str) -> None:
    """
    在非阻塞模式下播放文本音频 - 不使用asyncio，避免阻塞

    这个函数不返回任何值，也不抛出任何异常，确保始终快速返回

    Args:
        text: 要播放的文本
    """
    # 在完全独立的线程中处理所有音频相关操作
    import threading

    def audio_worker():
        try:
            # 这个函数在完全独立的线程中运行
            import os
            import subprocess
            import tempfile

            # 检查是否安装了espeak
            try:
                if os.name == 'nt':  # Windows
                    # 尝试使用Windows内置的语音合成
                    import win32com.client
                    speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    # 设置为中文音色（如果有）
                    try:
                        voices = speaker.GetVoices()
                        for i in range(voices.Count):
                            if "Chinese" in voices.Item(i).GetDescription():
                                speaker.Voice = voices.Item(i)
                                break
                    except:
                        pass
                    # 播放文本
                    speaker.Speak(text)
                    logger.info(f"已使用Windows语音合成播放文本")
                else:  # Linux/Mac
                    # 使用espeak或say命令
                    if shutil.which('espeak'):
                        subprocess.Popen(['espeak', '-v', 'zh', text],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                        logger.info(f"已使用espeak播放文本")
                    elif shutil.which('say'):  # macOS
                        subprocess.Popen(['say', text],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
                        logger.info(f"已使用say播放文本")
                    else:
                        logger.warning("未找到可用的文本到语音命令")
            except Exception as e:
                logger.warning(f"使用系统TTS时出错: {e}")
                # 失败时回退到opus方法
                fallback_opus_tts()

        except Exception as e:
            # 完全捕获所有异常，确保线程安全退出
            logger.error(f"音频工作线程出错: {e}")

    def fallback_opus_tts():
        """使用opus实现的备用TTS方式"""
        try:
            # 在这个函数中实现完整的opus音频播放逻辑
            import asyncio

            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 确保Opus库已经设置好
            from src.utils.opus_loader import setup_opus
            setup_opus()

            # 导入必要的库
            import opuslib
            import pyaudio
            import numpy as np
            from src.constants.constants import AudioConfig

            async def generate_and_play():
                # 转换文本到opus音频
                opus_frames = await text_to_opus_audio(text)
                if not opus_frames:
                    return

                # 创建Opus解码器
                decoder = opuslib.Decoder(AudioConfig.OUTPUT_SAMPLE_RATE, AudioConfig.CHANNELS)

                # 创建PyAudio实例
                p = pyaudio.PyAudio()

                # 打开音频输出流
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=AudioConfig.CHANNELS,
                    rate=AudioConfig.OUTPUT_SAMPLE_RATE,
                    output=True
                )

                # 解码并播放每一帧
                for frame in opus_frames:
                    # 解码Opus帧到PCM
                    pcm = decoder.decode(frame, AudioConfig.OUTPUT_FRAME_SIZE)
                    # 转换为numpy数组以便处理
                    pcm_array = np.frombuffer(pcm, dtype=np.int16)
                    # 播放音频
                    stream.write(pcm_array.tobytes())

                # 清理资源
                stream.stop_stream()
                stream.close()
                p.terminate()

                logger.info(f"文本 \"{text}\" 已使用opus音频播放")

            # 运行协程直到完成
            loop.run_until_complete(generate_and_play())
            # 关闭事件循环
            loop.close()

        except Exception as e:
            logger.error(f"opus音频回退方案出错: {e}")

    # 创建并启动线程
    audio_thread = threading.Thread(target=audio_worker)
    audio_thread.daemon = True
    audio_thread.start()
    logger.info("已启动非阻塞音频播放线程")


def extract_verification_code(text: str) -> Optional[str]:
    """
    从文本中提取6位验证码，支持中间带空格的形式

    Args:
        text: 包含验证码的文本

    Returns:
        Optional[str]: 提取的验证码，如果未找到则返回None
    """
    try:
        import re
        # 匹配类似 222944 或 2 2 2 9 4 4 这种形式
        match = re.search(r'((?:\d\s*){6,})', text)
        if match:
            code_with_spaces = match.group(1)
            code = ''.join(code_with_spaces.split())  # 去除空格
            logger.info(f"已从文本中提取验证码: {code}")
            return code
        else:
            logger.warning(f"未能从文本中找到验证码: {text}")
            return None
    except Exception as e:
        logger.error(f"提取验证码时出错: {e}")
        return None


def handle_verification_code(text: str) -> None:
    """
    处理验证码文本：提取验证码，复制到剪贴板，打开网站

    Args:
        text: 包含验证码的文本
    """
    # 提取验证码
    code = extract_verification_code(text)
    if not code:
        return

    # 尝试复制到剪贴板
    copy_to_clipboard(code)

    # 从配置中获取OTA_URL的域名部分
    from src.utils.config_manager import ConfigManager
    config = ConfigManager.get_instance()
    ota_url = config.get_config("SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL", "")
    # 尝试打开浏览器，仅打开根域名
    open_url(ota_url)