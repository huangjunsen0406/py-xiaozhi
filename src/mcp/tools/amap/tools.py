"""
高德地图 MCP 工具定义.
"""

from typing import Any, Dict, List


class AmapTools:
    """
    高德地图工具集.
    """

    def __init__(self, api_key: str):
        # 延迟导入避免循环导入
        from .manager import AmapManager
        self.manager = AmapManager(api_key)

    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取所有工具定义.
        """
        # 原子工具
        atomic_tools = [
            {
                "name": "maps_regeocode",
                "description": "将一个高德经纬度坐标转换为行政区划地址信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "经纬度坐标，格式为：经度,纬度",
                        }
                    },
                    "required": ["location"],
                },
            },
            {
                "name": "maps_geo",
                "description": "将详细的结构化地址转换为经纬度坐标。支持对地标性名胜景区、建筑物名称解析为经纬度坐标",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "address": {
                            "type": "string",
                            "description": "待解析的结构化地址信息",
                        },
                        "city": {
                            "type": "string",
                            "description": "指定查询的城市（可选）",
                        },
                    },
                    "required": ["address"],
                },
            },
            {
                "name": "maps_ip_location",
                "description": "IP定位根据用户输入的IP地址，定位IP的所在位置",
                "inputSchema": {
                    "type": "object",
                    "properties": {"ip": {"type": "string", "description": "IP地址"}},
                    "required": ["ip"],
                },
            },
            {
                "name": "maps_weather",
                "description": "根据城市名称或者标准adcode查询指定城市的天气",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名称或者adcode"}
                    },
                    "required": ["city"],
                },
            },
            {
                "name": "maps_search_detail",
                "description": "查询关键词搜索或者周边搜索获取到的POI ID的详细信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "关键词搜索或者周边搜索获取到的POI ID",
                        }
                    },
                    "required": ["id"],
                },
            },
            {
                "name": "maps_direction_walking",
                "description": "步行路径规划API可以根据输入起点终点经纬度坐标规划100km以内的步行通勤方案",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "出发点经纬度，坐标格式为：经度,纬度",
                        },
                        "destination": {
                            "type": "string",
                            "description": "目的地经纬度，坐标格式为：经度,纬度",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "maps_direction_driving",
                "description": "驾车路径规划API可以根据用户起终点经纬度坐标规划以小客车、轿车通勤出行的方案",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "出发点经纬度，坐标格式为：经度,纬度",
                        },
                        "destination": {
                            "type": "string",
                            "description": "目的地经纬度，坐标格式为：经度,纬度",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "maps_bicycling",
                "description": "骑行路径规划用于规划骑行通勤方案，规划时会考虑天桥、单行线、封路等情况。最大支持500km的骑行路线规划",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "出发点经纬度，坐标格式为：经度,纬度",
                        },
                        "destination": {
                            "type": "string",
                            "description": "目的地经纬度，坐标格式为：经度,纬度",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "maps_direction_transit_integrated",
                "description": "公交路径规划API可以根据用户起终点经纬度坐标规划综合各类公共交通方式的通勤方案",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "出发点经纬度，坐标格式为：经度,纬度",
                        },
                        "destination": {
                            "type": "string",
                            "description": "目的地经纬度，坐标格式为：经度,纬度",
                        },
                        "city": {
                            "type": "string",
                            "description": "公共交通规划起点城市",
                        },
                        "cityd": {
                            "type": "string",
                            "description": "公共交通规划终点城市",
                        },
                    },
                    "required": ["origin", "destination", "city", "cityd"],
                },
            },
            {
                "name": "maps_distance",
                "description": "距离测量API可以测量两个经纬度坐标之间的距离，支持驾车、步行以及球面距离测量",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origins": {
                            "type": "string",
                            "description": "起点经纬度，可以传多个坐标，使用分号隔离，比如120,30;120,31",
                        },
                        "destination": {
                            "type": "string",
                            "description": "终点经纬度，坐标格式为：经度,纬度",
                        },
                        "type": {
                            "type": "string",
                            "description": "距离测量类型，1代表驾车距离测量，0代表直线距离测量，3代表步行距离测量",
                        },
                    },
                    "required": ["origins", "destination"],
                },
            },
            {
                "name": "maps_text_search",
                "description": "关键词搜索，根据用户传入关键词，搜索出相关的POI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keywords": {"type": "string", "description": "搜索关键词"},
                        "city": {"type": "string", "description": "查询城市（可选）"},
                        "types": {
                            "type": "string",
                            "description": "POI类型，比如加油站（可选）",
                        },
                    },
                    "required": ["keywords"],
                },
            },
            {
                "name": "maps_around_search",
                "description": "周边搜索，根据用户传入关键词以及坐标location，搜索出radius半径范围的POI",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "中心点经纬度，格式为：经度,纬度",
                        },
                        "radius": {"type": "string", "description": "搜索半径（米）"},
                        "keywords": {
                            "type": "string",
                            "description": "搜索关键词（可选）",
                        },
                    },
                    "required": ["location"],
                },
            },
        ]
        
        # 智能组合工具
        smart_tools = [
            {
                "name": "smart_get_current_location",
                "description": "智能定位 - 自动获取用户当前位置，支持IP定位和地理编码",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_ip": {
                            "type": "string",
                            "description": "用户IP地址（可选，不提供则自动获取）",
                        }
                    },
                    "required": [],
                },
            },
            {
                "name": "smart_route_planning",
                "description": "智能路线规划 - 支持地址名称到地址名称的路线规划。例如：'云升科学园到科学城地铁站步行方案'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "起点地址名称",
                        },
                        "destination": {
                            "type": "string",
                            "description": "终点地址名称",
                        },
                        "city": {
                            "type": "string",
                            "description": "所在城市（可选，默认广州）",
                        },
                        "travel_mode": {
                            "type": "string",
                            "description": "出行方式：walking(步行)、driving(驾车)、bicycling(骑行)、transit(公交)，默认walking",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
            {
                "name": "smart_find_nearby_places",
                "description": "附近地点搜索 - 自动定位并搜索附近的地点。例如：'附近有哪些奶茶店'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "搜索关键词，如'奶茶店'、'餐厅'、'超市'、'银行'等",
                        },
                        "radius": {
                            "type": "string",
                            "description": "搜索半径（米），默认2000米",
                        },
                        "user_location": {
                            "type": "string",
                            "description": "用户位置坐标（可选，不提供则自动定位）",
                        },
                    },
                    "required": ["keywords"],
                },
            },
            {
                "name": "smart_find_nearest_place",
                "description": "最近的XX查找 - 找到最近的某类地点并规划路线。例如：'最近的奶茶店怎么走'、'最近的餐厅在哪里'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "搜索关键词，如'奶茶店'、'餐厅'、'地铁站'、'银行'等",
                        },
                        "radius": {
                            "type": "string",
                            "description": "搜索半径（米），默认5000米",
                        },
                        "user_location": {
                            "type": "string",
                            "description": "用户位置坐标（可选，不提供则自动定位）",
                        },
                    },
                    "required": ["keywords"],
                },
            },
            {
                "name": "smart_find_nearest_subway",
                "description": "最近地铁站查找 - 找到最近的地铁站并规划路线。例如：'最近的地铁站怎么走'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_location": {
                            "type": "string",
                            "description": "用户位置坐标（可选，不提供则自动定位）",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "smart_find_nearby_subway_stations",
                "description": "附近地铁站列表 - 获取附近所有地铁站信息。例如：'附近有哪些地铁站'",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "radius": {
                            "type": "string",
                            "description": "搜索半径（米），默认3000米",
                        },
                        "user_location": {
                            "type": "string",
                            "description": "用户位置坐标（可选，不提供则自动定位）",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "smart_navigation_to_place",
                "description": "导航到指定地点 - 智能选择最佳路线并提供多种出行方式对比",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "目的地名称",
                        },
                        "city": {
                            "type": "string",
                            "description": "所在城市（可选，默认广州）",
                        },
                        "user_location": {
                            "type": "string",
                            "description": "用户位置坐标（可选，不提供则自动定位）",
                        },
                    },
                    "required": ["destination"],
                },
            },
            {
                "name": "smart_compare_routes",
                "description": "多种出行方式对比 - 比较不同出行方式的时间和距离",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "origin": {
                            "type": "string",
                            "description": "起点地址名称",
                        },
                        "destination": {
                            "type": "string",
                            "description": "终点地址名称",
                        },
                        "city": {
                            "type": "string",
                            "description": "所在城市（可选，默认广州）",
                        },
                    },
                    "required": ["origin", "destination"],
                },
            },
        ]
        
        # 合并所有工具
        return atomic_tools + smart_tools

    async def execute_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具.
        """
        try:
            # 原子工具
            if tool_name == "maps_regeocode":
                return await self.manager.regeocode(arguments["location"])

            elif tool_name == "maps_geo":
                return await self.manager.geocode(
                    arguments["address"], arguments.get("city")
                )

            elif tool_name == "maps_ip_location":
                return await self.manager.ip_location(arguments["ip"])

            elif tool_name == "maps_weather":
                return await self.manager.weather(arguments["city"])

            elif tool_name == "maps_search_detail":
                return await self.manager.search_detail(arguments["id"])

            elif tool_name == "maps_direction_walking":
                return await self.manager.direction_walking(
                    arguments["origin"], arguments["destination"]
                )

            elif tool_name == "maps_direction_driving":
                return await self.manager.direction_driving(
                    arguments["origin"], arguments["destination"]
                )

            elif tool_name == "maps_bicycling":
                return await self.manager.direction_bicycling(
                    arguments["origin"], arguments["destination"]
                )

            elif tool_name == "maps_direction_transit_integrated":
                return await self.manager.direction_transit(
                    arguments["origin"],
                    arguments["destination"],
                    arguments["city"],
                    arguments["cityd"],
                )

            elif tool_name == "maps_distance":
                return await self.manager.distance(
                    arguments["origins"],
                    arguments["destination"],
                    arguments.get("type", "1"),
                )

            elif tool_name == "maps_text_search":
                return await self.manager.text_search(
                    arguments["keywords"],
                    arguments.get("city", ""),
                    arguments.get("types", ""),
                )

            elif tool_name == "maps_around_search":
                return await self.manager.around_search(
                    arguments["location"],
                    arguments.get("radius", "1000"),
                    arguments.get("keywords", ""),
                )

            # 智能组合工具
            elif tool_name == "smart_get_current_location":
                return await self.manager.get_current_location(
                    arguments.get("user_ip")
                )

            elif tool_name == "smart_route_planning":
                return await self.manager.route_planning(
                    arguments["origin"],
                    arguments["destination"],
                    arguments.get("city", "广州"),
                    arguments.get("travel_mode", "walking")
                )

            elif tool_name == "smart_find_nearby_places":
                return await self.manager.find_nearby_places(
                    arguments["keywords"],
                    arguments.get("radius", "2000"),
                    arguments.get("user_location")
                )

            elif tool_name == "smart_find_nearest_place":
                return await self.manager.find_nearest_place(
                    arguments["keywords"],
                    arguments.get("user_location"),
                    arguments.get("radius", "5000")
                )

            elif tool_name == "smart_find_nearest_subway":
                return await self.manager.find_nearest_subway(
                    arguments.get("user_location")
                )

            elif tool_name == "smart_find_nearby_subway_stations":
                return await self.manager.find_nearby_subway_stations(
                    arguments.get("user_location"),
                    arguments.get("radius", "3000")
                )

            elif tool_name == "smart_navigation_to_place":
                return await self.manager.navigation_to_place(
                    arguments["destination"],
                    arguments.get("city", "广州"),
                    arguments.get("user_location")
                )

            elif tool_name == "smart_compare_routes":
                return await self.manager.compare_routes(
                    arguments["origin"],
                    arguments["destination"],
                    arguments.get("city", "广州")
                )

            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"success": False, "error": f"Tool execution failed: {str(e)}"}

    async def close(self):
        """
        关闭资源.
        """
        await self.manager.close()
