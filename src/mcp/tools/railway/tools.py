"""12306工具函数实现.

提供各种12306相关的查询功能.
"""

import json
from typing import Any, Dict

from src.utils.logging_config import get_logger

from .client import get_railway_client

logger = get_logger(__name__)


async def get_current_date(args: Dict[str, Any]) -> str:
    """
    获取当前日期（上海时区）.
    """
    try:
        client = await get_railway_client()
        current_date = client.get_current_date()
        logger.info(f"获取当前日期: {current_date}")
        return current_date

    except Exception as e:
        logger.error(f"获取当前日期失败: {e}", exc_info=True)
        return f"获取当前日期失败: {str(e)}"


async def get_stations_in_city(args: Dict[str, Any]) -> str:
    """
    获取城市中的所有车站.
    """
    try:
        city = args.get("city", "")
        if not city:
            return "错误: 城市名称不能为空"

        client = await get_railway_client()
        stations = client.get_stations_in_city(city)

        if not stations:
            return f"未找到城市 '{city}' 的车站信息"

        result = {
            "city": city,
            "stations": [
                {
                    "station_code": station.station_code,
                    "station_name": station.station_name,
                    "station_pinyin": station.station_pinyin,
                }
                for station in stations
            ],
        }

        logger.info(f"查询城市 {city} 的车站: 找到 {len(stations)} 个车站")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"查询城市车站失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def get_city_station_code(args: Dict[str, Any]) -> str:
    """
    获取城市主要车站编码.
    """
    try:
        cities = args.get("cities", "")
        if not cities:
            return "错误: 城市名称不能为空"

        client = await get_railway_client()
        city_list = cities.split("|")
        result = {}

        for city in city_list:
            city = city.strip()
            station = client.get_city_main_station(city)

            if station:
                result[city] = {
                    "station_code": station.station_code,
                    "station_name": station.station_name,
                }
            else:
                result[city] = {"error": "未找到城市主要车站"}

        logger.info(f"查询城市主要车站: {cities}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"查询城市主要车站失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def get_station_by_name(args: Dict[str, Any]) -> str:
    """
    根据车站名获取车站信息.
    """
    try:
        station_names = args.get("station_names", "")
        if not station_names:
            return "错误: 车站名称不能为空"

        client = await get_railway_client()
        name_list = station_names.split("|")
        result = {}

        for name in name_list:
            name = name.strip()
            station = client.get_station_by_name(name)

            if station:
                result[name] = {
                    "station_code": station.station_code,
                    "station_name": station.station_name,
                    "city": station.city,
                }
            else:
                result[name] = {"error": "未找到车站"}

        logger.info(f"根据名称查询车站: {station_names}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"根据名称查询车站失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def get_station_by_code(args: Dict[str, Any]) -> str:
    """
    根据车站编码获取车站信息.
    """
    try:
        station_code = args.get("station_code", "")
        if not station_code:
            return "错误: 车站编码不能为空"

        client = await get_railway_client()
        station = client.get_station_by_code(station_code)

        if not station:
            return f"未找到车站编码 '{station_code}' 对应的车站"

        result = {
            "station_code": station.station_code,
            "station_name": station.station_name,
            "station_pinyin": station.station_pinyin,
            "city": station.city,
            "code": station.code,
        }

        logger.info(f"根据编码查询车站: {station_code}")
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"根据编码查询车站失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def query_train_tickets(args: Dict[str, Any]) -> str:
    """
    查询火车票.
    """
    try:
        date = args.get("date", "")
        from_station = args.get("from_station", "")
        to_station = args.get("to_station", "")
        train_filters = args.get("train_filters", "")
        sort_by = args.get("sort_by", "")
        reverse = args.get("reverse", False)
        limit = args.get("limit", 0)

        if not all([date, from_station, to_station]):
            return "错误: 日期、出发站和到达站都是必需参数"

        client = await get_railway_client()
        success, tickets, message = await client.query_tickets(
            date, from_station, to_station, train_filters, sort_by, reverse, limit
        )

        if not success:
            return f"查询失败: {message}"

        if not tickets:
            return "未找到符合条件的车次"

        # 格式化输出
        result = _format_tickets(tickets)

        logger.info(f"查询车票: {date} {from_station}->{to_station}, {message}")
        return result

    except Exception as e:
        logger.error(f"查询车票失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def query_transfer_tickets(args: Dict[str, Any]) -> str:
    """
    查询中转车票.
    """
    try:
        date = args.get("date", "")
        from_station = args.get("from_station", "")
        to_station = args.get("to_station", "")
        middle_station = args.get("middle_station", "")
        show_wz = args.get("show_wz", False)
        train_filters = args.get("train_filters", "")
        sort_by = args.get("sort_by", "")
        reverse = args.get("reverse", False)
        limit = args.get("limit", 10)

        if not all([date, from_station, to_station]):
            return "错误: 日期、出发站和到达站都是必需参数"

        client = await get_railway_client()
        success, transfers, message = await client.query_transfer_tickets(
            date,
            from_station,
            to_station,
            middle_station,
            show_wz,
            train_filters,
            sort_by,
            reverse,
            limit,
        )

        if not success:
            return f"查询失败: {message}"

        if not transfers:
            return "未找到符合条件的中转方案"

        # 格式化输出
        result = _format_transfer_tickets(transfers)

        logger.info(f"查询中转票: {date} {from_station}->{to_station}, {message}")
        return result

    except Exception as e:
        logger.error(f"查询中转车票失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


async def query_train_route(args: Dict[str, Any]) -> str:
    """
    查询车次经停站.
    """
    try:
        # 暂时返回不支持的信息
        return "车次经停站查询功能正在开发中，请稍后再试"

    except Exception as e:
        logger.error(f"查询车次经停站失败: {e}", exc_info=True)
        return f"查询失败: {str(e)}"


def _format_tickets(tickets: list) -> str:
    """
    格式化车票信息.
    """
    if not tickets:
        return "没有查询到相关车次信息"

    result_lines = []
    result_lines.append("车次 | 出发站 -> 到达站 | 出发时间 -> 到达时间 | 历时")
    result_lines.append("-" * 80)

    for ticket in tickets:
        # 车次基本信息
        basic_info = (
            f"{ticket.start_train_code} | "
            f"{ticket.from_station} -> {ticket.to_station} | "
            f"{ticket.start_time} -> {ticket.arrive_time} | "
            f"{ticket.duration}"
        )
        result_lines.append(basic_info)

        # 座位和价格信息
        for price in ticket.prices:
            ticket_status = _format_ticket_status(price.num)
            price_info = f"  - {price.seat_name}: {ticket_status} {price.price}元"
            result_lines.append(price_info)

        # 特性标记
        if ticket.features:
            features_info = f"  - 特性: {', '.join(ticket.features)}"
            result_lines.append(features_info)

        result_lines.append("")  # 空行分隔

    return "\n".join(result_lines)


def _format_ticket_status(num: str) -> str:
    """
    格式化票量信息.
    """
    if num.isdigit():
        count = int(num)
        if count == 0:
            return "无票"
        else:
            return f"剩余{count}张票"

    # 处理特殊状态
    status_map = {
        "有": "有票",
        "充足": "有票",
        "无": "无票",
        "--": "无票",
        "": "无票",
        "候补": "无票需候补",
    }

    return status_map.get(num, f"{num}票")


def _format_transfer_tickets(transfers: list) -> str:
    """
    格式化中转车票信息.
    """
    if not transfers:
        return "没有查询到相关中转方案"

    result_lines = []
    result_lines.append(
        "出发时间 -> 到达时间 | 出发车站 -> 中转车站 -> 到达车站 | 换乘标志 | 换乘等待时间 | 总历时"
    )
    result_lines.append("=" * 120)

    for transfer in transfers:
        # 基本信息
        basic_info = (
            f"{transfer.start_date} {transfer.start_time} -> {transfer.arrive_date} {transfer.arrive_time} | "
            f"{transfer.from_station_name} -> {transfer.middle_station_name} -> {transfer.end_station_name} | "
            f"{'Same_Train' if transfer.same_train else 'Same_Station' if transfer.same_station else 'Different_Station'} | "
            f"{transfer.wait_time} | {transfer.duration}"
        )
        result_lines.append(basic_info)
        result_lines.append("-" * 80)

        # 车次详情
        for i, ticket in enumerate(transfer.ticket_list, 1):
            segment_info = (
                f"  第{i}程: {ticket.start_train_code} | "
                f"{ticket.from_station} -> {ticket.to_station} | "
                f"{ticket.start_time} -> {ticket.arrive_time} | "
                f"{ticket.duration}"
            )
            result_lines.append(segment_info)

            # 座位和价格信息
            for price in ticket.prices:
                ticket_status = _format_ticket_status(price.num)
                price_info = f"    - {price.seat_name}: {ticket_status} {price.price}元"
                result_lines.append(price_info)

            # 特性标记
            if ticket.features:
                features_info = f"    - 特性: {', '.join(ticket.features)}"
                result_lines.append(features_info)

        result_lines.append("")  # 空行分隔

    return "\n".join(result_lines)
