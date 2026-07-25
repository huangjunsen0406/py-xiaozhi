"""音乐下载：解析直链；后台 FFmpeg copy 预取到本地缓存."""

from __future__ import annotations

import asyncio
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

from src.logging import get_logger
from src.utils.resource_finder import get_ffmpeg_path

from .cache import MusicCache

logger = get_logger()

# 直链搞不定时，走酷我官方试听
_KUWO_PLAYURL = "https://wapi.kuwo.cn/api/v1/www/music/playUrl"
_QUALITY_FALLBACKS = ("320k", "128k")

_SUBPROCESS_KW = (
    {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
)


class MusicDownloader:
    """解析播放地址；可选后台 copy 整首到缓存（按网速，不跟播放进度走）."""

    def __init__(self, cache: MusicCache, config: dict[str, Any] | None = None) -> None:
        self._cache = cache
        self._config = config or {}
        # 上次失败原因，给上层提示用
        self.last_error: str | None = None
        self._prefetch_task: asyncio.Task | None = None
        self._prefetch_song_id: str | None = None

    def set_config(self, config: dict[str, Any]) -> None:
        self._config = config

    async def get_or_download(
        self,
        song_id: str,
        api_url: str,
        *,
        filename: str | None = None,
    ) -> Path | None:
        """有缓存直接用，没有再下载."""
        self._cache.prepare()
        name = filename or f"{song_id}.mp3"
        hit = self._cache.find_song_file(song_id)
        if hit is not None:
            logger.info(f"使用缓存: {hit}")
            return hit

        cache_path = self._cache.root / name
        if cache_path.exists():
            logger.info(f"使用缓存: {cache_path}")
            return cache_path

        return await self.download(api_url, name, song_id=song_id)

    @staticmethod
    def _extract_url_from_payload(data: Any) -> str | None:
        # 各家 JSON 字段不太一样，尽量抠出 url
        if not isinstance(data, dict):
            return None

        real_url = data.get("url")
        if isinstance(real_url, str) and real_url.startswith("http"):
            return real_url

        inner = data.get("data")
        if isinstance(inner, dict):
            nested = inner.get("url")
            if isinstance(nested, str) and nested.startswith("http"):
                return nested
        elif isinstance(inner, str) and inner.startswith("http"):
            return inner

        return None

    @staticmethod
    def _describe_api_failure(data: Any) -> str:
        if not isinstance(data, dict):
            return "直链 API 返回无法解析的数据"

        code = data.get("code")
        msg = str(data.get("msg") or data.get("message") or "").strip()

        # lx-music-api 常见 code
        if code == 1 or "禁止批量下载" in msg or "block ip" in msg.lower():
            return (
                "直链 API 已封禁当前 IP（禁止批量下载）。"
                "可切换网络/IP，或在设置中更换 MUSIC.URL_API"
            )
        if code == 5 or "too many" in msg.lower():
            return "直链 API 请求过于频繁，请稍后再试"
        if code == 2:
            return "直链 API 获取播放地址失败（曲库无源或解析失败）"
        if code == 4:
            return "直链 API 内部错误"
        if code == 6:
            return "直链 API 参数错误"

        if msg:
            return f"直链 API 失败: {msg}"
        return f"直链 API 未能返回播放 URL: {data}"

    def _lx_headers(self) -> dict[str, str]:
        # 对齐 Huibq/keep-alive render_api.js：只认 Key + UA
        return {
            "X-Request-Key": self._config.get("URL_API_KEY", "share-v3"),
            "User-Agent": "lx-music-request",
            "Content-Type": "application/json",
        }

    def _browser_headers(self) -> dict[str, str]:
        # 酷我官方 playUrl 用
        headers = dict(self._config.get("HEADERS") or {})
        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        )
        headers.setdefault("Referer", "https://www.kuwo.cn/")
        headers.setdefault("Accept", "application/json, text/plain, */*")
        return headers

    def media_headers(self, media_url: str) -> dict[str, str]:
        """给 CDN / FFmpeg 流式播放用的请求头（不是 JSON API 那套）."""
        host = (urlparse(media_url).hostname or "").lower()
        ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        headers = {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        }
        if "kuwo" in host or "sycdn" in host or "bd-lv" in host:
            headers["Referer"] = "https://www.kuwo.cn/"
            headers["Origin"] = "https://www.kuwo.cn"
        return headers

    # 旧名
    def _download_headers(self, download_url: str) -> dict[str, str]:
        return self.media_headers(download_url)

    async def _fetch_json(
        self, url: str, headers: dict[str, str], *, timeout: int = 15
    ) -> Any | None:
        try:
            response = await asyncio.to_thread(
                requests.get, url, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(
                f"请求失败 {urlparse(url).netloc}: {e}", exc_info=True
            )
            return None

    def _candidate_lx_urls(self, api_url: str) -> list[str]:
        # 先按配置音质试，再试 128k
        urls = [api_url]
        m = re.search(r"/url/[^/]+/[^/]+/([^/?#]+)", api_url)
        if not m:
            return urls
        current_quality = m.group(1)
        for q in _QUALITY_FALLBACKS:
            if q == current_quality:
                continue
            alt = re.sub(
                r"(/url/[^/]+/[^/]+/)[^/?#]+",
                rf"\g<1>{q}",
                api_url,
                count=1,
            )
            if alt not in urls:
                urls.append(alt)
        return urls

    async def _resolve_via_lx_api(self, api_url: str) -> tuple[str | None, str | None]:
        last_reason: str | None = None
        headers = self._lx_headers()

        for candidate in self._candidate_lx_urls(api_url):
            logger.debug(f"尝试直链 API: {candidate}")
            data = await self._fetch_json(candidate, headers)
            if data is None:
                last_reason = "直链 API 网络请求失败"
                continue

            real_url = self._extract_url_from_payload(data)
            if real_url:
                logger.info(f"直链 API 解析成功: {real_url[:80]}...")
                return real_url, None

            last_reason = self._describe_api_failure(data)
            logger.warning(f"直链 API 未返回 URL: {data}")

            # IP 被封了换音质也没用
            if "封禁" in (last_reason or "") or "禁止批量下载" in str(data):
                break

        return None, last_reason

    async def _resolve_via_kuwo_official(
        self, song_id: str
    ) -> tuple[str | None, str | None]:
        # 免费歌能听；付费歌官方会直接说不行
        if not song_id or song_id == "unknown":
            return None, "缺少歌曲 ID，无法回退官方接口"

        headers = self._browser_headers()
        last_reason: str | None = None

        for br in ("320kmp3", "128kmp3"):
            url = f"{_KUWO_PLAYURL}?mid={song_id}&type=music&httpsStatus=1&br={br}"
            logger.debug(f"尝试酷我官方 playUrl: mid={song_id} br={br}")
            data = await self._fetch_json(url, headers)
            if data is None:
                last_reason = "酷我官方接口网络请求失败"
                continue

            real_url = self._extract_url_from_payload(data)
            if real_url:
                logger.info(f"酷我官方接口解析成功: {real_url[:80]}...")
                return real_url, None

            msg = ""
            if isinstance(data, dict):
                msg = str(data.get("msg") or data.get("message") or "").strip()
            if "付费" in msg:
                last_reason = f"该歌曲为付费内容，官方接口无法试听（{msg}）"
                break
            last_reason = msg or f"酷我官方接口未返回 URL: {data}"
            logger.warning(last_reason)

        return None, last_reason

    async def resolve_play_url(
        self, api_url: str, *, song_id: str | None = None
    ) -> str | None:
        # 直链 → 降音质 → 官方接口
        self.last_error = None
        reasons: list[str] = []

        try:
            real_url, reason = await self._resolve_via_lx_api(api_url)
            if real_url:
                return real_url
            if reason:
                reasons.append(reason)

            # 没传 song_id 时从 url 路径里抠
            sid = song_id
            if not sid or sid == "unknown":
                m = re.search(r"/url/[^/]+/([^/]+)/", api_url)
                if m:
                    sid = m.group(1)

            if sid:
                real_url, reason = await self._resolve_via_kuwo_official(sid)
                if real_url:
                    return real_url
                if reason:
                    reasons.append(reason)

            self.last_error = "；".join(reasons) if reasons else "未能解析播放地址"
            logger.error(f"未能解析播放 URL: {self.last_error}")
            return None
        except Exception as e:
            self.last_error = f"解析播放 URL 异常: {e}"
            logger.error(self.last_error, exc_info=True)
            return None

    def _sync_download(
        self, download_url: str, headers: dict, temp_path: Path, cache_path: Path
    ) -> Path:
        # CDN 偶发 RemoteDisconnected，多试两次
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                if temp_path.exists():
                    temp_path.unlink()
                with requests.get(
                    download_url,
                    headers=headers,
                    stream=True,
                    timeout=45,
                    allow_redirects=True,
                ) as response:
                    response.raise_for_status()
                    with open(temp_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                if temp_path.stat().st_size <= 0:
                    raise IOError("下载文件为空")
                shutil.move(str(temp_path), str(cache_path))
                return cache_path
            except (requests.RequestException, OSError) as e:
                last_err = e
                logger.warning(
                    f"下载重试 {attempt + 1}/3 失败: {e}"
                )
        assert last_err is not None
        raise last_err

    async def download(
        self, api_url: str, filename: str, *, song_id: str | None = None
    ) -> Path | None:
        """下载并写入缓存目录."""
        self._cache.prepare()
        temp_path = None
        try:
            download_url = await self.resolve_play_url(api_url, song_id=song_id)
            if not download_url:
                return None

            temp_path = self._cache.temp_path(filename)
            cache_path = self._cache.root / filename
            headers = self.media_headers(download_url)
            logger.debug(
                f"开始下载音频: host={urlparse(download_url).hostname}"
            )

            result = await asyncio.to_thread(
                self._sync_download,
                download_url,
                headers,
                temp_path,
                cache_path,
            )
            logger.info(f"音乐下载完成并缓存: {result}")
            return result
        except Exception as e:
            self.last_error = f"下载失败: {e}"
            logger.error(self.last_error, exc_info=True)
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_e:
                    logger.debug(f"清理临时文件失败: {cleanup_e}")
            return None

    def start_prefetch(
        self,
        media_url: str,
        song_id: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """后台按网速 FFmpeg -c copy 整首落盘，不跟播放进度同步.

        类似 HTML audio 的缓冲：播的同时尽快把整文件拉完，听完前也可能已缓存好。
        换歌会取消上一次预取；暂停/停止当前歌不取消（继续缓冲）。
        """
        if not song_id or song_id == "unknown":
            return
        self._cache.prepare()
        if self._cache.find_song_file(song_id) is not None:
            logger.debug(f"已有缓存，跳过预取: {song_id}")
            return

        # 同一首歌已在预取
        if (
            self._prefetch_task
            and not self._prefetch_task.done()
            and self._prefetch_song_id == song_id
        ):
            return

        self.cancel_prefetch()
        hdrs = dict(headers or self.media_headers(media_url))
        self._prefetch_song_id = song_id
        self._prefetch_task = asyncio.create_task(
            self._prefetch_copy_loop(media_url, song_id, hdrs),
            name=f"music:prefetch:{song_id}",
        )
        logger.info(f"后台预取缓存: song_id={song_id}")

    def cancel_prefetch(self) -> None:
        """取消后台预取（换歌时）."""
        task = self._prefetch_task
        self._prefetch_task = None
        self._prefetch_song_id = None
        if task and not task.done():
            task.cancel()

    async def _prefetch_copy_loop(
        self, media_url: str, song_id: str, headers: dict[str, str]
    ) -> None:
        final = self._cache.path_for_song(song_id)
        part = final.with_name(f"{final.stem}.part{final.suffix}")
        try:
            if part.exists():
                part.unlink()
        except Exception:
            pass

        try:
            ok = await self._ffmpeg_copy_url(media_url, part, headers)
            if not ok:
                return
            if not part.exists() or part.stat().st_size <= 1024:
                logger.warning(f"预取文件过小，丢弃: {part.name}")
                if part.exists():
                    part.unlink()
                return
            if final.exists():
                final.unlink()
            part.replace(final)
            logger.info(
                f"后台预取完成（可本地播）: {final.name} ({final.stat().st_size} bytes)"
            )
        except asyncio.CancelledError:
            logger.debug(f"后台预取取消: {song_id}")
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass
            raise
        except Exception as e:
            logger.warning(f"后台预取失败 {song_id}: {e}", exc_info=True)
            try:
                if part.exists():
                    part.unlink()
            except Exception:
                pass
        finally:
            if self._prefetch_song_id == song_id:
                self._prefetch_task = None
                self._prefetch_song_id = None

    async def _ffmpeg_copy_url(
        self, media_url: str, out_path: Path, headers: dict[str, str]
    ) -> bool:
        """用 FFmpeg -c copy 按网速拉整首，不解码、不跟播放限速."""
        from src.audio_codecs.music_decoder import _ffmpeg_header_args

        ffmpeg = get_ffmpeg_path()
        cmd = [
            ffmpeg,
            "-y",
            "-reconnect",
            "1",
            "-reconnect_streamed",
            "1",
            "-reconnect_delay_max",
            "5",
        ]
        cmd.extend(_ffmpeg_header_args(headers))
        cmd.extend(
            [
                "-i",
                media_url,
                "-vn",
                "-c:a",
                "copy",
                "-loglevel",
                "error",
                str(out_path),
            ]
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                **_SUBPROCESS_KW,
            )
            _, stderr = await proc.communicate()
            if proc.returncode != 0:
                err = (stderr or b"").decode("utf-8", errors="ignore").strip()
                logger.warning(
                    f"FFmpeg copy 预取失败 rc={proc.returncode}: {err[:300]}"
                )
                return False
            return True
        except FileNotFoundError:
            logger.warning("FFmpeg 不可用，后台预取跳过")
            return False
        except Exception as e:
            logger.warning(f"FFmpeg copy 预取异常: {e}", exc_info=True)
            return False
