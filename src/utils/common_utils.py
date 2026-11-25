"""通用工具函数模块（剪贴板与原子文件写入）."""

import os
import tempfile
from pathlib import Path

from src.logging import get_logger

logger = get_logger()


def atomic_write_bytes(
    target: Path,
    content: bytes,
    *,
    suffix: str = ".tmp",
    replace=os.replace,
) -> None:
    """将完整字节内容写入同目录临时文件、fsync 后原子替换目标文件."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=suffix, dir=target.parent
    )
    tmp_path = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        replace(tmp_path, target)
    finally:
        tmp_path.unlink(missing_ok=True)


def atomic_write_text(
    target: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    suffix: str = ".tmp",
    replace=os.replace,
) -> None:
    """原子写入 UTF-8 文本文件."""
    atomic_write_bytes(
        target, text.encode(encoding), suffix=suffix, replace=replace
    )


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
        logger.error(f"复制到剪贴板时出错: {e}", exc_info=True)
        return False
