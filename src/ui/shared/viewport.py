"""界面统一接口：gui / cli / gpio 都实现这一套."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ViewPort(Protocol):
    """写界面用的方法集合."""

    async def start(self, mode: str = "cli") -> None:
        """启动."""
        ...

    async def close(self) -> None:
        """关闭."""
        ...

    def set_status(self, status: str, connected: bool = True) -> None:
        """状态栏."""
        ...

    def set_emotion(self, emotion: str) -> None:
        """表情名，具体资源各端自己解析."""
        ...

    def set_chat_text(self, text: str) -> None:
        """对话内容（TTS / STT）."""
        ...

    def set_music_line(self, text: str) -> None:
        """音乐状态或歌词."""
        ...

    def set_button_text(self, text: str) -> None:
        """主按钮文案；没有按钮可以空实现."""
        ...

    def set_auto_mode(self, auto_mode: bool) -> None:
        """刷新自动/手动显示（真状态在 Session 里）."""
        ...

    def is_auto_mode(self) -> bool:
        """界面上记录的当前模式（比如 GPIO 按键分支会用到）."""
        ...
