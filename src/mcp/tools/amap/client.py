"""
高德地图 API 客户端.
"""

from typing import Any, Dict, List, Optional

import aiohttp

from .models import (
    POI,
    AddressComponent,
    DistanceResult,
    GeocodeResult,
    IPLocationResult,
    Location,
    RoutePath,
    RouteResult,
    RouteStep,
    SearchResult,
    SearchSuggestion,
    TransitResult,
    TransitRoute,
    TransitSegment,
    WeatherForecast,
    WeatherInfo,
)


class AmapClient:
    """
    高德地图API客户端.
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://restapi.amap.com"
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送API请求.
        """
        if not self.session:
            self.session = aiohttp.ClientSession()

        params.update({"key": self.api_key, "source": "py_mcp"})

        url = f"{self.base_url}{endpoint}"
        async with self.session.get(url, params=params) as response:
            data = await response.json()
            return data

    async def regeocode(self, location: str) -> Dict[str, Any]:
        """
        逆地理编码.
        """
        params = {"location": location}
        data = await self._request("/v3/geocode/regeo", params)

        if data.get("status") != "1":
            raise Exception(
                f"RGeocoding failed: {data.get('info', data.get('infocode'))}"
            )

        regeocode = data["regeocode"]
        addr_comp = regeocode["addressComponent"]

        return {
            "province": addr_comp.get("province"),
            "city": addr_comp.get("city"),
            "district": addr_comp.get("district"),
        }

    async def geocode(
        self, address: str, city: Optional[str] = None
    ) -> List[GeocodeResult]:
        """
        地理编码.
        """
        params = {"address": address}
        if city:
            params["city"] = city

        data = await self._request("/v3/geocode/geo", params)

        if data.get("status") != "1":
            raise Exception(
                f"Geocoding failed: {data.get('info', data.get('infocode'))}"
            )

        results = []
        for geo in data.get("geocodes", []):
            lon, lat = map(float, geo["location"].split(","))
            location = Location(longitude=lon, latitude=lat)

            addr_comp = AddressComponent(
                province=geo.get("province"),
                city=geo.get("city"),
                district=geo.get("district"),
                street=geo.get("street"),
                number=geo.get("number"),
                country=geo.get("country"),
                citycode=geo.get("citycode"),
                adcode=geo.get("adcode"),
            )

            result = GeocodeResult(
                location=location, address_component=addr_comp, level=geo.get("level")
            )
            results.append(result)

        return results

    async def ip_location(self, ip: str) -> IPLocationResult:
        """
        IP定位.
        """
        params = {"ip": ip}
        data = await self._request("/v3/ip", params)

        if data.get("status") != "1":
            raise Exception(
                f"IP Location failed: {data.get('info', data.get('infocode'))}"
            )

        return IPLocationResult(
            province=data.get("province", ""),
            city=data.get("city", ""),
            adcode=data.get("adcode", ""),
            rectangle=data.get("rectangle", ""),
        )

    async def weather(self, city: str) -> WeatherForecast:
        """
        天气查询.
        """
        params = {"city": city, "extensions": "all"}
        data = await self._request("/v3/weather/weatherInfo", params)

        if data.get("status") != "1":
            raise Exception(
                f"Get weather failed: {data.get('info', data.get('infocode'))}"
            )

        forecast = data["forecasts"][0]
        weather_list = []

        for cast in forecast.get("casts", []):
            weather_info = WeatherInfo(
                city=forecast["city"],
                date=cast.get("date", ""),
                weather=cast.get("dayweather", ""),
                temperature=f"{cast.get('nighttemp', '')}-{cast.get('daytemp', '')}°C",
                wind_direction=cast.get("daywind", ""),
                wind_power=cast.get("daypower", ""),
                humidity=cast.get("humidity", ""),
            )
            weather_list.append(weather_info)

        return WeatherForecast(city=forecast["city"], forecasts=weather_list)

    async def search_detail(self, poi_id: str) -> POI:
        """
        POI详情查询.
        """
        params = {"id": poi_id}
        data = await self._request("/v3/place/detail", params)

        if data.get("status") != "1":
            raise Exception(
                f"Get poi detail failed: {data.get('info', data.get('infocode'))}"
            )

        poi_data = data["pois"][0]
        lon, lat = map(float, poi_data["location"].split(","))
        location = Location(longitude=lon, latitude=lat)

        return POI(
            id=poi_data["id"],
            name=poi_data["name"],
            address=poi_data.get("address", ""),
            location=location,
            type_code=poi_data.get("typecode"),
            business_area=poi_data.get("business_area"),
            city=poi_data.get("cityname"),
            alias=poi_data.get("alias"),
            biz_ext=poi_data.get("biz_ext"),
        )

    async def direction_walking(self, origin: str, destination: str) -> RouteResult:
        """
        步行路径规划.
        """
        params = {"origin": origin, "destination": destination}
        data = await self._request("/v3/direction/walking", params)

        if data.get("status") != "1":
            raise Exception(
                f"Direction Walking failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_route_result(data["route"])

    async def direction_driving(self, origin: str, destination: str) -> RouteResult:
        """
        驾车路径规划.
        """
        params = {"origin": origin, "destination": destination}
        data = await self._request("/v3/direction/driving", params)

        if data.get("status") != "1":
            raise Exception(
                f"Direction Driving failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_route_result(data["route"])

    async def direction_bicycling(self, origin: str, destination: str) -> RouteResult:
        """
        骑行路径规划.
        """
        params = {"origin": origin, "destination": destination}
        data = await self._request("/v4/direction/bicycling", params)

        if data.get("errcode") != 0:
            raise Exception(
                f"Direction bicycling failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_route_result(data["data"])

    async def direction_transit(
        self, origin: str, destination: str, city: str, cityd: str
    ) -> TransitResult:
        """
        公交路径规划.
        """
        params = {
            "origin": origin,
            "destination": destination,
            "city": city,
            "cityd": cityd,
        }
        data = await self._request("/v3/direction/transit/integrated", params)

        if data.get("status") != "1":
            raise Exception(
                f"Direction Transit failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_transit_result(data["route"])

    async def distance(
        self, origins: str, destination: str, distance_type: str = "1"
    ) -> List[DistanceResult]:
        """
        距离测量.
        """
        params = {"origins": origins, "destination": destination, "type": distance_type}
        data = await self._request("/v3/distance", params)

        if data.get("status") != "1":
            raise Exception(
                f"Distance failed: {data.get('info', data.get('infocode'))}"
            )

        results = []
        for result in data.get("results", []):
            distance_result = DistanceResult(
                origin_id=result.get("origin_id", ""),
                dest_id=result.get("dest_id", ""),
                distance=int(result.get("distance", 0)),
                duration=int(result.get("duration", 0)),
            )
            results.append(distance_result)

        return results

    async def text_search(
        self, keywords: str, city: str = "", citylimit: str = "false"
    ) -> SearchResult:
        """
        关键词搜索.
        """
        params = {"keywords": keywords, "city": city, "citylimit": citylimit}
        data = await self._request("/v3/place/text", params)

        if data.get("status") != "1":
            raise Exception(
                f"Text Search failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_search_result(data)

    async def around_search(
        self, location: str, radius: str = "1000", keywords: str = ""
    ) -> SearchResult:
        """
        周边搜索.
        """
        params = {"location": location, "radius": radius, "keywords": keywords}
        data = await self._request("/v3/place/around", params)

        if data.get("status") != "1":
            raise Exception(
                f"Around Search failed: {data.get('info', data.get('infocode'))}"
            )

        return self._parse_search_result(data)

    def _parse_route_result(self, route_data: Dict[str, Any]) -> RouteResult:
        """
        解析路线结果.
        """
        origin_str = route_data.get("origin", "0,0")
        dest_str = route_data.get("destination", "0,0")

        origin_lon, origin_lat = map(float, origin_str.split(","))
        dest_lon, dest_lat = map(float, dest_str.split(","))

        origin = Location(longitude=origin_lon, latitude=origin_lat)
        destination = Location(longitude=dest_lon, latitude=dest_lat)

        paths = []
        for path_data in route_data.get("paths", []):
            steps = []
            for step_data in path_data.get("steps", []):
                step = RouteStep(
                    instruction=step_data.get("instruction", ""),
                    road=step_data.get("road", ""),
                    distance=int(step_data.get("distance", 0)),
                    orientation=step_data.get("orientation", ""),
                    duration=int(step_data.get("duration", 0)),
                )
                steps.append(step)

            path = RoutePath(
                distance=int(path_data.get("distance", 0)),
                duration=int(path_data.get("duration", 0)),
                steps=steps,
            )
            paths.append(path)

        return RouteResult(origin=origin, destination=destination, paths=paths)

    def _parse_transit_result(self, route_data: Dict[str, Any]) -> TransitResult:
        """
        解析公交路线结果.
        """
        origin_str = route_data.get("origin", "0,0")
        dest_str = route_data.get("destination", "0,0")

        origin_lon, origin_lat = map(float, origin_str.split(","))
        dest_lon, dest_lat = map(float, dest_str.split(","))

        origin = Location(longitude=origin_lon, latitude=origin_lat)
        destination = Location(longitude=dest_lon, latitude=dest_lat)

        transits = []
        for transit_data in route_data.get("transits", []):
            segments = []
            for segment_data in transit_data.get("segments", []):
                segment = TransitSegment()
                segments.append(segment)

            transit = TransitRoute(
                duration=int(transit_data.get("duration", 0)),
                walking_distance=int(transit_data.get("walking_distance", 0)),
                segments=segments,
            )
            transits.append(transit)

        return TransitResult(
            origin=origin,
            destination=destination,
            distance=int(route_data.get("distance", 0)),
            transits=transits,
        )

    def _parse_search_result(self, data: Dict[str, Any]) -> SearchResult:
        """
        解析搜索结果.
        """
        suggestion_data = data.get("suggestion", {})
        suggestion = SearchSuggestion(
            keywords=suggestion_data.get("keywords", []),
            cities=[
                {"name": city.get("name", "")}
                for city in suggestion_data.get("cities", [])
            ],
        )

        pois = []
        for poi_data in data.get("pois", []):
            location_str = poi_data.get("location", "0,0")
            if "," in location_str:
                lon, lat = map(float, location_str.split(","))
            else:
                lon, lat = 0.0, 0.0

            location = Location(longitude=lon, latitude=lat)

            poi = POI(
                id=poi_data.get("id", ""),
                name=poi_data.get("name", ""),
                address=poi_data.get("address", ""),
                location=location,
                type_code=poi_data.get("typecode"),
            )
            pois.append(poi)

        return SearchResult(suggestion=suggestion, pois=pois)
