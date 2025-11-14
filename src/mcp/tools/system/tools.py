"""系统工具实现.

提供具体的系统工具功能实现
"""

import asyncio
from typing import Any, Dict

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


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


async def _get_audio_status() -> Dict[str, Any]:
    """
    获取音频状态.
    """
    try:
        from src.utils.volume_controller import VolumeController

        if VolumeController.check_dependencies():
            volume_controller = VolumeController()
            # 使用线程池获取音量，避免阻塞
            current_volume = await asyncio.to_thread(volume_controller.get_volume)
            return {
                "volume": current_volume,
                "muted": current_volume == 0,
                "available": True,
            }
        else:
            return {
                "volume": 50,
                "muted": False,
                "available": False,
                "reason": "Dependencies not available",
            }

    except Exception as e:
        logger.warning(f"[SystemTools] 获取音频状态失败: {e}")
        return {"volume": 50, "muted": False, "available": False, "error": str(e)}


def _get_application_status() -> Dict[str, Any]:
    """
    获取应用状态信息.
    """
    try:
        from src.application import Application
        from src.iot.thing_manager import ThingManager

        app = Application.get_instance()
        thing_manager = ThingManager.get_instance()

        # DeviceState的值直接是字符串，不需要访问.name属性
        device_state = str(app.get_device_state())
        iot_count = len(thing_manager.things) if thing_manager else 0

        return {
            "device_state": device_state,
            "iot_devices": iot_count,
        }

    except Exception as e:
        logger.warning(f"[SystemTools] 获取应用状态失败: {e}")
        return {"device_state": "unknown", "iot_devices": 0, "error": str(e)}
