"""UI 相关事件的数据类."""

from dataclasses import dataclass


@dataclass
class UISendTextRequest:
    """发文本."""

    text: str
