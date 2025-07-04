"""音乐工具管理器.

负责音乐工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .music_player import get_music_player_instance

logger = get_logger(__name__)


class MusicToolsManager:
    """
    音乐工具管理器.
    """

    def __init__(self):
        """
        初始化音乐工具管理器.
        """
        self._initialized = False
        self._music_player = None
        logger.info("[MusicManager] 音乐工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有音乐工具.
        """
        try:
            logger.info("[MusicManager] 开始注册音乐工具")

            # 获取音乐播放器单例实例
            self._music_player = get_music_player_instance()

            # 注册搜索并播放工具
            self._register_search_and_play_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册播放/暂停工具
            self._register_play_pause_tool(add_tool, PropertyList)

            # 注册停止工具
            self._register_stop_tool(add_tool, PropertyList)

            # 注册跳转工具
            self._register_seek_tool(add_tool, PropertyList, Property, PropertyType)

            # 注册获取歌词工具
            self._register_get_lyrics_tool(add_tool, PropertyList)

            # 注册获取状态工具
            self._register_get_status_tool(add_tool, PropertyList)

            # 注册获取本地歌单工具
            self._register_get_local_playlist_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            self._initialized = True
            logger.info("[MusicManager] 音乐工具注册完成")

        except Exception as e:
            logger.error(f"[MusicManager] 音乐工具注册失败: {e}", exc_info=True)
            raise

    def _register_search_and_play_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册搜索并播放工具.
        """

        async def search_and_play_wrapper(args: Dict[str, Any]) -> str:
            song_name = args.get("song_name", "")
            result = await self._music_player.search_and_play(song_name)
            return result.get("message", "搜索播放完成")

        search_props = PropertyList([Property("song_name", PropertyType.STRING)])

        add_tool(
            (
                "music_player.search_and_play",
                "Search for a song and start playing it. Finds songs by name and "
                "automatically starts playback. Use this to play specific songs "
                "requested by the user.",
                search_props,
                search_and_play_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册搜索播放工具成功")

    def _register_play_pause_tool(self, add_tool, PropertyList):
        """
        注册播放/暂停工具.
        """

        async def play_pause_wrapper(args: Dict[str, Any]) -> str:
            result = await self._music_player.play_pause()
            return result.get("message", "播放状态切换完成")

        add_tool(
            (
                "music_player.play_pause",
                "Toggle between play and pause states. If music is playing, it will "
                "pause. If music is paused or stopped, it will resume or start playing. "
                "Use this when user wants to pause/resume music.",
                PropertyList(),
                play_pause_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册播放暂停工具成功")

    def _register_stop_tool(self, add_tool, PropertyList):
        """
        注册停止工具.
        """

        async def stop_wrapper(args: Dict[str, Any]) -> str:
            result = await self._music_player.stop()
            return result.get("message", "停止播放完成")

        add_tool(
            (
                "music_player.stop",
                "Stop music playback completely. This will stop the current song "
                "and reset the position to the beginning. Use this when user wants "
                "to stop music completely.",
                PropertyList(),
                stop_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册停止工具成功")

    def _register_seek_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册跳转工具.
        """

        async def seek_wrapper(args: Dict[str, Any]) -> str:
            position = args.get("position", 0)
            result = await self._music_player.seek(float(position))
            return result.get("message", "跳转完成")

        seek_props = PropertyList(
            [Property("position", PropertyType.INTEGER, min_value=0)]
        )

        add_tool(
            (
                "music_player.seek",
                "Jump to a specific position in the currently playing song. "
                "Position is specified in seconds from the beginning. Use this "
                "when user wants to skip to a specific part of a song.",
                seek_props,
                seek_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册跳转工具成功")

    def _register_get_lyrics_tool(self, add_tool, PropertyList):
        """
        注册获取歌词工具.
        """

        async def get_lyrics_wrapper(args: Dict[str, Any]) -> str:
            result = await self._music_player.get_lyrics()
            if result.get("status") == "success":
                lyrics = result.get("lyrics", [])
                return "歌词内容:\n" + "\n".join(lyrics)
            else:
                return result.get("message", "获取歌词失败")

        add_tool(
            (
                "music_player.get_lyrics",
                "Get the lyrics of the currently playing song. Returns the complete "
                "lyrics with timestamps. Use this when user asks for lyrics or wants "
                "to see the words of the current song.",
                PropertyList(),
                get_lyrics_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册获取歌词工具成功")

    def _register_get_status_tool(self, add_tool, PropertyList):
        """
        注册获取状态工具.
        """

        async def get_status_wrapper(args: Dict[str, Any]) -> str:
            result = await self._music_player.get_status()
            if result.get("status") == "success":
                status_info = []
                status_info.append(f"当前歌曲: {result.get('current_song', '无')}")
                status_info.append(
                    f"播放状态: {'播放中' if result.get('is_playing') else '已停止'}"
                )
                if result.get("is_playing"):
                    if result.get("paused"):
                        status_info.append("状态: 已暂停")
                    else:
                        status_info.append("状态: 正在播放")

                    duration = result.get("duration", 0)
                    position = result.get("position", 0)
                    progress = result.get("progress", 0)

                    status_info.append(f"播放时长: {self._format_time(duration)}")
                    status_info.append(f"当前位置: {self._format_time(position)}")
                    status_info.append(f"播放进度: {progress}%")
                    has_lyrics = "是" if result.get("has_lyrics") else "否"
                    status_info.append(f"歌词可用: {has_lyrics}")

                return "\n".join(status_info)
            else:
                return "获取播放器状态失败"

        add_tool(
            (
                "music_player.get_status",
                "Get the current status of the music player including current song, "
                "play state, position, duration, and progress. Use this to check "
                "what's currently playing or get detailed playback information.",
                PropertyList(),
                get_status_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册获取状态工具成功")

    def _register_get_local_playlist_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册获取本地歌单工具.
        """

        async def get_local_playlist_wrapper(args: Dict[str, Any]) -> str:
            force_refresh = args.get("force_refresh", False)
            result = await self._music_player.get_local_playlist(force_refresh)

            if result.get("status") == "success":
                playlist = result.get("playlist", [])
                total_count = result.get("total_count", 0)

                if playlist:
                    playlist_text = f"本地音乐歌单 (共{total_count}首):\n"
                    playlist_text += "\n".join(playlist)
                    return playlist_text
                else:
                    return "本地缓存中没有音乐文件"
            else:
                return result.get("message", "获取本地歌单失败")

        refresh_props = PropertyList(
            [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
        )

        add_tool(
            (
                "music_player.get_local_playlist",
                "Get the local music playlist from cache. Shows all songs that have been "
                "downloaded and cached locally. Returns songs in format 'Title - Artist'. "
                "To play a song from this list, use search_and_play with just the song title "
                "(not the full 'Title - Artist' format). For example: if the list shows "
                "'菊花台 - 周杰伦', call search_and_play with song_name='菊花台'.",
                refresh_props,
                get_local_playlist_wrapper,
            )
        )
        logger.debug("[MusicManager] 注册获取本地歌单工具成功")

    def _format_time(self, seconds: float) -> str:
        """
        将秒数格式化为 mm:ss 格式.
        """
        minutes = int(seconds) // 60
        seconds = int(seconds) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def is_initialized(self) -> bool:
        """
        检查管理器是否已初始化.
        """
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        """
        获取管理器状态.
        """
        return {
            "initialized": self._initialized,
            "tools_count": 7,  # 当前注册的工具数量
            "available_tools": [
                "search_and_play",
                "play_pause",
                "stop",
                "seek",
                "get_lyrics",
                "get_status",
                "get_local_playlist",
            ],
            "music_player_ready": self._music_player is not None,
        }


# 全局管理器实例
_music_tools_manager = None


def get_music_tools_manager() -> MusicToolsManager:
    """
    获取音乐工具管理器单例.
    """
    global _music_tools_manager
    if _music_tools_manager is None:
        _music_tools_manager = MusicToolsManager()
        logger.debug("[MusicManager] 创建音乐工具管理器实例")
    return _music_tools_manager
