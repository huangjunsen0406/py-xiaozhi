"""系统级 MCP 工具（装饰器注册）."""

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool

from .app_management.killer import kill_application as _kill_application
from .app_management.killer import (
    list_running_applications as _list_running_applications,
)
from .app_management.launcher import launch_application as _launch_application
from .app_management.scanner import (
    scan_installed_applications as _scan_installed_applications,
)
from .tools import get_volume as _get_volume
from .tools import get_volume_status as _get_volume_status
from .tools import set_volume as _set_volume

logger = get_logger()


@mcp_tool(
    name="self.audio_speaker.set_volume",
    description=(
        "Set the system speaker volume to an absolute value (0-100).\n"
        "Use when user mentions: volume, sound, louder, quieter, mute, unmute, adjust volume.\n"
        "Examples: 'set volume to 50', 'turn volume up', 'make it louder', 'mute', "
        "'音量设为50', '调大声音', '声音小一点', '静音'.\n"
        "Parameter:\n"
        "- volume: Integer (0-100) representing the target volume level. Set to 0 for mute."
    ),
    props=[Prop("volume", PropType.INT, min_val=0, max_val=100)],
)
async def tool_set_volume(args):
    return await _set_volume(args)


@mcp_tool(
    name="self.audio_speaker.get_volume",
    description=(
        "Get the current system speaker volume level.\n"
        "Use when user asks about: current volume, volume level, how loud, what's the volume.\n"
        "Examples: 'what is the current volume?', 'how loud is it?', 'check volume level', "
        "'现在音量多少?', '查看音量', '音量是多少'.\n"
        "Returns: Integer (0-100) representing the current volume level."
    ),
)
async def tool_get_volume(args):
    return await _get_volume(args)


@mcp_tool(
    name="self.audio_speaker.get_volume_status",
    description=(
        "Get detailed speaker volume status including whether audio output is muted and "
        "whether the volume controller dependencies are available. Returns a JSON payload "
        "with fields: volume (0-100), muted (bool), available (bool), reason/error(optional)."
    ),
)
async def tool_get_volume_status(args):
    return await _get_volume_status(args)


@mcp_tool(
    name="self.application.launch",
    description=(
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
    props=[Prop("app_name", PropType.STR)],
)
async def tool_launch_application(args):
    return await _launch_application(args)


@mcp_tool(
    name="self.application.scan_installed",
    description=(
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
    props=[Prop("force_refresh", PropType.BOOL, default=False)],
)
async def tool_scan_installed(args):
    return await _scan_installed_applications(args)


@mcp_tool(
    name="self.application.kill",
    description=(
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
    props=[
        Prop("app_name", PropType.STR),
        Prop("force", PropType.BOOL, default=False),
    ],
)
async def tool_kill_application(args):
    return await _kill_application(args)


@mcp_tool(
    name="self.application.list_running",
    description=(
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
    props=[Prop("filter_name", PropType.STR, default="")],
)
async def tool_list_running(args):
    return await _list_running_applications(args)
