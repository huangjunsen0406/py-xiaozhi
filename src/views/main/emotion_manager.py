# -*- coding: utf-8 -*-
"""
表情管理器模块 - 负责表情资源的加载和缓存.
"""

from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QUrl

from src.logging import get_logger
from src.utils.resource_finder import get_assets_dir

logger = get_logger()


class EmotionManager:
    """表情管理器 - 处理表情文件的查找、缓存和 URL 转换"""

    # 支持的表情文件扩展名
    EMOTION_EXTENSIONS = (".gif", ".png", ".jpg", ".jpeg", ".webp")

    def __init__(self):
        """初始化表情管理器"""
        self._emotion_cache: dict[str, str] = {}
        self._last_emotion_name: Optional[str] = None
        self._emotion_dir = get_assets_dir() / "emojis"

        if not self._emotion_dir.exists():
            logger.warning(f"表情目录不存在: {self._emotion_dir}")

    def get_emotion_url(self, emotion_name: str) -> str:
        """
        获取表情的 QML 可用 URL.

        Args:
            emotion_name: 表情名称

        Returns:
            表情的 file:// URL 或 emoji 字符
        """
        if emotion_name == self._last_emotion_name:
            # 快速路径：如果与上次相同，直接返回缓存
            return self._emotion_cache.get(emotion_name, "😊")

        self._last_emotion_name = emotion_name

        # 检查缓存
        if emotion_name in self._emotion_cache:
            return self._emotion_cache[emotion_name]

        # 查找并缓存
        asset_path = self._find_emotion_asset(emotion_name)
        url_or_text = self._to_qml_url(asset_path)
        self._emotion_cache[emotion_name] = url_or_text

        return url_or_text

    def _find_emotion_asset(self, emotion_name: str) -> str:
        """
        查找表情资源文件路径.

        Args:
            emotion_name: 表情名称

        Returns:
            表情文件的绝对路径，或回退到 neutral，或 emoji 字符
        """
        # 尝试查找指定的表情
        path = self._find_emotion_file(emotion_name)
        if path:
            return str(path)

        # 回退到 neutral
        neutral_path = self._find_emotion_file("neutral")
        if neutral_path:
            logger.debug(f"表情 {emotion_name} 不存在，使用 neutral")
            return str(neutral_path)

        # 最终回退到 emoji
        logger.warning(f"表情 {emotion_name} 和 neutral 都不存在，使用 emoji")
        return "😊"

    def _find_emotion_file(self, name: str) -> Optional[Path]:
        """
        在表情目录中查找指定名称的文件.

        Args:
            name: 表情名称（不含扩展名）

        Returns:
            找到的文件路径，或 None
        """
        for ext in self.EMOTION_EXTENSIONS:
            file_path = self._emotion_dir / f"{name}{ext}"
            if file_path.exists():
                return file_path
        return None

    @staticmethod
    def _to_qml_url(path: str) -> str:
        """
        将本地文件路径转换为 QML 可用的 file:// URL.

        Args:
            path: 文件路径或 emoji 字符

        Returns:
            QML 可用的 URL 字符串
        """
        if not path:
            return ""

        # 已经是 URL 格式，直接返回
        if path.startswith(("qrc:/", "file:")):
            return path

        # 仅当路径存在时才转换为 file URL，避免把 emoji 当作路径
        try:
            from pathlib import Path

            if Path(path).exists():
                return QUrl.fromLocalFile(path).toString()
        except Exception:
            pass

        # 不是文件路径（可能是 emoji），保持原样
        return path

    def clear_cache(self):
        """清空表情缓存"""
        self._emotion_cache.clear()
        self._last_emotion_name = None
        logger.debug("表情缓存已清空")

    def preload_emotions(self, emotion_names: list[str]):
        """
        预加载指定的表情到缓存.

        Args:
            emotion_names: 要预加载的表情名称列表
        """
        for name in emotion_names:
            self.get_emotion_url(name)
        logger.info(f"已预加载 {len(emotion_names)} 个表情")
