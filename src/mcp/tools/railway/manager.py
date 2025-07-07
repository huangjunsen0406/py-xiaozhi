"""
12306铁路查询工具管理器.

负责注册和管理所有12306相关工具.
"""

from typing import Any, Dict

from src.utils.logging_config import get_logger

from .tools import (
    get_city_station_code,
    get_current_date,
    get_station_by_code,
    get_station_by_name,
    get_stations_in_city,
    query_train_route,
    query_train_tickets,
    query_transfer_tickets,
)

logger = get_logger(__name__)


class RailwayManager:
    """
    铁路查询工具管理器.
    """

    def __init__(self):
        """
        初始化铁路工具管理器.
        """
        self._initialized = False
        logger.info("[12306_mcp] 初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有铁路查询工具.
        """
        try:
            logger.info("[12306_mcp] 开始注册工具")

            # 注册基础工具
            self._register_basic_tools(add_tool, PropertyList, Property, PropertyType)

            # 注册查询工具
            self._register_query_tools(add_tool, PropertyList, Property, PropertyType)

            self._initialized = True
            logger.info("[12306_mcp] 工具注册完成")

        except Exception as e:
            logger.error(f"[12306_mcp] 工具注册失败: {e}", exc_info=True)
            raise

    def _register_basic_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册基础工具.
        """
        # 获取当前日期
        add_tool(
            (
                "self.railway.get_current_date",
                "Get current date in Shanghai timezone (Asia/Shanghai, UTC+8) in 'YYYY-MM-DD' format. "
                "This tool is essential for parsing relative dates mentioned by users (like 'tomorrow', "
                "'next week') and providing accurate date inputs for other railway query tools.\n"
                "Use this tool when:\n"
                "1. User mentions relative dates ('tomorrow', 'day after tomorrow', 'next Monday')\n"
                "2. You need the current date as reference for date calculations\n"
                "3. Before calling ticket query tools that require specific dates\n"
                "4. When validating if a requested date is valid (not in the past)\n\n"
                "The returned date follows the format 'YYYY-MM-DD' and can be used directly "
                "in other railway tools that require date parameters.",
                PropertyList(),
                get_current_date,
            )
        )

        # 查询城市中的车站
        city_stations_props = PropertyList(
            [Property("city", PropertyType.STRING)]
        )
        add_tool(
            (
                "self.railway.get_stations_in_city",
                "Get all railway stations within a specific city by Chinese city name. "
                "Returns a comprehensive list of stations in the city with their codes and names.\n"
                "Use this tool when:\n"
                "1. User asks 'what stations are in Beijing/Shanghai/etc.'\n"
                "2. You need to show all available stations in a city\n"
                "3. User wants to choose from multiple stations in a city\n"
                "4. Before booking tickets to help user select the right station\n\n"
                "Args:\n"
                "  city: Chinese city name (e.g., '北京', '上海', '广州')\n\n"
                "Returns detailed station information including station codes needed for ticket queries.",
                city_stations_props,
                get_stations_in_city,
            )
        )

        # 获取城市主要车站编码
        city_code_props = PropertyList(
            [Property("cities", PropertyType.STRING)]
        )
        add_tool(
            (
                "self.railway.get_city_station_codes",
                "Get main station codes for cities by Chinese city names. This tool provides "
                "the primary station code for each city, which represents the main railway station "
                "in that city (usually the station with the same name as the city).\n"
                "Use this tool when:\n"
                "1. User provides city names as departure/arrival locations\n"
                "2. You need station codes for ticket queries but user only mentioned cities\n"
                "3. Converting city names to station codes for API calls\n"
                "4. When user says 'from Beijing to Shanghai' (meaning main stations)\n\n"
                "Args:\n"
                "  cities: City names separated by '|' (e.g., '北京|上海|广州')\n\n"
                "Returns the primary station code and name for each city, essential for "
                "ticket booking and route planning.",
                city_code_props,
                get_city_station_code,
            )
        )

        # 根据车站名获取编码
        station_name_props = PropertyList(
            [Property("station_names", PropertyType.STRING)]
        )
        add_tool(
            (
                "self.railway.get_station_codes_by_names",
                "Get station codes by specific Chinese station names. This tool converts "
                "exact station names to their corresponding codes needed for ticket queries.\n"
                "Use this tool when:\n"
                "1. User provides specific station names (e.g., '北京南', '上海虹桥')\n"
                "2. Converting station names to codes for API calls\n"
                "3. User wants to depart from/arrive at a specific station (not just city)\n"
                "4. Validating if a station name exists in the system\n\n"
                "Args:\n"
                "  station_names: Station names separated by '|' (e.g., '北京南|上海虹桥|广州南')\n\n"
                "Returns station codes and names for exact station matching.",
                station_name_props,
                get_station_by_name,
            )
        )

        # 根据编码获取车站信息
        station_code_props = PropertyList(
            [Property("station_code", PropertyType.STRING)]
        )
        add_tool(
            (
                "self.railway.get_station_by_code",
                "Get detailed station information by station code (3-letter telecode). "
                "Returns comprehensive station details including Chinese name, pinyin, city, etc.\n"
                "Use this tool when:\n"
                "1. You have a station code and need detailed information\n"
                "2. Validating station codes from other tool results\n"
                "3. Getting human-readable station information for display\n"
                "4. Debugging or verifying station code correctness\n\n"
                "Args:\n"
                "  station_code: 3-letter station code (e.g., 'BJP', 'SHH', 'SZQ')\n\n"
                "Returns detailed station information including full name, pinyin, and city.",
                station_code_props,
                get_station_by_code,
            )
        )

        logger.debug("[12306_mcp] 注册基础工具成功")

    def _register_query_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册查询工具.
        """
        # 查询车票
        ticket_props = PropertyList(
            [
                Property("date", PropertyType.STRING),
                Property("from_station", PropertyType.STRING),
                Property("to_station", PropertyType.STRING),
                Property("train_filters", PropertyType.STRING, default_value=""),
                Property("sort_by", PropertyType.STRING, default_value=""),
                Property("reverse", PropertyType.BOOLEAN, default_value=False),
                Property("limit", PropertyType.INTEGER, default_value=0, min_value=0, max_value=50),
            ]
        )
        add_tool(
            (
                "self.railway.query_tickets",
                "Query 12306 train tickets with comprehensive filtering and sorting options. "
                "This is the main tool for finding available trains between two stations.\n"
                "Use this tool when user wants to:\n"
                "1. Search for train tickets between two locations\n"
                "2. Find specific types of trains (high-speed, regular, etc.)\n"
                "3. Check ticket availability and prices\n"
                "4. Plan travel with specific departure/arrival time preferences\n"
                "5. Compare different train options\n\n"
                "Train Filter Options:\n"
                "- 'G': High-speed trains and intercity trains (G/C prefix)\n"
                "- 'D': Electric multiple unit trains (D prefix)\n"
                "- 'Z': Direct express trains (Z prefix)\n"
                "- 'T': Express trains (T prefix)\n"
                "- 'K': Fast trains (K prefix)\n"
                "- 'O': Other types (not in above categories)\n"
                "- Can combine multiple filters like 'GD' for high-speed and EMU trains\n\n"
                "Sort Options:\n"
                "- 'start_time': Sort by departure time (earliest first)\n"
                "- 'arrive_time': Sort by arrival time (earliest first)\n"
                "- 'duration': Sort by travel duration (shortest first)\n\n"
                "Args:\n"
                "  date: Travel date in 'YYYY-MM-DD' format (use get_current_date for relative dates)\n"
                "  from_station: Departure station code (get from station lookup tools)\n"
                "  to_station: Arrival station code (get from station lookup tools)\n"
                "  train_filters: Train type filters (optional, e.g., 'G' for high-speed only)\n"
                "  sort_by: Sort method (optional: start_time/arrive_time/duration)\n"
                "  reverse: Reverse sort order (default: false)\n"
                "  limit: Maximum number of results (default: 0 = no limit)\n\n"
                "Returns detailed ticket information including train numbers, times, prices, and seat availability.",
                ticket_props,
                query_train_tickets,
            )
        )

        # 查询中转车票
        transfer_props = PropertyList(
            [
                Property("date", PropertyType.STRING),
                Property("from_station", PropertyType.STRING),
                Property("to_station", PropertyType.STRING),
                Property("middle_station", PropertyType.STRING, default_value=""),
                Property("show_wz", PropertyType.BOOLEAN, default_value=False),
                Property("train_filters", PropertyType.STRING, default_value=""),
                Property("sort_by", PropertyType.STRING, default_value=""),
                Property("reverse", PropertyType.BOOLEAN, default_value=False),
                Property("limit", PropertyType.INTEGER, default_value=10, min_value=1, max_value=20),
            ]
        )
        add_tool(
            (
                "self.railway.query_transfer_tickets",
                "Query 12306 transfer/connecting train tickets for routes requiring transfers. "
                "This tool finds multi-leg journeys when direct trains are not available.\n"
                "Use this tool when:\n"
                "1. No direct trains available between two cities\n"
                "2. User specifically asks for transfer/connecting options\n"
                "3. Looking for alternative routes with connections\n"
                "4. User mentions a specific transfer city\n"
                "5. Direct routes are sold out or inconvenient\n\n"
                "Transfer Types:\n"
                "- Same station transfer: Change trains at the same station\n"
                "- Different station transfer: Move between different stations in transfer city\n"
                "- Same train transfer: Transfer within the same train (rare)\n\n"
                "Args:\n"
                "  date: Travel date in 'YYYY-MM-DD' format\n"
                "  from_station: Departure station code\n"
                "  to_station: Final destination station code\n"
                "  middle_station: Preferred transfer station code (optional)\n"
                "  show_wz: Include trains with no seats available (default: false)\n"
                "  train_filters: Train type filters (same as direct tickets)\n"
                "  sort_by: Sort method (start_time/arrive_time/duration)\n"
                "  reverse: Reverse sort order\n"
                "  limit: Maximum transfer options to return (default: 10)\n\n"
                "Returns transfer journey options with detailed information about each leg, "
                "waiting times, and total travel duration.",
                transfer_props,
                query_transfer_tickets,
            )
        )

        # 查询车次经停站
        route_props = PropertyList(
            [
                Property("train_no", PropertyType.STRING),
                Property("from_station_code", PropertyType.STRING),
                Property("to_station_code", PropertyType.STRING),
                Property("depart_date", PropertyType.STRING),
            ]
        )
        add_tool(
            (
                "self.railway.query_train_route",
                "Query detailed route information for a specific train, showing all stations "
                "the train stops at with arrival/departure times and stop duration.\n"
                "Use this tool when user asks:\n"
                "1. 'Which stations does train G123 stop at?'\n"
                "2. 'What is the route of this train?'\n"
                "3. 'When does train D456 arrive at [specific station]?'\n"
                "4. 'How long does the train stop at [station]?'\n"
                "5. User wants to board/alight at intermediate stations\n\n"
                "Important Notes:\n"
                "- train_no is the actual train number (e.g., '240000G10336'), not display name ('G1033')\n"
                "- You can get train_no from ticket query results\n"
                "- from_station_code and to_station_code define the journey segment\n"
                "- depart_date is when the train departs from from_station_code\n\n"
                "Args:\n"
                "  train_no: Actual train number from ticket query results (required)\n"
                "  from_station_code: Journey start station code (required)\n"
                "  to_station_code: Journey end station code (required)\n"
                "  depart_date: Departure date in 'YYYY-MM-DD' format (required)\n\n"
                "Returns detailed station-by-station information including arrival times, "
                "departure times, and stop durations for the entire route.",
                route_props,
                query_train_route,
            )
        )

        logger.debug("[12306_mcp] 注册查询工具成功")

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
            "tools_count": 8,
            "available_tools": [
                "get_current_date",
                "get_stations_in_city",
                "get_city_station_codes",
                "get_station_codes_by_names",
                "get_station_by_code",
                "query_tickets",
                "query_transfer_tickets",
                "query_train_route",
            ],
        }


# 全局管理器实例
_railway_manager = None


def get_railway_manager() -> RailwayManager:
    """
    获取铁路工具管理器单例.
    """
    global _railway_manager
    if _railway_manager is None:
        _railway_manager = RailwayManager()
        logger.debug("[12306_mcp] 创建管理器实例")
    return _railway_manager
