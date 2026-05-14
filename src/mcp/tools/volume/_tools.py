"""音量控制 MCP 工具（装饰器注册）."""

import asyncio
import json
from typing import Any

from src.logging import get_logger
from src.mcp.decorators import Prop, PropType, mcp_tool

from .volume_controller import VolumeController

logger = get_logger()

_volume_controller: VolumeController | None = None


def _get_volume_controller() -> VolumeController | None:
    """获取或初始化模块级音量控制器单例."""
    global _volume_controller
    if _volume_controller is None:
        if not VolumeController.check_dependencies():
            return None
        try:
            _volume_controller = VolumeController()
        except Exception as e:
            logger.error(f"音量控制器初始化失败: {e}", exc_info=True)
            return None
    return _volume_controller


async def _set_volume(args: dict[str, Any]) -> bool:
    """设置音量."""
    try:
        volume = args["volume"]
        logger.info(f"[VolumeTools] 设置音量到 {volume}")

        # 验证音量范围
        if not (0 <= volume <= 100):
            logger.warning(f"[VolumeTools] 音量值超出范围: {volume}")
            return False

        controller = _get_volume_controller()
        if controller is None:
            logger.warning("[VolumeTools] 音量控制依赖不完整，无法设置音量")
            return False

        await asyncio.to_thread(controller.set_volume, volume)
        logger.info(f"[VolumeTools] 音量设置成功: {volume}")
        return True

    except KeyError:
        logger.error("[VolumeTools] 缺少volume参数")
        return False
    except Exception as e:
        logger.error(f"[VolumeTools] 设置音量失败: {e}", exc_info=True)
        return False


async def _get_volume(args: dict[str, Any]) -> int:
    """获取当前音量."""
    try:
        logger.info("[VolumeTools] 获取当前音量")

        controller = _get_volume_controller()
        if controller is None:
            logger.warning("[VolumeTools] 音量控制依赖不完整，返回默认音量")
            return VolumeController.DEFAULT_VOLUME

        current_volume = await asyncio.to_thread(controller.get_volume)
        logger.info(f"[VolumeTools] 当前音量: {current_volume}")
        return current_volume

    except Exception as e:
        logger.error(f"[VolumeTools] 获取音量失败: {e}", exc_info=True)
        return VolumeController.DEFAULT_VOLUME


async def _get_volume_status(args: dict[str, Any]) -> str:
    """获取音频状态（音量/静音/可用性）."""
    try:
        controller = _get_volume_controller()
        if controller is not None:
            current_volume = await asyncio.to_thread(controller.get_volume)
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
        logger.warning(f"[VolumeTools] 获取音量状态失败: {e}")
        status = {
            "volume": 50,
            "muted": False,
            "available": False,
            "error": str(e),
        }

    return json.dumps(status, ensure_ascii=False)


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
