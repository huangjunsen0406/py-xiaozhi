"""倒计时器MCP工具函数.

提供给MCP服务器调用的异步工具函数
"""

import json
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .timer_service import get_timer_service

logger = get_logger(__name__)


async def start_countdown_timer(args: Dict[str, Any]) -> str:
    """启动一个倒计时任务.

    Args:
        args: 包含以下参数的字典
            - command: 要执行的MCP工具调用 (JSON格式字符串，包含name和arguments字段)
            - delay: 延迟时间（秒），可选，默认为5秒
            - description: 任务描述，可选

    Returns:
        str: JSON格式的结果字符串
    """
    try:
        command = args["command"]
        delay = args.get("delay")
        description = args.get("description", "")

        logger.info(f"[TimerTools] 启动倒计时 - 命令: {command}, 延迟: {delay}秒")

        timer_service = get_timer_service()
        result = await timer_service.start_countdown(
            command=command, delay=delay, description=description
        )

        logger.info(f"[TimerTools] 倒计时启动结果: {result['success']}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[TimerTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"启动倒计时失败: {str(e)}"
        logger.error(f"[TimerTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def cancel_countdown_timer(args: Dict[str, Any]) -> str:
    """取消指定的倒计时任务.

    Args:
        args: 包含以下参数的字典
            - timer_id: 要取消的计时器ID

    Returns:
        str: JSON格式的结果字符串
    """
    try:
        timer_id = args["timer_id"]

        logger.info(f"[TimerTools] 取消倒计时 {timer_id}")

        timer_service = get_timer_service()
        result = await timer_service.cancel_countdown(timer_id)

        logger.info(f"[TimerTools] 倒计时取消结果: {result['success']}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[TimerTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"取消倒计时失败: {str(e)}"
        logger.error(f"[TimerTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def get_active_countdown_timers(args: Dict[str, Any]) -> str:
    """获取所有活动的倒计时任务状态.

    Args:
        args: 空字典（此函数无需参数）

    Returns:
        str: JSON格式的活动计时器列表
    """
    try:
        logger.info("[TimerTools] 获取活动倒计时列表")

        timer_service = get_timer_service()
        result = await timer_service.get_active_timers()

        logger.info(f"[TimerTools] 当前活动倒计时数量: {result['total_active_timers']}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        error_msg = f"获取活动倒计时失败: {str(e)}"
        logger.error(f"[TimerTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
