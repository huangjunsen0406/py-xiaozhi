"""统一的应用程序扫描器入口.

根据当前系统自动选择对应的扫描器实现
"""

import asyncio
import json
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .utils import get_system_scanner

logger = get_logger(__name__)


async def scan_installed_applications(args: Dict[str, Any]) -> str:
    """扫描系统中所有已安装的应用程序.

    Args:
        args: 包含扫描参数的字典
            - force_refresh: 是否强制重新扫描（可选，默认False）

    Returns:
        str: JSON格式的应用程序列表
    """
    try:
        force_refresh = args.get("force_refresh", False)
        logger.info(f"[AppScanner] 开始扫描已安装应用程序，强制刷新: {force_refresh}")

        # 获取系统对应的扫描器
        scanner = get_system_scanner()
        if not scanner:
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

        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(scanner.scan_installed_applications)

        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"成功扫描到 {len(apps)} 个已安装应用程序",
        }

        logger.info(f"[AppScanner] 扫描完成，找到 {len(apps)} 个应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)

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


async def list_running_applications(args: Dict[str, Any]) -> str:
    """列出系统中正在运行的应用程序.

    Args:
        args: 包含过滤参数的字典
            - filter_name: 应用名称过滤条件（可选）

    Returns:
        str: JSON格式的运行应用程序列表
    """
    try:
        filter_name = args.get("filter_name", "")
        logger.info(f"[AppScanner] 开始列出正在运行的应用程序，过滤条件: {filter_name}")

        # 获取系统对应的扫描器
        scanner = get_system_scanner()
        if not scanner:
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

        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(scanner.scan_running_applications)

        # 应用过滤条件
        if filter_name:
            filter_lower = filter_name.lower()
            filtered_apps = []
            for app in apps:
                if (
                    filter_lower in app.get("name", "").lower()
                    or filter_lower in app.get("display_name", "").lower()
                    or filter_lower in app.get("command", "").lower()
                ):
                    filtered_apps.append(app)
            apps = filtered_apps

        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"找到 {len(apps)} 个正在运行的应用程序",
        }

        logger.info(f"[AppScanner] 列出完成，找到 {len(apps)} 个正在运行的应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"列出运行应用程序失败: {str(e)}"
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
