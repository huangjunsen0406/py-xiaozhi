"""最小外挂媒体插件模板（同時兼容 python-inprocess 与 python-subprocess）."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _history_file(data_dir: Path | None) -> Path | None:
    if data_dir is None:
        return None
    return Path(data_dir) / "history.json"


def _append_history(data_dir: Path | None, entry: dict[str, Any]) -> None:
    path = _history_file(data_dir)
    if path is None:
        return
    try:
        items = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []
        if not isinstance(items, list):
            items = []
    except Exception:
        items = []
    items.insert(0, entry)
    path.write_text(
        json.dumps(items[:20], ensure_ascii=False, indent=2), encoding="utf-8"
    )


def register(host) -> None:
    player = host.get("media_player")
    data_dir = host.get("data_dir")

    @host.tool(
        "demo_media.play_url",
        "通过宿主应用内播放器播放指定的 HTTP(S) 音频直链或本地音频绝对路径。",
        [
            {"name": "url", "type": "string"},
            {"name": "title", "type": "string", "default": ""},
        ],
    )
    async def play_url(args: dict[str, Any]) -> str:
        if player is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": "未授权应用内播放能力，请在「参数设置 → MCP 工具」中开启「允许外挂使用应用内播放」。",
                },
                ensure_ascii=False,
            )
        url = str(args.get("url") or "").strip()
        title = str(args.get("title") or "").strip()
        result = await player.play_url(url, title=title)
        if result.get("status") == "success":
            _append_history(data_dir, {"title": result.get("title", title), "url": url})
        return json.dumps(result, ensure_ascii=False)

    @host.tool(
        "demo_media.list_history",
        "查看示例媒体插件记录的最近播放历史。",
        [],
    )
    def list_history(_args: dict[str, Any]) -> str:
        path = _history_file(data_dir)
        if path is None or not path.is_file():
            return json.dumps({"status": "success", "items": []}, ensure_ascii=False)
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            items = []
        return json.dumps({"status": "success", "items": items}, ensure_ascii=False)
