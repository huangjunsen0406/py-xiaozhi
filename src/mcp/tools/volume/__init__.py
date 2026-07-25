"""音量控制工具.

- VolumeController / 平台后端：见 volume_controller / windows|macos|linux
- register_volume_tools: 向 McpServer 注册（闭包持有 controller，无模块单例）
"""

from ._tools import create_volume_controller, register_volume_tools
from .volume_controller import VolumeController

__all__ = [
    "VolumeController",
    "create_volume_controller",
    "register_volume_tools",
]
