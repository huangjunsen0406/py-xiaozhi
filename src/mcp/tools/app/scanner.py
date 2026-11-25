"""统一的应用程序扫描器入口.

根据当前系统自动选择对应的扫描器实现
"""

import json
from typing import Any, Dict

from src.logging import get_logger

from .utils import (
    dump_app_list_result,
    get_cached_applications,
    get_system_scanner,
)

logger = get_logger()


async def scan_installed_applications(args: Dict[str, Any]) -> str:
    """扫描系统中所有已安装的应用程序.

    Args:
        args: 包含扫描参数的字典
            - force_refresh: 是否强制重新扫描（可选，默认False）

    Returns:
        str: JSON格式的应用程序列表
    """
    try:
        force_refresh = bool(args.get("force_refresh", False))
        logger.info(f"[AppScanner] 开始扫描已安装应用程序，强制刷新: {force_refresh}")

        if not get_system_scanner():
            error_msg = "不支持的操作系统"
            logger.error(f"[AppScanner] {error_msg}")
            return json.dumps(
                {
                    "success": False,
                    "total_count": 0,
                    "applications": [],
                    "message": error_msg,
                },
                ensure_ascii=False,
            )

        apps = await get_cached_applications(force_refresh=force_refresh)

        compact: list[dict[str, str]] = []
        for app in apps:
            name = app.get("name") or ""
            display_name = app.get("display_name") or name
            entry: dict[str, str] = {"name": name}
            if display_name and display_name != name:
                entry["display_name"] = display_name
            compact.append(entry)

        logger.info(f"[AppScanner] 扫描完成，找到 {len(compact)} 个应用程序")
        return dump_app_list_result(
            compact,
            total_count=len(compact),
            message=f"成功扫描到 {len(compact)} 个已安装应用程序",
        )

    except Exception as e:
        error_msg = f"扫描应用程序失败: {str(e)}"
        logger.error(f"[AppScanner] {error_msg}", exc_info=True)
        return json.dumps(
            {
                "success": False,
                "total_count": 0,
                "applications": [],
                "message": error_msg,
            },
            ensure_ascii=False,
        )
