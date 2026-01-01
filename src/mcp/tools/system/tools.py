"""系统工具实现.

提供具体的系统工具功能实现
"""

import asyncio
from typing import Any, Dict

from src.logging import get_logger

logger = get_logger()


async def set_volume(args: Dict[str, Any]) -> bool:
    """
    设置音量.
    """
    try:
        volume = args["volume"]
        logger.info(f"[SystemTools] 设置音量到 {volume}")

        # 验证音量范围
        if not (0 <= volume <= 100):
            logger.warning(f"[SystemTools] 音量值超出范围: {volume}")
            return False

        # 直接使用VolumeController设置音量
        from src.utils.volume_controller import VolumeController

        # 检查依赖并创建音量控制器
        if not VolumeController.check_dependencies():
            logger.warning("[SystemTools] 音量控制依赖不完整，无法设置音量")
            return False

        volume_controller = VolumeController()
        await asyncio.to_thread(volume_controller.set_volume, volume)
        logger.info(f"[SystemTools] 音量设置成功: {volume}")
        return True

    except KeyError:
        logger.error("[SystemTools] 缺少volume参数")
        return False
    except Exception as e:
        logger.error(f"[SystemTools] 设置音量失败: {e}", exc_info=True)
        return False


async def get_volume(args: Dict[str, Any]) -> int:
    """
    获取当前音量.
    """
    try:
        logger.info("[SystemTools] 获取当前音量")

        # 直接使用VolumeController获取音量
        from src.utils.volume_controller import VolumeController

        # 检查依赖并创建音量控制器
        if not VolumeController.check_dependencies():
            logger.warning("[SystemTools] 音量控制依赖不完整，返回默认音量")
            return VolumeController.DEFAULT_VOLUME

        volume_controller = VolumeController()
        current_volume = await asyncio.to_thread(volume_controller.get_volume)
        logger.info(f"[SystemTools] 当前音量: {current_volume}")
        return current_volume

    except Exception as e:
        logger.error(f"[SystemTools] 获取音量失败: {e}", exc_info=True)
        from src.utils.volume_controller import VolumeController

        return VolumeController.DEFAULT_VOLUME


async def get_volume_status(args: Dict[str, Any]) -> str:
    """
    获取音频状态（音量/静音/可用性）.
    """
    try:
        from src.utils.volume_controller import VolumeController

        if VolumeController.check_dependencies():
            volume_controller = VolumeController()
            current_volume = await asyncio.to_thread(volume_controller.get_volume)
            status = {
                "volume": current_volume,
                "muted": current_volume == 0,
                "available": True,
            }
        else:
            status = {
                "volume": 50,
                "muted": False,
                "available": False,
                "reason": "Dependencies not available",
            }
    except Exception as e:
        logger.warning(f"[SystemTools] 获取音量状态失败: {e}")
        status = {
            "volume": 50,
            "muted": False,
            "available": False,
            "error": str(e),
        }

    import json

    return json.dumps(status, ensure_ascii=False)
