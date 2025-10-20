"""温度和湿度工具."""

from .manager import TemperatureToolsManager


def get_temperature_manager():
    """
    获取温度和湿度工具管理器实例.
    """
    return TemperatureToolsManager()