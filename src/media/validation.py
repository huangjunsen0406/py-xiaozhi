"""媒体源与 HTTP 请求头安全校验."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

_ALLOWED_HEADER_NAMES = frozenset(
    {
        "accept",
        "accept-language",
        "authorization",
        "cookie",
        "origin",
        "range",
        "referer",
        "user-agent",
    }
)

# 匹配 URI scheme（排除 Windows 盘符如 C:\...）
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]{1,}:")


def validate_media_source(source: str | Path) -> tuple[str, bool]:
    """校验媒体地址，返回 ``(normalized_source, is_http)``.

    仅允许：
    1. 合法的 ``http://`` 或 ``https://`` URL（含非空主机名，无控制字符）；
    2. 已存在的本地文件绝对路径（拒绝目录、相对路径和危险 ffmpeg 协议如 ``pipe:`` / ``concat:``）。
    """
    if isinstance(source, Path):
        raw = str(source)
    elif isinstance(source, str):
        raw = source.strip()
    else:
        raise ValueError("媒体地址必须为字符串或路径")

    if not raw or any(ch in raw for ch in ("\r", "\n", "\x00")):
        raise ValueError("媒体地址无效或包含非法字符")

    lower = raw.lower()
    if lower.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError(f"无效的 HTTP 媒体地址: {raw}")
        return raw, True

    if _SCHEME_RE.match(raw):
        raise ValueError(f"不支持的媒体协议: {raw.split(':', 1)[0]}")

    path = Path(raw)
    if not path.is_absolute():
        raise ValueError(f"本地媒体路径必须为绝对路径: {raw}")
    if not path.exists() or not path.is_file():
        raise ValueError(f"本地媒体文件不存在: {raw}")
    return str(path.resolve()), False


def sanitize_headers(
    headers: Mapping[str, str] | None,
) -> dict[str, str] | None:
    """过滤并校验 HTTP 请求头，防止 CRLF 注入与非法头部透传."""
    if not headers:
        return None
    if not isinstance(headers, Mapping):
        raise ValueError("headers 必须为映射对象")

    cleaned: dict[str, str] = {}
    for raw_key, raw_value in headers.items():
        key = str(raw_key).strip()
        value = str(raw_value).strip()
        if not key or not value:
            continue
        if any(ch in key or ch in value for ch in ("\r", "\n", "\x00")):
            raise ValueError(f"请求头包含非法控制字符: {key}")
        if key.lower() not in _ALLOWED_HEADER_NAMES:
            continue
        cleaned[key] = value
    return cleaned or None
