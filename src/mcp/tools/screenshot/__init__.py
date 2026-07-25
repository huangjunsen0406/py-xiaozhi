"""Screenshot tools for MCP.

截图实例由调用方创建/注入。
"""

from .register import create_screenshot_camera, register_screenshot_tools

__all__ = [
    "create_screenshot_camera",
    "register_screenshot_tools",
]
