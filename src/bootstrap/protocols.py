"""
接口协议定义.

定义插件、窗口与核心服务之间的契约，实现松耦合。
"""

from typing import Protocol, Callable, Awaitable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.constants.constants import DeviceState, ListeningMode


class PluginContext(Protocol):
    """
    插件可访问的只读上下文.

    插件通过此接口获取应用状态，但不能直接修改状态。
    """

    def get_device_state(self) -> "DeviceState":
        """获取当前设备状态."""
        ...

    def get_listening_mode(self) -> "ListeningMode":
        """获取当前监听模式."""
        ...

    def is_listening(self) -> bool:
        """是否正在监听."""
        ...

    def is_speaking(self) -> bool:
        """是否正在说话."""
        ...

    def is_idle(self) -> bool:
        """是否处于空闲状态."""
        ...

    def is_audio_channel_opened(self) -> bool:
        """音频通道是否已打开."""
        ...

    def should_capture_audio(self) -> bool:
        """是否应该采集音频."""
        ...

    def is_keep_listening(self) -> bool:
        """是否保持持续监听."""
        ...

    def get_config(self) -> Any:
        """获取配置管理器."""
        ...


class PluginCommands(Protocol):
    """
    插件可执行的命令.

    插件通过此接口执行操作，由核心服务实现具体逻辑。
    """

    async def start_listening(self, mode: "ListeningMode") -> None:
        """开始监听."""
        ...

    async def stop_listening(self) -> None:
        """停止监听."""
        ...

    async def abort_speaking(self, reason: str) -> None:
        """中止语音输出."""
        ...

    async def send_audio(self, data: bytes) -> None:
        """发送音频数据."""
        ...

    async def send_text(self, text: str) -> None:
        """发送文本消息."""
        ...

    async def send_wake_word_detected(self, text: str) -> None:
        """发送检测到的文本（唤醒词或用户输入）."""
        ...

    async def send_mcp_message(self, payload: str) -> None:
        """发送 MCP 消息（会自动包装格式）."""
        ...

    async def connect_protocol(self) -> bool:
        """连接协议通道."""
        ...

    def spawn(self, coro: Awaitable[Any], name: str) -> Any:
        """创建异步任务."""
        ...

    def schedule_command_nowait(self, fn: Callable, *args, **kwargs) -> None:
        """调度命令（非阻塞）."""
        ...

    def request_shutdown(self) -> None:
        """请求关闭应用."""
        ...


class WindowContext(Protocol):
    """
    窗口可访问的上下文.

    窗口通过此接口与核心服务交互。
    """

    def get_device_state(self) -> "DeviceState":
        """获取当前设备状态."""
        ...

    def get_listening_mode(self) -> "ListeningMode":
        """获取当前监听模式."""
        ...

    def is_listening(self) -> bool:
        """是否正在监听."""
        ...

    def is_speaking(self) -> bool:
        """是否正在说话."""
        ...

    def is_idle(self) -> bool:
        """是否处于空闲状态."""
        ...

    def is_audio_channel_opened(self) -> bool:
        """音频通道是否已打开."""
        ...

    def request_shutdown(self) -> None:
        """请求关闭应用."""
        ...

    def on_start_listening(self) -> None:
        """用户请求开始监听."""
        ...

    def on_stop_listening(self) -> None:
        """用户请求停止监听."""
        ...

    def on_manual_listen_press(self) -> None:
        """用户按下手动监听按钮."""
        ...

    def on_manual_listen_release(self) -> None:
        """用户释放手动监听按钮."""
        ...

    def on_auto_conversation_start(self) -> None:
        """用户启动自动对话."""
        ...


class EventHandler(Protocol):
    """事件处理器协议."""

    async def __call__(self, data: Any = None) -> None:
        """处理事件."""
        ...


class EventBusProtocol(Protocol):
    """
    事件总线协议.

    用于组件间解耦通信。
    """

    def on(self, event: str, handler: Callable[..., Awaitable[None]]) -> None:
        """注册事件处理器."""
        ...

    def off(self, event: str, handler: Callable[..., Awaitable[None]]) -> None:
        """移除事件处理器."""
        ...

    async def emit(self, event: str, data: Any = None) -> None:
        """触发事件."""
        ...
