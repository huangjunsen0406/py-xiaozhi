"""温度和湿度工具管理器.

负责温度和湿度工具的初始化、配置和MCP工具注册
"""

from src.utils.logging_config import get_logger

from .tools import get_temperature_humidity_wrapper

logger = get_logger(__name__)


class TemperatureToolsManager:
    """
    温度和湿度工具管理器.
    """

    def __init__(self):
        """
        初始化温度和湿度工具管理器.
        """
        self._initialized = False
        logger.info("[TemperatureManager] 温度和湿度工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有温度和湿度工具.
        """
        try:
            logger.info("[TemperatureManager] 开始注册温度和湿度工具")

            # 注册获取温度和湿度工具
            self._register_temperature_humidity_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            self._initialized = True
            logger.info("[TemperatureManager] 温度和湿度工具注册完成")

        except Exception as e:
            logger.error(f"[TemperatureManager] 温度和湿度工具注册失败: {e}", exc_info=True)
            raise

    def _register_temperature_humidity_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册温度和湿度获取工具.
        """
        add_tool(
            (
                "environment.get_temperature_humidity",
                "获取室内温度和湿度数据。数据由后台服务提供。\n"
                "返回包含温度(°C)和湿度(%)的JSON数据。\n"
                "使用场景：\n"
                "1. 查询当前室内温度和湿度\n"
                "2. 监控环境条件\n"
                "3. 智能家居环境监测",
                PropertyList(),  # 无需参数
                get_temperature_humidity_wrapper,
            )
        )
        logger.debug("[TemperatureManager] 注册温度和湿度工具成功")