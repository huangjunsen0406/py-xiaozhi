"""事件总线.

提供组件间解耦通信机制。
"""

import asyncio
from collections import defaultdict
from typing import Any, Awaitable, Callable

from src.logging import get_logger

logger = get_logger()


# 预定义事件名称
class Events:
    """
    预定义事件常量.
    """

    # 设备状态
    DEVICE_STATE_CHANGED = "device_state_changed"

    # 协议相关
    PROTOCOL_CONNECTED = "protocol_connected"
    PROTOCOL_DISCONNECTED = "protocol_disconnected"
    INCOMING_JSON = "incoming_json"
    INCOMING_AUDIO = "incoming_audio"

    # 网络错误
    NETWORK_ERROR = "network_error"

    # 音频通道
    AUDIO_CHANNEL_OPENED = "audio_channel_opened"
    AUDIO_CHANNEL_CLOSED = "audio_channel_closed"

    # 应用生命周期
    APP_SHUTDOWN = "app_shutdown"

    # 音乐播放器事件
    MUSIC_STATE_CHANGED = "music_state_changed"  # 播放状态变化
    MUSIC_LYRICS_UPDATE = "music_lyrics_update"  # 歌词更新
    MUSIC_PROGRESS_UPDATE = "music_progress_update"  # 进度更新

    # 音乐控制命令（从外部控制 MusicPlayer）
    MUSIC_PAUSE_REQUEST = "music_pause_request"  # 请求暂停（如 TTS）
    MUSIC_RESUME_REQUEST = "music_resume_request"  # 请求恢复

    # UI 用户操作事件（View → Plugin）
    UI_BUTTON_PRESS = "ui_button_press"  # 按钮按下（手动模式）
    UI_BUTTON_RELEASE = "ui_button_release"  # 按钮释放（手动模式）
    UI_AUTO_TOGGLE = "ui_auto_toggle"  # 自动模式切换
    UI_AUTO_START = "ui_auto_start"  # 自动模式开始监听
    UI_ABORT_REQUEST = "ui_abort_request"  # 中断请求
    UI_SEND_TEXT = "ui_send_text"  # 发送文本
    UI_QUIT_REQUEST = "ui_quit_request"  # 退出请求
    UI_OPEN_SETTINGS = "ui_open_settings"  # 打开设置窗口

    # UI 更新事件（Plugin → View）
    UI_UPDATE_TEXT = "ui_update_text"  # 更新文本显示
    UI_UPDATE_EMOTION = "ui_update_emotion"  # 更新表情
    UI_UPDATE_STATUS = "ui_update_status"  # 更新状态
    UI_TOGGLE_MODE = "ui_toggle_mode"  # 切换对话模式
    UI_TOGGLE_WINDOW = "ui_toggle_window"  # 切换窗口可见性


class EventBus:
    """事件总线.

    支持异步事件处理，实现组件间松耦合通信。

    用法:     bus = EventBus()

    # 注册处理器 async def on_state_changed(state):     print(f"State: {state}")

    bus.on(Events.DEVICE_STATE_CHANGED, on_state_changed)

    # 触发事件 await bus.emit(Events.DEVICE_STATE_CHANGED, DeviceState.LISTENING)

    # 移除处理器 bus.off(Events.DEVICE_STATE_CHANGED, on_state_changed)
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable[..., Awaitable[None]]]] = defaultdict(
            list
        )
        self._lock = asyncio.Lock()

    def on(self, event: str, handler: Callable[..., Awaitable[None]]) -> None:
        """注册事件处理器.

        Args:
            event: 事件名称
            handler: 异步处理函数
        """
        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)
            logger.debug(f"EventBus: 注册处理器 {handler.__name__} -> {event}")

    def off(self, event: str, handler: Callable[..., Awaitable[None]]) -> None:
        """移除事件处理器.

        Args:
            event: 事件名称
            handler: 要移除的处理函数
        """
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)
            logger.debug(f"EventBus: 移除处理器 {handler.__name__} <- {event}")

    def clear(self, event: str = None) -> None:
        """清除事件处理器.

        Args:
            event: 事件名称，为 None 时清除所有
        """
        if event is None:
            self._handlers.clear()
            logger.debug("EventBus: 清除所有处理器")
        elif event in self._handlers:
            self._handlers[event].clear()
            logger.debug(f"EventBus: 清除事件 {event} 的所有处理器")

    async def emit(self, event: str, data: Any = None) -> None:
        """触发事件.

        并行调用所有注册的处理器。

        Args:
            event: 事件名称
            data: 事件数据
        """
        handlers = self._handlers.get(event, [])
        if not handlers:
            return

        logger.debug(f"EventBus: 触发事件 {event}, {len(handlers)} 个处理器")

        # 并行执行所有处理器
        tasks = []
        for handler in handlers:
            try:
                tasks.append(self._safe_call(handler, data))
            except Exception as e:
                logger.error(f"EventBus: 创建任务失败 {handler.__name__}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def emit_sequential(self, event: str, data: Any = None) -> None:
        """顺序触发事件.

        按注册顺序依次调用处理器。

        Args:
            event: 事件名称
            data: 事件数据
        """
        handlers = self._handlers.get(event, [])
        for handler in handlers:
            await self._safe_call(handler, data)

    async def _safe_call(
        self, handler: Callable[..., Awaitable[None]], data: Any
    ) -> None:
        """
        安全调用处理器，捕获异常.
        """
        try:
            if data is None:
                await handler()
            else:
                await handler(data)
        except Exception as e:
            logger.error(f"EventBus: 处理器 {handler.__name__} 执行异常: {e}")

    def has_handlers(self, event: str) -> bool:
        """
        检查事件是否有处理器.
        """
        return bool(self._handlers.get(event))

    def handler_count(self, event: str) -> int:
        """
        获取事件的处理器数量.
        """
        return len(self._handlers.get(event, []))
