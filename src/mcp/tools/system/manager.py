"""系统工具管理器.

负责系统工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .app_management.killer import kill_application, list_running_applications
from .app_management.launcher import launch_application
from .app_management.scanner import scan_installed_applications
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

            # 注册应用程序启动工具
            self._register_app_launcher_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册应用程序扫描工具
            self._register_app_scanner_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册应用程序关闭工具
            self._register_app_killer_tools(
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
                "【音量控制】当用户提到：调音量、声音大小、音量设为、调大声音、调小声音、声音太大/太小、"
                "静音、取消静音、增大音量、降低音量、把声音、音量调整、声音调节 时调用本工具。\n"
                "功能：设置系统扬声器音量到绝对值(0-100)。\n"
                "使用场景：\n"
                "1. 用户要求设置音量到具体数值 (例如: '音量设为50', '把声音调到80', 'volume to 30')\n"
                "2. 用户要求相对调整音量 ('调大一点', '声音小一点', '再大声点'): 必须先调用 "
                "`self.get_device_status` 获取当前 audio_speaker.volume, 计算目标值(保持在0-100内), 然后调用本工具\n"
                "3. 静音/取消静音: 静音设volume=0, 取消静音可设为之前的值或默认值(如30-50)\n\n"
                "参数说明：\n"
                "- volume: 整数类型，范围[0, 100]，表示目标音量的绝对值\n\n"
                "重要提示：如果当前音量未知，切勿猜测 —— 必须先调用 `self.get_device_status` 获取。"
                "本工具不支持切换静音状态，要静音请设置volume=0。\n"
                "English: Set the volume of the audio speaker. If the current volume is unknown, "
                "you must call `self.get_device_status` tool first and then call this tool. "
                "Use when user mentions: volume, sound, louder, quieter, mute, unmute, adjust volume. "
                "Examples: '音量设为50', '调大声音', '声音小一点', 'set volume to 80', 'turn it up'.",
                volume_props,
                set_volume,
            )
        )
        logger.debug("[SystemManager] 注册音量控制工具成功")

    def _register_app_launcher_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册应用程序启动工具.
        """
        app_props = PropertyList([Property("app_name", PropertyType.STRING)])
        add_tool(
            (
                "self.application.launch",
                "Launch desktop applications and software programs by name. This tool "
                "opens applications installed on the user's computer across Windows, "
                "macOS, and Linux platforms. It automatically detects the operating "
                "system and uses appropriate launch methods.\n"
                "Use this tool when the user wants to:\n"
                "1. Open specific software applications (e.g., 'QQ', 'QQ音乐', 'WeChat', '微信')\n"
                "2. Launch system utilities (e.g., 'Calculator', '计算器', 'Notepad', '记事本')\n"
                "3. Start browsers (e.g., 'Chrome', 'Firefox', 'Safari')\n"
                "4. Open media players (e.g., 'VLC', 'Windows Media Player')\n"
                "5. Launch development tools (e.g., 'VS Code', 'PyCharm')\n"
                "6. Start games or other installed programs\n\n"
                "Examples of valid app names:\n"
                "- Chinese: 'QQ音乐', '微信', '计算器', '记事本', '浏览器'\n"
                "- English: 'QQ', 'WeChat', 'Calculator', 'Notepad', 'Chrome'\n"
                "- Mixed: 'QQ Music', 'Microsoft Word', 'Adobe Photoshop'\n\n"
                "The system will try multiple launch strategies including direct execution, "
                "system commands, and path searching to find and start the application.",
                app_props,
                launch_application,
            )
        )
        logger.debug("[SystemManager] 注册应用程序启动工具成功")

    def _register_app_scanner_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册应用程序扫描工具.
        """
        scanner_props = PropertyList(
            [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
        )
        add_tool(
            (
                "self.application.scan_installed",
                "Scan and list all installed applications on the system. This tool "
                "provides a comprehensive list of available applications that can be "
                "launched using the launch tool. It scans system directories, registry "
                "(Windows), and application folders to find installed software.\n"
                "Use this tool when:\n"
                "1. User asks what applications are available on the system\n"
                "2. You need to find the correct application name before launching\n"
                "3. User wants to see all installed software\n"
                "4. Application launch fails and you need to check available apps\n\n"
                "The scan results include both system applications (Calculator, Notepad) "
                "and user-installed software (QQ, WeChat, Chrome, etc.). Each application "
                "entry contains the clean name for launching and display name for reference.\n\n"
                "After scanning, use the 'name' field from results with self.application.launch "
                "to start applications. For example, if scan shows {name: 'QQ', display_name: 'QQ音乐'}, "
                "use self.application.launch with app_name='QQ' to launch it.",
                scanner_props,
                scan_installed_applications,
            )
        )
        logger.debug("[SystemManager] 注册应用程序扫描工具成功")

    def _register_app_killer_tools(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册应用程序关闭工具.
        """
        # 注册应用程序关闭工具
        killer_props = PropertyList(
            [
                Property("app_name", PropertyType.STRING),
                Property("force", PropertyType.BOOLEAN, default_value=False),
            ]
        )
        add_tool(
            (
                "self.application.kill",
                "Close or terminate running applications by name. This tool can gracefully "
                "close applications or force-kill them if needed. It automatically finds "
                "running processes matching the application name and terminates them.\n"
                "Use this tool when:\n"
                "1. User asks to close, quit, or exit an application\n"
                "2. User wants to stop or terminate a running program\n"
                "3. Application is unresponsive and needs to be force-closed\n"
                "4. User says 'close QQ', 'quit Chrome', 'stop music player', etc.\n\n"
                "Parameters:\n"
                "- app_name: Name of the application to close (e.g., 'QQ', 'Chrome', 'Calculator')\n"
                "- force: Set to true for force-kill unresponsive applications (default: false)\n\n"
                "The tool will find all running processes matching the application name and "
                "attempt to close them gracefully. If force=true, it will use system kill "
                "commands to immediately terminate the processes.",
                killer_props,
                kill_application,
            )
        )

        # 注册运行中应用程序列表工具
        list_props = PropertyList(
            [Property("filter_name", PropertyType.STRING, default_value="")]
        )
        add_tool(
            (
                "self.application.list_running",
                "List all currently running applications and processes. This tool provides "
                "real-time information about active applications on the system, including "
                "process IDs, names, and commands.\n"
                "Use this tool when:\n"
                "1. User asks what applications are currently running\n"
                "2. You need to check if a specific application is running before closing it\n"
                "3. User wants to see active processes or programs\n"
                "4. Troubleshooting application issues\n\n"
                "Parameters:\n"
                "- filter_name: Optional filter to show only applications containing this name\n\n"
                "Returns detailed information about running applications including process IDs "
                "which can be useful for targeted application management.",
                list_props,
                list_running_applications,
            )
        )
        logger.debug("[SystemManager] 注册应用程序关闭工具成功")

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
            "tools_count": 6,  # 当前注册的工具数量
            "available_tools": [
                "get_device_status",
                "set_volume",
                "launch_application",
                "scan_installed_applications",
                "kill_application",
                "list_running_applications",
            ],
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
