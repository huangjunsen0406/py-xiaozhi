"""音乐 MCP 工具：由容器注入的 MusicPlayer 注册，不使用全局 get_instance."""

from typing import Any, Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .music_player import MusicPlayer

logger = get_logger()


def register_music_tools(
    add_tool: Callable[[McpTool], None], player: MusicPlayer
) -> None:
    """向 McpServer 注册音乐工具（闭包持有容器注入的 player）."""

    async def search_and_play(args: dict[str, Any]) -> str:
        song_name = (args or {}).get("song_name", "")
        result = await player.search_and_play(song_name)
        return result.get("message", "搜索播放完成")

    async def pause(args: dict[str, Any]) -> str:
        # MCP 工具侧默认 manual；TTS 暂停走 EventBus 不经此工具
        result = await player.pause(source="manual")
        return result.get("message", "已暂停")

    async def resume(args: dict[str, Any]) -> str:
        result = await player.resume()
        return result.get("message", "已恢复播放")

    async def stop(args: dict[str, Any]) -> str:
        result = await player.stop()
        return result.get("message", "停止播放完成")

    async def seek(args: dict[str, Any]) -> str:
        percent = int(args.get("percent", -1))
        position = int(args.get("position", -1))
        kwargs: dict[str, Any] = {}
        if percent >= 0:
            kwargs["percent"] = percent
        elif position >= 0:
            kwargs["position"] = position
        else:
            return "请指定 percent（0-100）或 position（秒）"
        result = await player.seek(**kwargs)
        return result.get("message", "跳转完成")

    async def get_status(args: dict[str, Any]) -> str:
        result = await player.get_status()
        return result.get("message", "无法获取状态")

    async def get_lyrics(args: dict[str, Any]) -> str:
        result = await player.get_lyrics()
        if result.get("status") == "success":
            lyrics = result.get("lyrics", [])
            return "歌词内容:\n" + "\n".join(lyrics)
        return result.get("message", "获取歌词失败")

    async def get_local_playlist(args: dict[str, Any]) -> str:
        force_refresh = args.get("force_refresh", False)
        result = await player.get_local_playlist(force_refresh)
        if result.get("status") == "success":
            playlist = result.get("playlist", [])
            total_count = result.get("total_count", 0)
            if playlist:
                text = f"本地音乐歌单 (共{total_count}首):\n"
                text += "\n".join(playlist)
                return text
            return "本地缓存中没有音乐文件"
        return result.get("message", "获取本地歌单失败")

    tools: list[McpTool] = [
        McpTool(
            "music_player.search_and_play",
            (
                "搜索并播放指定的歌曲。根据歌名在线搜索歌曲并自动开始播放。"
                "如果已有音乐在播放，会自动停止当前音乐并播放新歌曲。"
                "用于播放用户请求的特定歌曲，例如'播放周杰伦的稻香'、'听一下孤勇者'。"
            ),
            PropertyList([Property("song_name", PropertyType.STRING)]),
            search_and_play,
        ),
        McpTool(
            "music_player.pause",
            (
                "暂停当前正在播放的音乐，保持播放位置，之后可用 resume 恢复。"
                "当用户说'暂停音乐'、'先停一下音乐'、'音乐暂停'时，必须调用此工具。"
                "重要：回复用户之前先调用此工具，否则 TTS 结束后音乐会自动恢复。"
            ),
            PropertyList(),
            pause,
        ),
        McpTool(
            "music_player.resume",
            (
                "恢复播放之前暂停的音乐，从暂停位置继续。"
                "当用户说'继续播放'、'恢复音乐'、'把音乐打开'时调用。"
                "注意：TTS 说话时音乐会自动暂停，说完自动恢复，无需调用此工具。"
                "只有用户主动暂停后要求恢复时才需要调用。"
            ),
            PropertyList(),
            resume,
        ),
        McpTool(
            "music_player.stop",
            (
                "完全停止并关闭音乐播放，重置到开头。"
                "当用户说'关闭音乐'、'停止音乐'、'不听了'、'别放了'、'关掉音乐'时，必须调用此工具。"
                "与 pause 的区别：stop 是彻底关闭，pause 是临时暂停可恢复。"
            ),
            PropertyList(),
            stop,
        ),
        McpTool(
            "music_player.seek",
            (
                "【进度/跳转专用】跳转到当前歌曲的指定位置。"
                "用户说「跳到30%」「进度跳转20%」「跳到一半」时：必须用 percent（0-100），"
                "由播放器按总时长自动换算秒数，不要查歌词、不要猜位置。"
                "用户说「跳到2分钟」「跳到90秒」「回到开头」时：用 position（秒，从0开始）。"
                "「快进30秒」：先 get_status 取当前位置，再 position=当前秒+30。"
                "与 get_lyrics 无关；百分比跳转不需要歌词。"
            ),
            PropertyList(
                [
                    Property("percent", PropertyType.INTEGER, default_value=-1),
                    Property("position", PropertyType.INTEGER, default_value=-1),
                ]
            ),
            seek,
        ),
        McpTool(
            "music_player.get_status",
            (
                "查询当前播放状态：歌名、是否播放/暂停、总时长（秒）、当前位置（秒）、进度百分比。"
                "用于「现在播到哪了」「这首歌多长」「快进前先看进度」等。"
                "不要用本工具代替 seek；跳转请调用 seek。"
            ),
            PropertyList(),
            get_status,
        ),
        McpTool(
            "music_player.get_lyrics",
            (
                "仅用于获取当前歌曲的歌词文本。"
                "当用户问「歌词是什么」「唱了什么」时调用。"
                "禁止用于：进度跳转、跳到百分之几、快进/快退、计算播放位置——"
                "那些请用 music_player.seek（百分比用 percent）。"
            ),
            PropertyList(),
            get_lyrics,
        ),
        McpTool(
            "music_player.get_local_playlist",
            (
                "获取本地音乐歌单。显示所有已下载并缓存的歌曲。"
                "返回格式：'歌名 - 歌手'，例如'菊花台 - 周杰伦'。"
                "用于用户询问'我有哪些歌'、'本地歌曲列表'、'缓存了什么音乐'等场景。"
                "注意：播放列表中的歌曲时，只需使用歌名调用 search_and_play，"
                "例如列表显示'菊花台 - 周杰伦'，调用 search_and_play(song_name='菊花台') 即可。"
            ),
            PropertyList(
                [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
            ),
            get_local_playlist,
        ),
    ]

    for tool in tools:
        add_tool(tool)
    logger.info("已注册 %d 个音乐 MCP 工具（容器注入 MusicPlayer）", len(tools))
