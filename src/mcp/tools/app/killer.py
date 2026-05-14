"""应用终止和运行进程管理.

通过 process_manager（psutil）提供跨平台的进程终止和列表功能。
"""

import asyncio
import json
from typing import Any

from src.logging import get_logger

from .process_manager import kill_application_by_name
from .process_manager import list_running_applications as _list_apps

logger = get_logger()


async def kill_application(args: dict[str, Any]) -> bool:
    """关闭应用程序.

    Args:
        args: 包含应用程序名称的参数字典
            - app_name: 应用程序名称
            - force: 是否强制关闭（可选，默认 False）

    Returns:
        关闭是否成功
    """
    try:
        app_name = args["app_name"]
        force = args.get("force", False)
        logger.info(f"[AppKiller] 尝试关闭应用程序: {app_name}, 强制关闭: {force}")

        success = await asyncio.to_thread(kill_application_by_name, app_name, force)

        if success:
            logger.info(f"[AppKiller] 成功关闭应用程序: {app_name}")
        else:
            logger.warning(f"[AppKiller] 未能关闭应用程序: {app_name}")

        return success

    except Exception as e:
        logger.error(f"[AppKiller] 关闭应用程序时出错: {e}", exc_info=True)
        return False


async def list_running_applications(args: dict[str, Any]) -> str:
    """列出所有正在运行的应用程序.

    Args:
        args: 包含列出参数的字典
            - filter_name: 过滤应用程序名称（可选）

    Returns:
        JSON 格式的运行中应用程序列表
    """
    try:
        filter_name = args.get("filter_name", "")
        logger.info(f"[AppKiller] 开始列出正在运行的应用程序，过滤条件: {filter_name}")

        apps = await asyncio.to_thread(_list_apps, filter_name)

        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps[:50],
            "message": f"找到 {len(apps)} 个正在运行的应用程序",
        }

        logger.info(f"[AppKiller] 列出完成，找到 {len(apps)} 个正在运行的应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"列出运行中应用程序失败: {e}"
        logger.error(f"[AppKiller] {error_msg}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "total_count": 0,
                "applications": [],
                "message": error_msg,
            },
            ensure_ascii=False,
        )
