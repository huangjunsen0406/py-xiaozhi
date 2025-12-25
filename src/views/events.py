"""UI 事件数据类型定义.

用于 EventBus 事件通信的数据结构。
"""

from dataclasses import dataclass


@dataclass
class UITextUpdate:
    """UI 文本更新事件数据.

    Attributes:
        text: 要显示的文本
    """

    text: str


@dataclass
class UIEmotionUpdate:
    """UI 表情更新事件数据.

    Attributes:
        emotion: 表情名称 (如 "happy", "sad", "neutral" 等)
    """

    emotion: str


@dataclass
class UIStatusUpdate:
    """UI 状态更新事件数据.

    Attributes:
        status: 状态文本
        connected: 是否已连接
    """

    status: str
    connected: bool


@dataclass
class UISendTextRequest:
    """UI 发送文本请求数据.

    Attributes:
        text: 要发送的文本
    """

    text: str
