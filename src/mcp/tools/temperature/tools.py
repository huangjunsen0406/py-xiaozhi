"""温度和湿度工具实现.

提供获取室内温度和湿度数据的功能
"""

import sys
from typing import Any, Dict

from src.utils.logging_config import get_logger

# 添加mcps路径到sys.path
mcps_path = "/home/orangepi/super-orangepi/mcps"
if mcps_path not in sys.path:
    sys.path.insert(0, mcps_path)

from temperature.temperature_tool import get_temperature_humidity

logger = get_logger(__name__)


async def get_temperature_humidity_wrapper(args: Dict[str, Any]) -> str:
    """
    获取室内温度和湿度数据.

    Args:
        args: 参数字典，包含可选的pin参数

    Returns:
        JSON字符串，包含温度和湿度数据
    """
    try:
        logger.info("[TemperatureTools] 开始获取温度和湿度数据")

        result = await get_temperature_humidity(args)

        logger.info("[TemperatureTools] 成功获取温度和湿度数据")
        return result

    except Exception as e:
        logger.error(f"[TemperatureTools] 获取温度湿度数据失败: {e}", exc_info=True)
        import json
        return json.dumps({"error": str(e)}, ensure_ascii=False)