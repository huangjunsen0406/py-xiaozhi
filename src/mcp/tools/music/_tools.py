"""
Music tool registrations via decorators.
"""

from typing import Any, Dict

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool

from .music_player import get_music_player_instance

logger = get_logger()


def _player():
    return get_music_player_instance()


async def _call_player(method_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    method = getattr(_player(), method_name)
    if args:
        return await method(**args)
    return await method()


@mcp_tool(
    name="music_player.search_and_play",
    description=(
        "搜索并播放指定的歌曲。根据歌名在线搜索歌曲并自动开始播放。"
        "如果已有音乐在播放，会自动停止当前音乐并播放新歌曲。"
        "用于播放用户请求的特定歌曲，例如'播放周杰伦的稻香'、'听一下孤勇者'。"
    ),
    props=[Prop("song_name", PropType.STR)],
)
async def tool_music_search(args):
    result = await _call_player("search_and_play", args)
    return result.get("message", "搜索播放完成")


@mcp_tool(
    name="music_player.pause",
    description=(
        "暂停当前正在播放的音乐，保持播放位置，之后可用 resume 恢复。"
        "当用户说'暂停音乐'、'先停一下音乐'、'音乐暂停'时，必须调用此工具。"
        "重要：回复用户之前先调用此工具，否则 TTS 结束后音乐会自动恢复。"
    ),
)
async def tool_music_pause(args):
    result = await _call_player("pause", args)
    return result.get("message", "已暂停")


@mcp_tool(
    name="music_player.resume",
    description=(
        "恢复播放之前暂停的音乐，从暂停位置继续。"
        "当用户说'继续播放'、'恢复音乐'、'把音乐打开'时调用。"
        "注意：TTS 说话时音乐会自动暂停，说完自动恢复，无需调用此工具。"
        "只有用户主动暂停后要求恢复时才需要调用。"
    ),
)
async def tool_music_resume(args):
    result = await _call_player("resume", args)
    return result.get("message", "已恢复播放")


@mcp_tool(
    name="music_player.stop",
    description=(
        "完全停止并关闭音乐播放，重置到开头。"
        "当用户说'关闭音乐'、'停止音乐'、'不听了'、'别放了'、'关掉音乐'时，必须调用此工具。"
        "与 pause 的区别：stop 是彻底关闭，pause 是临时暂停可恢复。"
    ),
)
async def tool_music_stop(args):
    result = await _call_player("stop", args)
    return result.get("message", "停止播放完成")


@mcp_tool(
    name="music_player.seek",
    description=(
        "跳转到歌曲的指定位置。position 参数单位为秒（从开头计算）。"
        "用于用户要求'快进到2分钟'、'跳到副歌部分'、'回到开头'、'跳转30%'、'跳到30秒'等场景。"
        "注意：如果用户说'快进30秒'，需要先获取当前位置，再加上30秒。"
    ),
    props=[Prop("position", PropType.INT, min_val=0)],
)
async def tool_music_seek(args):
    result = await _call_player("seek", args)
    return result.get("message", "跳转完成")


@mcp_tool(
    name="music_player.get_lyrics",
    description=(
        "获取当前播放歌曲的歌词。返回完整歌词及时间戳。"
        "用于用户询问'这首歌的歌词是什么'、'帮我看看歌词'、'歌词里唱的什么'等场景。"
    ),
)
async def tool_music_get_lyrics(args):
    result = await _player().get_lyrics()
    if result.get("status") == "success":
        lyrics = result.get("lyrics", [])
        return "歌词内容:\n" + "\n".join(lyrics)
    return result.get("message", "获取歌词失败")


@mcp_tool(
    name="music_player.get_local_playlist",
    description=(
        "获取本地音乐歌单。显示所有已下载并缓存的歌曲。"
        "返回格式：'歌名 - 歌手'，例如'菊花台 - 周杰伦'。"
        "用于用户询问'我有哪些歌'、'本地歌曲列表'、'缓存了什么音乐'等场景。"
        "注意：播放列表中的歌曲时，只需使用歌名调用 search_and_play，"
        "例如列表显示'菊花台 - 周杰伦'，调用 search_and_play(song_name='菊花台') 即可。"
    ),
    props=[Prop("force_refresh", PropType.BOOL, default=False)],
)
async def tool_music_get_playlist(args):
    force_refresh = args.get("force_refresh", False)
    result = await _player().get_local_playlist(force_refresh)

    if result.get("status") == "success":
        playlist = result.get("playlist", [])
        total_count = result.get("total_count", 0)
        if playlist:
            playlist_text = f"本地音乐歌单 (共{total_count}首):\n"
            playlist_text += "\n".join(playlist)
            return playlist_text
        return "本地缓存中没有音乐文件"
    return result.get("message", "获取本地歌单失败")
