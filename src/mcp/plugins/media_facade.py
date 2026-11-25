"""MCP 外挂生命周期与受控媒体播放门面（MediaPlayerFacade）.

设计原则：
1. 最小暴露面：外挂仅能调用 play_url / pause / resume / stop / seek / get_status / set_subtitle，
   无法接触宿主 MediaPlayer 内部字段、AudioCodec 或 EventBus。
2. 生命周期绑定：每个插件实例持有独立 PluginLifecycle；插件卸载后句柄立即失效，
   且自动停止仍归属该插件的媒体播放流。
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any

from src.logging import get_logger

if TYPE_CHECKING:
    from src.media.media_player import MediaPlayer

logger = get_logger()


class PluginLifecycle:
    """单次外挂插件安装的生命周期令牌."""

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self._active = True
        self._cleanups: list[Callable[[], Any]] = []

    @property
    def active(self) -> bool:
        return self._active

    def assert_active(self) -> None:
        if not self._active:
            raise RuntimeError(
                f"插件 {self.plugin_id} 已卸载，宿主能力句柄已失效"
            )

    def add_cleanup(self, callback: Callable[[], Any]) -> None:
        if not self._active:
            self._run_cleanup(callback)
            return
        self._cleanups.append(callback)

    def revoke(self) -> None:
        """标记失效并执行所有清理钩子（幂等）."""
        if not self._active:
            return
        self._active = False
        callbacks = list(self._cleanups)
        self._cleanups.clear()
        for callback in callbacks:
            self._run_cleanup(callback)

    def _run_cleanup(self, callback: Callable[[], Any]) -> None:
        try:
            result = callback()
            if inspect.isawaitable(result):
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(result, name=f"plugin-cleanup:{self.plugin_id}")
                except RuntimeError:
                    if inspect.iscoroutine(result):
                        result.close()
        except Exception as exc:
            logger.debug(
                "[MCP插件:%s] 生命周期清理异常: %s", self.plugin_id, exc, exc_info=True
            )


class MediaPlayerFacade:
    """暴露给单个外挂插件的受控媒体播放门面."""

    _RPC_ACTIONS = frozenset(
        {
            "play_url",
            "pause",
            "resume",
            "stop",
            "seek",
            "get_status",
            "set_subtitle",
        }
    )

    def __init__(
        self,
        player: MediaPlayer,
        *,
        plugin_id: str,
        lifecycle: PluginLifecycle,
    ) -> None:
        self._player = player
        self._plugin_id = plugin_id
        self._lifecycle = lifecycle
        self._lifecycle.add_cleanup(self._stop_owned_on_unload)

    def _stop_owned_on_unload(self):
        if self._player.owner_id == self._plugin_id:
            return self._player.stop(only_owner=self._plugin_id)
        return None

    async def play_url(
        self,
        url: str,
        *,
        title: str = "",
        start_position: float = 0.0,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.play_url(
            url,
            title=title,
            start_position=start_position,
            headers=headers,
            owner_id=self._plugin_id,
        )

    async def pause(self) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.pause(source="manual")

    async def resume(self) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.resume()

    async def stop(self) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.stop()

    async def seek(
        self,
        *,
        position: float | None = None,
        percent: float | None = None,
    ) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.seek(position=position, percent=percent)

    async def get_status(self) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.get_status()

    async def set_subtitle(self, text: str) -> dict[str, Any]:
        self._lifecycle.assert_active()
        return await self._player.set_subtitle(text, owner_id=self._plugin_id)

    async def dispatch_rpc(
        self, action: str, kwargs: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        """供 python-subprocess 双向 host_call 调度受控方法."""
        self._lifecycle.assert_active()
        if action not in self._RPC_ACTIONS:
            raise ValueError(f"不支持的 media_player 方法: {action}")
        params = dict(kwargs or {})
        if action == "play_url":
            return await self.play_url(
                str(params.get("url") or params.get("source") or ""),
                title=str(params.get("title") or ""),
                start_position=float(params.get("start_position") or 0.0),
                headers=params.get("headers"),
            )
        if action == "pause":
            return await self.pause()
        if action == "resume":
            return await self.resume()
        if action == "stop":
            return await self.stop()
        if action == "seek":
            return await self.seek(
                position=params.get("position"),
                percent=params.get("percent"),
            )
        if action == "get_status":
            return await self.get_status()
        if action == "set_subtitle":
            return await self.set_subtitle(str(params.get("text") or ""))
        raise ValueError(f"不支持的 media_player 方法: {action}")
