"""系统工具包.

提供完整的系统管理功能，包括设备状态查询、音频控制等操作。
"""

from .manager import SystemToolsManager, get_system_tools_manager
from .tools import get_volume, set_volume

__all__ = [
    "SystemToolsManager",
    "get_system_tools_manager",
    "set_volume",
    "get_volume",
]
