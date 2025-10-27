"""12306铁路查询工具管理器.

负责注册和管理所有12306相关工具.
"""

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

from src.utils.logging_config import get_logger

from .client import get_railway_client
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


class RailwayToolsManager:
    """
    Railway工具管理器 - 适配MCP服务器.
    """

    def __init__(self):
        """
        初始化Railway工具管理器.
        """
        self._initialized = False
        logger.info("[Railway] Railway工具管理器初始化")

    def init_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        初始化并注册所有Railway工具.
        """
        try:
            logger.info("[Railway] 开始注册Railway工具")

            # 注册智能工具
            self._register_smart_tools(add_tool, PropertyList, Property, PropertyType)

            # 注册原子工具
            self._register_atomic_tools(add_tool, PropertyList, Property, PropertyType)

            self._initialized = True
            logger.info("[Railway] Railway工具注册完成")

        except Exception as e:
            logger.error(f"[Railway] Railway工具注册失败: {e}", exc_info=True)
            raise

    def _register_smart_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册智能工具 - 用户友好的高级功能.
        """

        # 1. 智能火车票查询
        smart_ticket_props = PropertyList(
            [
                Property("departure_city", PropertyType.STRING),
                Property("arrival_city", PropertyType.STRING),
                Property("travel_date", PropertyType.STRING, default_value=""),
                Property("train_type", PropertyType.STRING, default_value=""),
                Property("departure_time", PropertyType.STRING, default_value=""),
                Property("limit", PropertyType.INTEGER, default_value=10),
            ]
        )
        add_tool(
            (
                "self.railway.smart_ticket_query",
                "Smart train ticket query that handles natural language inputs. "
                "This tool automatically converts city names to station codes and handles "
                "relative dates like 'tomorrow', 'next Monday', etc.\n"
                "Use this tool when user asks:\n"
                "1. '查询明天从北京到上海的火车票'\n"
                "2. '我想看看后天广州到深圳的高铁'\n"
                "3. 'Help me find tickets from Beijing to Shanghai tomorrow'\n"
                "4. '帮我查一下这周六从杭州到南京的车票'\n"
                "5. '查询2025年1月15日北京南到天津的动车'\n\n"
                "Train Type Options:\n"
                "- '高铁' or 'high-speed': G-series trains\n"
                "- '动车' or 'EMU': D-series trains\n"
                "- '直达' or 'direct': Z-series trains\n"
                "- '特快' or 'express': T-series trains\n"
                "- '快速' or 'fast': K-series trains\n"
                "- Empty string: all types\n\n"
                "Departure Time Options:\n"
                "- '上午' or 'morning': 06:00-12:00\n"
                "- '下午' or 'afternoon': 12:00-18:00\n"
                "- '晚上' or 'evening': 18:00-23:59\n\n"
                "Returns formatted ticket information with prices and availability.",
                smart_ticket_props,
                self._smart_ticket_query_callback,
            )
        )

        # 2. 智能中转查询
        smart_transfer_props = PropertyList(
            [
                Property("departure_city", PropertyType.STRING),
                Property("arrival_city", PropertyType.STRING),
                Property("travel_date", PropertyType.STRING, default_value=""),
                Property("transfer_city", PropertyType.STRING, default_value=""),
                Property("limit", PropertyType.INTEGER, default_value=5),
            ]
        )
        add_tool(
            (
                "self.railway.smart_transfer_query",
                "Smart transfer ticket query for routes requiring connections. "
                "This tool finds optimal transfer routes when direct trains are not available.\n"
                "Use this tool when:\n"
                "1. '从北京到广州没有直达车怎么办'\n"
                "2. '查询从哈尔滨到昆明的中转方案'\n"
                "3. '我需要在郑州中转，帮我查票'\n"
                "4. 'Find transfer options from Beijing to Guangzhou'\n"
                "5. User asks for alternative routes with connections\n\n"
                "Returns optimized transfer options with waiting times and total journey duration.",
                smart_transfer_props,
                self._smart_transfer_query_callback,
            )
        )

        # 3. 智能车站查询
        smart_station_props = PropertyList([Property("query", PropertyType.STRING)])
        add_tool(
            (
                "self.railway.smart_station_query",
                "Smart station information query that handles various types of station queries.\n"
                "Use this tool when user asks:\n"
                "1. '北京有哪些火车站'\n"
                "2. '上海的主要火车站是哪个'\n"
                "3. '查询北京南站的车站编码'\n"
                "4. '虹桥站的详细信息'\n"
                "5. 'What stations are in Beijing?'\n\n"
                "Returns comprehensive station information including codes, names, and cities.",
                smart_station_props,
                self._smart_station_query_callback,
            )
        )

        # 4. 智能出行建议
        smart_suggestion_props = PropertyList(
            [
                Property("departure_city", PropertyType.STRING),
                Property("arrival_city", PropertyType.STRING),
                Property("travel_date", PropertyType.STRING, default_value=""),
                Property("preferences", PropertyType.STRING, default_value=""),
            ]
        )
        add_tool(
            (
                "self.railway.smart_travel_suggestion",
                "Smart travel suggestion that provides comprehensive travel advice. "
                "This tool analyzes available options and gives personalized recommendations.\n"
                "Use this tool when user asks:\n"
                "1. '从北京到上海怎么去最好'\n"
                "2. '给我推荐一下从广州到深圳的出行方案'\n"
                "3. '我想要最快的方案去杭州'\n"
                "4. '经济实惠的火车票推荐'\n"
                "5. 'What's the best way to travel from A to B?'\n\n"
                "Preferences can include: '最快', '最便宜', '舒适', '上午出发', '下午到达' etc.\n"
                "Returns detailed travel recommendations with pros and cons.",
                smart_suggestion_props,
                self._smart_suggestion_callback,
            )
        )

        logger.debug("[Railway] 注册智能工具成功")

    def _register_atomic_tools(self, add_tool, PropertyList, Property, PropertyType):
        """
        注册原子工具 - 高级用户和开发者使用.
        """
        # 获取当前日期
        add_tool(
            (
                "self.railway.get_current_date",
                "Get current date in Shanghai timezone (Asia/Shanghai, UTC+8) in 'YYYY-MM-DD' format. "
                "This tool is essential for parsing relative dates mentioned by users (like 'tomorrow', "
                "'next week') and providing accurate date inputs for other railway query tools.",
                PropertyList(),
                get_current_date,
            )
        )

        # 查询城市中的车站
        city_stations_props = PropertyList([Property("city", PropertyType.STRING)])
        add_tool(
            (
                "self.railway.get_stations_in_city",
                "Get all railway stations within a specific city by Chinese city name. "
                "Returns a comprehensive list of stations in the city with their codes and names.",
                city_stations_props,
                get_stations_in_city,
            )
        )

        # 获取城市主要车站编码
        city_code_props = PropertyList([Property("cities", PropertyType.STRING)])
        add_tool(
            (
                "self.railway.get_city_station_codes",
                "Get main station codes for cities by Chinese city names. This tool provides "
                "the primary station code for each city, which represents the main railway station "
                "in that city (usually the station with the same name as the city).",
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
                "exact station names to their corresponding codes needed for ticket queries.",
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
                "Returns comprehensive station details including Chinese name, pinyin, city, etc.",
                station_code_props,
                get_station_by_code,
            )
        )

        # 查询车票
        ticket_props = PropertyList(
            [
                Property("date", PropertyType.STRING),
                Property("from_station", PropertyType.STRING),
                Property("to_station", PropertyType.STRING),
                Property("train_filters", PropertyType.STRING, default_value=""),
                Property("sort_by", PropertyType.STRING, default_value=""),
                Property("reverse", PropertyType.BOOLEAN, default_value=False),
                Property(
                    "limit",
                    PropertyType.INTEGER,
                    default_value=0,
                    min_value=0,
                    max_value=50,
                ),
            ]
        )
        add_tool(
            (
                "self.railway.query_tickets",
                "Query 12306 train tickets with comprehensive filtering and sorting options. "
                "This is the main tool for finding available trains between two stations.",
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
                Property(
                    "limit",
                    PropertyType.INTEGER,
                    default_value=10,
                    min_value=1,
                    max_value=20,
                ),
            ]
        )
        add_tool(
            (
                "self.railway.query_transfer_tickets",
                "Query 12306 transfer/connecting train tickets for routes requiring transfers. "
                "This tool finds multi-leg journeys when direct trains are not available.",
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
                "the train stops at with arrival/departure times and stop duration.",
                route_props,
                query_train_route,
            )
        )

        logger.debug("[Railway] 注册原子工具成功")

    # ==================== 智能工具回调函数 ====================

    async def _smart_ticket_query_callback(self, args: Dict[str, Any]) -> str:
        """
        智能火车票查询回调.
        """
        try:
            departure_city = args.get("departure_city", "")
            arrival_city = args.get("arrival_city", "")
            travel_date = args.get("travel_date", "")
            train_type = args.get("train_type", "")
            departure_time = args.get("departure_time", "")
            limit = args.get("limit", 10)

            if not departure_city or not arrival_city:
                return "错误：出发城市和到达城市不能为空"

            # 获取当前日期
            current_date = await self._get_current_date()

            # 处理日期
            if not travel_date:
                travel_date = current_date
            else:
                travel_date = self._parse_date(travel_date, current_date)

            # 获取车站编码
            from_station_code = await self._get_station_code(departure_city)
            to_station_code = await self._get_station_code(arrival_city)

            if not from_station_code or not to_station_code:
                return f"错误：无法找到 {departure_city} 或 {arrival_city} 的车站信息"

            # 转换车次类型
            train_filters = self._convert_train_type(train_type)

            # 查询车票
            client = await get_railway_client()
            success, tickets, message = await client.query_tickets(
                travel_date,
                from_station_code,
                to_station_code,
                train_filters,
                "start_time",
                False,
                limit,
            )

            if not success:
                return f"查询失败: {message}"

            if not tickets:
                return (
                    f"未找到 {travel_date} 从 {departure_city} 到 {arrival_city} 的车票"
                )

            # 根据出发时间过滤
            if departure_time:
                tickets = self._filter_by_departure_time(tickets, departure_time)

            # 格式化结果
            return self._format_smart_tickets(
                tickets, departure_city, arrival_city, travel_date
            )

        except Exception as e:
            logger.error(f"[Railway] 智能车票查询失败: {e}", exc_info=True)
            return f"查询失败: {str(e)}"

    async def _smart_transfer_query_callback(self, args: Dict[str, Any]) -> str:
        """
        智能中转查询回调.
        """
        try:
            departure_city = args.get("departure_city", "")
            arrival_city = args.get("arrival_city", "")
            travel_date = args.get("travel_date", "")
            transfer_city = args.get("transfer_city", "")
            limit = args.get("limit", 5)

            if not departure_city or not arrival_city:
                return "错误：出发城市和到达城市不能为空"

            # 获取当前日期
            current_date = await self._get_current_date()

            # 处理日期
            if not travel_date:
                travel_date = current_date
            else:
                travel_date = self._parse_date(travel_date, current_date)

            # 获取车站编码
            from_station_code = await self._get_station_code(departure_city)
            to_station_code = await self._get_station_code(arrival_city)

            if not from_station_code or not to_station_code:
                return f"错误：无法找到 {departure_city} 或 {arrival_city} 的车站信息"

            # 获取中转站编码
            middle_station_code = ""
            if transfer_city:
                middle_station_code = await self._get_station_code(transfer_city)

            # 查询中转车票
            client = await get_railway_client()
            success, transfers, message = await client.query_transfer_tickets(
                travel_date,
                from_station_code,
                to_station_code,
                middle_station_code,
                False,
                "",
                "start_time",
                False,
                limit,
            )

            if not success:
                return f"查询失败: {message}"

            if not transfers:
                return f"未找到 {travel_date} 从 {departure_city} 到 {arrival_city} 的中转方案"

            # 格式化结果
            return self._format_smart_transfers(
                transfers, departure_city, arrival_city, travel_date
            )

        except Exception as e:
            logger.error(f"[Railway] 智能中转查询失败: {e}", exc_info=True)
            return f"查询失败: {str(e)}"

    async def _smart_station_query_callback(self, args: Dict[str, Any]) -> str:
        """
        智能车站查询回调.
        """
        try:
            query = args.get("query", "")
            if not query:
                return "错误：查询内容不能为空"

            # 判断查询类型
            if "有哪些" in query or "stations" in query.lower():
                # 城市车站查询
                city = self._extract_city_from_query(query)
                if city:
                    return await self._query_city_stations(city)

            elif "主要" in query or "main" in query.lower():
                # 主要车站查询
                city = self._extract_city_from_query(query)
                if city:
                    return await self._query_main_station(city)

            elif "编码" in query or "code" in query.lower():
                # 车站编码查询
                station_name = self._extract_station_from_query(query)
                if station_name:
                    return await self._query_station_code(station_name)

            else:
                # 通用车站信息查询
                station_name = self._extract_station_from_query(query)
                if station_name:
                    return await self._query_station_info(station_name)

            return "无法理解您的查询，请提供更具体的信息"

        except Exception as e:
            logger.error(f"[Railway] 智能车站查询失败: {e}", exc_info=True)
            return f"查询失败: {str(e)}"

    async def _smart_suggestion_callback(self, args: Dict[str, Any]) -> str:
        """
        智能出行建议回调.
        """
        try:
            departure_city = args.get("departure_city", "")
            arrival_city = args.get("arrival_city", "")
            travel_date = args.get("travel_date", "")
            preferences = args.get("preferences", "")

            if not departure_city or not arrival_city:
                return "错误：出发城市和到达城市不能为空"

            # 获取当前日期
            current_date = await self._get_current_date()

            # 处理日期
            if not travel_date:
                travel_date = current_date
            else:
                travel_date = self._parse_date(travel_date, current_date)

            # 获取车站编码
            from_station_code = await self._get_station_code(departure_city)
            to_station_code = await self._get_station_code(arrival_city)

            if not from_station_code or not to_station_code:
                return f"错误：无法找到 {departure_city} 或 {arrival_city} 的车站信息"

            # 查询直达车票
            client = await get_railway_client()
            success, tickets, _ = await client.query_tickets(
                travel_date,
                from_station_code,
                to_station_code,
                "",
                "start_time",
                False,
                20,
            )

            suggestions = []

            if success and tickets:
                # 分析直达车票
                suggestions.extend(self._analyze_direct_tickets(tickets, preferences))

            # 查询中转方案
            transfer_success, transfers, _ = await client.query_transfer_tickets(
                travel_date,
                from_station_code,
                to_station_code,
                "",
                False,
                "",
                "start_time",
                False,
                5,
            )

            if transfer_success and transfers:
                # 分析中转方案
                suggestions.extend(
                    self._analyze_transfer_options(transfers, preferences)
                )

            if not suggestions:
                return f"抱歉，未找到 {travel_date} 从 {departure_city} 到 {arrival_city} 的出行方案"

            # 格式化建议
            return self._format_travel_suggestions(
                suggestions, departure_city, arrival_city, travel_date, preferences
            )

        except Exception as e:
            logger.error(f"[Railway] 智能出行建议失败: {e}", exc_info=True)
            return f"建议生成失败: {str(e)}"

    # ==================== 辅助方法 ====================

    async def _get_current_date(self) -> str:
        """
        获取当前日期.
        """
        client = await get_railway_client()
        return client.get_current_date()

    async def _get_station_code(self, city_or_station: str) -> str:
        """
        获取车站编码.
        """
        client = await get_railway_client()

        # 先尝试作为车站名查询
        station = client.get_station_by_name(city_or_station)
        if station:
            return station.station_code

        # 再尝试作为城市查询主要车站
        station = client.get_city_main_station(city_or_station)
        if station:
            return station.station_code

        return ""

    def _parse_date(self, date_str: str, current_date: str) -> str:
        """
        解析日期字符串.
        """
        try:
            # 处理相对日期
            if "今天" in date_str or "today" in date_str.lower():
                return current_date
            elif "明天" in date_str or "tomorrow" in date_str.lower():
                date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                return (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
            elif "后天" in date_str or "day after tomorrow" in date_str.lower():
                date_obj = datetime.strptime(current_date, "%Y-%m-%d")
                return (date_obj + timedelta(days=2)).strftime("%Y-%m-%d")
            elif "这周" in date_str or "this week" in date_str.lower():
                # 简单处理，返回当前日期
                return current_date
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
                # 已经是标准格式
                return date_str
            else:
                # 尝试解析其他格式
                return current_date
        except Exception:
            return current_date

    def _convert_train_type(self, train_type: str) -> str:
        """
        转换车次类型.
        """
        if not train_type:
            return ""

        type_mapping = {
            "高铁": "G",
            "high-speed": "G",
            "动车": "D",
            "EMU": "D",
            "直达": "Z",
            "direct": "Z",
            "特快": "T",
            "express": "T",
            "快速": "K",
            "fast": "K",
        }

        return type_mapping.get(train_type, "")

    def _filter_by_departure_time(self, tickets, departure_time: str):
        """
        根据出发时间过滤车票.
        """
        if not departure_time:
            return tickets

        time_ranges = {
            "上午": ("06:00", "12:00"),
            "morning": ("06:00", "12:00"),
            "下午": ("12:00", "18:00"),
            "afternoon": ("12:00", "18:00"),
            "晚上": ("18:00", "23:59"),
            "evening": ("18:00", "23:59"),
        }

        time_range = time_ranges.get(departure_time)
        if not time_range:
            return tickets

        start_time, end_time = time_range
        filtered_tickets = []

        for ticket in tickets:
            if start_time <= ticket.start_time <= end_time:
                filtered_tickets.append(ticket)

        return filtered_tickets

    def _format_smart_tickets(
        self, tickets, departure_city: str, arrival_city: str, travel_date: str
    ) -> str:
        """
        格式化智能车票结果.
        """
        if not tickets:
            return "没有找到符合条件的车票"

        result_lines = []
        result_lines.append(
            f"🚄 {travel_date} {departure_city} → {arrival_city} 火车票查询结果\n"
        )

        for i, ticket in enumerate(tickets[:10], 1):
            result_lines.append(f"📍 {i}. {ticket.start_train_code}")
            result_lines.append(
                f"   🕐 {ticket.start_time} → {ticket.arrive_time} ({ticket.duration})"
            )
            result_lines.append(f"   🚉 {ticket.from_station} → {ticket.to_station}")

            # 座位信息
            if ticket.prices:
                result_lines.append("   💺 座位信息:")
                for price in ticket.prices[:4]:  # 只显示前4种座位
                    status = self._format_ticket_status(price.num)
                    result_lines.append(
                        f"     • {price.seat_name}: {status} ¥{price.price}"
                    )

            # 特性
            if ticket.features:
                result_lines.append(f"   ✨ 特性: {', '.join(ticket.features)}")

            result_lines.append("")

        return "\n".join(result_lines)

    def _format_smart_transfers(
        self, transfers, departure_city: str, arrival_city: str, travel_date: str
    ) -> str:
        """
        格式化智能中转结果.
        """
        if not transfers:
            return "没有找到符合条件的中转方案"

        result_lines = []
        result_lines.append(
            f"🔄 {travel_date} {departure_city} → {arrival_city} 中转方案查询结果\n"
        )

        for i, transfer in enumerate(transfers[:5], 1):
            result_lines.append(f"📍 方案 {i}:")
            result_lines.append(
                f"   🕐 {transfer.start_time} → {transfer.arrive_time} (总时长: {transfer.duration})"
            )
            result_lines.append(
                f"   🚉 {transfer.from_station_name} → {transfer.middle_station_name} → {transfer.end_station_name}"
            )
            result_lines.append(f"   ⏰ 换乘等待: {transfer.wait_time}")
            result_lines.append(
                f"   🔄 换乘方式: {'同站换乘' if transfer.same_station else '跨站换乘'}"
            )

            # 车次信息
            result_lines.append("   🚄 车次信息:")
            for j, ticket in enumerate(transfer.ticket_list, 1):
                result_lines.append(
                    f"     第{j}程: {ticket.start_train_code} ({ticket.start_time}-{ticket.arrive_time})"
                )

            result_lines.append("")

        return "\n".join(result_lines)

    def _format_ticket_status(self, num: str) -> str:
        """
        格式化票量状态.
        """
        if num.isdigit():
            count = int(num)
            return f"余{count}张" if count > 0 else "无票"

        status_map = {
            "有": "有票",
            "充足": "充足",
            "无": "无票",
            "--": "无票",
            "": "无票",
            "候补": "候补",
        }

        return status_map.get(num, "未知")

    def _extract_city_from_query(self, query: str) -> str:
        """
        从查询中提取城市名.
        """
        # 简单正则提取
        patterns = [
            r"([北京|上海|广州|深圳|杭州|南京|天津|重庆|成都|武汉|西安|郑州|长沙|南昌|福州|厦门|合肥|济南|青岛|大连|沈阳|哈尔滨|长春|石家庄|太原|呼和浩特|银川|西宁|乌鲁木齐|拉萨|昆明|贵阳|南宁|海口|兰州]+)",
            r"([A-Za-z]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                return match.group(1)

        return ""

    def _extract_station_from_query(self, query: str) -> str:
        """
        从查询中提取车站名.
        """
        # 去除常见的停用词
        stop_words = ["查询", "的", "车站", "编码", "信息", "详细"]
        for word in stop_words:
            query = query.replace(word, "")

        # 提取可能的车站名
        query = query.strip()
        if len(query) > 1:
            return query

        return ""

    async def _query_city_stations(self, city: str) -> str:
        """
        查询城市车站.
        """
        client = await get_railway_client()
        stations = client.get_stations_in_city(city)

        if not stations:
            return f"未找到城市 '{city}' 的车站信息"

        result_lines = [f"🏢 {city} 的火车站列表:\n"]
        for i, station in enumerate(stations, 1):
            result_lines.append(f"{i}. {station.station_name} ({station.station_code})")

        return "\n".join(result_lines)

    async def _query_main_station(self, city: str) -> str:
        """
        查询主要车站.
        """
        client = await get_railway_client()
        station = client.get_city_main_station(city)

        if not station:
            return f"未找到城市 '{city}' 的主要车站"

        return f"🏢 {city} 的主要车站: {station.station_name} ({station.station_code})"

    async def _query_station_code(self, station_name: str) -> str:
        """
        查询车站编码.
        """
        client = await get_railway_client()
        station = client.get_station_by_name(station_name)

        if not station:
            return f"未找到车站 '{station_name}'"

        return f"🏢 {station.station_name} 的车站编码: {station.station_code}"

    async def _query_station_info(self, station_name: str) -> str:
        """
        查询车站信息.
        """
        client = await get_railway_client()
        station = client.get_station_by_name(station_name)

        if not station:
            return f"未找到车站 '{station_name}'"

        return f"🏢 {station.station_name}\n编码: {station.station_code}\n城市: {station.city}\n拼音: {station.station_pinyin}"

    def _analyze_direct_tickets(self, tickets, preferences: str) -> List[Dict]:
        """
        分析直达车票.
        """
        suggestions = []

        if "最快" in preferences or "fastest" in preferences.lower():
            # 找最快的车次
            fastest = min(tickets, key=lambda t: t.duration)
            suggestions.append(
                {
                    "type": "direct",
                    "title": "最快直达",
                    "ticket": fastest,
                    "reason": f"最短旅行时间 {fastest.duration}",
                }
            )

        if "最便宜" in preferences or "cheapest" in preferences.lower():
            # 找最便宜的车次
            cheapest = min(
                tickets,
                key=lambda t: min(
                    [p.price for p in t.prices if p.num != "无" and p.num != "--"]
                ),
            )
            suggestions.append(
                {
                    "type": "direct",
                    "title": "最经济直达",
                    "ticket": cheapest,
                    "reason": "票价最低",
                }
            )

        # 默认推荐高铁
        for ticket in tickets:
            if ticket.start_train_code.startswith("G"):
                suggestions.append(
                    {
                        "type": "direct",
                        "title": "高铁推荐",
                        "ticket": ticket,
                        "reason": "高铁舒适快捷",
                    }
                )
                break

        return suggestions[:3]

    def _analyze_transfer_options(self, transfers, preferences: str) -> List[Dict]:
        """
        分析中转方案.
        """
        suggestions = []

        if transfers:
            # 推荐等待时间适中的方案
            good_transfers = [
                t for t in transfers if "1小时" in t.wait_time or "2小时" in t.wait_time
            ]
            if good_transfers:
                suggestions.append(
                    {
                        "type": "transfer",
                        "title": "推荐中转方案",
                        "transfer": good_transfers[0],
                        "reason": "换乘等待时间适中",
                    }
                )

        return suggestions[:2]

    def _format_travel_suggestions(
        self,
        suggestions,
        departure_city: str,
        arrival_city: str,
        travel_date: str,
        preferences: str,
    ) -> str:
        """
        格式化出行建议.
        """
        if not suggestions:
            return "暂无出行建议"

        result_lines = []
        result_lines.append(
            f"💡 {travel_date} {departure_city} → {arrival_city} 出行建议\n"
        )

        if preferences:
            result_lines.append(f"🎯 您的偏好: {preferences}\n")

        for i, suggestion in enumerate(suggestions, 1):
            result_lines.append(f"📍 建议 {i}: {suggestion['title']}")
            result_lines.append(f"   💭 推荐理由: {suggestion['reason']}")

            if suggestion["type"] == "direct":
                ticket = suggestion["ticket"]
                result_lines.append(
                    f"   🚄 {ticket.start_train_code} ({ticket.start_time}-{ticket.arrive_time})"
                )
                result_lines.append(
                    f"   🚉 {ticket.from_station} → {ticket.to_station}"
                )
                if ticket.prices:
                    min_price = min(
                        [
                            p.price
                            for p in ticket.prices
                            if p.num != "无" and p.num != "--"
                        ]
                    )
                    result_lines.append(f"   💰 起价: ¥{min_price}")

            elif suggestion["type"] == "transfer":
                transfer = suggestion["transfer"]
                result_lines.append(
                    f"   🔄 {transfer.start_time} → {transfer.arrive_time} (总时长: {transfer.duration})"
                )
                result_lines.append(
                    f"   🚉 {transfer.from_station_name} → {transfer.middle_station_name} → {transfer.end_station_name}"
                )
                result_lines.append(f"   ⏰ 换乘等待: {transfer.wait_time}")

            result_lines.append("")

        return "\n".join(result_lines)

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
            "smart_tools_count": 4,
            "atomic_tools_count": 8,
            "available_smart_tools": [
                "smart_ticket_query",
                "smart_transfer_query",
                "smart_station_query",
                "smart_travel_suggestion",
            ],
        }


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
        city_stations_props = PropertyList([Property("city", PropertyType.STRING)])
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
        city_code_props = PropertyList([Property("cities", PropertyType.STRING)])
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
                Property(
                    "limit",
                    PropertyType.INTEGER,
                    default_value=0,
                    min_value=0,
                    max_value=50,
                ),
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
                Property(
                    "limit",
                    PropertyType.INTEGER,
                    default_value=10,
                    min_value=1,
                    max_value=20,
                ),
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
