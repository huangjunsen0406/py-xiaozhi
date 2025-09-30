from abc import ABC, abstractmethod
from typing import Callable, Optional

from src.utils.logging_config import get_logger


class BaseDisplay(ABC):
    """
    显示接口的抽象基类.
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    async def set_callbacks(
        self,
        press_callback: Optional[Callable] = None,
        release_callback: Optional[Callable] = None,
        mode_callback: Optional[Callable] = None,
        auto_callback: Optional[Callable] = None,
        abort_callback: Optional[Callable] = None,
        send_text_callback: Optional[Callable] = None,
    ):
        """
        设置回调函数.
        """

    @abstractmethod
    async def update_button_status(self, text: str):
        """
        更新按钮状态.
        """

    @abstractmethod
    async def update_status(self, status: str, connected: bool):
        """
        更新状态文本.
        """

    @abstractmethod
    async def update_text(self, text: str):
        """
        更新TTS文本.
        """

    @abstractmethod
    async def update_emotion(self, emotion_name: str):
        """
        更新表情.
        """

    @abstractmethod
    async def start(self):
        """
        启动显示.
        """

    @abstractmethod
    async def close(self):
        """
        关闭显示.
        """
