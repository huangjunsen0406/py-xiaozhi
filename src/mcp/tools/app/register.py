"""应用管理 MCP 工具：显式 register_app_tools."""

from __future__ import annotations

from collections.abc import Callable

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .killer import kill_application as _kill_application
from .killer import list_running_applications as _list_running_applications
from .launcher import launch_application as _launch_application
from .scanner import scan_installed_applications as _scan_installed_applications

logger = get_logger()


def register_app_tools(add_tool: Callable[[McpTool], None]) -> None:
    """向 McpServer 注册应用管理工具."""

    async def launch_application(args):
        return await _launch_application(args)

    async def scan_installed(args):
        return await _scan_installed_applications(args)

    async def kill_application(args):
        return await _kill_application(args)

    async def list_running(args):
        return await _list_running_applications(args)

    tools: list[McpTool] = [
        McpTool(
            "self.application.launch",
            (
                "Launch desktop applications and software programs by name. This tool opens applications installed "
                "on the user's computer across Windows, macOS, and Linux platforms. It automatically detects the "
                "operating system and uses appropriate launch methods.\n"
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
                "The system will try multiple launch strategies including direct execution, system commands, "
                "and path searching to find and start the application."
            ),
            PropertyList([Property("app_name", PropertyType.STRING)]),
            launch_application,
        ),
        McpTool(
            "self.application.scan_installed",
            (
                "Scan and list all installed applications on the system. This tool provides a comprehensive list "
                "of available applications that can be launched using the launch tool. It scans system directories, "
                "registry (Windows), and application folders to find installed software.\n"
                "Use this tool when:\n"
                "1. User asks what applications are available on the system\n"
                "2. You need to find the correct application name before launching\n"
                "3. User wants to see all installed software\n"
                "4. Application launch fails and you need to check available apps\n\n"
                "The scan results include both system applications (Calculator, Notepad) and user-installed software "
                "(QQ, WeChat, Chrome, etc.). Each application entry contains the clean name for launching and display "
                "name for reference.\n\n"
                "After scanning, use the 'name' field from results with self.application.launch to start applications. "
                "For example, if scan shows {name: 'QQ', display_name: 'QQ音乐'}, use self.application.launch "
                "with app_name='QQ' to launch it."
            ),
            PropertyList(
                [Property("force_refresh", PropertyType.BOOLEAN, default_value=False)]
            ),
            scan_installed,
        ),
        McpTool(
            "self.application.kill",
            (
                "Close or terminate running applications by name. This tool can gracefully close applications or "
                "force-kill them if needed. It automatically finds running processes matching the application name "
                "and terminates them.\n"
                "Use this tool when:\n"
                "1. User asks to close, quit, or exit an application\n"
                "2. User wants to stop or terminate a running program\n"
                "3. Application is unresponsive and needs to be force-closed\n"
                "4. User says 'close QQ', 'quit Chrome', 'stop music player', etc.\n\n"
                "Parameters:\n"
                "- app_name: Name of the application to close (e.g., 'QQ', 'Chrome', 'Calculator')\n"
                "- force: Set to true for force-kill unresponsive applications (default: false)\n\n"
                "The tool will find all running processes matching the application name and attempt to close them "
                "gracefully. If force=true, it will use system kill commands to immediately terminate the processes."
            ),
            PropertyList(
                [
                    Property("app_name", PropertyType.STRING),
                    Property("force", PropertyType.BOOLEAN, default_value=False),
                ]
            ),
            kill_application,
        ),
        McpTool(
            "self.application.list_running",
            (
                "List all currently running applications and processes. This tool provides real-time information "
                "about active applications on the system, including process IDs, names, and commands.\n"
                "Use this tool when:\n"
                "1. User asks what applications are currently running\n"
                "2. You need to check if a specific application is running before closing it\n"
                "3. User wants to see active processes or programs\n"
                "4. Troubleshooting application issues\n\n"
                "Parameters:\n"
                "- filter_name: Optional filter to show only applications containing this name\n\n"
                "Returns detailed information about running applications including process IDs which can be useful "
                "for targeted application management."
            ),
            PropertyList(
                [Property("filter_name", PropertyType.STRING, default_value="")]
            ),
            list_running,
        ),
    ]

    for tool in tools:
        add_tool(tool)
    logger.info("已注册 %d 个应用 MCP 工具（register_app_tools）", len(tools))
