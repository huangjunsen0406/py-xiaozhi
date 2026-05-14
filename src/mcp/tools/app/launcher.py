"""统一的应用程序启动器.

根据系统自动选择对应的启动器实现。
"""

import asyncio
import platform
from typing import Any

from src.logging import get_logger

from .utils import find_best_matching_app

logger = get_logger()


async def launch_application(args: dict[str, Any]) -> bool:
    try:
        app_name = args["app_name"]
        logger.info(f"[AppLauncher] 尝试启动应用程序: {app_name}")

        matched_app = await _find_matching_application(app_name)
        if matched_app:
            logger.info(
                f"[AppLauncher] 找到匹配的应用程序: "
                f"{matched_app.get('display_name', matched_app.get('name', ''))}"
            )
            success = await _launch_matched_app(matched_app, app_name)
        else:
            logger.info(f"[AppLauncher] 未找到精确匹配，使用原始名称: {app_name}")
            success = await _launch_by_name(app_name)

        if success:
            logger.info(f"[AppLauncher] 成功启动应用程序: {app_name}")
        else:
            logger.warning(f"[AppLauncher] 启动应用程序失败: {app_name}")

        return success

    except KeyError:
        logger.error("[AppLauncher] 缺少app_name参数")
        return False
    except Exception as e:
        logger.error(f"[AppLauncher] 启动应用程序失败: {e}", exc_info=True)
        return False


async def _find_matching_application(app_name: str) -> dict[str, Any] | None:
    try:
        return await find_best_matching_app(app_name, "installed")
    except Exception as e:
        logger.warning(f"[AppLauncher] 查找匹配应用程序时出错: {e}")
        return None


async def _launch_matched_app(
    matched_app: dict[str, Any], original_name: str
) -> bool:
    try:
        app_type = matched_app.get("type", "unknown")
        app_path = matched_app.get("path", matched_app.get("name", original_name))
        system = platform.system()

        if system == "Windows":
            if app_type == "uwp":
                from .launcher_windows import launch_uwp_app_by_path

                return await asyncio.to_thread(launch_uwp_app_by_path, app_path)
            elif app_type == "shortcut" and app_path.endswith(".lnk"):
                from .launcher_windows import launch_shortcut

                return await asyncio.to_thread(launch_shortcut, app_path)

        return await _launch_by_name(app_path)

    except Exception as e:
        logger.error(f"[AppLauncher] 启动匹配应用失败: {e}")
        return False


async def _launch_by_name(app_name: str) -> bool:
    try:
        system = platform.system()

        if system == "Windows":
            from .launcher_windows import launch_application

            return await asyncio.to_thread(launch_application, app_name)
        elif system == "Darwin":
            from .launcher_mac import launch_application

            return await asyncio.to_thread(launch_application, app_name)
        elif system == "Linux":
            from .launcher_linux import launch_application

            return await asyncio.to_thread(launch_application, app_name)
        else:
            logger.error(f"[AppLauncher] 不支持的操作系统: {system}")
            return False

    except Exception as e:
        logger.error(f"[AppLauncher] 启动应用程序失败: {e}")
        return False
