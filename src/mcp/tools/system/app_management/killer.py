"""统一的应用程序关闭器.

根据系统自动选择对应的关闭器实现
"""

import asyncio
import json
import platform
from typing import Any, Dict, List

from src.utils.logging_config import get_logger

from .utils import AppMatcher

logger = get_logger(__name__)


async def kill_application(args: Dict[str, Any]) -> bool:
    """关闭应用程序.

    Args:
        args: 包含应用程序名称的参数字典
            - app_name: 应用程序名称
            - force: 是否强制关闭（可选，默认False）

    Returns:
        bool: 关闭是否成功
    """
    try:
        app_name = args["app_name"]
        force = args.get("force", False)
        logger.info(f"[AppKiller] 尝试关闭应用程序: {app_name}, 强制关闭: {force}")

        # 首先尝试通过扫描找到正在运行的应用程序
        running_apps = await _find_running_applications(app_name)

        if not running_apps:
            logger.warning(f"[AppKiller] 未找到正在运行的应用程序: {app_name}")
            return False

        # 按系统选择关闭策略
        system = platform.system()
        if system == "Windows":
            # Windows使用复杂的分组关闭策略
            success = await asyncio.to_thread(
                _kill_windows_app_group, running_apps, app_name, force
            )
        else:
            # macOS和Linux使用简单的逐个关闭策略
            success_count = 0
            for app in running_apps:
                success = await asyncio.to_thread(_kill_app_sync, app, force, system)
                if success:
                    success_count += 1
                    logger.info(
                        f"[AppKiller] 成功关闭应用程序: {app['name']} (PID: {app.get('pid', 'N/A')})"
                    )
                else:
                    logger.warning(
                        f"[AppKiller] 关闭应用程序失败: {app['name']} (PID: {app.get('pid', 'N/A')})"
                    )

            success = success_count > 0
            logger.info(
                f"[AppKiller] 关闭操作完成，成功关闭 {success_count}/{len(running_apps)} 个进程"
            )

        return success

    except Exception as e:
        logger.error(f"[AppKiller] 关闭应用程序时出错: {e}", exc_info=True)
        return False


async def list_running_applications(args: Dict[str, Any]) -> str:
    """列出所有正在运行的应用程序.

    Args:
        args: 包含列出参数的字典
            - filter_name: 过滤应用程序名称（可选）

    Returns:
        str: JSON格式的运行中应用程序列表
    """
    try:
        filter_name = args.get("filter_name", "")
        logger.info(f"[AppKiller] 开始列出正在运行的应用程序，过滤条件: {filter_name}")

        # 使用线程池执行扫描，避免阻塞事件循环
        apps = await asyncio.to_thread(_list_running_apps_sync, filter_name)

        result = {
            "success": True,
            "total_count": len(apps),
            "applications": apps,
            "message": f"找到 {len(apps)} 个正在运行的应用程序",
        }

        logger.info(f"[AppKiller] 列出完成，找到 {len(apps)} 个正在运行的应用程序")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"列出运行中应用程序失败: {str(e)}"
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


async def _find_running_applications(app_name: str) -> List[Dict[str, Any]]:
    """查找正在运行的匹配应用程序.

    Args:
        app_name: 要查找的应用程序名称

    Returns:
        匹配的正在运行应用程序列表
    """
    try:
        # 获取所有正在运行的应用程序
        all_apps = await asyncio.to_thread(_list_running_apps_sync, "")

        # 使用统一匹配器找到最佳匹配
        matched_apps = []

        for app in all_apps:
            score = AppMatcher.match_application(app_name, app)
            if score >= 50:  # 匹配度阈值
                matched_apps.append(app)

        # 按匹配度排序
        matched_apps.sort(
            key=lambda x: AppMatcher.match_application(app_name, x), reverse=True
        )

        logger.info(f"[AppKiller] 找到 {len(matched_apps)} 个匹配的运行应用")
        return matched_apps

    except Exception as e:
        logger.warning(f"[AppKiller] 查找运行中应用程序时出错: {e}")
        return []


def _list_running_apps_sync(filter_name: str = "") -> List[Dict[str, Any]]:
    """同步列出正在运行的应用程序.

    Args:
        filter_name: 过滤应用程序名称

    Returns:
        正在运行的应用程序列表
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        from .mac.killer import list_running_applications

        return list_running_applications(filter_name)
    elif system == "Windows":  # Windows
        from .windows.killer import list_running_applications

        return list_running_applications(filter_name)
    elif system == "Linux":  # Linux
        from .linux.killer import list_running_applications

        return list_running_applications(filter_name)
    else:
        logger.warning(f"[AppKiller] 不支持的操作系统: {system}")
        return []


def _kill_app_sync(app: Dict[str, Any], force: bool, system: str) -> bool:
    """同步关闭应用程序.

    Args:
        app: 应用程序信息
        force: 是否强制关闭
        system: 操作系统类型

    Returns:
        bool: 关闭是否成功
    """
    try:
        pid = app.get("pid")
        if not pid:
            return False

        if system == "Windows":
            from .windows.killer import kill_application

            return kill_application(pid, force)
        elif system == "Darwin":  # macOS
            from .mac.killer import kill_application

            return kill_application(pid, force)
        elif system == "Linux":  # Linux
            from .linux.killer import kill_application

            return kill_application(pid, force)
        else:
            logger.error(f"[AppKiller] 不支持的操作系统: {system}")
            return False

    except Exception as e:
        logger.error(f"[AppKiller] 同步关闭应用程序失败: {e}")
        return False


def _kill_windows_app_group(
    apps: List[Dict[str, Any]], app_name: str, force: bool
) -> bool:
    """Windows系统的分组关闭策略.

    Args:
        apps: 匹配的应用程序进程列表
        app_name: 应用程序名称
        force: 是否强制关闭

    Returns:
        bool: 关闭是否成功
    """
    try:
        from .windows.killer import kill_application_group

        return kill_application_group(apps, app_name, force)
    except Exception as e:
        logger.error(f"[AppKiller] Windows分组关闭失败: {e}")
        return False


def get_system_killer():
    """根据当前系统获取对应的关闭器模块.

    Returns:
        对应系统的关闭器模块
    """
    system = platform.system()

    if system == "Darwin":  # macOS
        from .mac import killer

        return killer
    elif system == "Windows":  # Windows
        from .windows import killer

        return killer
    elif system == "Linux":  # Linux
        from .linux import killer

        return killer
    else:
        logger.warning(f"[AppKiller] 不支持的系统: {system}")
        return None
