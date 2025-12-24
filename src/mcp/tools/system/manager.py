"""系统工具管理器.

负责系统工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.logging import get_logger

from .app_management.killer import kill_application, list_running_applications
from .app_management.launcher import launch_application
from .app_management.scanner import scan_installed_applications
from .tools import get_volume, set_volume

logger = get_logger()


class SystemToolsManager:
    """
    系统工具管理器.
    """

    def __init__(self):
        """
        初始化系统工具管理器.
        """
        logger.info("[SystemManager] 系统工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有系统工具.
        """
        try:
            logger.info("[SystemManager] 开始注册系统工具")

            # 注册简单工具（无复杂逻辑的）
            simple_tools = [
                (
                    "self.audio_speaker.set_volume",
                    "Set the system speaker volume to an absolute value (0-100).\n"
                    "Use when user mentions: volume, sound, louder, quieter, mute, unmute, adjust volume.\n"
                    "Examples: 'set volume to 50', 'turn volume up', 'make it louder', 'mute', "
                    "'音量设为50', '调大声音', '声音小一点', '静音'.\n"
                    "Parameter:\n"
                    "- volume: Integer (0-100) representing the target volume level. Set to 0 for mute.",
                    PropertyList(
                        [Property("volume", PropertyType.INTEGER, min_value=0, max_value=100)]
                    ),
                    set_volume,
                ),
                (
                    "self.audio_speaker.get_volume",
                    "Get the current system speaker volume level.\n"
                    "Use when user asks about: current volume, volume level, how loud, what's the volume.\n"
                    "Examples: 'what is the current volume?', 'how loud is it?', 'check volume level', "
                    "'现在音量多少?', '查看音量', '音量是多少'.\n"
                    "Returns:\n"
                    "- Integer (0-100) representing the current volume level.",
                    PropertyList([]),
                    get_volume,
                ),
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
                    PropertyList([Property("app_name", PropertyType.STRING)]),
                    launch_application,
                ),
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
                    PropertyList(
                        [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
                    ),
                    scan_installed_applications,
                ),
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
                    PropertyList(
                        [
                            Property("app_name", PropertyType.STRING),
                            Property("force", PropertyType.BOOLEAN, default_value=False),
                        ]
                    ),
                    kill_application,
                ),
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
                    PropertyList(
                        [Property("filter_name", PropertyType.STRING, default_value="")]
                    ),
                    list_running_applications,
                ),
            ]

            # 批量注册所有工具
            for tool_name, description, properties, callback in simple_tools:
                add_tool((tool_name, description, properties, callback))

            logger.info("[SystemManager] 系统工具注册完成")

        except Exception as e:
            logger.error(f"[SystemManager] 系统工具注册失败: {e}", exc_info=True)
            raise


def get_system_tools_manager() -> SystemToolsManager:
    """创建系统工具管理器实例."""
    return SystemToolsManager()
