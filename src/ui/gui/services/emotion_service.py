# -*- coding: utf-8 -*-
"""表情服务 - 管理表情资源."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl

from src.logging import get_logger
from src.utils.resource_finder import get_assets_dir

logger = get_logger()


class EmotionService(QObject):
    """表情服务 - 处理表情文件的查找和 URL 转换."""

    EXTENSIONS = (".gif", ".png", ".jpg", ".jpeg", ".webp")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cache: dict[str, str] = {}
        self._emotion_dir = get_assets_dir() / "emojis"

        if not self._emotion_dir.exists():
            logger.warning(f"表情目录不存在: {self._emotion_dir}")

    def get_emotion_url(self, emotion_name: str) -> str:
        """获取表情的 QML 可用 URL.

        Args:
            emotion_name: 表情名称

        Returns:
            file:// URL 或 emoji 字符
        """
        # 检查缓存
        if emotion_name in self._cache:
            return self._cache[emotion_name]

        # 查找文件
        path = self._find_emotion_file(emotion_name)
        if not path:
            # 回退到 neutral
            path = self._find_emotion_file("neutral")

        # 转换为 URL
        if path:
            url = QUrl.fromLocalFile(str(path)).toString()
        else:
            url = "😊"  # 最终回退
            logger.warning(f"表情 {emotion_name} 未找到，使用 emoji")

        self._cache[emotion_name] = url
        return url

    def _find_emotion_file(self, name: str) -> Optional[Path]:
        """查找表情文件."""
        for ext in self.EXTENSIONS:
            file_path = self._emotion_dir / f"{name}{ext}"
            if file_path.exists():
                return file_path
        return None

    def clear_cache(self):
        """清空缓存."""
        self._cache.clear()

    def preload(self, names: list[str]):
        """预加载表情."""
        for name in names:
            self.get_emotion_url(name)
        logger.debug(f"已预加载 {len(names)} 个表情")
