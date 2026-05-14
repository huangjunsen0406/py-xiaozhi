"""
通用工具函数集合模块.

包含浏览器操作、剪贴板、验证码提取等通用工具函数。
"""

import re
import webbrowser
from typing import Optional

from src.logging import get_logger

logger = get_logger()


def open_url(url: str) -> bool:
    """打开网页链接."""
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
    """复制文本到剪贴板."""
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


def extract_verification_code(text: str) -> Optional[str]:
    """从文本中提取验证码."""
    try:
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
        patterns = [
            r"验证码[：:]\s*(\d{6})",
            r"输入验证码[：:]\s*(\d{6})",
            r"输入\s*(\d{6})",
            r"验证码\s*(\d{6})",
            r"激活码[：:]\s*(\d{6})",
            r"(\d{6})[，,。.]",
            r"[，,。.]\s*(\d{6})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                code = match.group(1)
                logger.info(f"已从文本中提取验证码: {code}")
                return code

        # 通用模式匹配
        match = re.search(r"((?:\d\s*){6,})", text)
        if match:
            code = "".join(match.group(1).split())
            if len(code) == 6 and code.isdigit():
                logger.info(f"已从文本中提取验证码（通用模式）: {code}")
                return code

        logger.warning(f"未能从文本中找到验证码: {text}")
        return None
    except Exception as e:
        logger.error(f"提取验证码时出错: {e}")
        return None


def handle_verification_code(text: str) -> None:
    """处理验证码：提取并复制到剪贴板."""
    code = extract_verification_code(text)
    if code:
        copy_to_clipboard(code)
