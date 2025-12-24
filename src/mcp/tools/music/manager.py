"""音乐工具管理器.

负责音乐工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.logging import get_logger

from .music_player import get_music_player_instance

logger = get_logger()


class MusicToolsManager:
    """
    音乐工具管理器.
    """

    def __init__(self):
        """
        初始化音乐工具管理器.
        """
        self._music_player = None
        logger.info("[MusicManager] 音乐工具管理器初始化")

    def _create_simple_wrapper(self, method_name: str, default_message: str):
        """
        创建简单的 wrapper 函数（无参数或仅提取一个参数）.
        """

        async def wrapper(args: Dict[str, Any]) -> str:
            method = getattr(self._music_player, method_name)
            # 如果有参数，传递给方法
            if args:
                result = await method(**args)
            else:
                result = await method()
            return result.get("message", default_message)

        return wrapper

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有音乐工具.
        """
        try:
            logger.info("[MusicManager] 开始注册音乐工具")

            # 获取音乐播放器单例实例
            self._music_player = get_music_player_instance()

            # 注册简单工具（无额外逻辑的）
            simple_tools = [
                (
                    "music_player.search_and_play",
                    "搜索并播放指定的歌曲。根据歌名在线搜索歌曲并自动开始播放。"
                    "如果已有音乐在播放，会自动停止当前音乐并播放新歌曲。"
                    "用于播放用户请求的特定歌曲，例如'播放周杰伦的稻香'、'听一下孤勇者'。",
                    PropertyList([Property("song_name", PropertyType.STRING)]),
                    "search_and_play",
                    "搜索播放完成",
                ),
                (
                    "music_player.pause",
                    "暂停当前正在播放的音乐。调用此工具会立即停止音乐播放，保持当前位置。"
                    "用户可以稍后调用 resume 恢复播放。"
                    "注意：不要在 TTS 说话时主动调用此工具，TTS 会自动临时暂停音乐。"
                    "只有当用户明确说'暂停'、'暂停音乐'、'先停一下'等时才调用。",
                    PropertyList(),
                    "pause",
                    "已暂停",
                ),
                (
                    "music_player.resume",
                    "恢复播放之前暂停的音乐。从暂停的位置继续播放。"
                    "只有当音乐处于'已暂停'状态（用户主动暂停）时才调用此工具。"
                    "如果音乐只是被 TTS 临时打断，TTS 结束后会自动恢复，无需调用此工具。",
                    PropertyList(),
                    "resume",
                    "已恢复播放",
                ),
                (
                    "music_player.stop",
                    "完全停止音乐播放。停止当前歌曲并重置播放位置到开头。"
                    "与 pause（暂停）的区别：stop 是完全结束播放，pause 是临时暂停。"
                    "用于用户说'停止音乐'、'关闭音乐'、'别放了'等明确要求结束播放的场景。",
                    PropertyList(),
                    "stop",
                    "停止播放完成",
                ),
                (
                    "music_player.seek",
                    "跳转到歌曲的指定位置。position 参数单位为秒（从开头计算）。"
                    "用于用户要求'快进到2分钟'、'跳到副歌部分'、'回到开头'、'跳转30%'、'跳到30秒'等场景。"
                    "注意：如果用户说'快进30秒'，需要先获取当前位置，再加上30秒。",
                    PropertyList([Property("position", PropertyType.INTEGER, min_value=0)]),
                    "seek",
                    "跳转完成",
                ),
            ]

            # 批量注册简单工具
            for tool_name, description, properties, method_name, default_msg in simple_tools:
                add_tool(
                    (
                        tool_name,
                        description,
                        properties,
                        self._create_simple_wrapper(method_name, default_msg),
                    )
                )

            # 注册获取歌词工具（需要格式化）
            async def get_lyrics_wrapper(args: Dict[str, Any]) -> str:
                result = await self._music_player.get_lyrics()
                if result.get("status") == "success":
                    lyrics = result.get("lyrics", [])
                    return "歌词内容:\n" + "\n".join(lyrics)
                return result.get("message", "获取歌词失败")

            add_tool(
                (
                    "music_player.get_lyrics",
                    "获取当前播放歌曲的歌词。返回完整歌词及时间戳。"
                    "用于用户询问'这首歌的歌词是什么'、'帮我看看歌词'、'歌词里唱的什么'等场景。",
                    PropertyList(),
                    get_lyrics_wrapper,
                )
            )

            # 注册获取本地歌单工具（需要格式化）
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
                    return "本地缓存中没有音乐文件"
                return result.get("message", "获取本地歌单失败")

            add_tool(
                (
                    "music_player.get_local_playlist",
                    "获取本地音乐歌单。显示所有已下载并缓存的歌曲。"
                    "返回格式：'歌名 - 歌手'，例如'菊花台 - 周杰伦'。"
                    "用于用户询问'我有哪些歌'、'本地歌曲列表'、'缓存了什么音乐'等场景。"
                    "注意：播放列表中的歌曲时，只需使用歌名调用 search_and_play，"
                    "例如列表显示'菊花台 - 周杰伦'，调用 search_and_play(song_name='菊花台') 即可。",
                    PropertyList(
                        [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
                    ),
                    get_local_playlist_wrapper,
                )
            )

            logger.info("[MusicManager] 音乐工具注册完成")

        except Exception as e:
            logger.error(f"[MusicManager] 音乐工具注册失败: {e}", exc_info=True)
            raise


def get_music_tools_manager() -> MusicToolsManager:
    """创建音乐工具管理器实例."""
    return MusicToolsManager()
