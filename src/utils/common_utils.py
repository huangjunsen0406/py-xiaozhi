"""
通用工具函数集合模块 包含文本转语音、浏览器操作、剪贴板等通用工具函数.
"""

import queue
import shutil
import threading
import time
import webbrowser
from typing import Optional

from src.utils.logging_config import get_logger

logger = get_logger(__name__)

# 全局音频播放队列和锁
_audio_queue = queue.Queue()
_audio_lock = threading.Lock()
_audio_worker_thread = None
_audio_worker_running = False
_audio_device_warmed_up = False


def _warm_up_audio_device():
    """
    预热音频设备，防止首字被吞.
    """
    global _audio_device_warmed_up
    if _audio_device_warmed_up:
        return

    try:
        import platform
        import subprocess

        system = platform.system()

        if system == "Darwin":
            subprocess.run(
                ["say", "-v", "Ting-Ting", "嗡"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Linux" and shutil.which("espeak"):
            subprocess.run(
                ["espeak", "-v", "zh", "嗡"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        elif system == "Windows":
            import win32com.client

            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak("嗡")

        _audio_device_warmed_up = True
        logger.info("已预热音频设备")
    except Exception as e:
        logger.warning(f"预热音频设备失败: {e}")


def _audio_queue_worker():
    """
    音频队列工作线程，确保音频按顺序播放且不被截断.
    """

    while _audio_worker_running:
        try:
            text = _audio_queue.get(timeout=1)
            if text is None:
                break

            with _audio_lock:
                logger.info(f"开始播放音频: {text[:50]}...")
                success = _play_system_tts(text)

                if not success:
                    logger.warning("系统TTS失败，尝试备用方案")
                    import os

                    if os.name == "nt":
                        _play_windows_tts(text, set_chinese_voice=False)
                    else:
                        _play_system_tts(text)

                time.sleep(0.5)  # 播放结束后的停顿，防止尾音被吞

            _audio_queue.task_done()

        except queue.Empty:
            continue
        except Exception as e:
            logger.error(f"音频队列工作线程出错: {e}")

    logger.info("音频队列工作线程已停止")


def _ensure_audio_worker():
    """
    确保音频工作线程正在运行.
    """
    global _audio_worker_thread, _audio_worker_running

    if _audio_worker_thread is None or not _audio_worker_thread.is_alive():
        _warm_up_audio_device()
        _audio_worker_running = True
        _audio_worker_thread = threading.Thread(target=_audio_queue_worker, daemon=True)
        _audio_worker_thread.start()
        logger.info("音频队列工作线程已启动")


def open_url(url: str) -> bool:
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
    try:
        import pyperclip

        pyperclip.copy(text)
        logger.info(f'文本 "{text}" 已复制到剪贴板')
        return True
    except ImportError:
        logger.warning("未安装pyperclip模块，无法复制到剪贴板")
        return False
    except Exception as e:
        logger.error(f"复制到剪贴板时出错: {e}")
        return False


def _play_windows_tts(text: str, set_chinese_voice: bool = True) -> bool:
    try:
        import win32com.client

        speaker = win32com.client.Dispatch("SAPI.SpVoice")

        if set_chinese_voice:
            try:
                voices = speaker.GetVoices()
                for i in range(voices.Count):
                    if "Chinese" in voices.Item(i).GetDescription():
                        speaker.Voice = voices.Item(i)
                        break
            except Exception as e:
                logger.warning(f"设置中文音色时出错: {e}")

        try:
            speaker.Rate = -2
        except Exception:
            pass

        enhanced_text = text + "。 。 。"
        speaker.Speak(enhanced_text)
        logger.info("已使用Windows语音合成播放文本")
        time.sleep(0.5)
        return True
    except ImportError:
        logger.warning("Windows TTS不可用，跳过音频播放")
        return False
    except Exception as e:
        logger.error(f"Windows TTS播放出错: {e}")
        return False


def _play_linux_tts(text: str) -> bool:
    import subprocess

    if shutil.which("espeak"):
        try:
            enhanced_text = text + "。 。 。"
            result = subprocess.run(
                ["espeak", "-v", "zh", "-s", "150", "-g", "10", enhanced_text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            time.sleep(0.5)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("espeak播放超时")
            return False
        except Exception as e:
            logger.error(f"espeak播放出错: {e}")
            return False
    else:
        logger.warning("espeak不可用，跳过音频播放")
        return False


def _play_macos_tts(text: str) -> bool:
    import subprocess

    if shutil.which("say"):
        try:
            enhanced_text = text + "。 。 。"
            result = subprocess.run(
                ["say", "-r", "180", enhanced_text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
            time.sleep(0.5)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("say命令播放超时")
            return False
        except Exception as e:
            logger.error(f"say命令播放出错: {e}")
            return False
    else:
        logger.warning("say命令不可用，跳过音频播放")
        return False


def _play_system_tts(text: str) -> bool:
    import os
    import platform

    if os.name == "nt":
        return _play_windows_tts(text)
    else:
        system = platform.system()
        if system == "Linux":
            return _play_linux_tts(text)
        elif system == "Darwin":
            return _play_macos_tts(text)
        else:
            logger.warning(f"不支持的系统 {system}，跳过音频播放")
            return False


def play_audio_nonblocking(text: str) -> None:
    try:
        _ensure_audio_worker()
        _audio_queue.put(text)
        logger.info(f"已将音频任务添加到队列: {text[:50]}...")
    except Exception as e:
        logger.error(f"添加音频任务到队列时出错: {e}")

        def audio_worker():
            try:
                _warm_up_audio_device()
                _play_system_tts(text)
            except Exception as e:
                logger.error(f"备用音频播放出错: {e}")

        threading.Thread(target=audio_worker, daemon=True).start()


def extract_verification_code(text: str) -> Optional[str]:
    try:
        import re

        # 激活相关关键词列表
        activation_keywords = [
            "登录",
            "控制面板",
            "激活",
            "验证码",
            "绑定设备",
            "添加设备",
            "输入验证码",
            "输入",
            "面板",
            "xiaozhi.me",
            "激活码",
        ]

        # 检查文本是否包含激活相关关键词
        has_activation_keyword = any(keyword in text for keyword in activation_keywords)

        if not has_activation_keyword:
            logger.debug(f"文本不包含激活关键词，跳过验证码提取: {text}")
            return None

        # 更精确的验证码匹配模式
        # 匹配6位数字的验证码，可能有空格分隔
        patterns = [
            r"验证码[：:]\s*(\d{6})",  # 验证码：123456
            r"输入验证码[：:]\s*(\d{6})",  # 输入验证码：123456
            r"输入\s*(\d{6})",  # 输入123456
            r"验证码\s*(\d{6})",  # 验证码123456
            r"激活码[：:]\s*(\d{6})",  # 激活码：123456
            r"(\d{6})[，,。.]",  # 123456，或123456。
            r"[，,。.]\s*(\d{6})",  # ，123456
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                code = match.group(1)
                logger.info(f"已从文本中提取验证码: {code}")
                return code

        # 如果有激活关键词但没有匹配到精确模式，尝试原始模式
        # 但要求数字周围有特定的上下文
        match = re.search(r"((?:\d\s*){6,})", text)
        if match:
            code = "".join(match.group(1).split())
            # 验证码应该是6位数字
            if len(code) == 6 and code.isdigit():
                logger.info(f"已从文本中提取验证码（通用模式）: {code}")
                return code

        logger.warning(f"未能从文本中找到验证码: {text}")
        return None
    except Exception as e:
        logger.error(f"提取验证码时出错: {e}")
        return None


def handle_verification_code(text: str) -> None:
    code = extract_verification_code(text)
    if not code:
        return

    copy_to_clipboard(code)
