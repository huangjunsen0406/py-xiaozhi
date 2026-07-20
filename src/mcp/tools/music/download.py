"""音乐下载（单一职责：解析直链 + HTTP 落盘）.

依赖 MusicCache 提供路径；不负责播放与搜歌。
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Any

import requests

from src.logging import get_logger

from .cache import MusicCache

logger = get_logger()


class MusicDownloader:
    """将远程音频下载到本地缓存."""

    def __init__(self, cache: MusicCache, config: dict[str, Any] | None = None) -> None:
        self._cache = cache
        self._config = config or {}

    def set_config(self, config: dict[str, Any]) -> None:
        self._config = config

    async def get_or_download(
        self,
        song_id: str,
        api_url: str,
        *,
        filename: str | None = None,
    ) -> Path | None:
        """缓存命中则返回路径，否则下载后返回."""
        self._cache.prepare()
        name = filename or f"{song_id}.mp3"
        # 优先按 song_id 找任意扩展名
        hit = self._cache.find_song_file(song_id)
        if hit is not None:
            logger.info(f"使用缓存: {hit}")
            return hit

        cache_path = self._cache.root / name
        if cache_path.exists():
            logger.info(f"使用缓存: {cache_path}")
            return cache_path

        return await self.download(api_url, name)

    async def resolve_play_url(self, api_url: str) -> str | None:
        """请求直链 API 解析实际音频 URL."""
        try:
            headers = {
                "X-Request-Key": self._config.get("URL_API_KEY", "share-v3"),
                "User-Agent": "lx-music-request",
            }
            response = await asyncio.to_thread(
                requests.get,
                api_url,
                headers=headers,
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()

            real_url = None
            if isinstance(data, dict):
                real_url = data.get("url")
                if not real_url:
                    inner = data.get("data")
                    if isinstance(inner, dict):
                        real_url = inner.get("url")
                    elif isinstance(inner, str):
                        real_url = inner

            if not real_url:
                logger.error(f"未能从直链 API 提取播放 URL: {data}")
                return None

            logger.info(f"解析到播放地址: {real_url[:80]}...")
            return real_url
        except Exception as e:
            logger.error(f"解析播放 URL 失败: {e}", exc_info=True)
            return None

    def _sync_download(
        self, download_url: str, headers: dict, temp_path: Path, cache_path: Path
    ) -> Path:
        response = requests.get(
            download_url, headers=headers, stream=True, timeout=30
        )
        response.raise_for_status()
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        shutil.move(str(temp_path), str(cache_path))
        return cache_path

    async def download(self, api_url: str, filename: str) -> Path | None:
        """下载到缓存目录."""
        self._cache.prepare()
        temp_path = None
        try:
            download_url = await self.resolve_play_url(api_url)
            if not download_url:
                return None

            temp_path = self._cache.temp_path(filename)
            cache_path = self._cache.root / filename

            result = await asyncio.to_thread(
                self._sync_download,
                download_url,
                self._config.get("HEADERS", {}),
                temp_path,
                cache_path,
            )
            logger.info(f"音乐下载完成并缓存: {result}")
            return result
        except Exception as e:
            logger.error(f"下载失败: {e}", exc_info=True)
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_e:
                    logger.debug(f"清理临时文件失败: {cleanup_e}")
            return None
