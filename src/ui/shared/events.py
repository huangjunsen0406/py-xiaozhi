"""UI 事件数据类型定义.

用于 EventBus 事件通信的数据结构。
"""

from dataclasses import dataclass


@dataclass
class UITextUpdate:
    """UI 文本更新事件数据."""

    text: str


@dataclass
class UIEmotionUpdate:
    """UI 表情更新事件数据."""

    emotion: str


@dataclass
class UIStatusUpdate:
    """UI 状态更新事件数据."""

    status: str
    connected: bool


@dataclass
class UISendTextRequest:
    """UI 发送文本请求数据."""

    text: str
