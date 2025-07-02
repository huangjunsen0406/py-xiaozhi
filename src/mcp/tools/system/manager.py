"""系统工具管理器.

负责系统工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .tools import get_system_status, set_volume

logger = get_logger(__name__)


class SystemToolsManager:
    """
    系统工具管理器.
    """

    def __init__(self):
        """
        初始化系统工具管理器.
        """
        self._initialized = False
        logger.info("[SystemManager] 系统工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有系统工具.
        """
        try:
            logger.info("[SystemManager] 开始注册系统工具")

            # 注册获取设备状态工具
            self._register_device_status_tool(add_tool, PropertyList)

            # 注册音量控制工具
            self._register_volume_control_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            self._initialized = True
            logger.info("[SystemManager] 系统工具注册完成")

        except Exception as e:
            logger.error(f"[SystemManager] 系统工具注册失败: {e}", exc_info=True)
            raise

    def _register_device_status_tool(self, add_tool, PropertyList):
        """
        注册设备状态查询工具.
        """
        add_tool(
            (
                "self.get_device_status",
                "Provides comprehensive real-time system information including "
                "OS details, CPU usage, memory status, disk usage, battery info, "
                "audio speaker volume and settings, and application state.\n"
                "Use this tool for: \n"
                "1. Answering questions about current system condition\n"
                "2. Getting detailed hardware and software status\n"
                "3. Checking current audio volume level and mute status\n"
                "4. As the first step before controlling device settings",
                PropertyList(),
                get_system_status,
            )
        )
        logger.debug("[SystemManager] 注册设备状态工具成功")

    def _register_volume_control_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册音量控制工具.
        """
        volume_props = PropertyList(
            [Property("volume", PropertyType.INTEGER, min_value=0, max_value=100)]
        )
        add_tool(
            (
                "self.audio_speaker.set_volume",
                "Set the volume of the audio speaker. If the current volume is "
                "unknown, you must call `self.get_device_status` tool first and "
                "then call this tool.",
                volume_props,
                set_volume,
            )
        )
        logger.debug("[SystemManager] 注册音量控制工具成功")

    def is_initialized(self) -> bool:
        """
        检查管理器是否已初始化.
        """
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        """
        获取管理器状态.
        """
        return {
            "initialized": self._initialized,
            "tools_count": 2,  # 当前注册的工具数量
            "available_tools": ["get_device_status", "set_volume"],
        }


# 全局管理器实例
_system_tools_manager = None


def get_system_tools_manager() -> SystemToolsManager:
    """
    获取系统工具管理器单例.
    """
    global _system_tools_manager
    if _system_tools_manager is None:
        _system_tools_manager = SystemToolsManager()
        logger.debug("[SystemManager] 创建系统工具管理器实例")
    return _system_tools_manager
