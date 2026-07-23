"""激活验证码副作用：剪贴板与语音播报."""

from __future__ import annotations

from typing import Optional

from src.logging import get_logger

logger = get_logger()


def apply_code_side_effects(code: str, message: Optional[str] = None) -> None:
    """日志 + 剪贴板 + 播报；不负责 CLI/GUI 文案."""
    if not code:
        return
    msg = message or "请在控制面板输入验证码"
    logger.info(f"激活提示: {msg}")
    logger.info(f"验证码: {code}")

    text = f".请登录到控制面板添加设备，输入验证码：{' '.join(code)}..."
    try:
        from src.utils.common_utils import handle_verification_code

        handle_verification_code(text)
    except Exception as e:
        logger.debug(f"复制验证码失败: {e}")

    try:
        from src.utils.activation_announcer import announce_activation_code

        announce_activation_code(code, locale="zh-CN")
    except Exception as e:
        logger.debug(f"验证码播报失败: {e}")


def announce_code(code: str) -> None:
    """仅播报（轮询重试时用）."""
    if not code:
        return
    from src.utils.activation_announcer import announce_activation_code

    announce_activation_code(code, locale="zh-CN")
