"""
高德地图工具管理器.

负责高德地图工具的初始化、配置和MCP工具注册
"""

import json
from typing import Any, Dict, List, Optional, Union
import requests
import asyncio

from src.utils.logging_config import get_logger
from .tools import AmapTools
from .client import AmapClient

logger = get_logger(__name__)


class AmapToolsManager:
    """
    高德地图工具管理器 - 适配MCP服务器.
    """

    def __init__(self):
        """
        初始化高德地图工具管理器.
        """
        self._initialized = False
        self._api_key = "ce2a3951c9f3b82dea64ce37eeac4bdd"  # 高德地图API密钥
        self.amap_tools = AmapTools(self._api_key)
        logger.info("[AmapManager] 高德地图工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有高德地图工具.
        """
        try:
            logger.info("[AmapManager] 开始注册高德地图工具")

            # 注册智能组合工具
            self._register_smart_tools(add_tool, PropertyList, Property, PropertyType)

            # 注册原子工具（可选，主要用于高级用户）
            self._register_atomic_tools(add_tool, PropertyList, Property, PropertyType)

            self._initialized = True
            logger.info("[AmapManager] 高德地图工具注册完成")

        except Exception as e:
            logger.error(f"[AmapManager] 高德地图工具注册失败: {e}", exc_info=True)
            raise

    def _register_smart_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册智能组合工具 - 用户友好的高级功能.
        """
        
        # 1. 智能路线规划
        route_props = PropertyList([
            Property("origin", PropertyType.STRING),
            Property("destination", PropertyType.STRING),
            Property("city", PropertyType.STRING, default_value="广州"),
            Property("travel_mode", PropertyType.STRING, default_value="walking")
        ])
        add_tool((
            "self.maps.route_planning",
            "Intelligent route planning between two addresses. Supports natural language "
            "address input and multiple travel modes.\n"
            "Use this tool when user asks for directions between two places:\n"
            "1. '从云升科学园到科学城地铁站怎么走' → origin='云升科学园', destination='科学城地铁站'\n"
            "2. '去天河城的路线' → destination='天河城' (will auto-detect user location)\n"
            "3. '开车从A到B要多久' → travel_mode='driving'\n\n"
            "Travel modes:\n"
            "- walking: 步行路线 (default)\n"
            "- driving: 驾车路线\n"
            "- bicycling: 骑行路线\n"
            "- transit: 公交路线\n\n"
            "Returns complete route information including distance, duration, and step-by-step directions.",
            route_props,
            self._route_planning_callback
        ))

        # 2. 最近的XX查找
        nearest_props = PropertyList([
            Property("keywords", PropertyType.STRING),
            Property("radius", PropertyType.STRING, default_value="5000"),
            Property("user_location", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.find_nearest",
            "Find the nearest place of a specific type and provide walking directions. "
            "Automatically detects user location and finds the closest match.\n"
            "Use this tool when user asks for the nearest place:\n"
            "1. '最近的奶茶店怎么走' → keywords='奶茶店'\n"
            "2. '最近的餐厅在哪里' → keywords='餐厅'\n"
            "3. '最近的地铁站' → keywords='地铁站'\n"
            "4. '最近的银行' → keywords='银行'\n"
            "5. '最近的超市怎么去' → keywords='超市'\n\n"
            "Common keywords: 奶茶店, 餐厅, 地铁站, 银行, 超市, 医院, 药店, 加油站, 停车场\n\n"
            "Returns the nearest place with detailed information and walking route.",
            nearest_props,
            self._find_nearest_callback
        ))

        # 3. 附近地点搜索
        nearby_props = PropertyList([
            Property("keywords", PropertyType.STRING),
            Property("radius", PropertyType.STRING, default_value="2000"),
            Property("user_location", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.find_nearby",
            "Search for nearby places of a specific type. Returns a list of places "
            "within the specified radius with distance information.\n"
            "Use this tool when user asks for multiple nearby places:\n"
            "1. '附近有哪些奶茶店' → keywords='奶茶店'\n"
            "2. '附近的餐厅' → keywords='餐厅'\n"
            "3. '周边的超市' → keywords='超市'\n"
            "4. '附近2公里内的银行' → keywords='银行', radius='2000'\n\n"
            "Returns a list of places sorted by distance with names, addresses, and walking distances.",
            nearby_props,
            self._find_nearby_callback
        ))

        # 4. 智能导航
        navigation_props = PropertyList([
            Property("destination", PropertyType.STRING),
            Property("city", PropertyType.STRING, default_value="广州"),
            Property("user_location", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.navigation",
            "Intelligent navigation to a destination with multiple travel options. "
            "Automatically detects user location and provides optimal route recommendations.\n"
            "Use this tool when user asks for navigation to a specific place:\n"
            "1. '去天河城' → destination='天河城'\n"
            "2. '导航到广州塔' → destination='广州塔'\n"
            "3. '怎么去白云机场' → destination='白云机场'\n\n"
            "Returns comprehensive navigation information including multiple travel modes "
            "(walking, driving, cycling, transit) with time and distance comparisons.",
            navigation_props,
            self._navigation_callback
        ))

        # 5. 当前位置获取
        location_props = PropertyList([
            Property("user_ip", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.get_location",
            "Get current user location using IP-based geolocation. Automatically "
            "detects user's approximate location for other map services.\n"
            "Use this tool when:\n"
            "1. User asks 'where am I' or '我在哪里'\n"
            "2. Need to determine user location for other map functions\n"
            "3. User asks for nearby places without specifying location\n\n"
            "Returns current city, province, and approximate coordinates.",
            location_props,
            self._get_location_callback
        ))

        # 6. 路线对比
        compare_props = PropertyList([
            Property("origin", PropertyType.STRING),
            Property("destination", PropertyType.STRING),
            Property("city", PropertyType.STRING, default_value="广州")
        ])
        add_tool((
            "self.maps.compare_routes",
            "Compare different travel modes between two locations. Shows time, distance, "
            "and recommendations for walking, driving, cycling, and public transit.\n"
            "Use this tool when user asks to compare travel options:\n"
            "1. '从A到B，开车和坐地铁哪个快' → origin='A', destination='B'\n"
            "2. '比较一下去机场的各种方式' → destination='机场'\n"
            "3. '哪种方式最快' → will show all options with recommendations\n\n"
            "Returns detailed comparison of all available travel modes with time, "
            "distance, and suitability recommendations.",
            compare_props,
            self._compare_routes_callback
        ))

        logger.debug("[AmapManager] 注册智能组合工具成功")

    def _register_atomic_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册原子工具 - 高级用户和开发者使用.
        """
        
        # 地理编码
        geo_props = PropertyList([
            Property("address", PropertyType.STRING),
            Property("city", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.geocode",
            "Convert address to coordinates. Advanced tool for developers.\n"
            "Returns latitude and longitude coordinates for a given address.",
            geo_props,
            self._geocode_callback
        ))

        # 周边搜索
        around_props = PropertyList([
            Property("location", PropertyType.STRING),
            Property("radius", PropertyType.STRING, default_value="1000"),
            Property("keywords", PropertyType.STRING, default_value="")
        ])
        add_tool((
            "self.maps.around_search",
            "Search around a specific coordinate point. Advanced tool for developers.\n"
            "Requires exact latitude,longitude coordinates.",
            around_props,
            self._around_search_callback
        ))

        # IP定位
        ip_props = PropertyList([
            Property("ip", PropertyType.STRING)
        ])
        add_tool((
            "self.maps.ip_location",
            "Get location information from IP address. Advanced tool for developers.",
            ip_props,
            self._ip_location_callback
        ))

        logger.debug("[AmapManager] 注册原子工具成功")

    # ==================== 工具回调函数 ====================

    async def _route_planning_callback(self, args: Dict[str, Any]) -> str:
        """
        智能路线规划回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_route_planning", args)
            return self._format_route_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 路线规划失败: {e}", exc_info=True)
            return f"路线规划失败: {str(e)}"

    async def _find_nearest_callback(self, args: Dict[str, Any]) -> str:
        """
        最近地点查找回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_find_nearest_place", args)
            return self._format_nearest_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 最近地点查找失败: {e}", exc_info=True)
            return f"最近地点查找失败: {str(e)}"

    async def _find_nearby_callback(self, args: Dict[str, Any]) -> str:
        """
        附近地点搜索回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_find_nearby_places", args)
            return self._format_nearby_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 附近地点搜索失败: {e}", exc_info=True)
            return f"附近地点搜索失败: {str(e)}"

    async def _navigation_callback(self, args: Dict[str, Any]) -> str:
        """
        智能导航回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_navigation_to_place", args)
            return self._format_navigation_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 导航失败: {e}", exc_info=True)
            return f"导航失败: {str(e)}"

    async def _get_location_callback(self, args: Dict[str, Any]) -> str:
        """
        获取当前位置回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_get_current_location", args)
            return self._format_location_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 获取位置失败: {e}", exc_info=True)
            return f"获取位置失败: {str(e)}"

    async def _compare_routes_callback(self, args: Dict[str, Any]) -> str:
        """
        路线对比回调.
        """
        try:
            result = await self.amap_tools.execute_tool("smart_compare_routes", args)
            return self._format_compare_result(result)
        except Exception as e:
            logger.error(f"[AmapManager] 路线对比失败: {e}", exc_info=True)
            return f"路线对比失败: {str(e)}"

    async def _geocode_callback(self, args: Dict[str, Any]) -> str:
        """
        地理编码回调.
        """
        try:
            result = await self.amap_tools.execute_tool("maps_geo", args)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[AmapManager] 地理编码失败: {e}", exc_info=True)
            return f"地理编码失败: {str(e)}"

    async def _around_search_callback(self, args: Dict[str, Any]) -> str:
        """
        周边搜索回调.
        """
        try:
            result = await self.amap_tools.execute_tool("maps_around_search", args)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[AmapManager] 周边搜索失败: {e}", exc_info=True)
            return f"周边搜索失败: {str(e)}"

    async def _ip_location_callback(self, args: Dict[str, Any]) -> str:
        """
        IP定位回调.
        """
        try:
            result = await self.amap_tools.execute_tool("maps_ip_location", args)
            return json.dumps(result, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[AmapManager] IP定位失败: {e}", exc_info=True)
            return f"IP定位失败: {str(e)}"

    # ==================== 结果格式化函数 ====================

    def _format_route_result(self, result: Dict[str, Any]) -> str:
        """
        格式化路线规划结果.
        """
        if not result.get("success"):
            return f"路线规划失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        route = data["route"]
        
        output = f"🗺️ **路线规划**\n"
        output += f"📍 **起点**: {data['origin']['name']}\n"
        output += f"📍 **终点**: {data['destination']['name']}\n"
        output += f"🚶 **出行方式**: {data['travel_mode']}\n\n"
        
        if "paths" in route:
            path = route["paths"][0]
            output += f"📏 **距离**: {path['distance']}米\n"
            output += f"⏱️ **用时**: {path['duration']//60}分钟\n\n"
            
            if "steps" in path:
                output += "🚶 **详细路线**:\n"
                for i, step in enumerate(path["steps"][:5], 1):
                    output += f"{i}. {step['instruction']} ({step['distance']}米)\n"
                    
                if len(path["steps"]) > 5:
                    output += f"... 还有 {len(path['steps'])-5} 步\n"
        
        return output

    def _format_nearest_result(self, result: Dict[str, Any]) -> str:
        """
        格式化最近地点结果.
        """
        if not result.get("success"):
            return f"查找失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        place = data["nearest_place"]
        route = data["route"]
        
        output = f"🎯 **最近的{data['keywords']}**\n\n"
        output += f"📍 **名称**: {place['name']}\n"
        output += f"📍 **地址**: {place['address']}\n"
        output += f"📏 **距离**: {route['distance']}\n"
        output += f"⏱️ **步行时间**: {route['duration']}\n\n"
        
        if "steps" in route:
            output += "🚶 **步行路线**:\n"
            for i, step in enumerate(route["steps"][:3], 1):
                output += f"{i}. {step['instruction']}\n"
        
        return output

    def _format_nearby_result(self, result: Dict[str, Any]) -> str:
        """
        格式化附近地点结果.
        """
        if not result.get("success"):
            return f"搜索失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        places = data["places"]
        
        output = f"🔍 **附近的{data['keywords']}** (共{data['count']}个)\n\n"
        
        for i, place in enumerate(places[:8], 1):
            output += f"{i}. **{place['name']}**\n"
            output += f"   📍 {place['address']}\n"
            output += f"   🚶 {place['distance']}\n\n"
        
        if len(places) > 8:
            output += f"... 还有 {len(places)-8} 个地点\n"
        
        return output

    def _format_navigation_result(self, result: Dict[str, Any]) -> str:
        """
        格式化导航结果.
        """
        if not result.get("success"):
            return f"导航失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        destination = data["destination"]
        routes = data["routes"]
        recommended = data["recommended"]
        
        output = f"🧭 **导航到 {destination['name']}**\n\n"
        output += f"⭐ **推荐方式**: {recommended}\n\n"
        
        output += "📊 **出行方式对比**:\n"
        for mode, info in routes.items():
            if mode == "公交":
                output += f"🚌 **{mode}**: {info['duration']} (步行{info['walking_distance']})\n"
            else:
                output += f"🚶 **{mode}**: {info['distance']} - {info['duration']}\n"
        
        return output

    def _format_location_result(self, result: Dict[str, Any]) -> str:
        """
        格式化位置结果.
        """
        if not result.get("success"):
            return f"定位失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        
        output = f"📍 **当前位置**\n\n"
        output += f"🏙️ **城市**: {data['city']}\n"
        output += f"📍 **省份**: {data['province']}\n"
        output += f"📍 **地址**: {data['address']}\n"
        output += f"🌐 **坐标**: {data['location']}\n"
        
        return output

    def _format_compare_result(self, result: Dict[str, Any]) -> str:
        """
        格式化路线对比结果.
        """
        if not result.get("success"):
            return f"对比失败: {result.get('error', '未知错误')}"
        
        data = result["data"]
        origin = data["origin"]
        destination = data["destination"]
        comparisons = data["comparisons"]
        recommendations = data["recommendations"]
        
        output = f"⚖️ **路线对比: {origin['name']} → {destination['name']}**\n\n"
        
        for mode, info in comparisons.items():
            suitable = "✅" if info.get("suitable", True) else "❌"
            if mode == "公交":
                output += f"{suitable} **{mode}**: {info['duration_text']} (步行{info['walking_distance_text']})\n"
            else:
                output += f"{suitable} **{mode}**: {info['distance_text']} - {info['duration_text']}\n"
        
        if recommendations:
            output += f"\n💡 **推荐**: {recommendations[0]['mode']} - {recommendations[0]['reason']}\n"
        
        return output

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
            "api_key_configured": bool(self._api_key),
            "smart_tools_count": 6,
            "atomic_tools_count": 3,
            "available_smart_tools": [
                "route_planning",
                "find_nearest",
                "find_nearby",
                "navigation",
                "get_location",
                "compare_routes"
            ]
        }

    async def close(self):
        """
        关闭资源.
        """
        if self.amap_tools:
            await self.amap_tools.close()


# 全局管理器实例
_amap_tools_manager = None


def get_amap_tools_manager() -> AmapToolsManager:
    """
    获取高德地图工具管理器单例.
    """
    global _amap_tools_manager
    if _amap_tools_manager is None:
        _amap_tools_manager = AmapToolsManager()
        logger.debug("[AmapManager] 创建高德地图工具管理器实例")
    return _amap_tools_manager


# ==================== 原有的AmapManager类 ====================


class AmapManager:
    """
    高德地图工具管理器.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client: Optional[AmapClient] = None

    async def get_client(self) -> AmapClient:
        """
        获取客户端实例.
        """
        if not self.client:
            self.client = AmapClient(self.api_key)
        return self.client

    async def regeocode(self, location: str) -> Dict[str, Any]:
        """逆地理编码 - 将经纬度转换为地址"""
        client = await self.get_client()
        try:
            result = await client.regeocode(location)
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def geocode(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        """地理编码 - 将地址转换为经纬度"""
        client = await self.get_client()
        try:
            results = await client.geocode(address, city)
            return {
                "success": True,
                "data": [
                    {
                        "country": result.address_component.country,
                        "province": result.address_component.province,
                        "city": result.address_component.city,
                        "citycode": result.address_component.citycode,
                        "district": result.address_component.district,
                        "street": result.address_component.street,
                        "number": result.address_component.number,
                        "adcode": result.address_component.adcode,
                        "location": result.location.to_string(),
                        "level": result.level,
                    }
                    for result in results
                ],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def ip_location(self, ip: str) -> Dict[str, Any]:
        """
        IP定位.
        """
        client = await self.get_client()
        try:
            result = await client.ip_location(ip)
            return {
                "success": True,
                "data": {
                    "province": result.province,
                    "city": result.city,
                    "adcode": result.adcode,
                    "rectangle": result.rectangle,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def weather(self, city: str) -> Dict[str, Any]:
        """
        天气查询.
        """
        client = await self.get_client()
        try:
            result = await client.weather(city)
            return {
                "success": True,
                "data": {
                    "city": result.city,
                    "forecasts": [
                        {
                            "date": forecast.date,
                            "weather": forecast.weather,
                            "temperature": forecast.temperature,
                            "wind_direction": forecast.wind_direction,
                            "wind_power": forecast.wind_power,
                            "humidity": forecast.humidity,
                        }
                        for forecast in result.forecasts
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def search_detail(self, poi_id: str) -> Dict[str, Any]:
        """
        POI详情查询.
        """
        client = await self.get_client()
        try:
            result = await client.search_detail(poi_id)
            return {
                "success": True,
                "data": {
                    "id": result.id,
                    "name": result.name,
                    "location": result.location.to_string(),
                    "address": result.address,
                    "business_area": result.business_area,
                    "city": result.city,
                    "type_code": result.type_code,
                    "alias": result.alias,
                    "biz_ext": result.biz_ext,
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def direction_walking(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        步行路径规划.
        """
        client = await self.get_client()
        try:
            result = await client.direction_walking(origin, destination)
            return {
                "success": True,
                "data": {
                    "origin": result.origin.to_string(),
                    "destination": result.destination.to_string(),
                    "paths": [
                        {
                            "distance": path.distance,
                            "duration": path.duration,
                            "steps": [
                                {
                                    "instruction": step.instruction,
                                    "road": step.road,
                                    "distance": step.distance,
                                    "orientation": step.orientation,
                                    "duration": step.duration,
                                }
                                for step in path.steps
                            ],
                        }
                        for path in result.paths
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def direction_driving(self, origin: str, destination: str) -> Dict[str, Any]:
        """
        驾车路径规划.
        """
        client = await self.get_client()
        try:
            result = await client.direction_driving(origin, destination)
            return {
                "success": True,
                "data": {
                    "origin": result.origin.to_string(),
                    "destination": result.destination.to_string(),
                    "paths": [
                        {
                            "distance": path.distance,
                            "duration": path.duration,
                            "steps": [
                                {
                                    "instruction": step.instruction,
                                    "road": step.road,
                                    "distance": step.distance,
                                    "orientation": step.orientation,
                                    "duration": step.duration,
                                }
                                for step in path.steps
                            ],
                        }
                        for path in result.paths
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def direction_bicycling(
        self, origin: str, destination: str
    ) -> Dict[str, Any]:
        """
        骑行路径规划.
        """
        client = await self.get_client()
        try:
            result = await client.direction_bicycling(origin, destination)
            return {
                "success": True,
                "data": {
                    "origin": result.origin.to_string(),
                    "destination": result.destination.to_string(),
                    "paths": [
                        {
                            "distance": path.distance,
                            "duration": path.duration,
                            "steps": [
                                {
                                    "instruction": step.instruction,
                                    "road": step.road,
                                    "distance": step.distance,
                                    "orientation": step.orientation,
                                    "duration": step.duration,
                                }
                                for step in path.steps
                            ],
                        }
                        for path in result.paths
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def direction_transit(
        self, origin: str, destination: str, city: str, cityd: str
    ) -> Dict[str, Any]:
        """
        公交路径规划.
        """
        client = await self.get_client()
        try:
            result = await client.direction_transit(origin, destination, city, cityd)
            return {
                "success": True,
                "data": {
                    "origin": result.origin.to_string(),
                    "destination": result.destination.to_string(),
                    "distance": result.distance,
                    "transits": [
                        {
                            "duration": transit.duration,
                            "walking_distance": transit.walking_distance,
                            "segments": [
                                {
                                    "walking": {
                                        "distance": (
                                            segment.walking.distance
                                            if segment.walking
                                            else 0
                                        ),
                                        "duration": (
                                            segment.walking.duration
                                            if segment.walking
                                            else 0
                                        ),
                                    }
                                }
                                for segment in transit.segments
                            ],
                        }
                        for transit in result.transits
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def distance(
        self, origins: str, destination: str, distance_type: str = "1"
    ) -> Dict[str, Any]:
        """
        距离测量.
        """
        client = await self.get_client()
        try:
            results = await client.distance(origins, destination, distance_type)
            return {
                "success": True,
                "data": {
                    "results": [
                        {
                            "origin_id": result.origin_id,
                            "dest_id": result.dest_id,
                            "distance": result.distance,
                            "duration": result.duration,
                        }
                        for result in results
                    ]
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def text_search(
        self, keywords: str, city: str = "", types: str = ""
    ) -> Dict[str, Any]:
        """
        关键词搜索.
        """
        client = await self.get_client()
        try:
            result = await client.text_search(keywords, city)
            return {
                "success": True,
                "data": {
                    "suggestion": {
                        "keywords": result.suggestion.keywords,
                        "cities": result.suggestion.cities,
                    },
                    "pois": [
                        {
                            "id": poi.id,
                            "name": poi.name,
                            "address": poi.address,
                            "location": poi.location.to_string(),
                            "type_code": poi.type_code,
                        }
                        for poi in result.pois
                    ],
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def around_search(
        self, location: str, radius: str = "1000", keywords: str = ""
    ) -> Dict[str, Any]:
        """
        周边搜索.
        """
        client = await self.get_client()
        try:
            result = await client.around_search(location, radius, keywords)
            return {
                "success": True,
                "data": {
                    "pois": [
                        {
                            "id": poi.id,
                            "name": poi.name,
                            "address": poi.address,
                            "location": poi.location.to_string(),
                            "type_code": poi.type_code,
                        }
                        for poi in result.pois
                    ]
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_current_location(self, user_ip: Optional[str] = None) -> Dict[str, Any]:
        """
        智能定位 - 获取用户当前位置（基于IP）
        
        Args:
            user_ip: 用户IP地址，如果不提供则自动获取
            
        Returns:
            包含位置信息的字典，包括坐标、城市、省份等
        """
        try:
            # 步骤1: 获取用户IP（如果没有提供）
            if not user_ip:
                try:
                    # 策略1: 先尝试使用高德的自动IP识别
                    auto_ip_result = await self.ip_location("")
                    if auto_ip_result.get("success"):
                        auto_data = auto_ip_result["data"]
                        auto_city = auto_data.get("city", "")
                        auto_province = auto_data.get("province", "")
                        
                        # 如果高德自动识别有效（不是"未知"），优先使用
                        if auto_city and auto_province and auto_city != "未知" and auto_province != "未知":
                            user_ip = ""  # 使用高德自动识别
                            logger.debug(f"[AmapManager] 使用高德自动IP定位: {auto_province}{auto_city}")
                        else:
                            # 策略2: 高德自动识别无效，尝试第三方IP获取
                            logger.debug(f"[AmapManager] 高德自动IP定位无效，尝试第三方IP获取")
                            
                            # 优先获取IPv4地址
                            ipv4_sources = [
                                'https://ipinfo.io/json',
                                'https://httpbin.org/ip',
                                'https://api.ipify.org?format=json',
                            ]
                            
                            for source in ipv4_sources:
                                try:
                                    response = requests.get(source, timeout=2)
                                    if response.status_code == 200:
                                        data = response.json()
                                        if 'ip' in data:
                                            ip = data['ip']
                                            # 检查是否是IPv4格式
                                            if '.' in ip and ':' not in ip:
                                                # 测试这个IP是否能获得更好的定位
                                                test_result = await self.ip_location(ip)
                                                if test_result.get("success"):
                                                    test_data = test_result["data"]
                                                    test_city = test_data.get("city", "")
                                                    test_province = test_data.get("province", "")
                                                    
                                                    if test_city and test_province and test_city != "未知" and test_province != "未知":
                                                        user_ip = ip
                                                        logger.debug(f"[AmapManager] 使用第三方IP: {ip} -> {test_province}{test_city}")
                                                        break
                                        elif 'origin' in data:  # httpbin格式
                                            ip = data['origin']
                                            if '.' in ip and ':' not in ip:
                                                test_result = await self.ip_location(ip)
                                                if test_result.get("success"):
                                                    test_data = test_result["data"]
                                                    test_city = test_data.get("city", "")
                                                    test_province = test_data.get("province", "")
                                                    
                                                    if test_city and test_province and test_city != "未知" and test_province != "未知":
                                                        user_ip = ip
                                                        logger.debug(f"[AmapManager] 使用第三方IP: {ip} -> {test_province}{test_city}")
                                                        break
                                except:
                                    continue
                            
                            # 如果第三方IP也无效，回退到高德自动识别
                            if not user_ip:
                                user_ip = ""
                                logger.debug(f"[AmapManager] 回退到高德自动IP识别")
                    else:
                        # 高德自动识别完全失败，尝试第三方IP
                        logger.debug(f"[AmapManager] 高德自动IP识别失败，尝试第三方IP")
                        user_ip = ""
                        
                except Exception as e:
                    logger.error(f"[AmapManager] IP获取失败: {e}")
                    user_ip = ""
            
            # 步骤2: 使用高德IP定位服务
            ip_result = await self.ip_location(user_ip)
            if not ip_result.get("success"):
                return {"success": False, "error": "IP定位失败"}
            
            ip_data = ip_result["data"]
            
            # 高德IP定位返回的数据结构处理
            if isinstance(ip_data.get("city"), list):
                city = ip_data["city"][0] if ip_data["city"] else "未知"
            else:
                city = ip_data.get("city", "未知")
            
            if isinstance(ip_data.get("province"), list):
                province = ip_data["province"][0] if ip_data["province"] else "未知"
            else:
                province = ip_data.get("province", "未知")
            
            # 步骤3: 获取IP定位返回的坐标（如果有）
            if ip_data.get("location"):
                # 高德IP定位直接返回了坐标
                location = ip_data["location"]
            else:
                # 如果没有坐标，使用城市中心坐标
                geo_result = await self.geocode(f"{city}市中心", "")
                if not geo_result.get("success"):
                    return {"success": False, "error": "城市中心定位失败"}
                location = geo_result["data"][0]["location"]
            
            return {
                "success": True,
                "data": {
                    "ip": user_ip,
                    "province": province,
                    "city": city,
                    "location": location,
                    "address": f"{province}{city}",
                    "adcode": ip_data.get("adcode"),
                    "ip_info": ip_data
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"智能定位失败: {str(e)}"}

    async def route_planning(self, origin: str, destination: str, city: str = "广州", 
                           travel_mode: str = "walking") -> Dict[str, Any]:
        """
        路线规划 - 支持地址名称到地址名称的路线规划
        
        Args:
            origin: 起点地址名称
            destination: 终点地址名称  
            city: 所在城市
            travel_mode: 出行方式 (walking/driving/bicycling/transit)
            
        Returns:
            包含路线信息的字典
        """
        try:
            # 步骤1: 处理起点 - 判断是坐标还是地址
            if not origin or origin == "":
                # 空字符串表示使用IP定位
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "IP定位失败"}
                origin_location = location_result["data"]["location"]
                origin_name = location_result["data"]["address"]
                origin_detail = location_result["data"]
            elif "," in origin and origin.replace(",", "").replace(".", "").replace("-", "").isdigit():
                # 这是坐标格式，直接使用
                origin_location = origin
                # 通过逆地理编码获取地址名称
                regeo_result = await self.regeocode(origin)
                if regeo_result.get("success") and regeo_result.get("data"):
                    origin_name = regeo_result["data"].get("formatted_address", origin)
                    origin_detail = regeo_result["data"]
                else:
                    origin_name = origin
                    origin_detail = {}
            else:
                # 这是地址名称，进行地理编码
                origin_result = await self.geocode(origin, city)
                if not origin_result.get("success"):
                    return {"success": False, "error": f"无法识别起点地址: {origin}"}
                origin_location = origin_result["data"][0]["location"]
                origin_name = origin
                origin_detail = origin_result["data"][0]
            
            # 步骤2: 处理终点 - 判断是坐标还是地址
            if not destination or destination == "":
                # 空字符串表示使用IP定位
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "IP定位失败"}
                dest_location = location_result["data"]["location"]
                dest_name = location_result["data"]["address"]
                dest_detail = location_result["data"]
            elif "," in destination and destination.replace(",", "").replace(".", "").replace("-", "").isdigit():
                # 这是坐标格式，直接使用
                dest_location = destination
                # 通过逆地理编码获取地址名称
                regeo_result = await self.regeocode(destination)
                if regeo_result.get("success") and regeo_result.get("data"):
                    dest_name = regeo_result["data"].get("formatted_address", destination)
                    dest_detail = regeo_result["data"]
                else:
                    dest_name = destination
                    dest_detail = {}
            else:
                # 这是地址名称，进行地理编码
                dest_result = await self.geocode(destination, city)
                if not dest_result.get("success"):
                    return {"success": False, "error": f"无法识别终点地址: {destination}"}
                dest_location = dest_result["data"][0]["location"]
                dest_name = destination
                dest_detail = dest_result["data"][0]
            
            # 步骤3: 路线规划
            if travel_mode == "walking":
                route_result = await self.direction_walking(origin_location, dest_location)
            elif travel_mode == "driving":
                route_result = await self.direction_driving(origin_location, dest_location)
            elif travel_mode == "bicycling":
                route_result = await self.direction_bicycling(origin_location, dest_location)
            elif travel_mode == "transit":
                route_result = await self.direction_transit(origin_location, dest_location, city, city)
            else:
                return {"success": False, "error": f"不支持的出行方式: {travel_mode}"}
            
            if not route_result.get("success"):
                return {"success": False, "error": "路线规划失败"}
            
            return {
                "success": True,
                "data": {
                    "origin": {
                        "name": origin_name,
                        "location": origin_location,
                        "detail": origin_detail
                    },
                    "destination": {
                        "name": dest_name,
                        "location": dest_location,
                        "detail": dest_detail
                    },
                    "travel_mode": travel_mode,
                    "route": route_result["data"]
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"路线规划失败: {str(e)}"}

    async def find_nearby_places(self, keywords: str, radius: str = "2000", 
                               user_location: Optional[str] = None) -> Dict[str, Any]:
        """
        附近地点搜索 - 自动定位并搜索附近的地点
        
        Args:
            keywords: 搜索关键词 (如"奶茶店", "餐厅", "超市")
            radius: 搜索半径(米)
            user_location: 用户位置(可选，不提供则自动定位)
            
        Returns:
            包含附近地点信息的字典
        """
        try:
            # 步骤1: 获取用户位置
            if not user_location:
                # 使用高德IP定位服务
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "无法获取用户位置"}
                user_location = location_result["data"]["location"]
                city = location_result["data"]["city"]
            else:
                # 判断是坐标格式还是地址名称
                if "," in user_location and user_location.replace(",", "").replace(".", "").replace("-", "").isdigit():
                    # 这是坐标格式，直接使用
                    regeo_result = await self.regeocode(user_location)
                    city = regeo_result["data"].get("city", "未知") if regeo_result.get("success") else "未知"
                else:
                    # 这是地址名称，直接进行地理编码（不指定城市，让高德API自己处理）
                    geo_result = await self.geocode(user_location, "")
                    if not geo_result.get("success"):
                        return {"success": False, "error": f"无法识别地址: {user_location}"}
                    
                    # 更新为坐标格式
                    user_location = geo_result["data"][0]["location"]
                    city = geo_result["data"][0].get("city", "未知")
            
            # 步骤2: 周边搜索
            search_result = await self.around_search(user_location, radius, keywords)
            if not search_result.get("success"):
                return {"success": False, "error": "搜索失败"}
            
            pois = search_result["data"]["pois"]
            
            # 步骤3: 计算距离并排序
            enhanced_pois = []
            for poi in pois[:10]:  # 限制前10个结果
                distance_result = await self.distance(user_location, poi["location"], "3")
                distance = "未知"
                if distance_result.get("success") and distance_result["data"]["results"]:
                    try:
                        distance_m = distance_result["data"]["results"][0]["distance"]
                        distance = f"{distance_m}米"
                    except (KeyError, IndexError, TypeError):
                        distance = "未知"
                
                enhanced_pois.append({
                    "id": poi["id"],
                    "name": poi["name"],
                    "address": poi["address"],
                    "location": poi["location"],
                    "type_code": poi["type_code"],
                    "distance": distance
                })
            
            return {
                "success": True,
                "data": {
                    "user_location": user_location,
                    "city": city,
                    "keywords": keywords,
                    "radius": radius,
                    "count": len(enhanced_pois),
                    "places": enhanced_pois
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"附近搜索失败: {str(e)}"}

    async def find_nearest_place(self, keywords: str, user_location: Optional[str] = None, 
                              radius: str = "5000") -> Dict[str, Any]:
        """
        最近的XX查找 - 找到最近的某类地点并规划路线
        
        Args:
            keywords: 搜索关键词 (如"地铁站", "奶茶店", "餐厅", "超市")
            user_location: 用户位置(可选，不提供则自动定位)
            radius: 搜索半径(米)
            
        Returns:
            包含最近地点和路线信息的字典
        """
        try:
            # 步骤1: 获取用户位置
            if not user_location:
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "无法获取用户位置"}
                user_location = location_result["data"]["location"]
                city = location_result["data"]["city"]
            else:
                # 判断是坐标格式还是地址名称
                if "," in user_location and user_location.replace(",", "").replace(".", "").replace("-", "").isdigit():
                    # 这是坐标格式，直接使用
                    regeo_result = await self.regeocode(user_location)
                    city = regeo_result["data"].get("city", "未知") if regeo_result.get("success") else "未知"
                else:
                    # 这是地址名称，直接进行地理编码（不指定城市，让高德API自己处理）
                    geo_result = await self.geocode(user_location, "")
                    if not geo_result.get("success"):
                        return {"success": False, "error": f"无法识别地址: {user_location}"}
                    
                    # 更新为坐标格式
                    user_location = geo_result["data"][0]["location"]
                    city = geo_result["data"][0].get("city", "未知")
            
            # 步骤2: 搜索附近的地点
            search_result = await self.around_search(user_location, radius, keywords)
            if not search_result.get("success") or not search_result["data"]["pois"]:
                return {"success": False, "error": f"附近没有找到{keywords}"}
            
            nearest_place = search_result["data"]["pois"][0]
            
            # 步骤3: 规划到最近地点的路线
            walking_result = await self.direction_walking(user_location, nearest_place["location"])
            if not walking_result.get("success"):
                return {"success": False, "error": "路线规划失败"}
            
            path = walking_result["data"]["paths"][0]
            
            # 步骤4: 获取详细信息
            detail_result = await self.search_detail(nearest_place["id"])
            detail_info = detail_result["data"] if detail_result.get("success") else {}
            
            return {
                "success": True,
                "data": {
                    "user_location": user_location,
                    "city": city,
                    "keywords": keywords,
                    "nearest_place": {
                        "id": nearest_place["id"],
                        "name": nearest_place["name"],
                        "address": nearest_place["address"],
                        "location": nearest_place["location"],
                        "type_code": nearest_place["type_code"],
                        "detail": detail_info
                    },
                    "route": {
                        "distance": f"{path['distance']}米",
                        "duration": f"{path['duration']//60}分钟",
                        "steps": path["steps"][:5]  # 只显示前5步
                    }
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"{keywords}查找失败: {str(e)}"}

    async def find_nearest_subway(self, user_location: Optional[str] = None) -> Dict[str, Any]:
        """
        最近地铁站查找 - 找到最近的地铁站并规划路线
        
        Args:
            user_location: 用户位置(可选，不提供则自动定位)
            
        Returns:
            包含最近地铁站和路线信息的字典
        """
        try:
            # 步骤1: 获取用户位置
            if not user_location:
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "无法获取用户位置"}
                user_location = location_result["data"]["location"]
                city = location_result["data"]["city"]
            else:
                city = "广州"  # 默认城市
            
            # 步骤2: 搜索附近地铁站
            subway_result = await self.around_search(user_location, "5000", "地铁站")
            if not subway_result.get("success") or not subway_result["data"]["pois"]:
                return {"success": False, "error": "附近没有找到地铁站"}
            
            nearest_station = subway_result["data"]["pois"][0]
            
            # 步骤3: 规划到最近地铁站的路线
            walking_result = await self.direction_walking(user_location, nearest_station["location"])
            if not walking_result.get("success"):
                return {"success": False, "error": "路线规划失败"}
            
            path = walking_result["data"]["paths"][0]
            
            return {
                "success": True,
                "data": {
                    "user_location": user_location,
                    "city": city,
                    "nearest_station": {
                        "id": nearest_station["id"],
                        "name": nearest_station["name"],
                        "address": nearest_station["address"],
                        "location": nearest_station["location"]
                    },
                    "route": {
                        "distance": f"{path['distance']}米",
                        "duration": f"{path['duration']//60}分钟",
                        "steps": path["steps"][:5]  # 只显示前5步
                    }
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"地铁站查找失败: {str(e)}"}

    async def find_nearby_subway_stations(self, user_location: Optional[str] = None, 
                                        radius: str = "3000") -> Dict[str, Any]:
        """
        附近地铁站列表 - 获取附近所有地铁站信息
        
        Args:
            user_location: 用户位置(可选，不提供则自动定位)
            radius: 搜索半径(米)
            
        Returns:
            包含附近地铁站列表的字典
        """
        try:
            # 步骤1: 获取用户位置
            if not user_location:
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "无法获取用户位置"}
                user_location = location_result["data"]["location"]
                city = location_result["data"]["city"]
            else:
                city = "广州"  # 默认城市
            
            # 步骤2: 搜索附近地铁站
            subway_result = await self.around_search(user_location, radius, "地铁站")
            if not subway_result.get("success") or not subway_result["data"]["pois"]:
                return {"success": False, "error": "附近没有找到地铁站"}
            
            # 步骤3: 计算距离并排序
            stations = []
            for station in subway_result["data"]["pois"]:
                distance_result = await self.distance(user_location, station["location"], "3")
                distance = "未知"
                walking_time = "未知"
                
                if distance_result.get("success"):
                    distance_m = distance_result["data"]["results"][0]["distance"]
                    walking_time = f"{distance_m // 80}分钟"  # 步行速度约80米/分钟
                    distance = f"{distance_m}米"
                
                stations.append({
                    "id": station["id"],
                    "name": station["name"],
                    "address": station["address"],
                    "location": station["location"],
                    "distance": distance,
                    "walking_time": walking_time
                })
            
            return {
                "success": True,
                "data": {
                    "user_location": user_location,
                    "city": city,
                    "radius": radius,
                    "count": len(stations),
                    "stations": stations
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"地铁站搜索失败: {str(e)}"}

    async def navigation_to_place(self, destination: str, city: str = "广州",
                                user_location: Optional[str] = None) -> Dict[str, Any]:
        """
        导航到指定地点 - 智能选择最佳路线
        
        Args:
            destination: 目的地名称
            city: 所在城市
            user_location: 用户位置(可选，不提供则自动定位)
            
        Returns:
            包含导航信息的字典
        """
        try:
            # 步骤1: 获取用户位置
            if not user_location:
                location_result = await self.get_current_location()
                if not location_result.get("success"):
                    return {"success": False, "error": "无法获取用户位置"}
                user_location = location_result["data"]["location"]
                city = location_result["data"]["city"]
            
            # 步骤2: 目的地地理编码
            dest_result = await self.geocode(destination, city)
            if not dest_result.get("success"):
                return {"success": False, "error": f"无法识别目的地: {destination}"}
            
            dest_location = dest_result["data"][0]["location"]
            
            # 步骤3: 计算多种出行方式
            routes = {}
            
            # 步行
            walking_result = await self.direction_walking(user_location, dest_location)
            if walking_result.get("success"):
                path = walking_result["data"]["paths"][0]
                routes["步行"] = {
                    "distance": f"{path['distance']}米",
                    "duration": f"{path['duration']//60}分钟",
                    "steps": path["steps"][:3]  # 前3步
                }
            
            # 驾车
            driving_result = await self.direction_driving(user_location, dest_location)
            if driving_result.get("success"):
                path = driving_result["data"]["paths"][0]
                routes["驾车"] = {
                    "distance": f"{path['distance']}米",
                    "duration": f"{path['duration']//60}分钟",
                    "steps": path["steps"][:3]
                }
            
            # 骑行
            bicycling_result = await self.direction_bicycling(user_location, dest_location)
            if bicycling_result.get("success"):
                path = bicycling_result["data"]["paths"][0]
                routes["骑行"] = {
                    "distance": f"{path['distance']}米",
                    "duration": f"{path['duration']//60}分钟",
                    "steps": path["steps"][:3]
                }
            
            # 公交
            transit_result = await self.direction_transit(user_location, dest_location, city, city)
            if transit_result.get("success") and transit_result["data"]["transits"]:
                best_transit = min(transit_result["data"]["transits"], key=lambda x: x["duration"])
                routes["公交"] = {
                    "duration": f"{best_transit['duration']//60}分钟",
                    "walking_distance": f"{best_transit['walking_distance']}米",
                    "segments": len(best_transit["segments"])
                }
            
            # 推荐最佳路线
            best_route = "步行"
            if routes:
                # 根据时间选择最佳路线
                min_time = float('inf')
                for mode, info in routes.items():
                    if mode != "公交":
                        time = int(info["duration"].replace("分钟", ""))
                        if time < min_time:
                            min_time = time
                            best_route = mode
            
            return {
                "success": True,
                "data": {
                    "destination": {
                        "name": destination,
                        "location": dest_location,
                        "detail": dest_result["data"][0]
                    },
                    "routes": routes,
                    "recommended": best_route,
                    "user_location": user_location,
                    "city": city
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"导航失败: {str(e)}"}

    async def compare_routes(self, origin: str, destination: str, 
                           city: str = "广州") -> Dict[str, Any]:
        """
        多种出行方式对比 - 比较不同出行方式的时间和距离
        
        Args:
            origin: 起点地址名称
            destination: 终点地址名称
            city: 所在城市
            
        Returns:
            包含各种出行方式对比的字典
        """
        try:
            # 步骤1: 起点和终点地理编码
            origin_result = await self.geocode(origin, city)
            if not origin_result.get("success"):
                return {"success": False, "error": f"无法识别起点地址: {origin}"}
            
            dest_result = await self.geocode(destination, city)
            if not dest_result.get("success"):
                return {"success": False, "error": f"无法识别终点地址: {destination}"}
            
            origin_location = origin_result["data"][0]["location"]
            dest_location = dest_result["data"][0]["location"]
            
            # 步骤2: 计算各种出行方式
            comparisons = {}
            
            # 步行
            walking_result = await self.direction_walking(origin_location, dest_location)
            if walking_result.get("success"):
                path = walking_result["data"]["paths"][0]
                comparisons["步行"] = {
                    "distance": path["distance"],
                    "duration": path["duration"],
                    "distance_text": f"{path['distance']}米",
                    "duration_text": f"{path['duration']//60}分钟",
                    "suitable": path["duration"] <= 1800  # 30分钟内适合步行
                }
            
            # 驾车
            driving_result = await self.direction_driving(origin_location, dest_location)
            if driving_result.get("success"):
                path = driving_result["data"]["paths"][0]
                comparisons["驾车"] = {
                    "distance": path["distance"],
                    "duration": path["duration"],
                    "distance_text": f"{path['distance']}米",
                    "duration_text": f"{path['duration']//60}分钟",
                    "suitable": True
                }
            
            # 骑行
            bicycling_result = await self.direction_bicycling(origin_location, dest_location)
            if bicycling_result.get("success"):
                path = bicycling_result["data"]["paths"][0]
                comparisons["骑行"] = {
                    "distance": path["distance"],
                    "duration": path["duration"],
                    "distance_text": f"{path['distance']}米",
                    "duration_text": f"{path['duration']//60}分钟",
                    "suitable": path["distance"] <= 10000  # 10km内适合骑行
                }
            
            # 公交
            transit_result = await self.direction_transit(origin_location, dest_location, city, city)
            if transit_result.get("success") and transit_result["data"]["transits"]:
                best_transit = min(transit_result["data"]["transits"], key=lambda x: x["duration"])
                comparisons["公交"] = {
                    "duration": best_transit["duration"],
                    "duration_text": f"{best_transit['duration']//60}分钟",
                    "walking_distance": best_transit["walking_distance"],
                    "walking_distance_text": f"{best_transit['walking_distance']}米",
                    "suitable": True
                }
            
            # 推荐最佳方式
            recommendations = []
            if comparisons:
                # 按时间排序
                sorted_by_time = sorted(comparisons.items(), 
                                      key=lambda x: x[1].get("duration", float('inf')))
                
                for mode, info in sorted_by_time:
                    if info.get("suitable", True):
                        recommendations.append({
                            "mode": mode,
                            "reason": f"用时最短: {info.get('duration_text', '未知')}"
                        })
                        break
            
            return {
                "success": True,
                "data": {
                    "origin": {
                        "name": origin,
                        "location": origin_location
                    },
                    "destination": {
                        "name": destination,
                        "location": dest_location
                    },
                    "comparisons": comparisons,
                    "recommendations": recommendations
                }
            }
            
        except Exception as e:
            return {"success": False, "error": f"路线对比失败: {str(e)}"}

    async def close(self):
        """
        关闭客户端连接.
        """
        if self.client and self.client.session:
            await self.client.session.close()
            self.client = None