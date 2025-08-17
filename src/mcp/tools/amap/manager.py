"""高德地图工具管理器.

负责高德地图工具的初始化、配置和MCP工具注册
"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .tools import (
    maps_around_search,
    maps_direction_driving,
    maps_direction_walking,
    maps_distance,
    maps_geo,
    maps_ip_location,
    maps_regeocode,
    maps_search_detail,
    maps_text_search,
    maps_weather,
)

logger = get_logger(__name__)


class AmapToolsManager:
    """
    高德地图工具管理器.
    """

    def __init__(self):
        """
        初始化高德地图工具管理器.
        """
        self._initialized = False
        logger.info("[AmapManager] 高德地图工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有高德地图工具.
        """
        try:
            logger.info("[AmapManager] 开始注册高德地图工具")

            # 注册逆地理编码工具
            self._register_regeocode_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册地理编码工具
            self._register_geo_tool(add_tool, PropertyList, Property, PropertyType)

            # 注册IP定位工具
            self._register_ip_location_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册天气查询工具
            self._register_weather_tool(add_tool, PropertyList, Property, PropertyType)

            # 注册步行导航工具
            self._register_walking_tool(add_tool, PropertyList, Property, PropertyType)

            # 注册驾车导航工具
            self._register_driving_tool(add_tool, PropertyList, Property, PropertyType)

            # 注册关键词搜索工具
            self._register_text_search_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册周边搜索工具
            self._register_around_search_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册POI详情工具
            self._register_search_detail_tool(
                add_tool, PropertyList, Property, PropertyType
            )

            # 注册距离测量工具
            self._register_distance_tool(add_tool, PropertyList, Property, PropertyType)

            self._initialized = True
            logger.info("[AmapManager] 高德地图工具注册完成")

        except Exception as e:
            logger.error(f"[AmapManager] 高德地图工具注册失败: {e}", exc_info=True)
            raise

    def _register_regeocode_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册逆地理编码工具.
        """
        props = PropertyList(
            [
                Property(
                    "location",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.regeocode",
                "将经纬度坐标转换为详细地址信息。输入经纬度坐标（格式：经度,纬度），"
                "返回对应的省市区等地址信息。适用于：已知坐标查地址、位置反查、坐标解析等场景。"
                "Convert longitude and latitude coordinates to detailed address information.",
                props,
                maps_regeocode,
            )
        )
        logger.debug("[AmapManager] 注册逆地理编码工具成功")

    def _register_geo_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册地理编码工具.
        """
        props = PropertyList(
            [
                Property(
                    "address",
                    PropertyType.STRING,
                ),
                Property(
                    "city",
                    PropertyType.STRING,
                    default_value="",
                ),
            ]
        )

        add_tool(
            (
                "amap.geo",
                "将详细地址转换为经纬度坐标。支持对地标、建筑物名称解析为坐标。"
                "输入地址信息，可选择指定城市，返回对应的经纬度坐标。"
                "适用于：地址查坐标、导航起点终点设置、位置标定等场景。"
                "Convert detailed address to longitude and latitude coordinates.",
                props,
                maps_geo,
            )
        )
        logger.debug("[AmapManager] 注册地理编码工具成功")

    def _register_ip_location_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册IP定位工具.
        """
        props = PropertyList(
            [
                Property(
                    "ip",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.ip_location",
                "根据IP地址获取位置信息。输入IP地址，返回对应的省市区域信息。"
                "适用于：IP归属地查询、网络位置分析、地理位置统计等场景。"
                "Get location information based on IP address.",
                props,
                maps_ip_location,
            )
        )
        logger.debug("[AmapManager] 注册IP定位工具成功")

    def _register_weather_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册天气查询工具.
        """
        props = PropertyList(
            [
                Property(
                    "city",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.weather",
                "查询指定城市的天气信息。输入城市名称或adcode，返回详细的天气预报信息。"
                "适用于：天气查询、出行规划、天气预报等场景。"
                "Query weather information for specified city.",
                props,
                maps_weather,
            )
        )
        logger.debug("[AmapManager] 注册天气查询工具成功")

    def _register_walking_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册步行导航工具.
        """
        props = PropertyList(
            [
                Property(
                    "origin",
                    PropertyType.STRING,
                ),
                Property(
                    "destination",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.direction_walking",
                "规划步行路径。输入起点和终点的经纬度坐标，返回详细的步行导航方案。"
                "支持100km以内的步行路径规划，包含距离、时间、详细步骤等信息。"
                "适用于：步行导航、路径规划、出行方案等场景。"
                "Plan walking routes with detailed navigation information.",
                props,
                maps_direction_walking,
            )
        )
        logger.debug("[AmapManager] 注册步行导航工具成功")

    def _register_driving_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册驾车导航工具.
        """
        props = PropertyList(
            [
                Property(
                    "origin",
                    PropertyType.STRING,
                ),
                Property(
                    "destination",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.direction_driving",
                "规划驾车路径。输入起点和终点的经纬度坐标，返回详细的驾车导航方案。"
                "包含距离、时间、过路费、详细步骤等信息。适用于：驾车导航、路径规划、出行方案等场景。"
                "Plan driving routes with detailed navigation information.",
                props,
                maps_direction_driving,
            )
        )
        logger.debug("[AmapManager] 注册驾车导航工具成功")

    def _register_text_search_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册关键词搜索工具.
        """
        props = PropertyList(
            [
                Property(
                    "keywords",
                    PropertyType.STRING,
                ),
                Property(
                    "city",
                    PropertyType.STRING,
                    default_value="",
                ),
                Property(
                    "types",
                    PropertyType.STRING,
                    default_value="",
                ),
            ]
        )

        add_tool(
            (
                "amap.text_search",
                "根据关键词搜索POI。输入搜索关键词，可指定城市和POI类型，"
                "返回相关的地点信息列表。适用于：地点搜索、商家查找、设施查询等场景。"
                "Search POI by keywords with optional city and type filters.",
                props,
                maps_text_search,
            )
        )
        logger.debug("[AmapManager] 注册关键词搜索工具成功")

    def _register_around_search_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册周边搜索工具.
        """
        props = PropertyList(
            [
                Property(
                    "location",
                    PropertyType.STRING,
                ),
                Property(
                    "keywords",
                    PropertyType.STRING,
                    default_value="",
                ),
                Property(
                    "radius",
                    PropertyType.STRING,
                    default_value="1000",
                ),
            ]
        )

        add_tool(
            (
                "amap.around_search",
                "根据坐标搜索周边POI。输入中心点坐标，可指定搜索关键词和半径，"
                "返回周边的地点信息列表。适用于：附近搜索、周边查找、附近设施查询等场景。"
                "Search nearby POI around given coordinates.",
                props,
                maps_around_search,
            )
        )
        logger.debug("[AmapManager] 注册周边搜索工具成功")

    def _register_search_detail_tool(
        self, add_tool, PropertyList, Property, PropertyType
    ):
        """
        注册POI详情工具.
        """
        props = PropertyList(
            [
                Property(
                    "id",
                    PropertyType.STRING,
                ),
            ]
        )

        add_tool(
            (
                "amap.search_detail",
                "查询POI的详细信息。输入POI的ID（通过搜索获得），"
                "返回详细的地点信息，包括联系方式、营业时间、评分等。"
                "适用于：地点详情查询、商家信息获取、详细信息查看等场景。"
                "Get detailed information of POI by ID.",
                props,
                maps_search_detail,
            )
        )
        logger.debug("[AmapManager] 注册POI详情工具成功")

    def _register_distance_tool(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册距离测量工具.
        """
        props = PropertyList(
            [
                Property(
                    "origins",
                    PropertyType.STRING,
                ),
                Property(
                    "destination",
                    PropertyType.STRING,
                ),
                Property(
                    "type",
                    PropertyType.STRING,
                    default_value="1",
                ),
            ]
        )

        add_tool(
            (
                "amap.distance",
                "测量两点间距离。输入起点和终点坐标，可选择测量类型"
                "（1：驾车距离，0：直线距离，3：步行距离），返回距离和时间信息。"
                "适用于：距离计算、路程估算、时间预估等场景。"
                "Measure distance between coordinates with different travel modes.",
                props,
                maps_distance,
            )
        )
        logger.debug("[AmapManager] 注册距离测量工具成功")

    def is_initialized(self) -> bool:
        """
        检查管理器是否已初始化.
        """
        return self._initialized

    def get_status(self) -> Dict[str, Any]:
        """
        获取管理器状态.
        """
        return {
            "initialized": self._initialized,
            "tools_count": 10,  # 当前注册的工具数量
            "available_tools": [
                "regeocode",
                "geo",
                "ip_location",
                "weather",
                "direction_walking",
                "direction_driving",
                "text_search",
                "around_search",
                "search_detail",
                "distance",
            ],
        }


# 全局管理器实例
_amap_tools_manager = None


def get_amap_manager() -> AmapToolsManager:
    """
    获取高德地图工具管理器单例.
    """
    global _amap_tools_manager
    if _amap_tools_manager is None:
        _amap_tools_manager = AmapToolsManager()
        logger.debug("[AmapManager] 创建高德地图工具管理器实例")
    return _amap_tools_manager
