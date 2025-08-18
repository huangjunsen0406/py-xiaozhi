"""高德地图MCP工具函数.

提供给MCP服务器调用的异步工具函数，包括地理编码、路径规划、搜索等功能
"""

import json
from typing import Any, Dict

import aiohttp

from src.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_amap_api_key() -> str:
    """
    获取高德地图API密钥.
    """
    # api_key = os.getenv("AMAP_API_KEY")
    # if not api_key:
    #     raise ValueError("AMAP_API_KEY environment variable is not set")
    return ""


async def maps_regeocode(args: Dict[str, Any]) -> str:
    """将经纬度坐标转换为地址信息.

    Args:
        args: 包含以下参数的字典
            - location: 经纬度坐标（格式：经度,纬度）

    Returns:
        str: JSON格式的地址信息
    """
    try:
        location = args["location"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/geocode/regeo"
        params = {"location": location, "key": api_key, "source": "py_xiaozhi"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"逆地理编码失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        result = {
            "success": True,
            "data": {
                "province": data["regeocode"]["addressComponent"]["province"],
                "city": data["regeocode"]["addressComponent"]["city"],
                "district": data["regeocode"]["addressComponent"]["district"],
                "formatted_address": data["regeocode"]["formatted_address"],
            },
        }

        logger.info(f"[AmapTools] 逆地理编码成功: {location}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"逆地理编码失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_geo(args: Dict[str, Any]) -> str:
    """将地址转换为经纬度坐标.

    Args:
        args: 包含以下参数的字典
            - address: 待解析的地址
            - city: 指定查询的城市（可选）

    Returns:
        str: JSON格式的坐标信息
    """
    try:
        address = args["address"]
        city = args.get("city", "")
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/geocode/geo"
        params = {"address": address, "key": api_key, "source": "py_xiaozhi"}
        if city:
            params["city"] = city

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"地理编码失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        geocodes = data.get("geocodes", [])
        result_data = []

        for geo in geocodes:
            result_data.append(
                {
                    "country": geo.get("country"),
                    "province": geo.get("province"),
                    "city": geo.get("city"),
                    "citycode": geo.get("citycode"),
                    "district": geo.get("district"),
                    "street": geo.get("street"),
                    "number": geo.get("number"),
                    "adcode": geo.get("adcode"),
                    "location": geo.get("location"),
                    "level": geo.get("level"),
                    "formatted_address": geo.get("formatted_address"),
                }
            )

        result = {"success": True, "data": result_data}

        logger.info(f"[AmapTools] 地理编码成功: {address}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"地理编码失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_ip_location(args: Dict[str, Any]) -> str:
    """根据IP地址获取位置信息.

    Args:
        args: 包含以下参数的字典
            - ip: IP地址

    Returns:
        str: JSON格式的位置信息
    """
    try:
        ip = args["ip"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/ip"
        params = {"ip": ip, "key": api_key, "source": "py_xiaozhi"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"IP定位失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        result = {
            "success": True,
            "data": {
                "province": data.get("province"),
                "city": data.get("city"),
                "adcode": data.get("adcode"),
                "rectangle": data.get("rectangle"),
            },
        }

        logger.info(f"[AmapTools] IP定位成功: {ip}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"IP定位失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_weather(args: Dict[str, Any]) -> str:
    """查询城市天气信息.

    Args:
        args: 包含以下参数的字典
            - city: 城市名称或adcode

    Returns:
        str: JSON格式的天气信息
    """
    try:
        city = args["city"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "city": city,
            "key": api_key,
            "source": "py_xiaozhi",
            "extensions": "all",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"天气查询失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        forecasts = data.get("forecasts", [])
        if not forecasts:
            error_msg = "未找到天气数据"
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        forecast = forecasts[0]
        result = {
            "success": True,
            "data": {
                "city": forecast.get("city"),
                "reporttime": forecast.get("reporttime"),
                "casts": forecast.get("casts", []),
            },
        }

        logger.info(f"[AmapTools] 天气查询成功: {city}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"天气查询失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_direction_walking(args: Dict[str, Any]) -> str:
    """步行路径规划.

    Args:
        args: 包含以下参数的字典
            - origin: 出发点经纬度（格式：经度,纬度）
            - destination: 目的地经纬度（格式：经度,纬度）

    Returns:
        str: JSON格式的步行路径信息
    """
    try:
        origin = args["origin"]
        destination = args["destination"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/direction/walking"
        params = {
            "origin": origin,
            "destination": destination,
            "key": api_key,
            "source": "py_xiaozhi",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"步行路径规划失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        route = data.get("route", {})
        paths = route.get("paths", [])

        result_paths = []
        for path in paths:
            steps_data = []
            for step in path.get("steps", []):
                steps_data.append(
                    {
                        "instruction": step.get("instruction"),
                        "road": step.get("road"),
                        "distance": step.get("distance"),
                        "orientation": step.get("orientation"),
                        "duration": step.get("duration"),
                    }
                )

            result_paths.append(
                {
                    "distance": path.get("distance"),
                    "duration": path.get("duration"),
                    "steps": steps_data,
                }
            )

        result = {
            "success": True,
            "data": {
                "origin": route.get("origin"),
                "destination": route.get("destination"),
                "paths": result_paths,
            },
        }

        logger.info(f"[AmapTools] 步行路径规划成功: {origin} -> {destination}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"步行路径规划失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_direction_driving(args: Dict[str, Any]) -> str:
    """驾车路径规划.

    Args:
        args: 包含以下参数的字典
            - origin: 出发点经纬度（格式：经度,纬度）
            - destination: 目的地经纬度（格式：经度,纬度）

    Returns:
        str: JSON格式的驾车路径信息
    """
    try:
        origin = args["origin"]
        destination = args["destination"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/direction/driving"
        params = {
            "origin": origin,
            "destination": destination,
            "key": api_key,
            "source": "py_xiaozhi",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"驾车路径规划失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        route = data.get("route", {})
        paths = route.get("paths", [])

        result_paths = []
        for path in paths:
            steps_data = []
            for step in path.get("steps", []):
                steps_data.append(
                    {
                        "instruction": step.get("instruction"),
                        "road": step.get("road"),
                        "distance": step.get("distance"),
                        "orientation": step.get("orientation"),
                        "duration": step.get("duration"),
                    }
                )

            result_paths.append(
                {
                    "distance": path.get("distance"),
                    "duration": path.get("duration"),
                    "tolls": path.get("tolls"),
                    "toll_distance": path.get("toll_distance"),
                    "steps": steps_data,
                }
            )

        result = {
            "success": True,
            "data": {
                "origin": route.get("origin"),
                "destination": route.get("destination"),
                "taxi_cost": route.get("taxi_cost"),
                "paths": result_paths,
            },
        }

        logger.info(f"[AmapTools] 驾车路径规划成功: {origin} -> {destination}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"驾车路径规划失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_text_search(args: Dict[str, Any]) -> str:
    """关键词搜索POI.

    Args:
        args: 包含以下参数的字典
            - keywords: 搜索关键词
            - city: 查询城市（可选）
            - types: POI类型（可选）

    Returns:
        str: JSON格式的搜索结果
    """
    try:
        keywords = args["keywords"]
        city = args.get("city", "")
        types = args.get("types", "")
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/place/text"
        params = {
            "keywords": keywords,
            "key": api_key,
            "source": "py_xiaozhi",
            "citylimit": "false",
        }
        if city:
            params["city"] = city
        if types:
            params["types"] = types

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"搜索失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        pois = data.get("pois", [])
        result_pois = []

        for poi in pois:
            result_pois.append(
                {
                    "id": poi.get("id"),
                    "name": poi.get("name"),
                    "address": poi.get("address"),
                    "location": poi.get("location"),
                    "typecode": poi.get("typecode"),
                    "type": poi.get("type"),
                    "tel": poi.get("tel"),
                    "distance": poi.get("distance"),
                }
            )

        result = {
            "success": True,
            "data": {"count": data.get("count"), "pois": result_pois},
        }

        logger.info(f"[AmapTools] 搜索成功: {keywords}, 结果数量: {len(result_pois)}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"搜索失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_around_search(args: Dict[str, Any]) -> str:
    """周边搜索POI.

    Args:
        args: 包含以下参数的字典
            - location: 中心点经纬度（格式：经度,纬度）
            - keywords: 搜索关键词（可选）
            - radius: 搜索半径，单位米（可选，默认1000）

    Returns:
        str: JSON格式的周边搜索结果
    """
    try:
        location = args["location"]
        keywords = args.get("keywords", "")
        radius = args.get("radius", "1000")
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/place/around"
        params = {
            "location": location,
            "radius": radius,
            "key": api_key,
            "source": "py_xiaozhi",
        }
        if keywords:
            params["keywords"] = keywords

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"周边搜索失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        pois = data.get("pois", [])
        result_pois = []

        for poi in pois:
            result_pois.append(
                {
                    "id": poi.get("id"),
                    "name": poi.get("name"),
                    "address": poi.get("address"),
                    "location": poi.get("location"),
                    "typecode": poi.get("typecode"),
                    "type": poi.get("type"),
                    "tel": poi.get("tel"),
                    "distance": poi.get("distance"),
                }
            )

        result = {
            "success": True,
            "data": {"count": data.get("count"), "pois": result_pois},
        }

        logger.info(
            f"[AmapTools] 周边搜索成功: {location}, 结果数量: {len(result_pois)}"
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"周边搜索失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_search_detail(args: Dict[str, Any]) -> str:
    """查询POI详细信息.

    Args:
        args: 包含以下参数的字典
            - id: POI的ID

    Returns:
        str: JSON格式的详细信息
    """
    try:
        poi_id = args["id"]
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/place/detail"
        params = {"id": poi_id, "key": api_key, "source": "py_xiaozhi"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"POI详情查询失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        pois = data.get("pois", [])
        if not pois:
            error_msg = "未找到POI详情"
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        poi = pois[0]
        biz_ext = poi.get("biz_ext", {})

        result = {
            "success": True,
            "data": {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "location": poi.get("location"),
                "address": poi.get("address"),
                "business_area": poi.get("business_area"),
                "cityname": poi.get("cityname"),
                "type": poi.get("type"),
                "alias": poi.get("alias"),
                "tel": poi.get("tel"),
                "website": poi.get("website"),
                "email": poi.get("email"),
                "postcode": poi.get("postcode"),
                "rating": biz_ext.get("rating"),
                "cost": biz_ext.get("cost"),
                "opentime": biz_ext.get("opentime"),
            },
        }

        logger.info(f"[AmapTools] POI详情查询成功: {poi_id}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"POI详情查询失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)


async def maps_distance(args: Dict[str, Any]) -> str:
    """距离测量.

    Args:
        args: 包含以下参数的字典
            - origins: 起点经纬度，可多个，用分号分隔
            - destination: 终点经纬度
            - type: 距离测量类型（可选，默认1：驾车距离，0：直线距离，3：步行距离）

    Returns:
        str: JSON格式的距离信息
    """
    try:
        origins = args["origins"]
        destination = args["destination"]
        distance_type = args.get("type", "1")
        api_key = get_amap_api_key()

        url = "https://restapi.amap.com/v3/distance"
        params = {
            "origins": origins,
            "destination": destination,
            "type": distance_type,
            "key": api_key,
            "source": "py_xiaozhi",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

        if data.get("status") != "1":
            error_msg = f"距离测量失败: {data.get('info', data.get('infocode'))}"
            logger.error(f"[AmapTools] {error_msg}")
            return json.dumps(
                {"success": False, "message": error_msg}, ensure_ascii=False
            )

        results = data.get("results", [])
        result_data = []

        for result_item in results:
            result_data.append(
                {
                    "origin_id": result_item.get("origin_id"),
                    "dest_id": result_item.get("dest_id"),
                    "distance": result_item.get("distance"),
                    "duration": result_item.get("duration"),
                }
            )

        result = {"success": True, "data": {"results": result_data}}

        logger.info(f"[AmapTools] 距离测量成功: {origins} -> {destination}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except KeyError as e:
        error_msg = f"缺少必需参数: {e}"
        logger.error(f"[AmapTools] {error_msg}")
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
    except Exception as e:
        error_msg = f"距离测量失败: {str(e)}"
        logger.error(f"[AmapTools] {error_msg}", exc_info=True)
        return json.dumps({"success": False, "message": error_msg}, ensure_ascii=False)
