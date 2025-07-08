"""
高德地图工具管理器.
"""

from typing import Any, Dict, Optional

from .client import AmapClient


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

    async def close(self):
        """
        关闭客户端连接.
        """
        if self.client and self.client.session:
            await self.client.session.close()
            self.client = None
